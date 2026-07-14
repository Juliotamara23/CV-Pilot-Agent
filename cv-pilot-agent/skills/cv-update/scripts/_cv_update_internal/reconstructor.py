"""Full-profile reconstructor for cv-update: rewrites perfil.md from scratch.

Design rationale (ATS fidelity): A real ATS (Workday/Greenhouse/Lever) only
knows the CV submitted for each application.  Mixing fields from a previous
CV inflates HR evaluations.  Each perfil.md is an independent snapshot of
the LAST processed CV — never an accumulation.

This module REPLACES the old merger.py which preserved stale fields.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


# Canonical CV fields the parser extracts.  Order drives markdown output.
CANONICAL_FIELDS = [
    "nombre",
    "resumen",
    "linkedin",
    "github",
    "telefono",
    "correo",
    "cv_url",
    "experiencia",
    "educacion",
    "skills",
]

# Fields that appear in the Identity/Contact bullet section.
_IDENTITY_FIELDS = {"nombre": "Nombre", "resumen": "Resumen profesional"}
_CONTACT_FIELDS = {
    "linkedin": "LinkedIn",
    "github": "GitHub",
    "telefono": "WhatsApp / Teléfono",
    "correo": "Correo electrónico",
    "cv_url": "Link al CV",
}

# Placeholder for canonical fields not found in the new CV.
_PLACEHOLDER = "_(no detectado)_"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def serialize_markdown(fields: dict[str, str], source_pdf: str, timestamp: str) -> str:
    """Build the full perfil.md markdown from *fields* (no merging, no old data).

    Parameters
    ----------
    fields : dict
        Parsed CV fields.  Missing canonical keys get a ``_(no detectado)_`` placeholder.
    source_pdf : str
        Path to the source PDF (recorded in frontmatter).
    timestamp : str
        ISO-8601 generation timestamp (recorded in frontmatter).

    Returns
    -------
    str
        Complete markdown content for ``perfil.md``.
    """
    parts: list[str] = []

    # --- Frontmatter ---
    parts.append("---")
    parts.append(f"source: {source_pdf}")
    parts.append(f"generated: {timestamp}")
    parts.append("---")
    parts.append("")

    # --- Header ---
    parts.append("# Perfil")
    parts.append("")

    # --- Identidad ---
    parts.append("## Identidad")
    for key, label in _IDENTITY_FIELDS.items():
        val = fields.get(key, "").strip() or _PLACEHOLDER
        parts.append(f"- **{label}:** {val}")
    parts.append("")

    # --- Contacto ---
    parts.append("## Contacto")
    for key, label in _CONTACT_FIELDS.items():
        val = fields.get(key, "").strip()
        if val:
            parts.append(f"- **{label}:** {val}")
    parts.append("")

    # --- Experiencia ---
    parts.append("## Experiencia")
    parts.append("")
    parts.append(fields.get("experiencia", "").strip() or _PLACEHOLDER)
    parts.append("")

    # --- Educación ---
    parts.append("## Educación")
    parts.append("")
    parts.append(fields.get("educacion", "").strip() or _PLACEHOLDER)
    parts.append("")

    # --- Skills ---
    parts.append("## Skills Técnicos")
    parts.append("")
    parts.append(fields.get("skills", "").strip() or _PLACEHOLDER)
    parts.append("")

    # --- Extras: any non-canonical key the parser returned ---
    extras = {k: v for k, v in fields.items() if k not in CANONICAL_FIELDS and v.strip()}
    if extras:
        parts.append("## Extras")
        parts.append("")
        for key, val in extras.items():
            parts.append(f"### {key.replace('_', ' ').title()}")
            parts.append("")
            parts.append(val.strip())
            parts.append("")

    return "\n".join(parts).rstrip() + "\n"


def reconstruct_profile(new_fields: dict[str, str], source_pdf: str) -> dict[str, Any]:
    """Rebuild perfil.md from scratch using ONLY *new_fields*.

    This is the public API called by ``cli.py``.  It NEVER reads or
    preserves anything from the old perfil.md.

    Parameters
    ----------
    new_fields : dict
        Output of ``parser.parse_text()["fields"]``.
    source_pdf : str
        Path to the source PDF.

    Returns
    -------
    dict with keys:
        perfil_content   — full markdown string for perfil.md
        campos_extraidos — list of canonical field names that had a value
        campos_no_encontrados — list of canonical field names missing/empty
        fuente           — source PDF path
        timestamp        — ISO-8601 generation time
    """
    timestamp = _now_iso()

    extracted: list[str] = []
    missing: list[str] = []
    for key in CANONICAL_FIELDS:
        if new_fields.get(key, "").strip():
            extracted.append(key)
        else:
            missing.append(key)

    content = serialize_markdown(new_fields, source_pdf, timestamp)

    return {
        "perfil_content": content,
        "campos_extraidos": extracted,
        "campos_no_encontrados": missing,
        "fuente": source_pdf,
        "timestamp": timestamp,
    }
