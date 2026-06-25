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

    def test_analysis_help(self, query_script, tmp_db):
        proc = _run(query_script, os.environ.copy(), "analysis", "--help")
        assert proc.returncode == 0
        assert "insert" in proc.stdout
        assert "get" in proc.stdout

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
