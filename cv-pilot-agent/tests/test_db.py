"""Unit tests for `_lib/db.py` using an in-process SQLite file (CV_PILOT_DB)."""

import pytest

from _lib import db
from _lib.errors import JobNotFoundError, ValidationError
from _lib.models import AnalysisInsert, JobInsert


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
            observaciones="o", verdict="v", tldr="t",
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
            observaciones="o", verdict="v", tldr="t",
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
            observaciones="o", verdict="v", tldr="t",
        ))
        assert result["ok"] is True
        assert "analysis_id" in result
        got = db.get_job(h)["job"]
        assert got["status"] == "analyzed"

    def test_job_not_found(self, tmp_db):
        with pytest.raises(JobNotFoundError):
            db.insert_analysis(AnalysisInsert(
                job_hash="missing", percentage=50.0, comparativa="c",
                observaciones="o", verdict="v", tldr="t",
            ))


class TestGetAnalysis:
    def test_found(self, tmp_db):
        h = db.insert_job(JobInsert(company="A", position="P", location="L"))["hash"]
        db.insert_analysis(AnalysisInsert(
            job_hash=h, percentage=85.5, comparativa="c",
            observaciones="o", verdict="v", tldr="t",
        ))
        result = db.get_analysis(h)
        assert result["ok"] is True
        assert result["analysis"]["percentage"] == 85.5

    def test_not_found_raises(self, tmp_db):
        with pytest.raises(JobNotFoundError):
            db.get_analysis("missing")


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