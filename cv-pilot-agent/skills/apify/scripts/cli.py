"""Typer CLI dispatcher for multi-platform job scraping via Apify.

Replaces the prompt-driven `skills/apify/SKILL.md` flow with a deterministic
script invoked by the orchestrator (AGENTS.md) via subprocess::

    python skills/apify/scripts/cli.py --platform linkedin \
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
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Force UTF-8 on std streams so unicode never depends on the host codepage.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

# Make cv-pilot-agent/ importable (for _lib) when run by path.
_AGENT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_AGENT_ROOT))

import typer  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from platforms import (  # noqa: E402
    ComputrabajoAdapter,
    IndeedAdapter,
    LinkedinAdapter,
)
from platforms.base import PlatformAdapter, SearchParams  # noqa: E402

from _apify_internal.apify_client import (  # noqa: E402
    actor_cost,
    call_actor,
    check_apify_cli,
    fetch_dataset,
    launch_actor,
    persist_jobs,
    poll_run_status,
)
from _apify_internal.relevance import GENERIC_POSITIONS, label_relevance  # noqa: E402

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

_QUERY_PY = str(_AGENT_ROOT / "skills" / "database" / "scripts" / "query.py")


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
    check_apify_cli()
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
    cost = actor_cost(actor, params.count)

    if not confirm:
        _emit({
            "ok": True, "phase": "cost", "actor": actor, "platform": platform,
            "count": params.count, "cost_usd": cost,
            "position": position, "location": location,
        })
        return

    import time as _time
    _t0 = _time.monotonic()

    run_info = launch_actor(actor, adapter.build_input(params))
    run_id = run_info["id"]
    dataset_id = run_info["defaultDatasetId"]

    status = poll_run_status(run_id)
    elapsed = round(_time.monotonic() - _t0, 1)

    if status != "SUCCEEDED":
        _emit({
            "ok": False, "phase": "done", "platform": platform, "actor": actor,
            "error": f"actor run {status}", "code": f"APIFY_RUN_{status}",
            "run_id": run_id, "dataset_id": dataset_id,
            "elapsed_seconds": elapsed, "cost_usd": cost,
        })
        return

    raw = fetch_dataset(dataset_id)

    # -- filter error items (e.g. Indeed FOUND_NO_RESULTS) --------------- #
    valid_raw, error_items = adapter.filter_errors(raw)
    skipped_errors = [e.get("error", "UNKNOWN") for e in error_items]
    if error_items:
        typer.echo(
            f"Warning: {len(error_items)} error item(s) dropped from dataset "
            f"(codes: {', '.join(skipped_errors)}).",
            err=True,
        )

    if not valid_raw:
        _emit({
            "ok": True, "phase": "done", "platform": platform, "actor": actor,
            "count": 0, "cost_usd": cost, "relevance": {"high": 0, "medium": 0, "low": 0},
            "persisted": None, "skipped_errors": skipped_errors,
            "validation_failures": [],
            "run_id": run_id, "dataset_id": dataset_id,
            "elapsed_seconds": elapsed,
        })
        return

    # -- safe normalization (per-item isolation) ------------------------- #
    jobs, validation_failures = adapter.normalize_output_safe(valid_raw)
    if validation_failures:
        typer.echo(
            f"Warning: {len(validation_failures)} item(s) failed normalization.",
            err=True,
        )

    if not jobs:
        _emit({
            "ok": True, "phase": "done", "platform": platform, "actor": actor,
            "count": 0, "cost_usd": cost, "relevance": {"high": 0, "medium": 0, "low": 0},
            "persisted": None, "skipped_errors": skipped_errors,
            "validation_failures": validation_failures,
            "run_id": run_id, "dataset_id": dataset_id,
            "elapsed_seconds": elapsed,
        })
        return

    relevance = label_relevance(jobs, position)
    persisted = persist_jobs(jobs, _QUERY_PY)
    _emit({
        "ok": True, "phase": "done", "platform": platform, "actor": actor,
        "count": len(jobs), "cost_usd": cost, "relevance": relevance,
        "persisted": persisted, "skipped_errors": skipped_errors,
        "validation_failures": validation_failures,
        "run_id": run_id, "dataset_id": dataset_id,
        "elapsed_seconds": elapsed,
    })


if __name__ == "__main__":
    app()
