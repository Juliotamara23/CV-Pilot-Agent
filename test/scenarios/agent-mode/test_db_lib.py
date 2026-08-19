"""Unit tests for `_lib/db.py` using an in-process SQLite file (CV_PILOT_DB)."""

import sqlite3

import pytest

from _lib import db
from _lib.errors import JobNotFoundError, ValidationError
from _lib.models import AnalysisInsert, JobInsert, AnalysisUpdate, JobUpdate


class TestComputeHash:
    def test_deterministic(self):
        h1 = db.compute_hash("Acme", "Developer", "Madrid")
        h2 = db.compute_hash("Acme", "Developer", "Madrid")
        assert h1 == h2
        assert len(h1) == 64

    def test_normalization_titlecases_company(self):
        h1 = db.compute_hash("acme", "dev", "madrid")
        h2 = db.compute_hash("  acme  ", "dev", "madrid")
        assert h1 == h2  # strip + title normalize

    def test_different_location_different_hash(self):
        assert db.compute_hash("A", "P", "X") != db.compute_hash("A", "P", "Y")


class TestInsertJob:
    def test_new_insert(self, tmp_db):
        result = db.insert_job(
            JobInsert(company="Acme", position="Developer", location="Madrid",
                      public_date="2026-06-20")
        )
        assert result["ok"] is True
        assert result["is_new"] is True
        assert result["is_duplicate"] is False
        assert result["refreshed"] is False

    def test_duplicate_same_date_no_mutation(self, tmp_db):
        job = JobInsert(company="Acme", position="Developer", location="Madrid",
                        public_date="2026-06-20", url="https://old")
        db.insert_job(job)

        dup = db.insert_job(
            JobInsert(company="Acme", position="Developer", location="Madrid",
                      public_date="2026-06-20", url="https://new")
        )
        assert dup["is_new"] is False
        assert dup["is_duplicate"] is True
        assert dup["refreshed"] is False

        got = db.get_job(dup["hash"])["job"]
        assert got["url"] == "https://old"  # unchanged

    def test_duplicate_older_date_no_mutation(self, tmp_db):
        db.insert_job(JobInsert(company="Acme", position="Developer", location="Madrid",
                                public_date="2026-06-25"))
        dup = db.insert_job(
            JobInsert(company="Acme", position="Developer", location="Madrid",
                      public_date="2026-06-20", url="https://older")
        )
        assert dup["refreshed"] is False
        got = db.get_job(dup["hash"])["job"]
        assert got["public_date"] == "2026-06-25"

    def test_duplicate_newer_date_refreshes(self, tmp_db):
        job_hash = db.insert_job(
            JobInsert(company="Acme", position="Developer", location="Madrid",
                      public_date="2026-06-20", url="https://old")
        )["hash"]
        # Insert an analysis so we can assert it gets deleted on refresh.
        db.insert_analysis(AnalysisInsert(
            job_hash=job_hash, percentage=10.0, comparativa="c",
            observaciones="o", verdict="No apto", tldr="t",
        ))
        assert db.get_analysis(job_hash)["ok"] is True

        refreshed = db.insert_job(
            JobInsert(company="Acme", position="Developer", location="Madrid",
                      public_date="2026-06-25", url="https://new")
        )
        assert refreshed["is_new"] is False
        assert refreshed["is_duplicate"] is True
        assert refreshed["refreshed"] is True

        got = db.get_job(job_hash)["job"]
        assert got["public_date"] == "2026-06-25"
        assert got["url"] == "https://new"
        assert got["status"] == "new"  # reset

        with pytest.raises(JobNotFoundError):
            db.get_analysis(job_hash)  # analysis deleted


class TestInsertJobsBatch:
    def test_mixed_batch(self, tmp_db):
        h1 = db.insert_job(JobInsert(company="A", position="P", location="L",
                                     public_date="2026-06-20"))["hash"]
        batch = [
            {"company": "A", "position": "P", "location": "L", "public_date": "2026-06-25"},  # refresh
            {"company": "B", "position": "P", "location": "L"},  # new
            {"company": "C", "position": "P", "location": "L"},  # new
        ]
        result = db.insert_jobs_batch([JobInsert(**j) for j in batch])
        assert result["inserted"] == 2
        assert result["duplicates"] == 1
        assert result["refreshed"] == 1
        assert len(result["results"]) == 3
        assert result["results"][0]["hash"] == h1
        assert result["results"][0]["refreshed"] is True

    def test_empty_batch(self, tmp_db):
        result = db.insert_jobs_batch([])
        assert result["inserted"] == 0
        assert result["duplicates"] == 0
        assert result["results"] == []

    def test_all_duplicates_no_refresh(self, tmp_db):
        db.insert_job(JobInsert(company="A", position="P", location="L",
                                public_date="2026-06-25"))
        db.insert_job(JobInsert(company="B", position="P", location="L",
                                public_date="2026-06-25"))
        result = db.insert_jobs_batch([
            JobInsert(company="A", position="P", location="L", public_date="2026-06-20"),
            JobInsert(company="B", position="P", location="L", public_date="2026-06-20"),
        ])
        assert result["inserted"] == 0
        assert result["duplicates"] == 2
        assert result["refreshed"] == 0


class TestListJobs:
    def test_list_all(self, tmp_db):
        db.insert_job(JobInsert(company="A", position="P", location="L"))
        db.insert_job(JobInsert(company="B", position="P", location="L"))
        result = db.list_jobs()
        assert result["count"] == 2
        assert len(result["jobs"]) == 2

    def test_list_by_status(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        db.insert_job(JobInsert(company="B", position="P", location="L"))
        result = db.list_jobs(status="new")
        assert result["count"] == 2
        assert all(j["status"] == "new" for j in result["jobs"])

    def test_list_empty_status(self, tmp_db):
        result = db.list_jobs(status="discarded")
        assert result["count"] == 0
        assert result["jobs"] == []

    def test_list_invalid_status_raises(self, tmp_db):
        with pytest.raises(ValidationError):
            db.list_jobs(status="bogus")


class TestGetJob:
    def test_found(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        result = db.get_job(h)
        assert result["ok"] is True
        assert result["job"]["company"] == "A"

    def test_not_found_raises(self, tmp_db):
        with pytest.raises(JobNotFoundError):
            db.get_job("nonexistent")


class TestDeleteJobs:
    def test_dry_run_by_status(self, tmp_db):
        db.insert_job(JobInsert(company="A", position="P", location="L"))
        db.insert_job(JobInsert(company="B", position="P", location="L"))
        result = db.delete_jobs(status="new", dry_run=True)
        assert result["dry_run"] is True
        assert result["would_delete"] == 2
        # No mutation.
        assert db.list_jobs()["count"] == 2

    def test_delete_by_status(self, tmp_db):
        db.insert_job(JobInsert(company="A", position="P", location="L"))
        db.insert_job(JobInsert(company="B", position="P", location="L"))
        result = db.delete_jobs(status="new")
        assert result["deleted"] == 2
        assert db.list_jobs()["count"] == 0

    def test_delete_by_hash_removes_analysis(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        db.insert_analysis(AnalysisInsert(
            job_hash=h, percentage=50.0, comparativa="c",
            observaciones="o", verdict="No apto", tldr="t",
        ))
        result = db.delete_jobs(job_hash=h)
        assert result["deleted"] == 1
        with pytest.raises(JobNotFoundError):
            db.get_analysis(h)

    def test_delete_no_matches_raises(self, tmp_db):
        with pytest.raises(JobNotFoundError):
            db.delete_jobs(status="discarded")

    def test_delete_requires_filter(self, tmp_db):
        with pytest.raises(ValidationError):
            db.delete_jobs()


class TestInsertAnalysis:
    def test_insert_marks_analyzed(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        result = db.insert_analysis(AnalysisInsert(
            job_hash=h, percentage=85.5, comparativa="c",
            observaciones="o", verdict="Apto", tldr="t",
        ))
        assert result["ok"] is True
        assert "analysis_id" in result
        got = db.get_job(h)["job"]
        assert got["status"] == "analyzed"

    def test_insert_with_contact_method_persists(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        db.insert_analysis(AnalysisInsert(
            job_hash=h, percentage=85.5, comparativa="c",
            observaciones="o", verdict="Apto", tldr="t",
            contact_method="email",
        ))
        got = db.get_analysis(h)["analysis"]
        assert got["contact_method"] == "email"

    def test_insert_without_contact_method_defaults_none(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        db.insert_analysis(AnalysisInsert(
            job_hash=h, percentage=85.5, comparativa="c",
            observaciones="o", verdict="Apto", tldr="t",
        ))
        got = db.get_analysis(h)["analysis"]
        assert got["contact_method"] is None

    def test_job_not_found(self, tmp_db):
        with pytest.raises(JobNotFoundError):
            db.insert_analysis(AnalysisInsert(
                job_hash="missing", percentage=50.0, comparativa="c",
                observaciones="o", verdict="No apto", tldr="t",
            ))


class TestVerdictValidation:
    """Verdict must be one of the allowed business values (No apto, Apto con reservas, Apto).

    Validation happens at the domain boundary (insert_analysis / update_analysis).
    Invalid verdicts raise ValidationError with code VALIDATION_ERROR.
    """

    def test_valid_verdicts_accepted(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        for verdict in ("No apto", "Apto con reservas", "Apto"):
            # Clean slate for each verdict
            if verdict != "No apto":  # first iteration uses the existing job
                h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
            result = db.insert_analysis(AnalysisInsert(
                job_hash=h, percentage=50.0, comparativa="c",
                observaciones="o", verdict=verdict, tldr="t",
            ))
            assert result["ok"] is True
            got = db.get_analysis(h)["analysis"]
            assert got["verdict"] == verdict

    def test_invalid_verdict_rejected_on_insert(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        with pytest.raises(ValidationError) as exc:
            db.insert_analysis(AnalysisInsert(
                job_hash=h, percentage=50.0, comparativa="c",
                observaciones="o", verdict="Pending", tldr="t",
            ))
        assert exc.value.code == "VALIDATION_ERROR"
        assert "verdict" in str(exc.value).lower()

    def test_invalid_verdict_rejected_on_update(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        db.insert_analysis(AnalysisInsert(
            job_hash=h, percentage=50.0, comparativa="c",
            observaciones="o", verdict="Apto", tldr="t",
        ))
        with pytest.raises(ValidationError) as exc:
            db.update_analysis(job_hash=h, analysis_update=AnalysisUpdate(verdict="Undecided"))
        assert exc.value.code == "VALIDATION_ERROR"
        assert "verdict" in str(exc.value).lower()

    def test_verdict_case_sensitive(self, tmp_db):
        """Verdict values are exact Spanish strings — case matters."""
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        with pytest.raises(ValidationError):
            db.insert_analysis(AnalysisInsert(
                job_hash=h, percentage=50.0, comparativa="c",
                observaciones="o", verdict="no apto", tldr="t",  # lowercase
            ))
        with pytest.raises(ValidationError):
            db.insert_analysis(AnalysisInsert(
                job_hash=h, percentage=50.0, comparativa="c",
                observaciones="o", verdict="APTO", tldr="t",  # uppercase
            ))

    def test_empty_verdict_rejected(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        with pytest.raises(ValidationError):
            db.insert_analysis(AnalysisInsert(
                job_hash=h, percentage=50.0, comparativa="c",
                observaciones="o", verdict="", tldr="t",
            ))


class TestGetAnalysis:
    def test_found(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        db.insert_analysis(AnalysisInsert(
            job_hash=h, percentage=85.5, comparativa="c",
            observaciones="o", verdict="No apto", tldr="t",
        ))
        result = db.get_analysis(h)
        assert result["ok"] is True
        # Production schema: percentage is TEXT NOT NULL. SQLite returns it as
        # a string. The Pydantic model says float, but the DB column is TEXT.
        # Match what production actually returns.
        assert result["analysis"]["percentage"] == "85.5"

    def test_returns_contact_method(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        db.insert_analysis(AnalysisInsert(
            job_hash=h, percentage=70.0, comparativa="c",
            observaciones="o", verdict="No apto", tldr="t",
            contact_method="portal",
        ))
        analysis = db.get_analysis(h)["analysis"]
        assert analysis["contact_method"] == "portal"

    def test_not_found_raises(self, tmp_db):
        with pytest.raises(JobNotFoundError):
            db.get_analysis("missing")


class TestContactMethodSchema:
    """contact_method is now part of the canonical schema in conftest and init.py.

    The _ensure_schema migration was moved from db.py to scripts/init.py.
    Tests verify that contact_method works correctly with the full schema.
    """

    def test_contact_method_column_exists(self, tmp_db):
        """The conftest schema includes contact_method (matches init.py)."""
        conn = sqlite3.connect(str(tmp_db))
        cols = {row[1] for row in conn.execute("PRAGMA table_info(analyses)")}
        conn.close()
        assert "contact_method" in cols

    def test_contact_method_round_trip(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        db.insert_analysis(AnalysisInsert(
            job_hash=h, percentage=80.0, comparativa="c",
            observaciones="o", verdict="No apto", tldr="t",
            contact_method="email",
        ))
        got = db.get_analysis(h)["analysis"]
        assert got["contact_method"] == "email"


class TestUpdateStatus:
    def test_update_success(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        result = db.update_status(h, "applied")
        assert result["old_status"] == "new"
        assert result["new_status"] == "applied"
        assert db.get_job(h)["job"]["status"] == "applied"

    def test_invalid_status(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        with pytest.raises(ValidationError):
            db.update_status(h, "bogus")

    def test_job_not_found(self, tmp_db):
        with pytest.raises(JobNotFoundError):
            db.update_status("missing", "applied")


class TestUpdateAnalysis:
    def test_update_by_job_hash_updates_most_recent(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        db.insert_analysis(AnalysisInsert(job_hash=h, percentage=10.0, comparativa="c1", observaciones="o1", verdict="No apto", tldr="t1"))
        db.insert_analysis(AnalysisInsert(job_hash=h, percentage=20.0, comparativa="c2", observaciones="o2", verdict="Apto con reservas", tldr="t2"))
        # get_analysis returns most recent (20%)
        assert db.get_analysis(h)["analysis"]["percentage"] == "20.0"
        result = db.update_analysis(job_hash=h, analysis_update=AnalysisUpdate(verdict="Apto", percentage=99.0))
        assert result["ok"] is True
        assert result["selector"] == "job_hash"
        # Most recent should now have updated values
        got = db.get_analysis(h)["analysis"]
        assert got["verdict"] == "Apto"
        assert got["percentage"] == "99.0"
        # Other fields unchanged
        assert got["comparativa"] == "c2"

    def test_update_by_analysis_id_targets_specific_row(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        r1 = db.insert_analysis(AnalysisInsert(job_hash=h, percentage=10.0, comparativa="c1", observaciones="o1", verdict="No apto", tldr="t1"))
        r2 = db.insert_analysis(AnalysisInsert(job_hash=h, percentage=20.0, comparativa="c2", observaciones="o2", verdict="Apto con reservas", tldr="t2"))
        id1 = r1["analysis_id"]
        id2 = r2["analysis_id"]
        # Update the older one by ID
        result = db.update_analysis(analysis_id=id1, analysis_update=AnalysisUpdate(verdict="Apto"))
        assert result["ok"] is True
        assert result["selector"] == "analysis_id"
        assert result["analysis_id"] == id1
        # Verify older row updated
        conn = sqlite3.connect(str(tmp_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT verdict FROM analyses WHERE analysis_id = ?", (id1,)).fetchone()
        conn.close()
        assert row["verdict"] == "Apto"
        # Most recent unchanged
        assert db.get_analysis(h)["analysis"]["verdict"] == "Apto con reservas"

    def test_partial_update_leaves_other_fields_intact(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        db.insert_analysis(AnalysisInsert(job_hash=h, percentage=50.0, comparativa="orig-comp", observaciones="orig-obs", verdict="No apto", tldr="orig-tldr", contact_method="email"))
        result = db.update_analysis(job_hash=h, analysis_update=AnalysisUpdate(verdict="Apto"))
        assert result["ok"] is True
        got = db.get_analysis(h)["analysis"]
        assert got["verdict"] == "Apto"
        assert got["comparativa"] == "orig-comp"
        assert got["observaciones"] == "orig-obs"
        assert got["tldr"] == "orig-tldr"
        assert got["contact_method"] == "email"

    def test_no_fields_raises_validation_error(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        db.insert_analysis(AnalysisInsert(job_hash=h, percentage=50.0, comparativa="c", observaciones="o", verdict="No apto", tldr="t"))
        with pytest.raises(ValidationError) as exc:
            db.update_analysis(job_hash=h, analysis_update=AnalysisUpdate())
        assert exc.value.code == "VALIDATION_ERROR"

    def test_no_selector_raises_validation_error(self, tmp_db):
        with pytest.raises(ValidationError) as exc:
            db.update_analysis(analysis_update=AnalysisUpdate(verdict="No apto"))
        assert exc.value.code == "VALIDATION_ERROR"

    def test_both_selectors_raises_validation_error(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        db.insert_analysis(AnalysisInsert(job_hash=h, percentage=50.0, comparativa="c", observaciones="o", verdict="No apto", tldr="t"))
        with pytest.raises(ValidationError) as exc:
            db.update_analysis(job_hash=h, analysis_id="some-id", analysis_update=AnalysisUpdate(verdict="No apto"))
        assert exc.value.code == "VALIDATION_ERROR"

    def test_job_not_found_by_job_hash(self, tmp_db):
        with pytest.raises(JobNotFoundError) as exc:
            db.update_analysis(job_hash="missing", analysis_update=AnalysisUpdate(verdict="No apto"))
        assert exc.value.code == "JOB_NOT_FOUND"

    def test_analysis_not_found_by_job_hash(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        with pytest.raises(JobNotFoundError) as exc:
            db.update_analysis(job_hash=h, analysis_update=AnalysisUpdate(verdict="No apto"))
        assert exc.value.code == "ANALYSIS_NOT_FOUND"

    def test_analysis_not_found_by_id(self, tmp_db):
        with pytest.raises(JobNotFoundError) as exc:
            db.update_analysis(analysis_id="missing-id", analysis_update=AnalysisUpdate(verdict="No apto"))
        assert exc.value.code == "ANALYSIS_NOT_FOUND"

    def test_percentage_out_of_bounds_raises_validation_error(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        db.insert_analysis(AnalysisInsert(job_hash=h, percentage=50.0, comparativa="c", observaciones="o", verdict="No apto", tldr="t"))
        with pytest.raises(ValidationError) as exc:
            db.update_analysis(job_hash=h, analysis_update=AnalysisUpdate(percentage=101.0))
        assert exc.value.code == "VALIDATION_ERROR"
        with pytest.raises(ValidationError) as exc:
            db.update_analysis(job_hash=h, analysis_update=AnalysisUpdate(percentage=-1.0))
        assert exc.value.code == "VALIDATION_ERROR"

    def test_percentage_bounds_accept_boundaries(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        db.insert_analysis(AnalysisInsert(job_hash=h, percentage=50.0, comparativa="c", observaciones="o", verdict="No apto", tldr="t"))
        result = db.update_analysis(job_hash=h, analysis_update=AnalysisUpdate(percentage=0.0))
        assert result["ok"] is True
        result = db.update_analysis(job_hash=h, analysis_update=AnalysisUpdate(percentage=100.0))
        assert result["ok"] is True

    def test_oversized_text_raises_validation_error(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        db.insert_analysis(AnalysisInsert(job_hash=h, percentage=50.0, comparativa="c", observaciones="o", verdict="No apto", tldr="t"))
        with pytest.raises(ValidationError) as exc:
            db.update_analysis(job_hash=h, analysis_update=AnalysisUpdate(verdict="x" * 20001))
        assert exc.value.code == "VALIDATION_ERROR"
        with pytest.raises(ValidationError) as exc:
            db.update_analysis(job_hash=h, analysis_update=AnalysisUpdate(contact_method="x" * 51))
        assert exc.value.code == "VALIDATION_ERROR"


class TestDeleteAnalysis:
    def test_delete_by_analysis_id(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        r = db.insert_analysis(AnalysisInsert(job_hash=h, percentage=50.0, comparativa="c", observaciones="o", verdict="No apto", tldr="t"))
        aid = r["analysis_id"]
        result = db.delete_analysis(analysis_id=aid)
        assert result["ok"] is True
        assert result["deleted"] == 1
        with pytest.raises(JobNotFoundError):
            db.get_analysis(h)
        # Job should still exist
        assert db.get_job(h)["ok"] is True

    def test_delete_by_job_hash_deletes_most_recent(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        db.insert_analysis(AnalysisInsert(job_hash=h, percentage=10.0, comparativa="c1", observaciones="o1", verdict="No apto", tldr="t1"))
        db.insert_analysis(AnalysisInsert(job_hash=h, percentage=20.0, comparativa="c2", observaciones="o2", verdict="Apto con reservas", tldr="t2"))
        # Most recent is 20%
        assert db.get_analysis(h)["analysis"]["percentage"] == "20.0"
        result = db.delete_analysis(job_hash=h)
        assert result["ok"] is True
        assert result["deleted"] == 1
        # Now most recent should be the older one (10%)
        got = db.get_analysis(h)["analysis"]
        assert got["percentage"] == "10.0"
        # Job still exists
        assert db.get_job(h)["ok"] is True

    def test_delete_analysis_not_found_by_id(self, tmp_db):
        with pytest.raises(JobNotFoundError) as exc:
            db.delete_analysis(analysis_id="missing-id")
        assert exc.value.code == "ANALYSIS_NOT_FOUND"

    def test_delete_analysis_not_found_by_job_hash(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        with pytest.raises(JobNotFoundError) as exc:
            db.delete_analysis(job_hash=h)
        assert exc.value.code == "ANALYSIS_NOT_FOUND"

    def test_delete_no_selector_raises_validation_error(self, tmp_db):
        with pytest.raises(ValidationError) as exc:
            db.delete_analysis()
        assert exc.value.code == "VALIDATION_ERROR"

    def test_delete_both_selectors_raises_validation_error(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        r = db.insert_analysis(AnalysisInsert(job_hash=h, percentage=50.0, comparativa="c", observaciones="o", verdict="No apto", tldr="t"))
        with pytest.raises(ValidationError) as exc:
            db.delete_analysis(job_hash=h, analysis_id=r["analysis_id"])
        assert exc.value.code == "VALIDATION_ERROR"

    def test_delete_does_not_remove_job(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        r = db.insert_analysis(AnalysisInsert(job_hash=h, percentage=50.0, comparativa="c", observaciones="o", verdict="No apto", tldr="t"))
        db.delete_analysis(analysis_id=r["analysis_id"])
        job = db.get_job(h)["job"]
        assert job["job_hash"] == h
        assert job["status"] == "analyzed"  # status unchanged


class TestUpdateJob:
    def test_update_non_identity_fields(self, tmp_db):
        h = db.insert_job(JobInsert(company="Acme", position="Dev", location="Madrid", public_date="2026-06-20", url="https://old", salary="50k", description="old desc", source="manual"))["hash"]
        result = db.update_job(h, JobUpdate(public_date="2026-06-25", url="https://new", salary="60k", description="new desc", source="apify-linkedin"))
        assert result["ok"] is True
        assert result["job_hash"] == h
        got = db.get_job(h)["job"]
        assert got["public_date"] == "2026-06-25"
        assert got["url"] == "https://new"
        assert got["salary"] == "60k"
        assert got["description"] == "new desc"
        assert got["source"] == "apify-linkedin"
        # Identity fields unchanged
        assert got["company"] == "Acme"
        assert got["position"] == "Dev"
        assert got["location"] == "Madrid"

    def test_partial_update_leaves_other_fields_intact(self, tmp_db):
        h = db.insert_job(JobInsert(company="Acme", position="Dev", location="Madrid", external_id="ext-1", public_date="2026-06-20", url="https://old", salary="50k", description="old", source="manual"))["hash"]
        result = db.update_job(h, JobUpdate(salary="60k"))
        assert result["ok"] is True
        got = db.get_job(h)["job"]
        assert got["salary"] == "60k"
        assert got["external_id"] == "ext-1"
        assert got["public_date"] == "2026-06-20"
        assert got["url"] == "https://old"
        assert got["description"] == "old"
        assert got["source"] == "manual"

    def test_no_fields_raises_validation_error(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        with pytest.raises(ValidationError) as exc:
            db.update_job(h, JobUpdate())
        assert exc.value.code == "VALIDATION_ERROR"

    def test_oversized_field_raises_validation_error(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        with pytest.raises(ValidationError) as exc:
            db.update_job(h, JobUpdate(description="x" * 20001))
        assert exc.value.code == "VALIDATION_ERROR"
        with pytest.raises(ValidationError) as exc:
            db.update_job(h, JobUpdate(url="x" * 2001))
        assert exc.value.code == "VALIDATION_ERROR"
        with pytest.raises(ValidationError) as exc:
            db.update_job(h, JobUpdate(source="x" * 201))
        assert exc.value.code == "VALIDATION_ERROR"

    def test_job_not_found(self, tmp_db):
        with pytest.raises(JobNotFoundError) as exc:
            db.update_job("missing", JobUpdate(url="https://new"))
        assert exc.value.code == "JOB_NOT_FOUND"

    def test_update_job_does_not_touch_analyses(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        db.insert_analysis(AnalysisInsert(job_hash=h, percentage=50.0, comparativa="c", observaciones="o", verdict="No apto", tldr="t"))
        db.update_job(h, JobUpdate(url="https://new"))
        # Analysis should still exist
        got = db.get_analysis(h)["analysis"]
        assert got["percentage"] == "50.0"

    def test_update_job_does_not_touch_status(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        db.insert_analysis(AnalysisInsert(job_hash=h, percentage=50.0, comparativa="c", observaciones="o", verdict="No apto", tldr="t"))
        # Status is 'analyzed'
        assert db.get_job(h)["job"]["status"] == "analyzed"
        db.update_job(h, JobUpdate(url="https://new"))
        # Status should still be 'analyzed'
        assert db.get_job(h)["job"]["status"] == "analyzed"
