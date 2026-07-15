"""Apify client helpers for CV-Pilot job scraping.

Encapsulates CLI interaction with the ``apify`` tool: actor cost queries,
actor invocation, and dataset parsing.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Optional

import typer

from _lib.errors import CV_PilotError


def check_apify_cli() -> None:
    """Raise ``typer.Exit(1)`` if the ``apify`` CLI is not on PATH."""
    if shutil.which("apify") is None:
        typer.echo(
            json.dumps({
                "ok": False,
                "error": "Apify CLI not found on PATH. Install it and configure APIFY_TOKEN.",
                "code": "APIFY_CLI_MISSING",
            }, ensure_ascii=False),
            err=True,
        )
        raise typer.Exit(code=1)


def actor_cost(actor: str, count: int) -> float:
    """Query the Apify API for the actor's real-time price and compute total cost."""
    proc = subprocess.run(
        ["apify", "actors", "info", actor, "--json"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode != 0:
        typer.echo(
            json.dumps({
                "ok": False,
                "error": f"apify actors info failed: {proc.stderr.strip() or proc.stdout.strip()}",
                "code": "APIFY_INFO_FAILED",
            }, ensure_ascii=False),
            err=True,
        )
        raise typer.Exit(code=1)
    info = json.loads(proc.stdout)
    pricing = info.get("currentPricingInfo") or (info.get("pricingInfos") or [{}])[0] or info
    events = (pricing.get("pricingPerEvent") or {}).get("actorChargeEvents") or {}
    item = float(events.get("apify-default-dataset-item", {}).get("eventPriceUsd") or 0)
    start = float(events.get("apify-actor-start", {}).get("eventPriceUsd") or 0)
    return round(count * item + start, 6)


def parse_dataset(stdout: str) -> list[dict]:
    """Parse Apify dataset output (JSON array or NDJSON fallback)."""
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


def call_actor(actor: str, actor_input: dict) -> list[dict]:
    """Invoke an Apify actor and return the parsed dataset.

    .. deprecated::
        Use :func:`launch_actor` + :func:`poll_run_status` + :func:`fetch_dataset`
        for better control over variable-duration runs.
    """
    proc = subprocess.run(
        ["apify", "call", actor, "--input", json.dumps(actor_input),
         "--silent", "--output-dataset"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode != 0:
        typer.echo(
            json.dumps({
                "ok": False,
                "error": f"apify call failed: {proc.stderr.strip() or proc.stdout.strip()}",
                "code": "APIFY_CALL_FAILED",
            }, ensure_ascii=False),
            err=True,
        )
        raise typer.Exit(code=1)
    return parse_dataset(proc.stdout)


def launch_actor(actor: str, actor_input: dict) -> dict:
    """Start an actor run asynchronously. Returns the run info dict with
    ``run_id``, ``dataset_id`` (from ``defaultDatasetId``), ``status``,
    and ``startedAt``.  Does NOT wait for completion.

    Uses ``apify actors start --json`` which returns immediately.
    """
    proc = subprocess.run(
        ["apify", "actors", "start", actor,
         "--input", json.dumps(actor_input), "--json"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode != 0:
        typer.echo(
            json.dumps({
                "ok": False,
                "error": f"apify actors start failed: {proc.stderr.strip() or proc.stdout.strip()}",
                "code": "APIFY_START_FAILED",
            }, ensure_ascii=False),
            err=True,
        )
        raise typer.Exit(code=1)
    return json.loads(proc.stdout)


# Terminal run statuses — polling stops when the run reaches one of these.
_TERMINAL_STATUSES = frozenset({"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"})


def poll_run_status(
    run_id: str,
    cap_seconds: int = 180,
    backoff_seconds: tuple[int, ...] = (5, 5, 10, 15, 30, 60),
) -> str:
    """Poll the run's status until it reaches a terminal state.

    Returns the final status: ``SUCCEEDED``, ``FAILED``, ``ABORTED``,
    or ``TIMED-OUT``.  Raises :class:`TimeoutError` if the run doesn't
    terminate within *cap_seconds*.

    Writes one progress line to stderr per poll so the user sees activity.
    Backoff sequence is cycled: once exhausted, the last value repeats.
    """
    import time

    elapsed = 0
    poll_count = 0
    backoff_idx = 0

    while elapsed < cap_seconds:
        # Sleep first (the run needs time to progress).
        delay = backoff_seconds[min(backoff_idx, len(backoff_seconds) - 1)]
        time.sleep(delay)
        elapsed += delay
        poll_count += 1
        backoff_idx += 1

        # Query run status.
        proc = subprocess.run(
            ["apify", "runs", "info", run_id, "--json"],
            capture_output=True, text=True, encoding="utf-8",
        )
        if proc.returncode != 0:
            typer.echo(
                f"[{elapsed}s] poll={poll_count} WARNING: could not read run info",
                err=True,
            )
            continue

        info = json.loads(proc.stdout)
        # The status may be nested under the run object or at top level.
        status = info.get("status", "UNKNOWN")

        typer.echo(
            f"[{elapsed}s] status={status}, poll={poll_count}",
            err=True,
        )

        if status in _TERMINAL_STATUSES:
            return status

    raise TimeoutError(
        f"Run {run_id} did not reach a terminal state within {cap_seconds}s"
    )


def fetch_dataset(dataset_id: str) -> list[dict]:
    """Fetch all items from a known *dataset_id*.

    Uses ``apify datasets get-items <dataset_id> --format json``.
    Returns the raw items list.  Handles CLI warning text that may
    precede the JSON output.
    """
    proc = subprocess.run(
        ["apify", "datasets", "get-items", dataset_id, "--format", "json"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode != 0:
        typer.echo(
            json.dumps({
                "ok": False,
                "error": f"apify datasets get-items failed: {proc.stderr.strip() or proc.stdout.strip()}",
                "code": "APIFY_FETCH_FAILED",
            }, ensure_ascii=False),
            err=True,
        )
        raise typer.Exit(code=1)
    return parse_dataset(proc.stdout)


def persist_jobs(jobs: list, query_py: str) -> Optional[dict]:
    """Persist a batch of normalized jobs via ``query.py job insert-batch``.

    Returns the DB-level result dict (inserted/duplicates/refreshed) or
    ``None`` if the input list is empty.  DB-level validation failures
    (if any) are logged to stderr by query.py and surfaced in the CLI
    envelope via the ``failed`` key when the caller needs them.
    """
    from _lib.models import JobInsert  # avoid circular at module level

    if not jobs:
        return None
    payload = [j.model_dump() for j in jobs]
    import sys
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8"
    ) as tf:
        json.dump(payload, tf, ensure_ascii=False)
        tmp_path = tf.name
    try:
        proc = subprocess.run(
            [sys.executable, query_py, "job", "insert-batch", "--file", tmp_path],
            capture_output=True, text=True, encoding="utf-8",
        )
        if proc.returncode != 0:
            typer.echo(
                json.dumps({
                    "ok": False,
                    "error": f"query.py insert-batch failed: {proc.stderr.strip() or proc.stdout.strip()}",
                    "code": "PERSIST_FAILED",
                }, ensure_ascii=False),
                err=True,
            )
            raise typer.Exit(code=1)
        raw_result = json.loads(proc.stdout)
        # query.py now returns {"persisted": <db_result>, "failed": [...]}.
        # Unwrap so the CLI envelope's "persisted" field keeps the old shape
        # and DB-level failures are available separately.
        if isinstance(raw_result, dict) and "persisted" in raw_result:
            return raw_result["persisted"]
        return raw_result
    finally:
        Path(tmp_path).unlink(missing_ok=True)
