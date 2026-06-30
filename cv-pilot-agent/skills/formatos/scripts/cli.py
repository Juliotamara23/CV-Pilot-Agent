"""Typer CLI for CV-Pilot analysis report formatting.

Replaces the prompt-based Formatos SKILL with a deterministic script that reads
job + analysis + profile data (read-only) and emits a markdown or JSON report
to stdout. Invoked by the orchestration layer (AGENTS.md) via subprocess::

    python skills/formatos/scripts/cli.py --job <hash>
    python skills/formatos/scripts/cli.py --job <hash> --format json

A single command. Prints the report to stdout on success and exits 0; emits an
error envelope to stderr and exits non-zero on failure.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

from _lib.shared.cli_utils import setup_syspath, setup_utf8
from _lib.shared.profile_loader import load_profile

# Force UTF-8 on std streams so emoji/unicode never depend on host codepage.
setup_utf8()

# Make `cv-pilot-agent/` importable when the script is run by path.
_AGENT_ROOT = setup_syspath(levels_up=3)

import typer  # noqa: E402

from _lib import db  # noqa: E402
from _lib.errors import CV_PilotError  # noqa: E402

from _lib.builders import build_json, build_markdown  # noqa: E402

app = typer.Typer(
    name="format_report",
    help="CV-Pilot analysis report formatter (markdown | json).",
    add_completion=False,
    no_args_is_help=True,
)


def _emit_error(message: str, code: str) -> None:
    typer.echo(
        json.dumps({"ok": False, "error": message, "code": code}, ensure_ascii=False),
        err=True,
    )


# --------------------------------------------------------------------------- #
# Loaders (read-only DB + data/perfil.md)
# --------------------------------------------------------------------------- #
def _load_job(job_hash: str) -> dict:
    return db.get_job(job_hash)["job"]


def _load_analysis(job_hash: str) -> dict:
    return db.get_analysis(job_hash)["analysis"]


# --------------------------------------------------------------------------- #
# Command
# --------------------------------------------------------------------------- #
@app.command()
def main(
    job: str = typer.Option(..., help="job_hash (SHA256) of the analyzed job."),
    fmt: str = typer.Option("markdown", "--format", help="Output format: markdown | json."),
) -> None:
    """Format and print the analysis report for a job."""
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


if __name__ == "__main__":
    app()
