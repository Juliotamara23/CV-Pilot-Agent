"""Initialize the CV-Pilot SQLite database (idempotent).

The canonical DDL lives in `_lib/schema.sql` (single source of truth).
This script imports it so the production schema and the test fixture
cannot drift apart. Run directly or via `init` from any skill.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

# Make cv-pilot-agent/ importable so we can pull the canonical schema.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _lib._schema import get_schema_sql  # noqa: E402

# Database file location (production DB).
db_path = Path(__file__).resolve().parent.parent / "db" / "cv-pilot.db"


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Idempotent schema migrations — adds missing columns to existing DBs.

    New users get the full schema from ``_lib/schema.sql`` (loaded above).
    Existing DBs opened by this function get missing columns added
    automatically so the init script never needs to be modified for
    additive changes.
    """
    try:
        conn.execute("ALTER TABLE analyses ADD COLUMN contact_method TEXT")
    except sqlite3.OperationalError:
        # Column already exists — safe to ignore.
        pass


def init() -> None:
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(db_path)
        conn.executescript(get_schema_sql())
        conn.commit()

        # Run idempotent migrations for existing databases.
        _ensure_schema(conn)

        conn.close()
        print("DB Ready")
    except Exception as exc:
        print(f"ERROR: {exc}")


if __name__ == "__main__":
    init()
