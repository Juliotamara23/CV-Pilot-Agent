"""Typer CLI for CV-Pilot analysis report formatting.

Replaces the prompt-based Formatos SKILL with a deterministic script that reads
job + analysis + profile data (read-only) and emits a markdown or JSON report
to stdout. Invoked by the orchest layer (AGENTS.md) via subprocess::

    python skills/formatos/scripts/cli.py main --job <hash>
    python skills/formatos/scripts/cli.py main --job <hash> --format json
    python skills/formatos/scripts/cli.py all
    python skills/formatos/scripts/cli.py all --format json [--status analyzed] [--limit 50]
    python skills/formatos/scripts/cli.py list [--status S] [--limit N] [--fields f1,f2,...]

Commands:
    main  — single-job report (requires --job).
    all   — every analyzed job in one document (default: markdown).
    list  — decorated, field-selected one-line-per-field listing per job.

Prints the report to stdout on success and exits 0; emits an error envelope to
stderr and exits non-zero on failure.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

# Force UTF-8 on std streams so emoji/unicode never depend on host codepage.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

# Make `cv-pilot-agent/` importable when the script is run by path.
_AGENT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_AGENT_ROOT))

import typer  # noqa: E402

from _lib import db  # noqa: E402
from _lib.errors import CV_PilotError  # noqa: E402
from _lib.shared.profile_loader import load_profile  # noqa: E402

from _formatos_internal.builders import (  # noqa: E402
    LIST_SCALAR_FIELDS,
    build_json,
    build_list_lines,
    build_markdown,
)

app = typer.Typer(
    name="format_report",
    help="CV-Pilot analysis report formatter (markdown | json).",
    add_completion=False,
    no_args_is_help=True,
)

_NO_ANALYSIS_MSG = "No hay análisis pendientes"


def _emit_error(message: str, code: str) -> None:
    typer.echo(
        json.dumps({"ok": False, "error": message, "code": code}, ensure_ascii=False),
        err=True,
    )


# --------------------------------------------------------------------------- #
# Loaders (read-only DB + data/perfil.json)
# --------------------------------------------------------------------------- #
def _load_job(job_hash: str) -> dict:
    return db.get_job(job_hash)["job"]


def _load_analysis(job_hash: str) -> dict:
    return db.get_analysis(job_hash)["analysis"]


def _load_all_reports(status: str, limit: int) -> list[dict]:
    """Return ``[{job, analysis}, ...]`` for every job with an analysis.

    Fetches jobs filtered by *status* (default ``analyzed``) and pairs each
    with its latest analysis.  Jobs without an analysis are silently skipped.
    """
    jobs_result = db.list_jobs(status=status, limit=limit)
    reports: list[dict] = []
    for job_row in jobs_result.get("jobs", []):
        try:
            analysis = db.get_analysis(job_row["job_hash"])["analysis"]
        except CV_PilotError:
            continue
        reports.append({"job": job_row, "analysis": analysis})
    return reports


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
@app.command()
def main(
    job: str = typer.Option(..., help="job_hash (SHA256) of the analyzed job."),
    fmt: str = typer.Option("markdown", "--format", help="Output format: markdown | json."),
) -> None:
    """Format and print the analysis report for a single job."""
    fmt = (fmt or "").strip().lower()
    if fmt not in ("markdown", "json"):
        _emit_error(
            f"Invalid format '{fmt}'. Valid values: markdown, json",
            code="INVALID_FORMAT",
        )
        raise typer.Exit(code=1)
    try:
        job_row = _load_job(job)
        analysis = _load_analysis(job)
        profile = load_profile(_AGENT_ROOT)
    except CV_PilotError as exc:
        _emit_error(exc.message or exc.__class__.__name__, exc.code)
        raise typer.Exit(code=1)

    if fmt == "json":
        typer.echo(json.dumps(
            {"ok": True, "report": build_json(job_row, analysis, profile), "format": "json"},
            ensure_ascii=False, indent=2,
        ))
    else:
        typer.echo(build_markdown(job_row, analysis, profile))


@app.command("all")
def all_reports(
    fmt: str = typer.Option("markdown", "--format", help="Output format: markdown | json."),
    status: str = typer.Option("analyzed", "--status", help="Filter jobs by status."),
    limit: int = typer.Option(50, "--limit", help="Max jobs to fetch."),
) -> None:
    """Generate one report containing every analyzed job.

    Concatenates individual markdown reports with ``---`` separators, or returns
    a JSON list of ``{job, report}`` objects.  When no analyses exist, prints a
    clear message and exits 0 (no failure).
    """
    fmt = (fmt or "").strip().lower()
    if fmt not in ("markdown", "json"):
        _emit_error(
            f"Invalid format '{fmt}'. Valid values: markdown, json",
            code="INVALID_FORMAT",
        )
        raise typer.Exit(code=1)

    try:
        profile = load_profile(_AGENT_ROOT)
        reports = _load_all_reports(status=status, limit=limit)
    except CV_PilotError as exc:
        _emit_error(exc.message or exc.__class__.__name__, exc.code)
        raise typer.Exit(code=1)

    if not reports:
        if fmt == "json":
            typer.echo(json.dumps(
                {"ok": True, "count": 0, "reports": [], "format": "json"},
                ensure_ascii=False, indent=2,
            ))
        else:
            typer.echo(_NO_ANALYSIS_MSG)
        raise typer.Exit(code=0)

    if fmt == "json":
        entries = []
        for pair in reports:
            entries.append({
                "job_hash": pair["job"]["job_hash"],
                "report": build_json(pair["job"], pair["analysis"], profile),
            })
        typer.echo(json.dumps(
            {"ok": True, "count": len(entries), "reports": entries, "format": "json"},
            ensure_ascii=False, indent=2,
        ))
    else:
        parts: list[str] = []
        for i, pair in enumerate(reports):
            if i > 0:
                parts.append("\n---\n")
            parts.append(build_markdown(pair["job"], pair["analysis"], profile))
        typer.echo("".join(parts))


@app.command("list")
def list_reports(
    status: str = typer.Option("analyzed", "--status", help="Filter jobs by status."),
    limit: int = typer.Option(50, "--limit", help="Max jobs to fetch."),
    fields: str = typer.Option(
        "position,url,tldr,percentage",
        "--fields",
        help=(
            "Comma-separated scalar fields, in the order wanted. Valid values: "
            + ", ".join(LIST_SCALAR_FIELDS)
            + ". Default: position,url,tldr,percentage. Block fields "
            "(comparativa, observaciones) are not valid here."
        ),
    ),
) -> None:
    """Print a decorated per-job listing of the selected scalar fields.

    Each job is rendered as one ``{emote} {Etiqueta}: {valor}`` line per
    requested field, in the requested order (the emote belongs to the field).
    Jobs are separated by a single blank line. Uses the same DB access path
    and error envelope as the other commands.
    """
    selected = [f.strip() for f in (fields or "").split(",") if f.strip()]
    invalid = [f for f in selected if f not in LIST_SCALAR_FIELDS]
    if not selected or invalid:
        _emit_error(
            "Invalid --fields value(s): "
            + ", ".join(invalid or selected)
            + ". Valid scalar fields: "
            + ", ".join(LIST_SCALAR_FIELDS)
            + ". Block fields (comparativa, observaciones) are not valid here.",
            code="INVALID_FIELDS",
        )
        raise typer.Exit(code=1)
    # Deduplicate while preserving the requested order.
    seen: set[str] = set()
    ordered_fields = [f for f in selected if not (f in seen or seen.add(f))]

    try:
        reports = _load_all_reports(status=status, limit=limit)
    except CV_PilotError as exc:
        _emit_error(exc.message or exc.__class__.__name__, exc.code)
        raise typer.Exit(code=1)

    if not reports:
        typer.echo(_NO_ANALYSIS_MSG)
        raise typer.Exit(code=0)

    blocks: list[str] = []
    for pair in reports:
        blocks.append("\n".join(build_list_lines(pair["job"], pair["analysis"], ordered_fields)))
    typer.echo("\n\n".join(blocks))


if __name__ == "__main__":
    app()
