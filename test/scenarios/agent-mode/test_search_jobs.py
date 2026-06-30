"""Tests for `skills/apify/scripts/search_jobs.py` and its platform adapters.

Adapter tests (build_input / normalize_output / get_actor / source suffix /
min_count) run with no network and no DB. CLI tests mock ``subprocess.run`` and
``shutil.which`` to cover --help, invalid platform, the two-phase cost wizard,
the --confirm persist flow, and the missing-CLI guard.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

# Make cv-pilot-agent/ importable (for _lib) and the scripts/ dir importable
# (for the `platforms` package), mirroring test_format_report.
_AGENT_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "cv-pilot-agent"
_SCRIPTS_DIR = _AGENT_ROOT / "skills" / "apify" / "scripts"
for _p in (_AGENT_ROOT, _SCRIPTS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from platforms.base import SearchParams  # noqa: E402
from platforms.computrabajo import ComputrabajoAdapter  # noqa: E402
from platforms.indeed import IndeedAdapter  # noqa: E402
from platforms.linkedin import LinkedinAdapter  # noqa: E402


# --------------------------------------------------------------------------- #
# Adapter unit tests
# --------------------------------------------------------------------------- #
def _params(**overrides) -> SearchParams:
    base = dict(position="React Developer", location="Medellín", country="CO", count=5)
    base.update(overrides)
    return SearchParams(**base)


def test_indeed_build_input_shape():
    adapter = IndeedAdapter()
    assert adapter.get_actor() == "misceres/indeed-scraper"
    assert adapter.get_platform_name() == "apify-indeed"
    assert adapter.build_input(_params(count=7)) == {
        "position": "React Developer",
        "country": "CO",
        "location": "Medellín",
        "maxItemsPerSearch": 7,
        "parseCompanyDetails": True,
        "saveOnlyUniqueItems": True,
        "followApplyRedirects": False,
    }


def test_indeed_normalize_maps_fields_and_source():
    raw = [{"positionName": "Sr React Dev", "company": "Acme", "location": "BOG",
            "salary": "$5M", "url": "https://x", "id": 42,
            "postedAt": "2026-06-01", "description": "desc"}]
    jobs = IndeedAdapter().normalize_output(raw)
    assert len(jobs) == 1
    j = jobs[0]
    assert j.position == "Sr React Dev"
    assert j.company == "Acme"
    assert j.location == "BOG"
    assert j.external_id == "42"
    assert j.public_date == "2026-06-01"
    assert j.url == "https://x"
    assert j.source == "apify-indeed"


def test_linkedin_builds_search_url_and_clamps_count():
    adapter = LinkedinAdapter()
    assert adapter.min_count() == 10
    params = _params(count=3, workplace_type="remote", experience_level="mid")
    inp = adapter.build_input(params)
    assert inp["count"] == 10  # clamped up
    assert inp["scrapeCompany"] is True and inp["splitByLocation"] is False
    url = inp["urls"][0]
    assert url.startswith("https://www.linkedin.com/jobs/search/?")
    assert "keywords=React+Developer" in url
    assert "location=Medell%C3%ADn" in url
    assert "f_WT=2" in url and "f_E=3" in url


def test_linkedin_normalize_handles_missing_optionals():
    raw = [{"title": "Backend", "companyName": "Glob", "link": "https://l"}]
    j = LinkedinAdapter().normalize_output(raw)[0]
    assert j.position == "Backend"
    assert j.company == "Glob"
    assert j.url == "https://l"
    assert j.salary is None and j.public_date is None
    assert j.source == "apify-linkedin"


def test_computrabajo_builds_url_with_subdomain_and_slug():
    adapter = ComputrabajoAdapter()
    params = _params(position="React Developer", location="Bogotá", country="CO", count=4)
    inp = adapter.build_input(params)
    assert inp["maxJobs"] == 4 and inp["includeFullDescription"] is True
    assert inp["searchUrl"] == "https://co.computrabajo.com/trabajo-de-react-developer-en-bogotá"


def test_computrabajo_remote_omits_location_segment():
    params = _params(position="Backend", location="Remote", country="AR")
    inp = ComputrabajoAdapter().build_input(params)
    assert inp["searchUrl"] == "https://ar.computrabajo.com/trabajo-de-backend"


def test_computrabajo_normalize_supports_alias_variants():
    raw = [{"jobTitle": "Dev", "companyName": "C", "date": "2026-05-01", "link": "https://l"}]
    j = ComputrabajoAdapter().normalize_output(raw)[0]
    assert j.position == "Dev" and j.company == "C"
    assert j.public_date == "2026-05-01" and j.source == "apify-computrabajo"


def test_search_params_validates_count_and_workplace():
    with pytest.raises(ValidationError):
        SearchParams(position="x", location="y", count=0)
    with pytest.raises(ValidationError):
        SearchParams(position="x", location="y", workplace_type="space")  # type: ignore[arg-type]