"""Typer CLI for CV-Pilot database operations.

Invoked by the orchestration layer (AGENTS.md) via subprocess::

    python cv-pilot-agent/skills/database/scripts/query.py --help
    python cv-pilot-agent/skills/database/scripts/query.py job insert --company "Acme" ...

Three sub-apps (``job``, ``analysis``, ``status``) expose CRUD commands. Every
command prints a JSON envelope to stdout on success::

    {"ok": true, ...}

On error, an envelope goes to stderr and the process exits non-zero::

    {"ok": false, "error": "...", "code": "JOB_NOT_FOUND|...|DATABASE_ERROR"}

Field names follow the SQL schema verbatim; no translation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

from _lib.shared.cli_utils import setup_syspath, setup_utf8

# Force UTF-8 on the std streams so JSON output (ensure_ascii=False) and error
# envelopes never depend on the host console codepage (e.g. Windows cp1252).
setup_utf8()

# Make `cv-pilot-agent/` importable when the script is run by path.
setup_syspath(levels_up=3)

import typer  # noqa: E402

from _lib import db  # noqa: E402
from _lib.errors import CV_PilotError  # noqa: E402
from _lib.models import VALID_STATUSES, AnalysisInsert, JobInsert  # noqa: E402

app = typer.Typer(
    name="query",
    help="CV-Pilot database CLI: jobs, analyses, and status management.",
    add_completion=False,
    no_args_is_help=True,
)
job_app = typer.Typer(
    name="job", help="Insert, list, get, and delete jobs.", no_args_is_help=True
)
analysis_app = typer.Typer(
    name="analysis", help="Insert and fetch job analyses.", no_args_is_help=True
)
status_app = typer.Typer(
    name="status", help="Update a job's status.", no_args_is_help=True
)
app.add_typer(job_app, name="job")
app.add_typer(analysis_app, name="analysis")
app.add_typer(status_app, name="status")


def _emit(payload: dict) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False))


def _emit_error(message: str, code: str) -> None:
    typer.echo(
        json.dumps({"ok": False, "error": message, "code": code}, ensure_ascii=False),
        err=True,
    )


def _run(action) -> None:
    """Execute a zero-arg callable, mapping CV_PilotError to the stderr envelope."""
    try:
        action()
    except CV_PilotError as exc:
        _emit_error(exc.message or exc.__class__.__name__, exc.code)
        raise typer.Exit(code=1)


# --------------------------------------------------------------------------- #
# job
# --------------------------------------------------------------------------- #
@job_app.command("insert")
def job_insert(
    company: str = typer.Option(..., help="Company name (normalized: strip + title)."),
    position: str = typer.Option(..., help="Position title."),
    location: str = typer.Option(..., help="Location string."),
    external_id: Optional[str] = typer.Option(None, help="External/house job id."),
    public_date: Optional[str] = typer.Option(None, help="ISO-8601 publication date."),
    url: Optional[str] = typer.Option(None, help="Source URL."),
    salary: Optional[str] = typer.Option(None, help="Salary string (preserve format)."),
    description: Optional[str] = typer.Option(None, help="Raw job description."),
    source: str = typer.Option("manual", help="Origin (manual/apify-*/...)."),
) -> None:
    """Insert one job with SHA256 dedup + refresh semantics."""
    job = JobInsert(
        company=company,
        position=position,
        location=location,
        external_id=external_id,
        public_date=public_date,
        url=url,
        salary=salary,
        description=description,
        source=source,
    )
    _run(lambda: _emit(db.insert_job(job)))


@job_app.command("insert-batch")
def job_insert_batch(
    file: Path = typer.Option(..., help="JSON file holding an array of job objects."),
) -> None:
    """Insert many jobs from a JSON array file."""
    try:
        raw = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _emit_error(f"Cannot read batch file '{file}': {exc}", "VALIDATION_ERROR")
        raise typer.Exit(code=1)
    if not isinstance(raw, list):
        _emit_error("Batch file must contain a JSON array.", "VALIDATION_ERROR")
        raise typer.Exit(code=1)

    try:
        jobs = [JobInsert(**item) for item in raw]
    except (TypeError, ValueError) as exc:
        _emit_error(f"Invalid job shape in batch file: {exc}", "VALIDATION_ERROR")
        raise typer.Exit(code=1)

    _run(lambda: _emit(db.insert_jobs_batch(jobs)))


@job_app.command("list")
def job_list(
    status: Optional[str] = typer.Option(
        None, help=f"Filter by status ({', '.join(VALID_STATUSES)})."
    ),
    limit: int = typer.Option(10, min=1, help="Maximum rows to return."),
) -> None:
    """List jobs, optionally filtered by status."""
    _run(lambda: _emit(db.list_jobs(status=status, limit=limit)))


@job_app.command("get")
def job_get(
    hash: str = typer.Option(..., help="job_hash (SHA256) of the job."),
) -> None:
    """Return a single job by hash."""
    _run(lambda: _emit(db.get_job(hash)))


@job_app.command("delete")
def job_delete(
    status: Optional[str] = typer.Option(
        None, help=f"Delete all jobs with this status ({', '.join(VALID_STATUSES)})."
    ),
    hash: Optional[str] = typer.Option(None, help="Delete the single job with this hash."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without mutating."),
) -> None:
    """Delete jobs by status or by hash. ``--dry-run`` previews the count."""
    if status is None and hash is None:
        _emit_error("job delete requires --status or --hash.", "VALIDATION_ERROR")
        raise typer.Exit(code=1)
    if status is not None and hash is not None:
        _emit_error("Use --status OR --hash, not both.", "VALIDATION_ERROR")
        raise typer.Exit(code=1)
    if status is not None and status not in VALID_STATUSES:
        _emit_error(
            f"Invalid status '{status}'. Must be one of: {', '.join(VALID_STATUSES)}",
            "INVALID_STATUS",
        )
        raise typer.Exit(code=1)
    _run(lambda: _emit(db.delete_jobs(job_hash=hash, status=status, dry_run=dry_run)))


# --------------------------------------------------------------------------- #
# analysis
# --------------------------------------------------------------------------- #
@analysis_app.command("insert")
def analysis_insert(
    job_hash: str = typer.Option(..., help="job_hash the analysis refers to."),
    percentage: float = typer.Option(..., help="Match percentage (0-100)."),
    comparativa: str = typer.Option(..., help="Comparativa field (verbatim SQL column)."),
    observaciones: str = typer.Option(..., help="Observaciones field."),
    verdict: str = typer.Option(..., help="Verdict field."),
    tldr: str = typer.Option(..., help="Short summary (tldr) field."),
    contact_method: Optional[str] = typer.Option(
        None, help="Contact method (email|portal)."
    ),
) -> None:
    """Insert one analysis and mark its job ``analyzed``."""
    analysis = AnalysisInsert(
        job_hash=job_hash,
        percentage=percentage,
        comparativa=comparativa,
        observaciones=observaciones,
        verdict=verdict,
        tldr=tldr,
        contact_method=contact_method,
    )
    _run(lambda: _emit(db.insert_analysis(analysis)))


@analysis_app.command("get")
def analysis_get(
    job_hash: str = typer.Option(..., help="job_hash to fetch the analysis for."),
) -> None:
    """Return the analysis for a job hash."""
    _run(lambda: _emit(db.get_analysis(job_hash)))


# --------------------------------------------------------------------------- #
# status
# --------------------------------------------------------------------------- #
@status_app.command("set")
def status_set(
    hash: str = typer.Option(..., help="job_hash to update."),
    status: str = typer.Option(
        ..., help=f"New status ({', '.join(VALID_STATUSES)})."
    ),
) -> None:
    """Update a job's status to a valid enum value."""
    _run(lambda: _emit(db.update_status(hash, status)))


if __name__ == "__main__":
    app()