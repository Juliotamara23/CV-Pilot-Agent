"""Typer CLI for CV-Pilot analysis report formatting.

Replaces the prompt-based Formatos SKILL with a deterministic script that reads
job + analysis + profile data (read-only) and emits a markdown or JSON report
to stdout. Invoked by the orchestration layer (AGENTS.md) via subprocess::

    python skills/formatos/scripts/format_report.py --job <hash>
    python skills/formatos/scripts/format_report.py --job <hash> --format json

A single command. Prints the report to stdout on success and exits 0; emits an
error envelope to stderr and exits non-zero on failure.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional

# Force UTF-8 on std streams so emoji/unicode never depend on host codepage.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# Make `cv-pilot-agent/` importable when the script is run by path.
_AGENT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_AGENT_ROOT))

import typer  # noqa: E402

from _lib import db  # noqa: E402
from _lib.errors import CV_PilotError  # noqa: E402

app = typer.Typer(
    name="format_report",
    help="CV-Pilot analysis report formatter (markdown | json).",
    add_completion=False,
    no_args_is_help=True,
)

# Profile keys reused for the optional links footer.
_LINKS = ("cv_url", "linkedin", "github")
_LINK_TEXT = {"cv_url": "CV", "linkedin": "LinkedIn", "github": "GitHub"}


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


def _load_profile() -> dict:
    path = _AGENT_ROOT / "data" / "perfil.md"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    mapping = {
        "Nombre completo": "name",
        "LinkedIn": "linkedin",
        "GitHub": "github",
        "Link al CV": "cv_url",
    }
    profile = {key: None for key in mapping.values()}
    pattern = re.compile(r"^-\s*\*\*(.+?)\s*:\*\*\s*(.+?)\s*$", re.MULTILINE)
    for label, value in pattern.findall(text):
        key = mapping.get(label)
        if key:
            profile[key] = value.strip()
    return profile


# --------------------------------------------------------------------------- #
# Builders
# --------------------------------------------------------------------------- #
def _format_date(job: dict, analysis: dict) -> str:
    # public_date (job publication) takes precedence; created_at (analysis) is
    # the fallback when the publication date is missing — per spec.
    pd = job.get("public_date")
    if pd:
        return pd
    return analysis.get("created_at") or ""


def _format_comparativa(comparativa: Optional[str]) -> str:
    if not comparativa:
        return "_(Sin comparativa)_"
    lines = []
    for raw in comparativa.splitlines():
        entry = raw.strip()
        if not entry:
            continue
        # Preserve the documented "- Requisito | Análisis: evaluación" format;
        # ensure every non-empty line is a bullet (pipes are literal separators
        # in bullet lists — no escaping needed, list does not break on pipes).
        if not entry.startswith("- "):
            entry = f"- {entry}"
        lines.append(entry)
    return "\n".join(lines) if lines else "_(Sin comparativa)_"


def _links_html(profile: dict) -> str:
    parts = [
        f'<a href="{profile[key]}">{_LINK_TEXT[key]}</a>'
        for key in _LINKS if profile.get(key)
    ]
    return "".join(f"{p}<br>" for p in parts)


def _build_markdown(job: dict, analysis: dict, profile: dict) -> str:
    url = job.get("url")
    fuente = f'<a href="{url}">{url}</a>' if url else "Origen: Texto manual"
    company = job.get("company") or ""
    position = job.get("position") or ""
    location = job.get("location") or ""
    percentage = analysis.get("percentage")
    pct = f"{float(percentage):.0f}" if isinstance(percentage, (int, float)) else "0"
    observaciones = (analysis.get("observaciones") or "").strip()
    sections = [
        f"🆔 ID: {analysis.get('analysis_id') or ''}",
        f"📅 Fecha: {_format_date(job, analysis)}",
        f"🔗 Fuente: {fuente}",
        f"💻 Empresa: {company} | Cargo: {position}",
        f"🚩 Localidad: {location}",
        f"🎯 Porcentaje: {pct}%",
        "",
        "⚖️ Comparativa Técnica:",
        _format_comparativa(analysis.get("comparativa")),
        "",
        "💡 Observaciones y Riesgos:",
        observaciones if observaciones else "_(Sin observaciones)_",
        "",
        f"✅ Veredicto: {analysis.get('verdict') or ''}",
        f"🌟 TL;DR: {(analysis.get('tldr') or '').strip()}",
    ]
    body = "\n".join(sections)
    links = _links_html(profile)
    if links:
        body += "\n\n" + links
    return body


def _build_json(job: dict, analysis: dict, profile: dict) -> dict:
    return {
        "analysis_id": analysis.get("analysis_id"),
        "job_hash": analysis.get("job_hash"),
        "percentage": analysis.get("percentage"),
        "comparativa": analysis.get("comparativa"),
        "observaciones": analysis.get("observaciones"),
        "verdict": analysis.get("verdict"),
        "tldr": analysis.get("tldr"),
        "contact_method": analysis.get("contact_method"),
        "created_at": analysis.get("created_at"),
        "company": job.get("company"),
        "position": job.get("position"),
        "location": job.get("location"),
        "url": job.get("url"),
        "source": job.get("source"),
        "profile_links": {
            "cv_url": profile.get("cv_url"),
            "linkedin": profile.get("linkedin"),
            "github": profile.get("github"),
        },
    }


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
        profile = _load_profile()
    except CV_PilotError as exc:
        _emit_error(exc.message or exc.__class__.__name__, exc.code)
        raise typer.Exit(code=1)

    if fmt == "json":
        typer.echo(json.dumps(
            {"ok": True, "report": _build_json(job_row, analysis, profile), "format": "json"},
            ensure_ascii=False, indent=2,
        ))
    else:
        typer.echo(_build_markdown(job_row, analysis, profile))


if __name__ == "__main__":
    app()