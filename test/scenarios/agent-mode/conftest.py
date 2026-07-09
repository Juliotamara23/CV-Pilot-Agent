"""Shared fixtures for CV-Pilot database-scriptification tests.

Makes `cv-pilot-agent/` importable (so `import _lib` resolves) and provides a
throwaway SQLite database with the production schema for each test.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

# Resolve cv-pilot-agent/ from test/scenarios/agent-mode/.
# test/scenarios/agent-mode -> test/scenarios -> test -> repo root -> cv-pilot-agent
_AGENT_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "cv-pilot-agent"
if str(_AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(_AGENT_ROOT))

# Make test/test_helpers importable for token_counter and other test utilities.
# Append (not insert) so cv-pilot-agent/_lib/ takes priority for production imports.
_TEST_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_TEST_ROOT) not in sys.path:
    sys.path.append(str(_TEST_ROOT))

# Pull the canonical DDL from _lib/schema.sql (single source of truth). The
# production init script reads from the same file, so test and production
# cannot drift. If you add a column to schema.sql, both pick it up.
from _lib._schema import get_schema_sql as _get_schema_sql  # noqa: E402

SCHEMA_SQL = _get_schema_sql()


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Create a fresh DB file, set CV_PILOT_DB to it, and apply the schema."""
    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(db_file)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
    monkeypatch.setenv("CV_PILOT_DB", str(db_file))
    return db_file


@pytest.fixture()
def query_script():
    """Absolute path to the CLI entrypoint."""
    return str(_AGENT_ROOT / "skills" / "database" / "scripts" / "query.py")


# --------------------------------------------------------------------------- #
# Token usage tracking — collects per-test counts for the terminal summary.
# --------------------------------------------------------------------------- #

_token_counts: list[tuple[str, int]] = []


class TokenTracker:
    """Simple accumulator that records token counts for a single test."""

    def __init__(self) -> None:
        self.total: int = 0

    def add(self, tokens: int) -> None:
        """Record a token count (e.g. from count_tokens or count_tokens_in_messages)."""
        self.total += tokens


@pytest.fixture()
def token_tracker(request):
    """Fixture that provides a TokenTracker and auto-registers the count."""
    tracker = TokenTracker()
    yield tracker
    if tracker.total > 0:
        _token_counts.append((request.node.nodeid, tracker.total))


def pytest_terminal_summary(terminalreporter):
    """Print token usage stats at the end of the test run."""
    if not _token_counts:
        return
    counts = [c for _, c in _token_counts]
    total = sum(counts)
    mean = total // len(counts)
    maximum = max(counts)
    terminalreporter.write_sep("-", "token usage summary")
    terminalreporter.write_line(
        f"[tokens] total: {total}, mean: {mean}, max: {maximum}"
    )
