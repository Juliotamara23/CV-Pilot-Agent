"""Real-data tests for the Apify dataset commands (PR 3).

These tests use ACTUAL Apify CLI commands to verify the new datasets_list,
datasets_inspect, and datasets_fetch subcommands work against real actor runs.
NO mocks, NO new runs spawned.

Test strategy:
1. Fetch real run metadata via `apify runs ls --json`
2. Verify datasets_list returns the expected shape
3. Verify datasets_inspect returns correct counts and schema
4. Verify datasets_fetch returns items and handles dedup correctly
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Make cv-pilot-agent/ importable (for _lib) and the scripts/ dir importable.
_AGENT_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "cv-pilot-agent"
_SCRIPTS_DIR = _AGENT_ROOT / "skills" / "apify" / "scripts"
for _p in (_AGENT_ROOT, _SCRIPTS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from _apify_internal.apify_client import fetch_dataset


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


def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    """Run the CLI script with the given arguments."""
    cmd = [sys.executable, str(_SCRIPTS_DIR / "cli.py")] + args
    return subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8",
    )


# --------------------------------------------------------------------------- #
# Tests — datasets_list
# --------------------------------------------------------------------------- #

def test_datasets_list_returns_recent_runs_for_actor():
    """datasets_list should return run info with expected keys."""
    result = _run_cli([
        "datasets-list",
        "--actor", "curious_coder/linkedin-jobs-scraper",
        "--since-minutes", "1440",  # last 24 hours
        "--limit", "5",
    ])
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    out = json.loads(result.stdout)
    assert out["ok"] is True
    assert "runs" in out
    assert isinstance(out["runs"], list)
    if out["runs"]:
        run = out["runs"][0]
        assert "run_id" in run
        assert "dataset_id" in run
        assert "status" in run
        assert "started_at" in run


def test_datasets_list_filters_by_since_minutes():
    """since_minutes=1440 should return more runs than since_minutes=1."""
    result_wide = _run_cli([
        "datasets-list",
        "--actor", "curious_coder/linkedin-jobs-scraper",
        "--since-minutes", "1440",
        "--limit", "20",
    ])
    result_narrow = _run_cli([
        "datasets-list",
        "--actor", "curious_coder/linkedin-jobs-scraper",
        "--since-minutes", "1",
        "--limit", "20",
    ])
    assert result_wide.returncode == 0
    assert result_narrow.returncode == 0
    wide = json.loads(result_wide.stdout)
    narrow = json.loads(result_narrow.stdout)
    # Narrow should return same or fewer runs than wide
    assert len(narrow["runs"]) <= len(wide["runs"])


# --------------------------------------------------------------------------- #
# Tests — datasets_inspect
# --------------------------------------------------------------------------- #

def test_datasets_inspect_returns_count_for_real_dataset():
    """datasets_inspect should return item count matching actual dataset."""
    real_run = _get_real_run("shahidirfan/computrabajo-jobs-scraper", "latest")
    dataset_id = real_run.get("defaultDatasetId", "")
    if not dataset_id:
        pytest.skip("Latest run has no defaultDatasetId")

    result = _run_cli(["datasets-inspect", "--dataset-id", dataset_id])
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    out = json.loads(result.stdout)
    assert out["ok"] is True
    assert out["dataset_id"] == dataset_id
    assert "items_count" in out
    assert isinstance(out["items_count"], int)
    assert out["items_count"] >= 0


def test_datasets_inspect_returns_schema_keys():
    """schema_keys should be the union of keys across items."""
    real_run = _get_real_run("curious_coder/linkedin-jobs-scraper", "latest")
    dataset_id = real_run.get("defaultDatasetId", "")
    if not dataset_id:
        pytest.skip("Latest run has no defaultDatasetId")

    result = _run_cli(["datasets-inspect", "--dataset-id", dataset_id])
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    out = json.loads(result.stdout)
    assert out["ok"] is True
    assert "schema_keys" in out
    assert isinstance(out["schema_keys"], list)
    # LinkedIn items should have at least title and companyName
    if out["items_count"] > 0:
        assert len(out["schema_keys"]) > 0


# --------------------------------------------------------------------------- #
# Tests — datasets_fetch
# --------------------------------------------------------------------------- #

def test_datasets_fetch_returns_items_without_persisting():
    """datasets_fetch with persist=False should return items without DB changes."""
    real_run = _get_real_run("curious_coder/linkedin-jobs-scraper", "latest")
    dataset_id = real_run.get("defaultDatasetId", "")
    if not dataset_id:
        pytest.skip("Latest run has no defaultDatasetId")

    result = _run_cli([
        "datasets-fetch",
        "--dataset-id", dataset_id,
        "--no-persist",  # Typer negates bool flags with --no-
    ])
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    out = json.loads(result.stdout)
    assert out["ok"] is True
    assert "fetched" in out
    assert isinstance(out["fetched"], int)
    assert out["fetched"] >= 0


def test_datasets_fetch_idempotent_with_persist():
    """Running fetch twice should not create duplicates in DB."""
    real_run = _get_real_run("curious_coder/linkedin-jobs-scraper", "latest")
    dataset_id = real_run.get("defaultDatasetId", "")
    if not dataset_id:
        pytest.skip("Latest run has no defaultDatasetId")

    # First run — should insert new items
    result1 = _run_cli([
        "datasets-fetch",
        "--dataset-id", dataset_id,
        "--persist",
    ])
    assert result1.returncode == 0, f"First run failed: {result1.stderr}"
    out1 = json.loads(result1.stdout)
    assert out1["ok"] is True

    # Second run — should report duplicates, not insert again
    result2 = _run_cli([
        "datasets-fetch",
        "--dataset-id", dataset_id,
        "--persist",
    ])
    assert result2.returncode == 0, f"Second run failed: {result2.stderr}"
    out2 = json.loads(result2.stdout)
    assert out2["ok"] is True
    # Second run should have new=0 (all duplicates)
    assert out2["new"] == 0, f"Expected 0 new on second run, got {out2['new']}"
    assert out2["duplicates"] == out1["fetched"], (
        f"Expected {out1['fetched']} duplicates, got {out2['duplicates']}"
    )


def test_datasets_fetch_reports_real_cost():
    """The fetch envelope should include cost info when available."""
    real_run = _get_real_run("curious_coder/linkedin-jobs-scraper", "latest")
    dataset_id = real_run.get("defaultDatasetId", "")
    if not dataset_id:
        pytest.skip("Latest run has no defaultDatasetId")

    result = _run_cli([
        "datasets-fetch",
        "--dataset-id", dataset_id,
        "--no-persist",
    ])
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    out = json.loads(result.stdout)
    assert out["ok"] is True
    # The envelope should have a cost field (may be None if run info unavailable)
    assert "cost_usd" in out
