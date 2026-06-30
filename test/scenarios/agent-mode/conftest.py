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

# DDL mirrors scripts/init.py verbatim (which is code_guard protected and uses a
# fixed path, so tests reuse the schema here instead of importing it).
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    job_hash TEXT PRIMARY KEY,
    external_id TEXT,
    public_date TEXT,
    url TEXT,
    company TEXT,
    position TEXT,
    location TEXT,
    salary TEXT,
    description TEXT,
    status TEXT DEFAULT 'new' CHECK(status IN ('new','analyzed','discarded','applied','rejected')),
    source TEXT DEFAULT 'manual'
);
CREATE TABLE IF NOT EXISTS analyses (
    analysis_id TEXT PRIMARY KEY,
    job_hash TEXT,
    percentage REAL,
    comparativa TEXT,
    observaciones TEXT,
    verdict TEXT,
    tldr TEXT,
    contact_method TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(job_hash) REFERENCES jobs(job_hash)
);
"""


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
