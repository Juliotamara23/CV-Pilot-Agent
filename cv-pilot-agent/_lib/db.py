"""SQLite data-access layer for CV-Pilot.

All public functions return plain ``dict`` envelopes ready for JSON serialisation
to stdout. Errors raise one of the :mod:`_lib.errors` subclasses; the CLI maps
those to the stderr envelope.

Connection settings (PRAGMA, applied idempotently on every connect):
    * ``row_factory = sqlite3.Row`` — dict-like rows
    * ``journal_mode = WAL`` — concurrent reader/writer (ignored on :memory:)
    * ``foreign_keys = ON`` — enforce analyses.job_hash FK

Database path resolution:
    * ``$CV_PILOT_DB`` env var overrides the default path (used in tests).
    * default: ``<cv-pilot-agent>/db/cv-pilot.db`` (mirrors ``scripts/init.py:5``).

The schema itself lives in ``scripts/init.py`` (protected by code_guard.md); this
module never runs DDL. Callers (including tests) must initialise the schema first.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Optional

from .errors import DatabaseError, JobNotFoundError, ValidationError
from .models import VALID_STATUSES, AnalysisInsert, JobInsert

# Module-level default DB path: <this file>/../db/cv-pilot.db
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "db" / "cv-pilot.db"


def _resolve_db_path() -> str:
    override = os.environ.get("CV_PILOT_DB")
    if override:
        return override
    return str(DEFAULT_DB_PATH)


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Idempotent schema migrations — adds missing columns to existing DBs.

    New users get the full schema from ``scripts/init.py``. Existing DBs
    opened by this module get missing columns added automatically, so
    ``init.py`` never needs to be modified for additive changes.
    """
    try:
        conn.execute("ALTER TABLE analyses ADD COLUMN contact_method TEXT")
    except sqlite3.OperationalError:
        # Column already exists — safe to ignore.
        pass


def get_connection() -> sqlite3.Connection:
    """Open a connection configured for the contract (WAL, FK=ON, Row).

    Applies idempotent schema migrations on every connect so existing
    databases stay compatible without touching ``scripts/init.py``.
    """
    path = _resolve_db_path()
    try:
        conn = sqlite3.connect(path)
    except sqlite3.Error as exc:
        raise DatabaseError(f"Cannot open database at {path}: {exc}") from exc

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # WAL is a no-op on :memory: databases (returns "memory"); ignore the echo.
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.OperationalError:
        # In-memory / read-only filesystems reject WAL — fall back silently.
        pass
    _ensure_schema(conn)
    return conn


def _normalize(company: str, position: str, location: str) -> tuple[str, str, str]:
    return (company.strip().title(), position.strip(), location.strip())


def compute_hash(company: str, position: str, location: str) -> str:
    """SHA256 of normalized ``company|position|location``."""
    nc, np_, nl = _normalize(company, position, location)
    payload = f"{nc}|{np_}|{nl}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _row_to_job(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "job_hash": row["job_hash"],
        "external_id": row["external_id"],
        "public_date": row["public_date"],
        "url": row["url"],
        "company": row["company"],
        "position": row["position"],
        "location": row["location"],
        "salary": row["salary"],
        "description": row["description"],
        "status": row["status"],
        "source": row["source"],
    }


def insert_job(job: JobInsert) -> dict[str, Any]:
    """Insert a single job with dedup/refresh semantics.

    Returns ``{ok, hash, is_new, is_duplicate, refreshed?}``:

    * hash absent -> INSERT, ``is_new=True``.
    * hash present AND incoming ``public_date`` strictly newer (lex ISO-8601)
      -> DELETE analyses for the hash, UPDATE job (status reset to 'new',
      public_date/url/salary/description refreshed), ``refreshed=True``.
    * else -> no mutation, ``is_duplicate=True``.
    """
    job_hash = compute_hash(job.company, job.position, job.location)
    conn = get_connection()
    try:
        with conn:
            existing = conn.execute(
                "SELECT public_date, url, salary, description, status, source "
                "FROM jobs WHERE job_hash = ?",
                (job_hash,),
            ).fetchone()

            if existing is None:
                conn.execute(
                    "INSERT OR IGNORE INTO jobs "
                    "(job_hash, external_id, public_date, url, company, position, "
                    "location, salary, description, status, source) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?)",
                    (
                        job_hash,
                        job.external_id,
                        job.public_date,
                        job.url,
                        job.company.strip(),
                        job.position.strip(),
                        job.location.strip(),
                        job.salary,
                        job.description,
                        job.source,
                    ),
                )
                return {
                    "ok": True,
                    "hash": job_hash,
                    "is_new": True,
                    "is_duplicate": False,
                    "refreshed": False,
                }

            newer = (
                bool(job.public_date)
                and (existing["public_date"] is None or job.public_date > existing["public_date"])
            )

            if newer:
                conn.execute(
                    "DELETE FROM analyses WHERE job_hash = ?", (job_hash,)
                )
                conn.execute(
                    "UPDATE jobs SET status = 'new', public_date = ?, url = ?, "
                    "salary = ?, description = ? WHERE job_hash = ?",
                    (
                        job.public_date,
                        job.url,
                        job.salary,
                        job.description,
                        job_hash,
                    ),
                )
                return {
                    "ok": True,
                    "hash": job_hash,
                    "is_new": False,
                    "is_duplicate": True,
                    "refreshed": True,
                }

            return {
                "ok": True,
                "hash": job_hash,
                "is_new": False,
                "is_duplicate": True,
                "refreshed": False,
            }
    except sqlite3.Error as exc:
        raise DatabaseError(f"insert_job failed: {exc}") from exc
    finally:
        conn.close()


def insert_jobs_batch(jobs: list[JobInsert]) -> dict[str, Any]:
    """Process a batch, aggregating counts across all per-job outcomes."""
    inserted = 0
    duplicates = 0
    refreshed = 0
    results: list[dict[str, Any]] = []

    for job in jobs:
        outcome = insert_job(job)
        if outcome["is_new"]:
            inserted += 1
        else:
            duplicates += 1
        if outcome.get("refreshed"):
            refreshed += 1
        results.append({
            "hash": outcome["hash"],
            "is_new": outcome["is_new"],
            "is_duplicate": outcome["is_duplicate"],
            "refreshed": outcome.get("refreshed", False),
        })

    return {
        "ok": True,
        "inserted": inserted,
        "duplicates": duplicates,
        "refreshed": refreshed,
        "results": results,
    }


def list_jobs(status: Optional[str] = None, limit: int = 10) -> dict[str, Any]:
    """List jobs, optionally filtered by status, with a row cap."""
    conn = get_connection()
    try:
        if status is not None:
            if status not in VALID_STATUSES:
                raise ValidationError(
                    f"Invalid status '{status}'. Must be one of: "
                    f"{', '.join(VALID_STATUSES)}",
                    code="INVALID_STATUS",
                )
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status = ? LIMIT ?", (status, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM jobs LIMIT ?", (limit,)
            ).fetchall()
        return {"ok": True, "count": len(rows), "jobs": [_row_to_job(r) for r in rows]}
    except sqlite3.Error as exc:
        raise DatabaseError(f"list_jobs failed: {exc}") from exc
    finally:
        conn.close()


def get_job(job_hash: str) -> dict[str, Any]:
    """Return a single job row or raise ``JobNotFoundError``."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM jobs WHERE job_hash = ?", (job_hash,)
        ).fetchone()
        if row is None:
            raise JobNotFoundError(f"Job not found: {job_hash}")
        return {"ok": True, "job": _row_to_job(row)}
    finally:
        conn.close()


def delete_jobs(
    job_hash: Optional[str] = None,
    status: Optional[str] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Delete jobs by hash or by status.

    ``dry_run=True`` returns the would-be-deleted rows without mutating. The
    real delete removes matching analyses first (no CASCADE in the schema) then
    the jobs, in a single transaction.

    Empty result set raises ``JobNotFoundError`` with ``code='NO_JOBS_FOUND'``.
    """
    if job_hash is None and status is None:
        raise ValidationError("delete_jobs requires --hash or --status")

    if status is not None and status not in VALID_STATUSES:
        raise ValidationError(
            f"Invalid status '{status}'. Must be one of: "
            f"{', '.join(VALID_STATUSES)}",
            code="INVALID_STATUS",
        )

    conn = get_connection()
    try:
        if job_hash is not None:
            where_sql = "WHERE job_hash = ?"
            params: tuple[Any, ...] = (job_hash,)
        else:
            where_sql = "WHERE status = ?"
            params = (status,)

        rows = conn.execute(
            f"SELECT * FROM jobs {where_sql}", params
        ).fetchall()
        matched = [_row_to_job(r) for r in rows]

        if not matched:
            raise JobNotFoundError(
                f"No jobs found with status '{status}'" if status is not None
                else f"Job not found: {job_hash}",
                code="NO_JOBS_FOUND",
            )

        if dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "would_delete": len(matched),
                "jobs": matched,
            }

        with conn:
            conn.execute(
                f"DELETE FROM analyses WHERE job_hash IN "
                f"(SELECT job_hash FROM jobs {where_sql})",
                params,
            )
            conn.execute(f"DELETE FROM jobs {where_sql}", params)
        return {"ok": True, "deleted": len(matched)}
    except sqlite3.Error as exc:
        raise DatabaseError(f"delete_jobs failed: {exc}") from exc
    finally:
        conn.close()


def insert_analysis(analysis: AnalysisInsert) -> dict[str, Any]:
    """Insert an analysis row and mark the job ``analyzed`` in one transaction.

    Raises ``JobNotFoundError`` (code ``JOB_NOT_FOUND``) when the FK target is
    missing — mirrors the spec's "Analysis insert — job not found" scenario.
    """
    conn = get_connection()
    try:
        with conn:
            job_row = conn.execute(
                "SELECT 1 FROM jobs WHERE job_hash = ?", (analysis.job_hash,)
            ).fetchone()
            if job_row is None:
                raise JobNotFoundError(f"Job not found: {analysis.job_hash}")

            analysis_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO analyses "
                "(analysis_id, job_hash, percentage, comparativa, observaciones, "
                "verdict, tldr, contact_method) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    analysis_id,
                    analysis.job_hash,
                    analysis.percentage,
                    analysis.comparativa,
                    analysis.observaciones,
                    analysis.verdict,
                    analysis.tldr,
                    analysis.contact_method,
                ),
            )
            conn.execute(
                "UPDATE jobs SET status = 'analyzed' WHERE job_hash = ?",
                (analysis.job_hash,),
            )
        return {"ok": True, "analysis_id": analysis_id}
    except sqlite3.IntegrityError as exc:
        raise JobNotFoundError(
            f"Job not found: {analysis.job_hash}", code="JOB_NOT_FOUND"
        ) from exc
    except sqlite3.Error as exc:
        raise DatabaseError(f"insert_analysis failed: {exc}") from exc
    finally:
        conn.close()


def get_analysis(job_hash: str) -> dict[str, Any]:
    """Return the analysis for a job hash or raise ``JobNotFoundError``."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM analyses WHERE job_hash = ?", (job_hash,)
        ).fetchone()
        if row is None:
            raise JobNotFoundError(
                f"Analysis not found for job: {job_hash}",
                code="ANALYSIS_NOT_FOUND",
            )
        return {
            "ok": True,
            "analysis": {
                "analysis_id": row["analysis_id"],
                "job_hash": row["job_hash"],
                "percentage": row["percentage"],
                "comparativa": row["comparativa"],
                "observaciones": row["observaciones"],
                "verdict": row["verdict"],
                "tldr": row["tldr"],
                "contact_method": row["contact_method"],
                "created_at": row["created_at"],
            },
        }
    finally:
        conn.close()


def update_status(job_hash: str, status: str) -> dict[str, Any]:
    """Update a job's status. Validates the enum and job existence."""
    if status not in VALID_STATUSES:
        raise ValidationError(
            f"Invalid status '{status}'. Must be one of: "
            f"{', '.join(VALID_STATUSES)}",
            code="INVALID_STATUS",
        )

    conn = get_connection()
    try:
        with conn:
            row = conn.execute(
                "SELECT status FROM jobs WHERE job_hash = ?", (job_hash,)
            ).fetchone()
            if row is None:
                raise JobNotFoundError(f"Job not found: {job_hash}")
            old_status = row["status"]
            conn.execute(
                "UPDATE jobs SET status = ? WHERE job_hash = ?", (status, job_hash)
            )
        return {"ok": True, "old_status": old_status, "new_status": status}
    except sqlite3.Error as exc:
        raise DatabaseError(f"update_status failed: {exc}") from exc
    finally:
        conn.close()