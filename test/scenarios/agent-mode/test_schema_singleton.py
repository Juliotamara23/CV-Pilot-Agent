"""Tests for the canonical schema loader.

The production init script and the test fixture both read the DDL from
``cv-pilot-agent/_lib/schema.sql`` via ``_lib/_schema.get_schema_sql``.
These tests guard against accidentally bypassing the shared module
(which would re-introduce the schema-drift risk).
"""
from __future__ import annotations

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
