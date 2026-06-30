"""Report builders for CV-Pilot analysis formatting.

Pure functions that build markdown and JSON report representations from
job, analysis, and profile data.
"""

from __future__ import annotations

from typing import Optional

# Profile keys reused for the optional links footer.
_LINKS = ("cv_url", "linkedin", "github")
_LINK_TEXT = {"cv_url": "CV", "linkedin": "LinkedIn", "github": "GitHub"}


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


def links_html(profile: dict) -> str:
    """Build the HTML links footer from profile data."""
    parts = [
        f'<a href="{profile[key]}">{_LINK_TEXT[key]}</a>'
        for key in _LINKS if profile.get(key)
    ]
    return "".join(f"{p}<br>" for p in parts)


def build_markdown(job: dict, analysis: dict, profile: dict) -> str:
    """Build the full markdown report."""
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
    links = links_html(profile)
    if links:
        body += "\n\n" + links
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
