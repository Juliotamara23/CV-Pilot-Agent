"""Safe DB seeding helper for agent-mode tests using frozen Apify fixtures.

This module provides utilities to seed a temporary SQLite database with
real Apify fixture data (from test/fixtures/apify/) without making any
live Apify calls. Uses the same platform adapters as the production flow.

Usage in tests:
    from test_apify_seed_db import seed_db_from_fixtures

    def test_something(tmp_db):
        seed_db_from_fixtures(tmp_db, platform="linkedin", count=5)
        # ... run analysis, verify results
"""

import json
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import Literal

# Import platform adapters
_AGENT_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "cv-pilot-agent"
_SCRIPTS_DIR = _AGENT_ROOT / "skills" / "apify" / "scripts"
for _p in (_AGENT_ROOT, _SCRIPTS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from platforms.linkedin import LinkedinAdapter  # noqa: E402
from platforms.computrabajo import ComputrabajoAdapter  # noqa: E402
from platforms.indeed import IndeedAdapter  # noqa: E402

# Import production DB API for validated analysis insertion
from _lib.db import insert_analysis as _db_insert_analysis  # noqa: E402
from _lib.models import AnalysisInsert, validate_verdict  # noqa: E402
from _lib.errors import ValidationError  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures" / "apify"

_ADAPTER_MAP = {
    "linkedin": (LinkedinAdapter, "linkedin.json"),
    "computrabajo": (ComputrabajoAdapter, "computrabajo.json"),
    "indeed": (IndeedAdapter, "indeed.json"),
}


def _get_schema_sql() -> str:
    """Get canonical schema from production."""
    schema_file = _AGENT_ROOT / "_lib" / "schema.sql"
    return schema_file.read_text(encoding="utf-8")


def init_temp_db(db_path: Path) -> None:
    """Initialize a temporary database with the production schema."""
    conn = sqlite3.connect(db_path)
    conn.executescript(_get_schema_sql())
    conn.commit()
    conn.close()


def seed_db_from_fixtures(
    db_path: Path,
    platform: Literal["linkedin", "computrabajo", "indeed"],
    count: int = 10,
    *,
    clear_first: bool = True,
) -> list[dict]:
    """Seed a temporary DB with jobs from a frozen Apify fixture.

    Args:
        db_path: Path to the SQLite database file (will be initialized if needed).
        platform: Which platform fixture to use ("linkedin", "computrabajo", "indeed").
        count: Maximum number of jobs to insert (default: 10).
        clear_first: Whether to delete existing jobs before inserting (default: True).

    Returns:
        List of inserted job dicts with keys: job_hash, position, company, etc.

    Raises:
        FileNotFoundError: If the fixture file doesn't exist.
        ValueError: If platform is unknown.
    """
    if platform not in _ADAPTER_MAP:
        raise ValueError(f"Unknown platform: {platform}. Must be one of {list(_ADAPTER_MAP.keys())}")

    adapter_cls, fixture_name = _ADAPTER_MAP[platform]
    fixture_path = FIXTURES_DIR / fixture_name

    if not fixture_path.is_file():
        raise FileNotFoundError(
            f"Fixture not found: {fixture_path}. "
            f"Run the actor to refresh — see test_apify_fixtures.py docstring."
        )

    # Load fixture data
    raw_items = json.loads(fixture_path.read_text(encoding="utf-8"))
    if not raw_items:
        return []

    # Normalize using the platform adapter
    adapter = adapter_cls()
    valid_items, _ = adapter.filter_errors(raw_items)
    jobs = adapter.normalize_output(valid_items[:count])

    # Initialize DB if needed
    if not db_path.exists():
        init_temp_db(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        if clear_first:
            cursor.execute("DELETE FROM jobs")
            cursor.execute("DELETE FROM analyses")

        inserted = []
        for job in jobs:
            # Compute job_hash (same as production: SHA256 of company+position+location)
            import hashlib
            raw = (job.company + job.position + (job.location or "")).encode()
            job_hash = hashlib.sha256(raw).hexdigest()

            cursor.execute(
                """INSERT OR IGNORE INTO jobs
                   (job_hash, external_id, public_date, url, company,
                    position, location, salary, description, source, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new')""",
                (
                    job_hash,
                    job.external_id,
                    job.public_date,
                    job.url,
                    job.company,
                    job.position,
                    job.location,
                    job.salary,
                    job.description,
                    job.source,
                ),
            )
            if cursor.rowcount > 0:
                inserted.append({
                    "job_hash": job_hash,
                    "external_id": job.external_id,
                    "public_date": job.public_date,
                    "url": job.url,
                    "company": job.company,
                    "position": job.position,
                    "location": job.location,
                    "salary": job.salary,
                    "description": job.description,
                    "source": job.source,
                })

        conn.commit()
        return inserted
    finally:
        conn.close()


def seed_db_from_all_fixtures(
    db_path: Path,
    count_per_platform: int = 5,
) -> dict[str, list[dict]]:
    """Seed DB with jobs from all platform fixtures.

    Returns a dict mapping platform name to list of inserted jobs.
    """
    results: dict[str, list[dict]] = {}
    platforms: list[Literal["linkedin", "computrabajo", "indeed"]] = ["linkedin", "computrabajo", "indeed"]
    for i, platform in enumerate(platforms):
        results[platform] = seed_db_from_fixtures(
            db_path, platform, count=count_per_platform, clear_first=(i == 0)
        )
    return results


def get_pending_jobs(db_path: Path) -> list[dict]:
    """Get all jobs with status='new' from the DB."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT job_hash, external_id, public_date, url, company, position, "
            "location, salary, description, source, status "
            "FROM jobs WHERE status = 'new'"
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def insert_analysis(
    db_path: Path,
    job_hash: str,
    percentage: str,
    comparativa: str,
    observaciones: str,
    verdict: str,
    tldr: str,
    contact_method: str | None = None,
) -> str:
    """Insert an analysis record using the domain DB API with verdict validation.

    Uses _lib.db.insert_analysis which validates verdict against allowed values
    (No apto, Apto con reservas, Apto) and raises ValidationError for invalid verdicts.

    Returns analysis_id.
    """
    # Validate verdict at domain boundary — never persist invalid/undecided verdicts
    try:
        validate_verdict(verdict)
    except ValueError as exc:
        raise ValidationError(str(exc), code="VALIDATION_ERROR") from exc

    # Use the production DB API with the explicit db_path override
    import os
    os.environ["CV_PILOT_DB"] = str(db_path)

    analysis = AnalysisInsert(
        job_hash=job_hash,
        percentage=float(percentage.rstrip("%")),
        comparativa=comparativa,
        observaciones=observaciones,
        verdict=verdict,
        tldr=tldr,
        contact_method=contact_method,
    )
    result = _db_insert_analysis(analysis)
    return result["analysis_id"]


if __name__ == "__main__":
    # Demo: seed a temp DB and show results
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        print(f"Seeding {db_path}...")
        jobs = seed_db_from_fixtures(db_path, "linkedin", count=3)
        print(f"Inserted {len(jobs)} jobs from LinkedIn fixture")
        for job in jobs:
            print(f"  {job['position']} @ {job['company']} ({job['source']})")

        jobs = seed_db_from_fixtures(db_path, "computrabajo", count=3, clear_first=False)
        print(f"Inserted {len(jobs)} jobs from Computrabajo fixture")
        for job in jobs:
            print(f"  {job['position']} @ {job['company']} ({job['source']})")

        pending = get_pending_jobs(db_path)
        print(f"\nTotal pending jobs: {len(pending)}")