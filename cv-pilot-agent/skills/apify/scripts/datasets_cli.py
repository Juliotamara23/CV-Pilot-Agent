"""Typer CLI dispatcher for datasets inspection and fetching via Apify.

Replaces the prompt-driven `skills/apify/SKILL.md` flow with a deterministic
API client that reads datasets and returns them in JSON envelopes.

The agent uses this to:
1. List recent runs from an actor (datasets_list)
2. Inspect a dataset's count and schema (datasets_inspect)
3. Fetch and optionally persist items from a dataset (datasets_fetch)
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import typer

# Force UTF-8 on std streams so unicode never depends on the host codepage.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

# Make cv-pilot-agent/ importable (for _lib) when run by path.
_AGENT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_AGENT_ROOT))

from _apify_internal.apify_client import (  # noqa: E402
    check_apify_cli,
    fetch_dataset,
    persist_jobs,
)

from platforms.registry import resolve as _resolve_platform  # noqa: E402

app = typer.Typer(
    name="datasets",
    help="CLI tools for listing, inspecting, and fetching Apify datasets.",
    add_completion=False,
    no_args_is_help=True,
)

_QUERY_PY = str(_AGENT_ROOT / "skills" / "database" / "scripts" / "query.py")
def _emit(payload: dict) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False))
def _emit_error(message: str, code: str) -> None:
    typer.echo(
        json.dumps({"ok": False, "error": message, "code": code}, ensure_ascii=False),
        err=True,
    )
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
    platform: str = typer.Option("linkedin", help="Platform actor to use for normalization (linkedin|indeed|computrabajo)."),
) -> None:
    """Fetch a dataset and (optionally) persist items not already in our DB.
    The agent uses this to recover from interrupted runs or to retry validation
    on items that previously failed.
    """
    check_apify_cli()

    # Resolve platform adapter for normalization. Guard against unknown
    # platforms so the failure is a parseable JSON envelope (matching the
    # INVALID_PLATFORM contract used by cli.py search) instead of a raw
    # SystemExit text on stderr.
    try:
        adapter = _resolve_platform(platform)
    except SystemExit:
        from platforms.registry import list_platforms
        _emit_error(
            f"Invalid platform '{platform}'. Valid: {', '.join(list_platforms())}.",
            "INVALID_PLATFORM",
        )
        raise typer.Exit(code=1)

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

        # Normalize raw item using the platform adapter.
        try:
            normalized = adapter.normalize_raw_item(item)
            # Convert normalized dict to JobInsert.
            # Required fields: company, position; location defaults to "".
            if not normalized.get("company") or not normalized.get("position"):
                validation_failures.append({
                    "index": idx,
                    "raw_preview": str(item)[:200],
                    "error": f"Missing required fields after normalization: company='{normalized.get('company')}', position='{normalized.get('position')}'",
                })
                continue
            job = JobInsert(
                company=normalized.get("company", ""),
                position=normalized.get("position", ""),
                location=normalized.get("location", ""),
                external_id=normalized.get("external_id"),
                public_date=item.get("postedAt") or item.get("postedDate") or item.get("date") or None,
                url=normalized.get("url"),
                salary=normalized.get("salary"),
                description=normalized.get("description"),
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