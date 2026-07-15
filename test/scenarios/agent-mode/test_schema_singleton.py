"""Tests for the canonical schema loader.

The production init script and the test fixture both read the DDL from
``cv-pilot-agent/_lib/schema.sql`` via ``_lib/_schema.get_schema_sql``.
These tests guard against accidentally bypassing the shared module
(which would re-introduce the schema-drift risk).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


def test_schema_file_exists():
    # test/scenarios/agent-mode -> test/scenarios -> test -> repo root
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    schema_file = repo_root / "cv-pilot-agent" / "_lib" / "schema.sql"
    assert schema_file.is_file(), f"Canonical schema file missing: {schema_file}"


def test_get_schema_sql_returns_expected_tables():
    from _lib._schema import get_schema_sql

    schema = get_schema_sql()
    assert "CREATE TABLE IF NOT EXISTS jobs" in schema
    assert "CREATE TABLE IF NOT EXISTS analyses" in schema


def test_get_schema_sql_contains_critical_columns():
    """Regression: a future schema change must keep these columns.

    If you intentionally remove or rename any of these, update this
    test and verify the production code that depends on them.
    """
    from _lib._schema import get_schema_sql

    schema = get_schema_sql().lower()
    for column in ("job_hash", "company", "position", "location", "url", "status"):
        assert column in schema, f"Critical column missing from schema: {column}"


def test_init_script_uses_shared_loader():
    """Regression: scripts/init.py must import from _lib/_schema, not inline DDL.

    If this test fails, someone re-introduced inline schema in the init
    script. That re-opens the drift risk with the test fixture.
    """
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    init_script = repo_root / "cv-pilot-agent" / "scripts" / "init.py"
    content = init_script.read_text(encoding="utf-8")
    assert "_lib._schema" in content, "scripts/init.py must use the shared schema loader"
    assert "CREATE TABLE IF NOT EXISTS jobs" not in content, (
        "scripts/init.py contains inline DDL — remove it and use the shared schema"
    )


def test_conftest_uses_shared_loader():
    """Regression: conftest.py must import the schema, not inline it."""
    conftest = Path(__file__).resolve().parent / "conftest.py"
    content = conftest.read_text(encoding="utf-8")
    assert "_schema" in content or "_lib._schema" in content, (
        "conftest.py must use the shared schema loader"
    )
    assert content.count("CREATE TABLE IF NOT EXISTS jobs") <= 1, (
        "conftest.py has inline DDL — remove it and use the shared schema"
    )


def extract_schema(conn: sqlite3.Connection) -> dict[str, dict]:
    """Extract normalized schema info from a SQLite connection.

    Returns a dict keyed by table name, each containing a 'columns' list
    of dicts with keys: name, type, notnull, default, pk.
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
    tables = {}
    for (table_name,) in cur.fetchall():
        cur.execute(f"PRAGMA table_info({table_name})")
        columns = []
        for row in cur.fetchall():
            columns.append({
                "name": row[1],
                "type": row[2],
                "notnull": bool(row[3]),
                "default": row[4],
                "pk": bool(row[5]),
            })
        tables[table_name] = {"columns": columns}
    return tables


def _format_schema_diff(prod_schema: dict, canon_schema: dict) -> str:
    """Return a human-readable diff between two schemas."""
    lines = []
    all_tables = sorted(set(list(prod_schema.keys()) + list(canon_schema.keys())))
    for table in all_tables:
        if table not in prod_schema:
            lines.append(f"  MISSING IN PRODUCTION: table '{table}'")
            continue
        if table not in canon_schema:
            lines.append(f"  MISSING IN CANONICAL: table '{table}'")
            continue
        prod_cols = prod_schema[table]["columns"]
        canon_cols = canon_schema[table]["columns"]
        max_len = max(len(prod_cols), len(canon_cols))
        for i in range(max_len):
            p = prod_cols[i] if i < len(prod_cols) else None
            c = canon_cols[i] if i < len(canon_cols) else None
            if p is None:
                lines.append(f"  {table}: EXTRA column in canonical at [{i}]: {c['name']} {c['type']}")
                continue
            if c is None:
                lines.append(f"  {table}: MISSING column in canonical at [{i}]: {p['name']} {p['type']}")
                continue
            # Compare field by field
            for field in ("name", "type", "notnull", "default", "pk"):
                pv, cv = p[field], c[field]
                if pv != cv:
                    lines.append(
                        f"  {table}.{p['name']} [{field}]: "
                        f"production={pv!r} canonical={cv!r}"
                    )
    return "\n".join(lines)


def test_init_script_produces_matching_production_schema():
    """Regression: the canonical schema must exactly match the production DB.

    The production DB at cv-pilot-agent/db/cv-pilot.db is the source of truth.
    The canonical schema in _lib/schema.sql (used by both init.py and tests)
    must produce a structurally identical schema: same tables, same columns
    in order, same types, same nullability, same defaults, same PKs.
    """
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    prod_db_path = repo_root / "cv-pilot-agent" / "db" / "cv-pilot.db"
    assert prod_db_path.is_file(), f"Production DB not found: {prod_db_path}"

    # 1. Extract production schema (read-only)
    prod_conn = sqlite3.connect(f"file:{prod_db_path}?mode=ro", uri=True)
    try:
        prod_schema = extract_schema(prod_conn)
    finally:
        prod_conn.close()

    # 2. Create a fresh DB from the canonical schema
    from _lib._schema import get_schema_sql

    tmp_db = repo_root / "test" / "scenarios" / "agent-mode" / "_tmp_schema_test.db"
    try:
        canon_conn = sqlite3.connect(tmp_db)
        canon_conn.executescript(get_schema_sql())
        canon_conn.commit()
        canon_schema = extract_schema(canon_conn)
        canon_conn.close()
    finally:
        tmp_db.unlink(missing_ok=True)

    # 3. Compare
    diff = _format_schema_diff(prod_schema, canon_schema)
    assert prod_schema == canon_schema, (
        "Schema drift detected! Production DB differs from canonical schema.\n"
        "The production DB is the source of truth — fix _lib/schema.sql.\n\n"
        f"DIFF:\n{diff}"
    )
