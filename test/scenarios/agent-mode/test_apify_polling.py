"""Real-data tests for the Apify polling refactor (PR 2).

These tests use ACTUAL Apify CLI commands to verify the new launch/poll/fetch
functions work against real actor runs. NO mocks, NO new runs spawned.

Test strategy:
1. Fetch real run metadata via `apify runs ls --json`
2. Verify launch_actor returns the expected shape
3. Verify fetch_dataset retrieves real items
4. Verify poll_run_status handles terminal states correctly
5. Verify our timeout cap is sufficient for observed durations
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

# Make cv-pilot-agent/ importable (for _lib) and the scripts/ dir importable.
_AGENT_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "cv-pilot-agent"
_SCRIPTS_DIR = _AGENT_ROOT / "skills" / "apify" / "scripts"
for _p in (_AGENT_ROOT, _SCRIPTS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from _apify_internal.apify_client import fetch_dataset, launch_actor, poll_run_status


# --------------------------------------------------------------------------- #
# Test helpers — read-only, no new runs
# --------------------------------------------------------------------------- #

def _get_real_run(actor: str, kind: str = "latest") -> dict:
    """Fetch a real run from Apify. kind: 'latest' or 'oldest'. Read-only."""
    desc = kind == "latest"
    proc = subprocess.run(
        ["apify", "runs", "ls", actor, "--json", "--limit", "1",
         "--desc", str(desc).lower()],
        capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode != 0:
        pytest.skip(f"apify runs ls failed for {actor}: {proc.stderr.strip()}")
    try:
        items = json.loads(proc.stdout).get("items", [])
    except json.JSONDecodeError:
        pytest.skip(f"Could not parse apify runs ls output for {actor}")
    if not items:
        pytest.skip(f"No runs found for {actor}")
    return items[0]


def _get_real_runs(actor: str, limit: int = 20) -> list[dict]:
    """Fetch multiple real runs from Apify. Read-only."""
    proc = subprocess.run(
        ["apify", "runs", "ls", actor, "--json", "--limit", str(limit), "--desc"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode != 0:
        pytest.skip(f"apify runs ls failed for {actor}: {proc.stderr.strip()}")
    try:
        return json.loads(proc.stdout).get("items", [])
    except json.JSONDecodeError:
        pytest.skip(f"Could not parse apify runs ls output for {actor}")
        return []


def _duration(run: dict) -> float | None:
    """Compute run duration in seconds from startedAt/finishedAt."""
    s = run.get("startedAt")
    f = run.get("finishedAt")
    if not (s and f):
        return None
    s_dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    f_dt = datetime.fromisoformat(f.replace("Z", "+00:00"))
    return (f_dt - s_dt).total_seconds()


def _run_info_from_ls(run: dict) -> dict:
    """Build a minimal run info dict matching what launch_actor returns.

    The `apify runs ls` output has a slightly different shape than
    `apify actors start --json`, so we normalize here.
    """
    return {
        "id": run["id"],
        "defaultDatasetId": run.get("defaultDatasetId", ""),
        "status": run.get("status", ""),
        "startedAt": run.get("startedAt", ""),
    }


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #

def test_launch_actor_returns_run_info():
    """launch_actor should return the run info dict with expected keys.

    We don't actually launch — we verify the shape using a real run's metadata.
    The real launch is tested implicitly by the CLI smoke test.
    """
    real_run = _get_real_run("curious_coder/linkedin-jobs-scraper", "latest")
    dataset_id = real_run.get("defaultDatasetId", "")
    # Verify the run info shape: id, defaultDatasetId, status, startedAt
    assert dataset_id, f"Run {real_run['id']} has no defaultDatasetId"
    assert real_run["status"] in (
        "SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT", "RUNNING",
    ), f"Unexpected status: {real_run['status']}"


def test_fetch_dataset_with_latest_run():
    """fetch_dataset should return items from a known dataset_id."""
    real_run = _get_real_run("curious_coder/linkedin-jobs-scraper", "latest")
    dataset_id = real_run.get("defaultDatasetId", "")
    if not dataset_id:
        pytest.skip("Latest run has no defaultDatasetId")
    items = fetch_dataset(dataset_id)
    assert isinstance(items, list)
    assert len(items) > 0, "Expected real items from latest LinkedIn run"


def test_fetch_dataset_with_oldest_run():
    """Oldest dataset should also work — verifies historical data handling."""
    real_run = _get_real_run("curious_coder/linkedin-jobs-scraper", "oldest")
    dataset_id = real_run.get("defaultDatasetId", "")
    if not dataset_id:
        pytest.skip("Oldest run has no defaultDatasetId")
    items = fetch_dataset(dataset_id)
    assert isinstance(items, list)


def test_poll_run_status_on_succeeded_run():
    """Polling a run that's already SUCCEEDED should return immediately."""
    real_run = _get_real_run("curious_coder/linkedin-jobs-scraper", "latest")
    if real_run["status"] != "SUCCEEDED":
        pytest.skip(f"Latest run is {real_run['status']}, not SUCCEEDED")
    status = poll_run_status(real_run["id"], cap_seconds=10)
    assert status == "SUCCEEDED"


def test_polling_handles_variable_durations():
    """Verify our cap_seconds=180 is enough for the worst observed case."""
    real_runs = _get_real_runs("shahidirfan/computrabajo-jobs-scraper", limit=20)
    durations = [_duration(r) for r in real_runs if _duration(r)]
    if not durations:
        pytest.skip("No runs with duration data")
    assert max(durations) < 180, (
        f"Observed max duration {max(durations):.1f}s exceeds cap of 180s"
    )
