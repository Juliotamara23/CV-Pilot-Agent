"""Unit tests for `_lib/models.py`."""

import pytest
from pydantic import ValidationError

from _lib.models import AnalysisInsert, Analysis, Job, JobInsert


class TestJobInsert:
    def test_valid_minimal(self):
        job = JobInsert(company="acme", position="dev", location="madrid")
        assert job.company == "acme"
        assert job.source == "manual"
        assert job.external_id is None

    def test_missing_required_company(self):
        with pytest.raises(ValidationError):
            JobInsert(position="dev", location="madrid")

    def test_missing_required_position(self):
        with pytest.raises(ValidationError):
            JobInsert(company="acme", location="madrid")

    def test_missing_required_location(self):
        with pytest.raises(ValidationError):
            JobInsert(company="acme", position="dev")


class TestJob:
    def test_default_status_new(self):
        job = Job(job_hash="abc", company="acme", position="dev", location="madrid")
        assert job.status == "new"
        assert job.source == "manual"

    @pytest.mark.parametrize(
        "status",
        ["new", "analyzed", "discarded", "applied", "rejected"],
    )
    def test_valid_statuses(self, status):
        job = Job(
            job_hash="abc", company="acme", position="dev", location="madrid",
            status=status,
        )
        assert job.status == status

    def test_invalid_status_rejected(self):
        with pytest.raises(ValidationError):
            Job(
                job_hash="abc", company="acme", position="dev", location="madrid",
                status="invalid_status",
            )


class TestAnalysisInsert:
    def test_valid(self):
        a = AnalysisInsert(
            job_hash="h", percentage=85.5, comparativa="c",
            observaciones="o", verdict="v", tldr="t",
        )
        assert a.percentage == 85.5
        assert a.tldr == "t"

    def test_contact_method_defaults_none(self):
        a = AnalysisInsert(
            job_hash="h", percentage=85.5, comparativa="c",
            observaciones="o", verdict="v", tldr="t",
        )
        assert a.contact_method is None

    def test_contact_method_accepted(self):
        a = AnalysisInsert(
            job_hash="h", percentage=85.5, comparativa="c",
            observaciones="o", verdict="v", tldr="t",
            contact_method="email",
        )
        assert a.contact_method == "email"

    def test_missing_required_percentage(self):
        with pytest.raises(ValidationError):
            AnalysisInsert(
                job_hash="h", comparativa="c", observaciones="o",
                verdict="v", tldr="t",
            )

    def test_percentage_must_be_number(self):
        with pytest.raises(ValidationError):
            AnalysisInsert(
                job_hash="h", percentage="not-a-number", comparativa="c",
                observaciones="o", verdict="v", tldr="t",
            )


class TestAnalysis:
    def test_valid(self):
        a = Analysis(
            analysis_id="id", job_hash="h", percentage=50.0,
            comparativa="c", observaciones="o", verdict="v", tldr="t",
        )
        assert a.analysis_id == "id"
        assert a.created_at is None

    def test_contact_method_defaults_none(self):
        a = Analysis(
            analysis_id="id", job_hash="h", percentage=50.0,
            comparativa="c", observaciones="o", verdict="v", tldr="t",
        )
        assert a.contact_method is None

    def test_contact_method_accepted(self):
        a = Analysis(
            analysis_id="id", job_hash="h", percentage=50.0,
            comparativa="c", observaciones="o", verdict="v", tldr="t",
            contact_method="portal",
        )
        assert a.contact_method == "portal"
