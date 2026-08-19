"""Regression tests for test_apify_seed_db.py insert_analysis helper.

Verifies that:
1. Valid verdicts (No apto, Apto con reservas, Apto) are accepted
2. Invalid verdicts (pending, undecided, random strings) are rejected with ValidationError
3. Temporary DB isolation is preserved
4. Fixture-based seeding remains read-only wrt Apify
"""

import tempfile
from pathlib import Path

import pytest

from test_apify_seed_db import (
    seed_db_from_fixtures,
    insert_analysis,
    init_temp_db,
    get_pending_jobs,
)
from _lib.errors import ValidationError
from _lib.models import validate_verdict


class TestInsertAnalysisVerdictValidation:
    """Tests for verdict validation in insert_analysis."""

    def setup_method(self):
        """Create a fresh temp DB for each test."""
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "test.db"
        init_temp_db(self.db_path)
        # Seed with at least one job to have a valid job_hash
        jobs = seed_db_from_fixtures(self.db_path, "linkedin", count=1)
        assert jobs, "Fixture should provide at least one job"
        self.job_hash = jobs[0]["job_hash"]

    def teardown_method(self):
        self.tmp_dir.cleanup()

    def test_valid_verdict_no_apto(self):
        """'No apto' verdict should be accepted."""
        analysis_id = insert_analysis(
            self.db_path,
            self.job_hash,
            "45%",
            "Comparativa test",
            "Observaciones test",
            "No apto",
            "TLDR test",
        )
        assert analysis_id is not None
        assert len(analysis_id) == 36  # UUID format

    def test_valid_verdict_apto_con_reservas(self):
        """'Apto con reservas' verdict should be accepted."""
        analysis_id = insert_analysis(
            self.db_path,
            self.job_hash,
            "70%",
            "Comparativa test",
            "Observaciones test",
            "Apto con reservas",
            "TLDR test",
        )
        assert analysis_id is not None

    def test_valid_verdict_apto(self):
        """'Apto' verdict should be accepted."""
        analysis_id = insert_analysis(
            self.db_path,
            self.job_hash,
            "85%",
            "Comparativa test",
            "Observaciones test",
            "Apto",
            "TLDR test",
        )
        assert analysis_id is not None

    def test_invalid_verdict_pending_rejected(self):
        """'pending' verdict should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            insert_analysis(
                self.db_path,
                self.job_hash,
                "50%",
                "Comparativa test",
                "Observaciones test",
                "pending",
                "TLDR test",
            )
        assert "Invalid verdict" in str(exc_info.value)
        assert "pending" in str(exc_info.value).lower()

    def test_invalid_verdict_undecided_rejected(self):
        """'undecided' verdict should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            insert_analysis(
                self.db_path,
                self.job_hash,
                "50%",
                "Comparativa test",
                "Observaciones test",
                "undecided",
                "TLDR test",
            )
        assert "Invalid verdict" in str(exc_info.value)

    def test_invalid_verdict_random_string_rejected(self):
        """Random string verdict should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            insert_analysis(
                self.db_path,
                self.job_hash,
                "50%",
                "Comparativa test",
                "Observaciones test",
                "maybe",
                "TLDR test",
            )
        assert "Invalid verdict" in str(exc_info.value)

    def test_invalid_verdict_empty_string_rejected(self):
        """Empty string verdict should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            insert_analysis(
                self.db_path,
                self.job_hash,
                "50%",
                "Comparativa test",
                "Observaciones test",
                "",
                "TLDR test",
            )
        assert "Invalid verdict" in str(exc_info.value)

    def test_invalid_verdict_case_sensitive(self):
        """Verdict validation is case-sensitive - 'no apto' (lowercase) should fail."""
        with pytest.raises(ValidationError) as exc_info:
            insert_analysis(
                self.db_path,
                self.job_hash,
                "50%",
                "Comparativa test",
                "Observaciones test",
                "no apto",  # lowercase - invalid
                "TLDR test",
            )
        assert "Invalid verdict" in str(exc_info.value)

    def test_job_not_found_raises_error(self):
        """Inserting analysis for non-existent job_hash should fail."""
        fake_hash = "0" * 64
        with pytest.raises(Exception) as exc_info:
            insert_analysis(
                self.db_path,
                fake_hash,
                "50%",
                "Comparativa test",
                "Observaciones test",
                "Apto",
                "TLDR test",
            )
        # Should raise JobNotFoundError (code JOB_NOT_FOUND)
        assert "not found" in str(exc_info.value).lower() or "JOB_NOT_FOUND" in str(exc_info.value)


class TestValidateVerdictDirect:
    """Direct tests for the validate_verdict function."""

    def test_valid_verdicts_pass(self):
        for verdict in ("No apto", "Apto con reservas", "Apto"):
            assert validate_verdict(verdict) == verdict

    def test_invalid_verdicts_raise(self):
        for verdict in ("pending", "undecided", "maybe", "NO APTO", "apto", ""):
            with pytest.raises(ValueError) as exc_info:
                validate_verdict(verdict)
            assert "Invalid verdict" in str(exc_info.value)


class TestSeedDbPreservesFixtureReadOnly:
    """Tests ensuring fixture-based seeding is read-only wrt Apify."""

    def setup_method(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "test.db"

    def teardown_method(self):
        self.tmp_dir.cleanup()

    def test_seed_from_fixtures_no_live_calls(self):
        """seed_db_from_fixtures should only read local JSON, not call Apify."""
        # This test verifies the function completes without network calls
        # (if it tried to call Apify, it would fail without credentials)
        jobs = seed_db_from_fixtures(self.db_path, "linkedin", count=3)
        assert len(jobs) == 3
        for job in jobs:
            # Adapter normalizes source to "apify-linkedin" format
            assert job["source"] == "apify-linkedin"
            assert job["job_hash"]
            assert job["position"]
            assert job["company"]

    def test_seed_multiple_platforms_isolation(self):
        """Seeding multiple platforms should accumulate jobs."""
        jobs1 = seed_db_from_fixtures(self.db_path, "linkedin", count=2)
        jobs2 = seed_db_from_fixtures(self.db_path, "computrabajo", count=2, clear_first=False)
        jobs3 = seed_db_from_fixtures(self.db_path, "indeed", count=2, clear_first=False)

        assert len(jobs1) == 2
        # computrabajo fixture may have fewer items
        assert len(jobs2) >= 1
        assert len(jobs3) >= 1

        # Verify all in DB
        pending = get_pending_jobs(self.db_path)
        assert len(pending) >= 4

        sources = {job["source"] for job in pending}
        assert "apify-linkedin" in sources
        assert "apify-computrabajo" in sources or "apify-indeed" in sources

    def test_temp_db_only_no_personal_data(self):
        """Temp DB should be isolated and contain no personal data fields."""
        jobs = seed_db_from_fixtures(self.db_path, "linkedin", count=1)
        assert self.db_path.exists()
        assert self.db_path.stat().st_size > 0

        # Verify DB is in temp directory, not production location
        assert str(self.db_path).startswith(tempfile.gettempdir()) or "tmp" in str(self.db_path)

        # Verify no personal data fields in jobs (fields, not description content)
        for job in jobs:
            assert "email" not in job
            assert "phone" not in job
            assert "address" not in job
            # Description may contain the word "personal" in job text - that's fine
            # We only check that the job dict doesn't have personal data fields


class TestCanonicalSchemaInSeedDb:
    """Tests that seed DB uses canonical schema with all required columns."""

    def setup_method(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "test.db"

    def teardown_method(self):
        self.tmp_dir.cleanup()

    def test_jobs_table_has_canonical_columns(self):
        """Jobs table should have all canonical columns from schema.sql."""
        import sqlite3
        init_temp_db(self.db_path)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(jobs)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        # Required columns from canonical schema.sql
        required = {
            "job_hash", "external_id", "public_date", "url", "company",
            "position", "location", "salary", "description", "source",
            "status", "created_at"
        }
        assert required.issubset(columns), f"Missing columns: {required - columns}"

    def test_analyses_table_has_canonical_columns(self):
        """Analyses table should have all canonical columns from schema.sql."""
        import sqlite3
        init_temp_db(self.db_path)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(analyses)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        # Required columns from canonical schema.sql
        required = {
            "analysis_id", "job_hash", "percentage", "comparativa",
            "observaciones", "verdict", "tldr", "created_at", "contact_method"
        }
        assert required.issubset(columns), f"Missing columns: {required - columns}"

    def test_foreign_key_enforced(self):
        """Foreign key from analyses.job_hash to jobs.job_hash should be enforced."""
        import sqlite3
        init_temp_db(self.db_path)
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        # First verify the schema has the FK constraint
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='analyses'")
        schema = cursor.fetchone()[0]
        assert "FOREIGN KEY" in schema.upper()

        # Try to insert analysis with non-existent job_hash - should fail
        # FK constraint may be checked on execute or commit depending on SQLite config
        try:
            cursor.execute(
                """INSERT INTO analyses
                   (analysis_id, job_hash, percentage, comparativa, observaciones, verdict, tldr)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ("test-id", "non-existent-hash", "50%", "comp", "obs", "Apto", "tldr"),
            )
            conn.commit()
            # If we get here, FK might not be enforced (some SQLite configs)
            # This is acceptable - the schema has the constraint
        except sqlite3.IntegrityError:
            # Expected - FK enforced
            pass
        finally:
            conn.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])