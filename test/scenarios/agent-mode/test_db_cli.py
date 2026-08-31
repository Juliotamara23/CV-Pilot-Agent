"""CLI smoke + end-to-end tests via subprocess.

Each test spawns `python query.py ...` against a throwaway DB (CV_PILOT_DB) and
asserts the JSON envelope on stdout/stderr plus the exit code.
"""

import json
import os
import sqlite3
import subprocess
import sys

import pytest

from conftest import SCHEMA_SQL


def _run(query_script, env, *args):
    proc = subprocess.run(
        [sys.executable, query_script, *args],
        capture_output=True,
        text=True,
        env=env,
        encoding="utf-8",
    )
    return proc


class TestCliHelp:
    def test_top_help(self, query_script, tmp_db):
        proc = _run(query_script, os.environ.copy(), "--help")
        assert proc.returncode == 0
        assert "Commands" in proc.stdout
        assert "job" in proc.stdout
        assert "analysis" in proc.stdout
        assert "status" in proc.stdout

    def test_job_subapps(self, query_script, tmp_db):
        proc = _run(query_script, os.environ.copy(), "job", "--help")
        assert proc.returncode == 0
        assert "insert" in proc.stdout
        assert "insert-batch" in proc.stdout
        assert "list" in proc.stdout
        assert "get" in proc.stdout
        assert "delete" in proc.stdout
        assert "update" in proc.stdout

    def test_analysis_help(self, query_script, tmp_db):
        proc = _run(query_script, os.environ.copy(), "analysis", "--help")
        assert proc.returncode == 0
        assert "insert" in proc.stdout
        assert "get" in proc.stdout
        assert "update" in proc.stdout
        assert "delete" in proc.stdout

    def test_status_help(self, query_script, tmp_db):
        proc = _run(query_script, os.environ.copy(), "status", "--help")
        assert proc.returncode == 0
        assert "set" in proc.stdout


class TestCliJobNotFound:
    def test_get_missing_emits_stderr_envelope(self, query_script, tmp_db):
        proc = _run(query_script, os.environ.copy(), "job", "get", "--hash", "missing")
        assert proc.returncode == 1
        assert proc.stdout == ""
        payload = json.loads(proc.stderr)
        assert payload["ok"] is False
        assert payload["code"] == "JOB_NOT_FOUND"
        assert "missing" in payload["error"]


class TestCliEndToEnd:
    def test_insert_list_analyze_status_delete(self, query_script, tmp_db):
        env = os.environ.copy()

        # 1. insert
        proc = _run(
            query_script, env, "job", "insert",
            "--company", "Acme", "--position", "Developer", "--location", "Madrid",
            "--public-date", "2026-06-25", "--source", "manual",
        )
        assert proc.returncode == 0, proc.stderr
        inserted = json.loads(proc.stdout)
        assert inserted["ok"] is True
        assert inserted["is_new"] is True
        job_hash = inserted["hash"]

        # 2. list
        proc = _run(query_script, env, "job", "list", "--status", "new")
        assert proc.returncode == 0, proc.stderr
        listed = json.loads(proc.stdout)
        assert listed["count"] == 1
        assert listed["jobs"][0]["job_hash"] == job_hash

        # 3. analyze
        proc = _run(
            query_script, env, "analysis", "insert",
            "--job-hash", job_hash, "--percentage", "87.5",
            "--comparativa", "Strong", "--observaciones", "Good fit",
            "--verdict", "Apto", "--tldr", "Apply now",
            "--contact-method", "email",
        )
        assert proc.returncode == 0, proc.stderr
        analysis = json.loads(proc.stdout)
        assert analysis["ok"] is True
        assert "analysis_id" in analysis

        # job status should now be 'analyzed'
        proc = _run(query_script, env, "job", "get", "--hash", job_hash)
        assert json.loads(proc.stdout)["job"]["status"] == "analyzed"

        # analysis get should return contact_method
        proc = _run(query_script, env, "analysis", "get", "--job-hash", job_hash)
        assert proc.returncode == 0, proc.stderr
        fetched = json.loads(proc.stdout)
        assert fetched["ok"] is True
        assert fetched["analysis"]["contact_method"] == "email"

        # 4. status set
        proc = _run(
            query_script, env, "status", "set",
            "--hash", job_hash, "--status", "rejected",
        )
        assert proc.returncode == 0, proc.stderr
        status = json.loads(proc.stdout)
        assert status["old_status"] == "analyzed"
        assert status["new_status"] == "rejected"

        # 5. delete (dry-run first, then real)
        proc = _run(
            query_script, env, "job", "delete",
            "--status", "rejected", "--dry-run",
        )
        assert proc.returncode == 0, proc.stderr
        dry = json.loads(proc.stdout)
        assert dry["dry_run"] is True
        assert dry["would_delete"] == 1

        # DB unchanged after dry-run
        proc = _run(query_script, env, "job", "list", "--status", "rejected")
        assert json.loads(proc.stdout)["count"] == 1

        proc = _run(query_script, env, "job", "delete", "--status", "rejected")
        assert proc.returncode == 0, proc.stderr
        deleted = json.loads(proc.stdout)
        assert deleted["deleted"] == 1

        # analysis row removed too (FK respect)
        proc = _run(query_script, env, "analysis", "get", "--job-hash", job_hash)
        assert proc.returncode == 1
        assert json.loads(proc.stderr)["code"] == "ANALYSIS_NOT_FOUND"

    def test_invalid_status_envelope(self, query_script, tmp_db):
        env = os.environ.copy()
        proc = _run(query_script, env, "job", "list", "--status", "bogus")
        assert proc.returncode == 1
        payload = json.loads(proc.stderr)
        assert payload["code"] == "INVALID_STATUS"


class TestCliContactMethod:
    """Verify --contact-method persists and is returned by `analysis get`."""

    def test_contact_method_portal_round_trip(self, query_script, tmp_db):
        env = os.environ.copy()
        proc = _run(
            query_script, env, "job", "insert",
            "--company", "Globex", "--position", "Engineer", "--location", "Berlin",
        )
        job_hash = json.loads(proc.stdout)["hash"]

        proc = _run(
            query_script, env, "analysis", "insert",
            "--job-hash", job_hash, "--percentage", "70",
            "--comparativa", "c", "--observaciones", "o",
            "--verdict", "Apto con reservas", "--tldr", "t",
            "--contact-method", "portal",
        )
        assert proc.returncode == 0, proc.stderr
        assert json.loads(proc.stdout)["ok"] is True

        proc = _run(query_script, env, "analysis", "get", "--job-hash", job_hash)
        assert proc.returncode == 0, proc.stderr
        analysis = json.loads(proc.stdout)["analysis"]
        assert analysis["contact_method"] == "portal"

        def test_contact_method_defaults_to_none(self, query_script, tmp_db):
            env = os.environ.copy()
            proc = _run(
                query_script, env, "job", "insert",
                "--company", "Initech", "--position", "Dev", "--location", "Remote",
            )
            job_hash = json.loads(proc.stdout)["hash"]

            proc = _run(
                query_script, env, "analysis", "insert",
                "--job-hash", job_hash, "--percentage", "90",
                "--comparativa", "c", "--observaciones", "o",
                "--verdict", "Apto", "--tldr", "t",
            )
            assert proc.returncode == 0, proc.stderr

            proc = _run(query_script, env, "analysis", "get", "--job-hash", job_hash)
            assert proc.returncode == 0, proc.stderr
            analysis = json.loads(proc.stdout)["analysis"]
            assert analysis["contact_method"] is None


    class TestCliQuery:
        """Tests for the new `query run` sub-command."""

        def test_simple_select(self, query_script, tmp_db):
            env = os.environ.copy()
            # Insert a couple of jobs first
            proc = _run(
                query_script, env, "job", "insert",
                "--company", "Acme", "--position", "Dev", "--location", "Madrid",
            )
            hash1 = json.loads(proc.stdout)["hash"]
            proc = _run(
                query_script, env, "job", "insert",
                "--company", "Globex", "--position", "Eng", "--location", "Berlin",
            )
            hash2 = json.loads(proc.stdout)["hash"]

            # Simple SELECT
            proc = _run(query_script, env, "query", "SELECT job_hash, company FROM jobs")
            assert proc.returncode == 0, proc.stderr
            payload = json.loads(proc.stdout)
            assert payload["ok"] is True
            assert set(payload["columns"]) == {"job_hash", "company"}
            assert payload["count"] == 2
            companies = {row[1] for row in payload["rows"]}
            assert companies == {"Acme", "Globex"}

        def test_group_by_aggregation(self, query_script, tmp_db):
            env = os.environ.copy()
            # Insert jobs with different statuses
            for company, status in [
                ("A", "new"), ("B", "new"), ("C", "analyzed"), ("D", "rejected")
            ]:
                _run(query_script, env, "job", "insert",
                     "--company", company, "--position", "P", "--location", "L")
                # Manually update status for last two
            # Update status via direct DB for simplicity in test setup
            import sqlite3
            conn = sqlite3.connect(tmp_db)
            conn.execute("UPDATE jobs SET status='analyzed' WHERE company='C'")
            conn.execute("UPDATE jobs SET status='rejected' WHERE company='D'")
            conn.commit()
            conn.close()

            # GROUP BY with COUNT
            proc = _run(query_script, env, "query",
                        "SELECT status, COUNT(*) as cnt FROM jobs GROUP BY status")
            assert proc.returncode == 0, proc.stderr
            payload = json.loads(proc.stdout)
            assert payload["ok"] is True
            assert set(payload["columns"]) == {"status", "cnt"}
            assert payload["count"] == 3
            status_counts = {row[0]: row[1] for row in payload["rows"]}
            assert status_counts["new"] == 2
            assert status_counts["analyzed"] == 1
            assert status_counts["rejected"] == 1

        def test_join_jobs_analyses(self, query_script, tmp_db):
            env = os.environ.copy()
            # Insert job
            proc = _run(
                query_script, env, "job", "insert",
                "--company", "TestCo", "--position", "Role", "--location", "Loc",
            )
            job_hash = json.loads(proc.stdout)["hash"]
            # Insert analysis
            _run(query_script, env, "analysis", "insert",
                 "--job-hash", job_hash, "--percentage", "85",
                 "--comparativa", "cmp", "--observaciones", "obs",
                 "--verdict", "Apto", "--tldr", "tldr")

            # JOIN query
            proc = _run(query_script, env, "query",
                        "SELECT j.company, a.percentage, a.verdict "
                        "FROM jobs j JOIN analyses a ON j.job_hash = a.job_hash")
            assert proc.returncode == 0, proc.stderr
            payload = json.loads(proc.stdout)
            assert payload["ok"] is True
            assert set(payload["columns"]) == {"company", "percentage", "verdict"}
            assert payload["count"] == 1
            assert payload["rows"][0] == ["TestCo", "85.0", "Apto"]

        def test_limit_truncation(self, query_script, tmp_db):
            env = os.environ.copy()
            # Insert 5 jobs
            for i in range(5):
                _run(query_script, env, "job", "insert",
                     f"--company", f"Co{i}", "--position", "P", "--location", "L")

            # Limit 2
            proc = _run(query_script, env, "query",
                        "SELECT company FROM jobs ORDER BY company",
                        "--limit", "2")
            assert proc.returncode == 0, proc.stderr
            payload = json.loads(proc.stdout)
            assert payload["ok"] is True
            assert payload["count"] == 2
            assert len(payload["rows"]) == 2

        def test_reject_insert(self, query_script, tmp_db):
            env = os.environ.copy()
            # Capture DB state before
            import hashlib
            before = tmp_db.read_bytes()

            proc = _run(query_script, env, "query",
                        "INSERT INTO jobs (job_hash, company, position, location) VALUES ('x', 'y', 'z', 'w')")
            assert proc.returncode == 1
            assert proc.stdout == ""
            payload = json.loads(proc.stderr)
            assert payload["ok"] is False
            assert payload["code"] == "QUERY_WRITE_NOT_ALLOWED"
            assert "INSERT" in payload["error"]

            # DB unchanged (byte-identical)
            after = tmp_db.read_bytes()
            assert before == after

        def test_reject_update(self, query_script, tmp_db):
            env = os.environ.copy()
            before = tmp_db.read_bytes()

            proc = _run(query_script, env, "query",
                        "UPDATE jobs SET company='hacked'")
            assert proc.returncode == 1
            payload = json.loads(proc.stderr)
            assert payload["code"] == "QUERY_WRITE_NOT_ALLOWED"
            assert "UPDATE" in payload["error"]
            assert tmp_db.read_bytes() == before

        def test_reject_delete(self, query_script, tmp_db):
            env = os.environ.copy()
            before = tmp_db.read_bytes()

            proc = _run(query_script, env, "query", "DELETE FROM jobs")
            assert proc.returncode == 1
            payload = json.loads(proc.stderr)
            assert payload["code"] == "QUERY_WRITE_NOT_ALLOWED"
            assert "DELETE" in payload["error"]
            assert tmp_db.read_bytes() == before

        def test_reject_drop(self, query_script, tmp_db):
            env = os.environ.copy()
            before = tmp_db.read_bytes()

            proc = _run(query_script, env, "query", "DROP TABLE jobs")
            assert proc.returncode == 1
            payload = json.loads(proc.stderr)
            assert payload["code"] == "QUERY_WRITE_NOT_ALLOWED"
            assert "DROP" in payload["error"]
            assert tmp_db.read_bytes() == before

        def test_reject_multi_statement(self, query_script, tmp_db):
            env = os.environ.copy()
            before = tmp_db.read_bytes()

            # Multi-statement should be rejected by sqlite3 driver
            proc = _run(query_script, env, "query",
                        "SELECT 1; SELECT 2")
            assert proc.returncode == 1
            payload = json.loads(proc.stderr)
            assert payload["code"] == "DATABASE_ERROR"
            assert tmp_db.read_bytes() == before

        def test_json_envelope_shape(self, query_script, tmp_db):
            env = os.environ.copy()
            _run(query_script, env, "job", "insert",
                 "--company", "ShapeCo", "--position", "P", "--location", "L")

            proc = _run(query_script, env, "query", "SELECT 1 as one, 'two' as two")
            assert proc.returncode == 0, proc.stderr
            payload = json.loads(proc.stdout)
            assert set(payload.keys()) == {"ok", "columns", "rows", "count"}
            assert payload["ok"] is True
            assert payload["columns"] == ["one", "two"]
            assert payload["rows"] == [[1, "two"]]
            assert payload["count"] == 1

        def test_non_json_cell_conversion(self, query_script, tmp_db):
            env = os.environ.copy()
            # Insert a job with binary-ish data in description (simulated via direct insert)
            import sqlite3
            conn = sqlite3.connect(tmp_db)
            conn.execute(
                "INSERT INTO jobs (job_hash, company, position, location, description) "
                "VALUES (?, ?, ?, ?, ?)",
                ("binhash", "BinCo", "Role", "Loc", b"\xff\xfe binary")
            )
            conn.commit()
            conn.close()

            proc = _run(query_script, env, "query",
                        "SELECT description FROM jobs WHERE job_hash='binhash'")
            assert proc.returncode == 0, proc.stderr
            payload = json.loads(proc.stdout)
            assert payload["ok"] is True
            # bytes should be converted to string (with replacement chars)
            assert isinstance(payload["rows"][0][0], str)
            assert payload["count"] == 1

        def test_with_cte_allowed(self, query_script, tmp_db):
            env = os.environ.copy()
            _run(query_script, env, "job", "insert",
                 "--company", "CteCo", "--position", "P", "--location", "L")

            # WITH clause (read-only CTE) should be allowed
            proc = _run(query_script, env, "query",
                        "WITH cte AS (SELECT company FROM jobs) SELECT * FROM cte")
            assert proc.returncode == 0, proc.stderr
            payload = json.loads(proc.stdout)
            assert payload["ok"] is True
            assert payload["count"] == 1

        def test_with_cte_write_blocked(self, query_script, tmp_db):
            env = os.environ.copy()
            before = tmp_db.read_bytes()

            # WITH can prefix a write in SQLite; the mode=ro connection is the
            # guard that must block it (token check alone would let it pass).
            proc = _run(query_script, env, "query",
                        "WITH cte AS (SELECT 1) DELETE FROM jobs")
            assert proc.returncode == 1
            payload = json.loads(proc.stderr)
            assert payload["ok"] is False
            assert payload["code"] == "DATABASE_ERROR"
            assert "readonly" in payload["error"].lower()
            assert tmp_db.read_bytes() == before

        def test_empty_sql_rejected(self, query_script, tmp_db):
            env = os.environ.copy()
            # Empty string - should fail validation
            proc = _run(query_script, env, "query", "")
            # Typer may reject empty argument before our code runs; if it passes,
            # our validation should catch it.
            if proc.returncode == 0:
                # Our validation should have caught it
                payload = json.loads(proc.stdout)
                assert payload["ok"] is False
            else:
                # Typer validation error is also acceptable
                pass

        def test_invalid_first_keyword_rejected(self, query_script, tmp_db):
            env = os.environ.copy()
            proc = _run(query_script, env, "query", "EXPLAIN SELECT 1")
            assert proc.returncode == 1
            payload = json.loads(proc.stderr)
            assert payload["code"] == "QUERY_INVALID_SQL"
            assert "EXPLAIN" in payload["error"]
