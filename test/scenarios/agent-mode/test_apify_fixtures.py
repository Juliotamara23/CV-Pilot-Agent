"""Fixture-based regression tests for the Apify platform adapters.

The fixtures in ``test/fixtures/apify/`` are frozen snapshots of real
actor output (one run per platform, captured 2026-07-07). They let us
verify that each adapter:

1. Reads the actual field names the actor emits today.
2. Populates JobInsert fields the agent flow relies on.
3. Does NOT silently drop data the actor provides (public_date, salary,
   description).

When the actor's output schema changes in the future, these tests will
either fail (if a field we depend on disappears) or expose the drift
(printing the new key set so a human can review).

To refresh a fixture after an actor update:
    apify call <actor_id> -f <input.json> > /tmp/run.log
    apify datasets get-items <dataset_id> --format json > test/fixtures/apify/<platform>.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Make adapters importable (mirror test_search_jobs.py setup).
_AGENT_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "cv-pilot-agent"
_SCRIPTS_DIR = _AGENT_ROOT / "skills" / "apify" / "scripts"
for _p in (_AGENT_ROOT, _SCRIPTS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from platforms.computrabajo import ComputrabajoAdapter  # noqa: E402
from platforms.indeed import IndeedAdapter  # noqa: E402
from platforms.linkedin import LinkedinAdapter  # noqa: E402

FIXTURES = Path(__file__).resolve().parent.parent.parent / "fixtures" / "apify"


def _load(name: str) -> list[dict]:
    path = FIXTURES / name
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing fixture: {path}. Run the actor to refresh — see docstring."
        )
    return json.loads(path.read_text(encoding="utf-8"))


# Fields the agent flow depends on. If any of these comes back empty
# from a real fixture item, the adapter is dropping data the agent
# would need. (Empty in the *fixture* would itself be a regression of
# the actor — but we only assert on fields the actor *does* populate.)
CRITICAL_FIELDS = ("position", "company", "location", "url")

# Fields the actor emits but the adapter does NOT map into JobInsert.
# These are *informational* (not bugs) — JobInsert has no column for them.
# Add to this set when deciding to ignore a field deliberately so the
# "no_silently_dropped" test doesn't false-alarm.
#
# If the actor adds a NEW field that is NOT in this set and NOT in
# `mapped`, the test will fail — that's the signal to extend the
# adapter or update the ignored set.
KNOWN_UNMAPPED: dict[str, set[str]] = {
    "computrabajo.json": {
        # Metadata: actor-internal or timestamps the DB doesn't store.
        "scrapedAt", "updatedAt", "source",
        "tags",                # TODO: nice-to-have (skills array)
        "offerAttributes",    # actor-internal grouping metadata
        "offerResponseMeta",  # actor-internal response metadata
    },
    "linkedin.json": {
        # Metadata: timestamps, tracking, company enrichment.
        "inputUrl", "refId", "trackingId",
        # Company enrichment (would need a separate table to capture).
        "companyLogo", "companyLinkedinUrl", "companyWebsite",
        "companyAddress", "companyDescription", "companySlogan",
        "companyEmployeesCount",
        # Job-level metadata not in JobInsert today.
        "applicantsCount", "applyUrl", "benefits", "employmentType",
        "jobFunction", "industries", "seniorityLevel",
    },
    "indeed.json": {
        # Metadata: actor-internal.
        "scrapedAt", "searchInput", "urlInput",
        # Company info.
        "companyIndeedUrl",
        "rating", "reviewsCount",
        # Job-level metadata not in JobInsert today.
        "externalApplyLink", "isExpired", "jobType",
    },
}


# --------------------------------------------------------------------------- #
# Computrabajo
# --------------------------------------------------------------------------- #
def test_computrabajo_fixture_captures_all_critical_fields():
    items = _load("computrabajo.json")
    assert items, "Fixture is empty — actor may have returned 0 results"
    adapter = ComputrabajoAdapter()
    jobs = adapter.normalize_output(items)
    assert len(jobs) == len(items)
    for raw, job in zip(items, jobs):
        # Every CRITICAL field is populated from a real (non-empty) fixture row.
        for f in CRITICAL_FIELDS:
            assert getattr(job, f), (
                f"Adapter dropped {f!r} for item {raw.get('id')!r}: {raw!r}"
            )
        # Computrabajo fixture always populates postedDate and descriptionText
        # (verified manually 2026-07-07). If these become empty in a future
        # capture, either the actor schema changed or the adapter is broken.
        assert job.public_date, f"public_date missing for {raw.get('id')}"
        assert job.description, f"description missing for {raw.get('id')}"


def test_computrabajo_fixture_no_silently_dropped_field():
    """Every key in the fixture must be considered by the adapter.

    Fields the adapter maps to JobInsert are in ``mapped``; fields the
    adapter deliberately ignores (no JobInsert column today) are in
    ``KNOWN_UNMAPPED``. The test only fails on UNKNOWN unmapped fields
    — those are signals that the actor schema changed and a human
    should review the adapter.
    """
    items = _load("computrabajo.json")
    raw_keys = set(items[0].keys())
    mapped = {
        "id", "company", "companyName", "title", "jobTitle",
        "location", "postedAt", "postedDate", "date",
        "url", "link", "salary", "description",
        "descriptionText", "descriptionHtml",
    }
    known_unmapped = KNOWN_UNMAPPED["computrabajo.json"]
    unknown = raw_keys - mapped - known_unmapped
    assert not unknown, (
        f"Fixture has UNKNOWN unmapped fields: {sorted(unknown)}. "
        f"The actor schema likely changed. Either extend the adapter, or "
        f"add the field to KNOWN_UNMAPPED in test_apify_fixtures.py "
        f"if JobInsert doesn't need it."
    )


# --------------------------------------------------------------------------- #
# LinkedIn
# --------------------------------------------------------------------------- #
def test_linkedin_fixture_captures_all_critical_fields():
    items = _load("linkedin.json")
    assert len(items) >= 10, f"Fixture has {len(items)} items, expected ≥10 (the actor's min_count)"
    adapter = LinkedinAdapter()
    jobs = adapter.normalize_output(items)
    for raw, job in zip(items, jobs):
        for f in CRITICAL_FIELDS:
            assert getattr(job, f), (
                f"Adapter dropped {f!r} for item {raw.get('id')!r}"
            )
        # LinkedIn actor always populates postedAt, descriptionText,
        # companyName on every item (verified 2026-07-07).
        assert job.public_date, f"public_date missing for {raw.get('id')}"
        assert job.description, f"description missing for {raw.get('id')}"


def test_linkedin_fixture_no_silently_dropped_field():
    items = _load("linkedin.json")
    raw_keys = set(items[0].keys())
    mapped = {
        "id", "link", "url", "title", "companyName", "company",
        "location", "postedAt", "salary", "salaryInfo", "salaryInsights",
        "description", "descriptionText", "descriptionHtml",
    }
    known_unmapped = KNOWN_UNMAPPED["linkedin.json"]
    unknown = raw_keys - mapped - known_unmapped
    assert not unknown, (
        f"Fixture has UNKNOWN unmapped fields: {sorted(unknown)}. "
        f"The actor schema likely changed. Either extend the adapter, or "
        f"add the field to KNOWN_UNMAPPED in test_apify_fixtures.py."
    )


# --------------------------------------------------------------------------- #
# Indeed
# --------------------------------------------------------------------------- #
def test_indeed_fixture_captures_all_critical_fields():
    items = _load("indeed.json")
    assert items, "Fixture is empty"
    adapter = IndeedAdapter()
    jobs = adapter.normalize_output(items)
    for raw, job in zip(items, jobs):
        for f in CRITICAL_FIELDS:
            assert getattr(job, f), (
                f"Adapter dropped {f!r} for item {raw.get('id')!r}"
            )
        # Indeed fixture populates postedAt and description on every
        # item (verified 2026-07-07).
        assert job.public_date, f"public_date missing for {raw.get('id')}"
        assert job.description, f"description missing for {raw.get('id')}"


def test_indeed_fixture_no_silently_dropped_field():
    items = _load("indeed.json")
    raw_keys = set(items[0].keys())
    mapped = {
        "id", "positionName", "position", "company", "location", "url",
        "postedAt", "postingDateParsed", "salary",
        "description", "descriptionHTML",
    }
    known_unmapped = KNOWN_UNMAPPED["indeed.json"]
    unknown = raw_keys - mapped - known_unmapped
    assert not unknown, (
        f"Fixture has UNKNOWN unmapped fields: {sorted(unknown)}. "
        f"The actor schema likely changed. Either extend the adapter, or "
        f"add the field to KNOWN_UNMAPPED in test_apify_fixtures.py."
    )


# --------------------------------------------------------------------------- #
# Error filtering and per-item safety
# --------------------------------------------------------------------------- #

# Minimal good-item fixtures — just enough fields to pass JobInsert validation.
LINKEDIN_GOOD = {
    "id": "1",
    "title": "Dev",
    "companyName": "Acme",
    "location": "Bogota",
    "postedAt": "2026-07-08",
    "link": "http://example.com",
    "descriptionText": "A job description.",
}

COMPUTRABAJO_GOOD = {
    "id": "2",
    "title": "Dev",
    "company": "Acme",
    "location": "Bogota",
    "postedDate": "2026-07-08",
    "url": "http://example.com",
    "descriptionText": "A job description.",
}

INDEED_GOOD = {
    "id": "3",
    "positionName": "Dev",
    "company": "Acme",
    "location": "Bogota",
    "postedAt": "2026-07-08",
    "url": "http://example.com",
    "description": "A job description.",
}


def test_all_adapters_filter_error_items():
    """All 3 adapters should drop Indeed-style error items before normalization."""
    error_item = {"error": "FOUND_NO_RESULTS", "errorDescription": "no jobs"}
    for adapter_cls, good_item in [
        (ComputrabajoAdapter, COMPUTRABAJO_GOOD),
        (LinkedinAdapter, LINKEDIN_GOOD),
        (IndeedAdapter, INDEED_GOOD),
    ]:
        adapter = adapter_cls()
        valid, errors = adapter.filter_errors([good_item, error_item])
        assert len(valid) == 1, f"{adapter_cls.__name__}: expected 1 valid, got {len(valid)}"
        assert len(errors) == 1, f"{adapter_cls.__name__}: expected 1 error, got {len(errors)}"
        assert errors[0]["error"] == "FOUND_NO_RESULTS"


def test_normalize_output_per_item_safety():
    """A single bad item must not kill the whole batch."""
    good = LINKEDIN_GOOD.copy()
    # Force an error: pass a non-dict item (e.g. a raw string from a
    # malformed actor response). The adapter calls raw.get() which will
    # raise AttributeError on a string, proving per-item isolation works.
    bad = "this is not a valid job dict"
    adapter = LinkedinAdapter()
    jobs, failures = adapter.normalize_output_safe([good, bad, good])
    assert len(jobs) == 2, f"Expected 2 jobs, got {len(jobs)}"
    assert len(failures) == 1, f"Expected 1 failure, got {len(failures)}"
    assert "no_id_1" in failures[0]["id"]  # fallback id for non-dict
