"""File generation for CV-Pilot onboarding.

Generates perfil.json, preferencias.json, and correos.md (stays MD).
Uses Pydantic schemas for validation.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from _onboarding_internal.renderer import email_block, render_template

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"


def _backup(out_dir: Path, name: str, no_backup: bool) -> None:
    if no_backup:
        return
    target = out_dir / name
    if target.is_file():
        shutil.copy2(target, out_dir / f"{name}.bak")


def _build_perfil_json(fields: dict) -> dict:
    """Build the perfil JSON dict from parsed fields."""
    from _lib.schemas.perfil_schema import PerfilSchema

    schema_fields = {}
    canonical = [
        "nombre", "correo", "telefono", "linkedin", "github", "cv_url",
        "resumen", "experiencia", "educacion", "skills",
    ]
    for key in canonical:
        val = fields.get(key, "")
        schema_fields[key] = val.strip() if isinstance(val, str) and val.strip() else None

    # Non-canonical fields -> extras
    extras = {}
    for k, v in fields.items():
        if k not in canonical and k != "email_examples" and isinstance(v, str) and v.strip():
            extras[k] = v.strip()
    if extras:
        schema_fields["extras"] = extras

    return PerfilSchema(**schema_fields).model_dump(exclude_none=True)


def _build_preferencias_json(fields: dict) -> dict:
    """Build the preferencias JSON dict from parsed fields."""
    from _lib.schemas.preferencias_schema import PreferenciasSchema

    # Normalize mimetismo
    mim = fields.get("mimetismo", "")
    if isinstance(mim, str):
        mim_val = mim.strip().lower() in ("sí", "si", "yes", "true", "1")
    else:
        mim_val = bool(mim) if mim is not None else None

    # Normalize booleans
    def _to_bool(val):
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.strip().lower() in ("sí", "si", "yes", "true", "1")
        return None

    schema_fields = {
        "mimetismo": mim_val,
        "sector": fields.get("sector", "").strip() or None,
        "tono": fields.get("tono", "").strip() or None,
        "idioma": fields.get("idioma", "").strip() or None,
        "gmail_drafts": _to_bool(fields.get("gmail_drafts", "")),
        "outlook_drafts": _to_bool(fields.get("outlook_drafts", "")),
        "pdf_soporte": _to_bool(fields.get("pdf_soporte", True)),
        "notas_adicionales": fields.get("notas_adicionales", "").strip() or None,
    }

    return PreferenciasSchema(**schema_fields).model_dump(exclude_none=True)


def generate_files(fields: dict, out_dir: Path, no_backup: bool) -> dict:
    """Render the output files and write them under ``out_dir``.

    Creates ``out_dir`` if missing. Backs up existing files to ``*.bak`` first
    unless ``no_backup`` is set.

    Outputs:
    - perfil.json (Pydantic-validated)
    - preferencias.json (Pydantic-validated)
    - correos.md (rendered from template, stays MD)
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    render_fields = dict(fields)
    render_fields.setdefault("notas", "")
    render_fields.setdefault("notas_adicionales", "")
    render_fields["email_bloque"] = email_block(fields)

    outputs = {}

    # --- perfil.json ---
    _backup(out_dir, "perfil.json", no_backup)
    perfil_data = _build_perfil_json(fields)
    (out_dir / "perfil.json").write_text(
        json.dumps(perfil_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    outputs["perfil_path"] = str(out_dir / "perfil.json")

    # --- preferencias.json ---
    _backup(out_dir, "preferencias.json", no_backup)
    prefs_data = _build_preferencias_json(fields)
    (out_dir / "preferencias.json").write_text(
        json.dumps(prefs_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    outputs["preferencias_path"] = str(out_dir / "preferencias.json")

    # --- correos.md (stays MD) ---
    _backup(out_dir, "correos.md", no_backup)
    rendered = render_template(TEMPLATES_DIR / "correos.template.md", render_fields)
    (out_dir / "correos.md").write_text(rendered, encoding="utf-8")
    outputs["correos_path"] = str(out_dir / "correos.md")

    return outputs
