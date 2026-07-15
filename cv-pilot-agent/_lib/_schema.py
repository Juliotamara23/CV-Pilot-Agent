"""Canonical schema loader for CV-Pilot's SQLite database.

The DDL lives in a single .sql file so production init and test fixtures
cannot drift. Importing scripts add `cv-pilot-agent/` to sys.path first.
"""
from __future__ import annotations

from pathlib import Path

_SCHEMA_FILE = Path(__file__).resolve().parent / "schema.sql"


def get_schema_sql() -> str:
    """Return the canonical DDL as a SQL string."""
    return _SCHEMA_FILE.read_text(encoding="utf-8")
