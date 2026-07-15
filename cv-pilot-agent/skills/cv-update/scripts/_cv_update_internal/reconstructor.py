"""Full-profile reconstructor for cv-update: writes perfil.json (Pydantic-validated).

Design rationale (ATS fidelity): A real ATS (Workday/Greenhouse/Lever) only
knows the CV submitted for each application.  Mixing fields from a previous
CV inflates HR evaluations.  Each perfil.json is an independent snapshot of
the LAST processed CV — never an accumulation.

This module REPLACES the old markdown-based reconstructor.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from _lib.schemas.perfil_schema import PerfilSchema


# Canonical CV fields the parser extracts.  Order drives JSON output.
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

# Placeholder for canonical fields not found in the new CV.
_PLACEHOLDER = "_(no detectado)_"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def reconstruct_profile(new_fields: dict[str, str], source_pdf: str) -> dict[str, Any]:
    """Rebuild perfil.json from scratch using ONLY *new_fields*.

    This is the public API called by ``cli.py``.  It NEVER reads or
    preserves anything from the old perfil.json.

    Parameters
    ----------
    new_fields : dict
        Output of ``parser.parse_text()["fields"]``.
    source_pdf : str
        Path to the source PDF.

    Returns
    -------
    dict with keys:
        perfil_path        — path to the .json file (set by caller)
        perfil_content     — dict validated by Pydantic (PerfilSchema)
        campos_extraidos   — list of canonical field names that had a value
        campos_no_encontrados — list of canonical field names missing/empty
        fuente             — source PDF path
        timestamp          — ISO-8601 generation time
    """
    timestamp = _now_iso()

    extracted: list[str] = []
    missing: list[str] = []
    for key in CANONICAL_FIELDS:
        if new_fields.get(key, "").strip():
            extracted.append(key)
        else:
            missing.append(key)

    # Build the PerfilSchema fields dict.
    schema_fields: dict[str, Any] = {}
    for key in CANONICAL_FIELDS:
        val = new_fields.get(key, "").strip()
        schema_fields[key] = val if val else None

    # Non-canonical fields go to extras.
    extras = {
        k: v for k, v in new_fields.items()
        if k not in CANONICAL_FIELDS and isinstance(v, str) and v.strip()
    }
    if extras:
        schema_fields["extras"] = extras

    schema_fields["fuente"] = source_pdf
    schema_fields["generated_at"] = timestamp

    perfil = PerfilSchema(**schema_fields)

    return {
        "perfil_content": perfil.model_dump(),
        "campos_extraidos": extracted,
        "campos_no_encontrados": missing,
        "fuente": source_pdf,
        "timestamp": timestamp,
    }
