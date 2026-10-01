"""Report builders for CV-Pilot analysis formatting.

Pure functions that build markdown and JSON report representations from
job, analysis, and profile data.
"""

from __future__ import annotations

from typing import Optional  # noqa: F401  (dict used for annotations)

# Single source of truth for field emoji decoration. The emote belongs to the
# FIELD, not to the report: every field selection carries its own emote.
# `build_markdown` and the `list` command (cli.py) both consume this map.
FIELD_EMOTES: dict = {
    "analysis_id": "🆔",
    "created_at": "📅",
    "url": "🔗",
    "company": "💻",
    "position": "💼",
    "location": "🚩",
    "percentage": "🎯",
    "verdict": "✅",
    "tldr": "🌟",
    "comparativa": "⚖️",
    "observaciones": "💡",
}

# Display labels for scalar listing fields (used by the `list` command).
LIST_FIELD_LABELS: dict = {
    "analysis_id": "ID",
    "created_at": "Fecha",
    "url": "Fuente",
    "company": "Empresa",
    "position": "Cargo",
    "location": "Localidad",
    "percentage": "Porcentaje",
    "verdict": "Veredicto",
    "tldr": "TL;DR",
}

# Scalar fields accepted by `--fields` (block fields excluded on purpose).
LIST_SCALAR_FIELDS = tuple(LIST_FIELD_LABELS)


def format_percentage(percentage) -> str:
    """Return the percentage as a rounded int string like '82', or '0'."""
    try:
        raw = str(percentage).replace("%", "").strip()
        return f"{float(raw):.0f}"
    except (ValueError, TypeError):
        return "0"


def format_source(job: dict) -> str:
    """Return the job URL, or the manual-origin fallback text."""
    url = job.get("url")
    return url if url else "Texto manual"


def build_list_lines(job: dict, analysis: dict, fields) -> list:
    """Build decorated listing lines ``{emote} {Etiqueta}: {valor}``.

    One line per requested field, in the caller-supplied order. Only scalar
    fields are supported (callers must validate against LIST_SCALAR_FIELDS).
    """
    lines = []
    for field in fields:
        emote = FIELD_EMOTES[field]
        label = LIST_FIELD_LABELS[field]
        if field == "analysis_id":
            value = analysis.get("analysis_id") or ""
        elif field == "created_at":
            value = format_date(job, analysis)
        elif field == "url":
            value = format_source(job)
        elif field in ("company", "position", "location"):
            value = job.get(field) or ""
        elif field == "percentage":
            value = f"{format_percentage(analysis.get('percentage'))}%"
        else:  # verdict, tldr
            value = (analysis.get(field) or "").strip()
        lines.append(f"{emote} {label}: {value}")
    return lines


def format_date(job: dict, analysis: dict) -> str:
    """Return the display date: public_date takes precedence; created_at is fallback."""
    pd = job.get("public_date")
    if pd:
        return pd
    return analysis.get("created_at") or ""


def format_comparativa(comparativa: Optional[str]) -> str:
    """Normalize comparativa text to a bullet list."""
    if not comparativa:
        return "_(Sin comparativa)_"
    lines = []
    for raw in comparativa.splitlines():
        entry = raw.strip()
        if not entry:
            continue
        if not entry.startswith("- "):
            entry = f"- {entry}"
        lines.append(entry)
    return "\n".join(lines) if lines else "_(Sin comparativa)_"


def build_markdown(job: dict, analysis: dict, profile: dict) -> str:
    """Build the full markdown report."""
    url = job.get("url")
    fuente = f'<a href="{url}">{url}</a>' if url else "Origen: Texto manual"
    company = job.get("company") or ""
    position = job.get("position") or ""
    location = job.get("location") or ""
    percentage = analysis.get("percentage")
    try:
        raw = str(percentage).replace("%", "").strip()
        pct = f"{float(raw):.0f}"
    except (ValueError, TypeError):
        pct = "0"
    observaciones = (analysis.get("observaciones") or "").strip()
    sections = [
        f"🆔 ID: {analysis.get('analysis_id') or ''}",
        f"📅 Fecha: {format_date(job, analysis)}",
        f"🔗 Fuente: {fuente}",
        f"💻 Empresa: {company} | Cargo: {position}",
        f"🚩 Localidad: {location}",
        f"🎯 Porcentaje: {pct}%",
        "",
        "⚖️ Comparativa Técnica:",
        format_comparativa(analysis.get("comparativa")),
        "",
        "💡 Observaciones y Riesgos:",
        observaciones if observaciones else "_(Sin observaciones)_",
        "",
        f"✅ Veredicto: {analysis.get('verdict') or ''}",
        f"🌟 TL;DR: {(analysis.get('tldr') or '').strip()}",
    ]
    body = "\n".join(sections)
    return body


def build_json(job: dict, analysis: dict, profile: dict) -> dict:
    """Build the JSON report dict."""
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
