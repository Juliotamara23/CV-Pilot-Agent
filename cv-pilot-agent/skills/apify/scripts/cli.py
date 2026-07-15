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
    parse_dataset,
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


# --------------------------------------------------------------------------- #
# Dataset inspection commands (PR 3)
# --------------------------------------------------------------------------- #

@app.command()
def datasets_list(
    actor: str = typer.Option(..., help="Actor full name (e.g., curious_coder/linkedin-jobs-scraper)."),
    since_minutes: int = typer.Option(60, help="Only show runs from the last N minutes."),
    limit: int = typer.Option(10, help="Maximum number of runs to list."),
) -> None:
    """List recent datasets for an actor. The agent uses this to find a
    dataset_id to inspect or fetch, based on the approximate time of the last run.
    """
    import time as _time
    from datetime import datetime, timedelta, timezone

    check_apify_cli()

    # Fetch recent runs from Apify.
    proc = subprocess.run(
        ["apify", "runs", "ls", actor, "--json", "--limit", str(limit), "--desc"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode != 0:
        _emit_error(
            f"apify runs ls failed: {proc.stderr.strip() or proc.stdout.strip()}",
            "APIFY_RUNS_LS_FAILED",
        )
        raise typer.Exit(code=1)

    try:
        runs_data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        _emit_error("Could not parse apify runs ls output", "APIFY_PARSE_ERROR")
        raise typer.Exit(code=1)

    raw_runs = runs_data.get("items", [])

    # Filter by since_minutes.
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)
    filtered: list[dict] = []
    for run in raw_runs:
        started = run.get("startedAt", "")
        if not started:
            continue
        try:
            started_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
            if started_dt >= cutoff:
                filtered.append(run)
        except (ValueError, TypeError):
            # Include runs with unparseable dates (defensive).
            filtered.append(run)

    # Build output rows.
    runs_out: list[dict] = []
    for run in filtered:
        started = run.get("startedAt", "")
        finished = run.get("finishedAt", "")
        elapsed = None
        if started and finished:
            try:
                s_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                f_dt = datetime.fromisoformat(finished.replace("Z", "+00:00"))
                elapsed = round((f_dt - s_dt).total_seconds(), 1)
            except (ValueError, TypeError):
                pass

        runs_out.append({
            "run_id": run.get("id", ""),
            "dataset_id": run.get("defaultDatasetId", ""),
            "items_count": run.get("stats", {}).get("itemCount") if isinstance(run.get("stats"), dict) else None,
            "started_at": started,
            "finished_at": finished,
            "elapsed_seconds": elapsed,
            "status": run.get("status", ""),
            "usage_total_usd": run.get("usageTotalUsd"),
        })

    _emit({
        "ok": True,
        "actor": actor,
        "since_minutes": since_minutes,
        "count": len(runs_out),
        "runs": runs_out,
    })


@app.command()
def datasets_inspect(
    dataset_id: str = typer.Option(..., help="The Apify dataset ID to inspect."),
) -> None:
    """Inspect a dataset: count items, show schema (set of keys across items).
    The agent uses this to verify how many items a dataset has, before fetching.
    """
    check_apify_cli()

    raw_items = fetch_dataset(dataset_id)
    items_count = len(raw_items)

    # Collect schema keys (union of all keys across items).
    schema_keys: set[str] = set()
    for item in raw_items:
        if isinstance(item, dict):
            schema_keys.update(item.keys())

    # Build a preview of the first item (truncated).
    sample_preview = None
    if raw_items and isinstance(raw_items[0], dict):
        sample_preview = {k: str(v)[:100] for k, v in list(raw_items[0].items())[:10]}

    _emit({
        "ok": True,
        "dataset_id": dataset_id,
        "items_count": items_count,
        "schema_keys": sorted(schema_keys),
        "sample_item_preview": sample_preview,
    })


@app.command()
def datasets_fetch(
    dataset_id: str = typer.Option(..., help="The Apify dataset ID to fetch from."),
    persist: bool = typer.Option(True, help="If True, persist items not already in DB. If False, just return them."),
) -> None:
    """Fetch a dataset and (optionally) persist items not already in our DB.
    The agent uses this to recover from interrupted runs or to retry validation
    on items that previously failed.
    """
    check_apify_cli()

    raw_items = fetch_dataset(dataset_id)
    fetched = len(raw_items)

    # Normalize items using generic field extraction.
    # Different actors use different field names; try common patterns.
    from _lib.db import compute_hash
    from _lib.models import JobInsert

    jobs: list[JobInsert] = []
    validation_failures: list[dict] = []

    for idx, item in enumerate(raw_items):
        if not isinstance(item, dict):
            validation_failures.append({
                "index": idx,
                "error": f"Item is not a dict: {type(item).__name__}",
            })
            continue

        # Extract fields using common actor field name patterns.
        company = (
            item.get("company")
            or item.get("companyName")
            or ""
        )
        position = (
            item.get("positionName")
            or item.get("title")
            or ""
        )
        location = (
            item.get("location")
            or item.get("jobLocation")
            or ""
        )

        if not company or not position:
            validation_failures.append({
                "index": idx,
                "raw_preview": str(item)[:200],
                "error": f"Missing required fields: company='{company}', position='{position}'",
            })
            continue

        try:
            job = JobInsert(
                company=company,
                position=position,
                location=location,
                external_id=str(item.get("id", "")) or None,
                public_date=item.get("postedAt") or item.get("postedDate") or item.get("date") or None,
                url=item.get("link") or item.get("url") or None,
                salary=item.get("salary") or None,
                description=(
                    item.get("descriptionText")
                    or item.get("descriptionHtml")
                    or item.get("description")
                    or None
                ),
                source="apify-dataset-recovery",
            )
            jobs.append(job)
        except Exception as exc:
            validation_failures.append({
                "index": idx,
                "raw_preview": str(item)[:200],
                "error": str(exc),
            })

    # Dedup and persist if requested.
    new_count = 0
    duplicate_count = 0
    persisted_result = None

    if jobs:
        # Compute hashes and check for existing jobs.
        hashes_seen: set[str] = set()
        new_jobs: list[JobInsert] = []

        for job in jobs:
            job_hash = compute_hash(job.company, job.position, job.location)
            if job_hash in hashes_seen:
                duplicate_count += 1
                continue
            hashes_seen.add(job_hash)

            # Check if job already exists in DB.
            try:
                proc = subprocess.run(
                    [sys.executable, _QUERY_PY, "job", "get", "--hash", job_hash],
                    capture_output=True, text=True, encoding="utf-8",
                )
                if proc.returncode == 0:
                    # Job exists — duplicate.
                    duplicate_count += 1
                    continue
            except Exception:
                pass  # If get fails, assume job doesn't exist.

            new_jobs.append(job)
            new_count += 1

        if persist and new_jobs:
            persisted_result = persist_jobs(new_jobs, _QUERY_PY)

    _emit({
        "ok": True,
        "dataset_id": dataset_id,
        "fetched": fetched,
        "new": new_count,
        "duplicates": duplicate_count,
        "validation_failures": validation_failures,
        "persisted": persisted_result,
        "cost_usd": None,  # Cost info would require run context, not available here.
    })


if __name__ == "__main__":
    app()
