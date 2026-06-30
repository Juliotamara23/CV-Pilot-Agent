"""Typer CLI dispatcher for multi-platform job scraping via Apify.

Replaces the prompt-driven `skills/apify/SKILL.md` flow with a deterministic
script invoked by the orchestrator (AGENTS.md) via subprocess::

    python skills/apify/scripts/search_jobs.py --platform linkedin \
        --position "React Developer" --location "Medellín" --count 5

Two-phase cost wizard: without ``--confirm`` the actor is *not* called — only
its real-time price is reported. With ``--confirm`` the actor runs, the dataset
is normalized through the platform adapter, every result is labeled by
relevance (high/medium/low) and persisted via `query.py job insert-batch`. The
script NEVER discards results: relevance is a label, not a filter.

All output is a single JSON envelope on stdout; errors go to stderr as
``{"ok": false, "error": "...", "code": "..."}`` with a non-zero exit.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

from _lib.shared.cli_utils import setup_syspath, setup_utf8

# Force UTF-8 on std streams so unicode never depends on the host codepage.
setup_utf8()

# Make cv-pilot-agent/ importable (for _lib) when run by path.
_AGENT_ROOT = setup_syspath(levels_up=3)

import typer  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from platforms import (  # noqa: E402
    ComputrabajoAdapter,
    IndeedAdapter,
    LinkedinAdapter,
)
from platforms.base import PlatformAdapter, SearchParams  # noqa: E402

app = typer.Typer(
    name="search_jobs",
    help="Multi-platform job scraping CLI via Apify actors.",
    add_completion=False,
    no_args_is_help=True,
)

ADAPTERS: dict[str, type[PlatformAdapter]] = {
    "indeed": IndeedAdapter,
    "linkedin": LinkedinAdapter,
    "computrabajo": ComputrabajoAdapter,
}

# Single-word positions tend to yield noisy, low-relevance results.
GENERIC_POSITIONS = {
    "developer", "desarrollador", "ingeniero", "engineer", "trabajo",
    "designer", "diseñador", "programador", "programmer", "analista", "analyst",
}

_QUERY_PY = _AGENT_ROOT / "skills" / "database" / "scripts" / "query.py"


def _emit(payload: dict) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False))


def _emit_error(message: str, code: str) -> None:
    typer.echo(
        json.dumps({"ok": False, "error": message, "code": code}, ensure_ascii=False),
        err=True,
    )


def _resolve_adapter(platform: str) -> PlatformAdapter:
    cls = ADAPTERS.get(platform)
    if cls is None:
        _emit_error(
            f"Invalid platform '{platform}'. Valid: {', '.join(ADAPTERS)}.",
            "INVALID_PLATFORM",
        )
        raise typer.Exit(code=1)
    return cls()


def _check_apify_cli() -> None:
    if shutil.which("apify") is None:
        _emit_error(
            "Apify CLI not found on PATH. Install it and configure APIFY_TOKEN.",
            "APIFY_CLI_MISSING",
        )
        raise typer.Exit(code=1)


def _actor_cost(actor: str, count: int) -> float:
    proc = subprocess.run(
        ["apify", "actors", "info", actor, "--json"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode != 0:
        _emit_error(
            f"apify actors info failed: {proc.stderr.strip() or proc.stdout.strip()}",
            "APIFY_INFO_FAILED",
        )
        raise typer.Exit(code=1)
    info = json.loads(proc.stdout)
    pricing = info.get("currentPricingInfo") or (info.get("pricingInfos") or [{}])[0] or info
    events = (pricing.get("pricingPerEvent") or {}).get("actorChargeEvents") or {}
    item = float(events.get("apify-default-dataset-item", {}).get("eventPriceUsd") or 0)
    start = float(events.get("apify-actor-start", {}).get("eventPriceUsd") or 0)
    return round(count * item + start, 6)


def _parse_dataset(stdout: str) -> list[dict]:
    text = stdout.strip()
    if not text:
        return []
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("items", "data"):
                if isinstance(data.get(key), list):
                    return data[key]
        return []
    except json.JSONDecodeError:
        # NDJSON fallback (one JSON object per line).
        items: list[dict] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return items


def _call_actor(actor: str, actor_input: dict) -> list[dict]:
    proc = subprocess.run(
        ["apify", "call", actor, "--input", json.dumps(actor_input),
         "--silent", "--output-dataset"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode != 0:
        _emit_error(
            f"apify call failed: {proc.stderr.strip() or proc.stdout.strip()}",
            "APIFY_CALL_FAILED",
        )
        raise typer.Exit(code=1)
    return _parse_dataset(proc.stdout)


def _persist(jobs: list) -> Optional[dict]:
    if not jobs:
        return None
    payload = [j.model_dump() for j in jobs]
    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8"
    ) as tf:
        json.dump(payload, tf, ensure_ascii=False)
        tmp_path = tf.name
    try:
        proc = subprocess.run(
            [sys.executable, str(_QUERY_PY), "job", "insert-batch", "--file", tmp_path],
            capture_output=True, text=True, encoding="utf-8",
        )
        if proc.returncode != 0:
            _emit_error(
                f"query.py insert-batch failed: {proc.stderr.strip() or proc.stdout.strip()}",
                "PERSIST_FAILED",
            )
            raise typer.Exit(code=1)
        return json.loads(proc.stdout)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


_TOKEN_RE = re.compile(r"[a-z0-9áéíóúñ]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


def _label_relevance(jobs: list, position: str) -> dict:
    pos_tokens = set(_tokens(position))
    counts = {"high": 0, "medium": 0, "low": 0}
    for job in jobs:
        title_tokens = set(_tokens(job.position))
        if not pos_tokens:
            counts["low"] += 1
        elif pos_tokens.issubset(title_tokens):
            counts["high"] += 1
        elif title_tokens & pos_tokens:
            counts["medium"] += 1
        else:
            counts["low"] += 1
    return counts


@app.command()
def search(
    platform: str = typer.Option(..., help="Target platform: indeed|linkedin|computrabajo."),
    position: str = typer.Option(..., help="Job title to search (avoid generic single words)."),
    location: str = typer.Option(..., help="City or 'Remote'."),
    country: str = typer.Option("CO", help="Country code (CO, AR, MX, PE, CL)."),
    count: int = typer.Option(5, min=1, max=100, help="Maximum results to fetch."),
    workplace: Optional[str] = typer.Option(
        None, "--workplace", help="onsite|remote|hybrid (LinkedIn only)."
    ),
    experience: Optional[str] = typer.Option(
        None, "--experience", help="entry|mid|senior (LinkedIn only)."
    ),
    confirm: bool = typer.Option(
        False, "--confirm", help="Run the actor; without it only the cost is reported."
    ),
) -> None:
    """Run a two-phase Apify job search, normalize and persist every result."""
    _check_apify_cli()
    adapter = _resolve_adapter(platform)

    if position.strip().lower() in GENERIC_POSITIONS:
        typer.echo(
            f"Warning: position '{position}' is generic; results may be low-relevance.",
            err=True,
        )

    try:
        params = SearchParams(
            position=position, location=location, country=country, count=count,
            workplace_type=workplace, experience_level=experience,  # type: ignore[arg-type]
        )
    except ValidationError as exc:
        _emit_error(str(exc), "INVALID_PARAMS")
        raise typer.Exit(code=1)

    min_c = adapter.min_count()
    if params.count < min_c:
        typer.echo(
            f"Warning: {platform} requires >= {min_c} results; "
            f"clamping count {params.count} -> {min_c}.",
            err=True,
        )
        params = params.model_copy(update={"count": min_c})

    actor = adapter.get_actor()
    cost = _actor_cost(actor, params.count)

    if not confirm:
        _emit({
            "ok": True, "phase": "cost", "actor": actor, "platform": platform,
            "count": params.count, "cost_usd": cost,
            "position": position, "location": location,
        })
        return

    raw = _call_actor(actor, adapter.build_input(params))
    jobs = adapter.normalize_output(raw)
    relevance = _label_relevance(jobs, position)
    persisted = _persist(jobs)
    _emit({
        "ok": True, "phase": "done", "platform": platform, "actor": actor,
        "count": len(jobs), "cost_usd": cost, "relevance": relevance,
        "persisted": persisted,
    })


if __name__ == "__main__":
    app()