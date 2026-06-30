"""Tests for `skills/apify/scripts/cli.py` and its platform adapters.

Adapter tests (build_input / normalize_output / get_actor / source suffix /
min_count) run with no network and no DB. CLI tests mock ``subprocess.run`` and
``shutil.which`` to cover --help, invalid platform, the two-phase cost wizard,
the --confirm persist flow, and the missing-CLI guard.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

# Make cv-pilot-agent/ importable (for _lib) and the scripts/ dir importable
# (for `cli` and the `platforms` package), mirroring test_format_report.
_AGENT_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "cv-pilot-agent"
_SCRIPTS_DIR = _AGENT_ROOT / "skills" / "apify" / "scripts"
for _p in (_AGENT_ROOT, _SCRIPTS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import cli as search_jobs  # type: ignore  # noqa: E402
from platforms.base import SearchParams  # noqa: E402
from platforms.computrabajo import ComputrabajoAdapter  # noqa: E402
from platforms.indeed import IndeedAdapter  # noqa: E402
from platforms.linkedin import LinkedinAdapter  # noqa: E402

runner = CliRunner()


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


# --------------------------------------------------------------------------- #
# CLI tests — subprocess.run and shutil.which are mocked; no network, no DB
# --------------------------------------------------------------------------- #
INFO_JSON = json.dumps({
    "currentPricingInfo": {
        "pricingPerEvent": {
            "actorChargeEvents": {
                "apify-default-dataset-item": {"eventPriceUsd": 0.001},
                "apify-actor-start": {"eventPriceUsd": 0.0005},
            }
        }
    }
})
INDEED_RAW = [{"positionName": "React Developer", "company": "Acme",
                "url": "https://x", "id": 7, "postedAt": "2026-06-01"}]
PERSIST_JSON = json.dumps({"ok": True, "inserted": 1, "duplicates": 0})


class _FakeProc:
    def __init__(self, args, returncode, stdout="", stderr=""):
        self.args = args
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _make_run(info=INFO_JSON, dataset=INDEED_RAW, persist=PERSIST_JSON, calls=None,
              fail_call=False):
    def _run(args, **kwargs):
        if calls is not None:
            calls.append(list(args))
        if args[0] == "apify" and args[1] == "actors":
            return _FakeProc(args, 0, stdout=info)
        if args[0] == "apify" and args[1] == "call":
            if fail_call:
                return _FakeProc(args, 1, stderr="boom")
            return _FakeProc(args, 0, stdout=json.dumps(dataset))
        # query.py job insert-batch
        return _FakeProc(args, 0, stdout=persist)
    return _run


def _has_apify(monkeypatch):
    monkeypatch.setattr(search_jobs.shutil, "which",
                        lambda name: "/usr/bin/apify" if name == "apify" else None)


def test_cli_help_exits_zero():
    result = runner.invoke(search_jobs.app, ["--help"])
    assert result.exit_code == 0
    assert "platform" in result.output


def test_cli_invalid_platform_errors(monkeypatch):
    _has_apify(monkeypatch)
    monkeypatch.setattr(search_jobs.subprocess, "run", _make_run())
    result = runner.invoke(
        search_jobs.app,
        ["--platform", "glassdoor", "--position", "Dev", "--location", "Bog"],
    )
    assert result.exit_code == 1
    assert "INVALID_PLATFORM" in (result.output + (result.stderr or ""))


def test_cost_phase_does_not_call_actor(monkeypatch):
    _has_apify(monkeypatch)
    calls = []
    monkeypatch.setattr(search_jobs.subprocess, "run",
                        _make_run(calls=calls, fail_call=True))
    result = runner.invoke(
        search_jobs.app,
        ["--platform", "indeed", "--position", "React Developer",
         "--location", "Bogota", "--count", "5"],
    )
    assert result.exit_code == 0, result.output
    out = json.loads(result.stdout)
    assert out["phase"] == "cost"
    assert out["actor"] == "misceres/indeed-scraper"
    assert out["count"] == 5
    assert out["cost_usd"] == 0.0055  # 5 * 0.001 + 0.0005
    # The actor was never called (cost-only phase).
    assert not any(c[0:2] == ["apify", "call"] for c in calls)


def test_confirm_phase_normalizes_persists_and_labels(monkeypatch):
    _has_apify(monkeypatch)
    monkeypatch.setattr(search_jobs.subprocess, "run", _make_run())
    result = runner.invoke(
        search_jobs.app,
        ["--platform", "indeed", "--position", "React Developer",
         "--location", "Bogota", "--count", "5", "--confirm"],
    )
    assert result.exit_code == 0, result.output
    out = json.loads(result.stdout)
    assert out["phase"] == "done"
    assert out["platform"] == "indeed"
    assert out["count"] == 1
    assert out["relevance"] == {"high": 1, "medium": 0, "low": 0}
    assert out["persisted"] == {"ok": True, "inserted": 1, "duplicates": 0}


def test_confirm_phase_empty_dataset(monkeypatch):
    _has_apify(monkeypatch)
    monkeypatch.setattr(search_jobs.subprocess, "run", _make_run(dataset=[]))
    result = runner.invoke(
        search_jobs.app,
        ["--platform", "indeed", "--position", "React Developer",
         "--location", "Bogota", "--count", "5", "--confirm"],
    )
    assert result.exit_code == 0, result.output
    out = json.loads(result.stdout)
    assert out["count"] == 0
    assert out["persisted"] is None
    assert out["relevance"] == {"high": 0, "medium": 0, "low": 0}


def test_apify_cli_missing_errors(monkeypatch):
    monkeypatch.setattr(search_jobs.shutil, "which", lambda name: None)
    result = runner.invoke(
        search_jobs.app,
        ["--platform", "indeed", "--position", "Dev", "--location", "Bog", "--confirm"],
    )
    assert result.exit_code == 1
    assert "APIFY_CLI_MISSING" in (result.output + (result.stderr or ""))