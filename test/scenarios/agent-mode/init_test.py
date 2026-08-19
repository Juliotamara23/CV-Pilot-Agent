import sqlite3
import os
import sys
from pathlib import Path

# Test DB lives under test/ to keep it out of the main flow
DB_PATH = Path(__file__).parent.parent.parent.parent / "test" / "cv-pilot-test.db"

# Make cv-pilot-agent importable to use the canonical schema
_AGENT_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "cv-pilot-agent"
if str(_AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(_AGENT_ROOT))

from _lib._schema import get_schema_sql  # noqa: E402

SCHEMA_SQL = get_schema_sql()


def init_test_db():
    """Initialize a clean test database using the production schema (single source of truth)."""
    if DB_PATH.exists():
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
    print(f"TEST_DB_READY: {DB_PATH}")


if __name__ == "__main__":
    init_test_db()
