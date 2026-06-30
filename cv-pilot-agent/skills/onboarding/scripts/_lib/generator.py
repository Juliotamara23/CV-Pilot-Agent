"""File generation for CV-Pilot onboarding.

Renders the three onboarding templates (perfil, correos, preferencias) and
writes them to the output directory.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from _lib.renderer import email_block, render_template

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"


def _backup(out_dir: Path, name: str, no_backup: bool) -> None:
    if no_backup:
        return
    target = out_dir / name
    if target.is_file():
        shutil.copy2(target, out_dir / f"{name}.bak")


def generate_files(fields: dict, out_dir: Path, no_backup: bool) -> dict:
    """Render the three templates and write them under ``out_dir``.

    Creates ``out_dir`` if missing. Backs up existing files to ``*.bak`` first
    unless ``no_backup`` is set.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    render_fields = dict(fields)
    render_fields.setdefault("notas", "")
    render_fields.setdefault("notas_adicionales", "")
    render_fields["email_bloque"] = email_block(fields)

    outputs = {}
    for template_name, out_name in (
        ("perfil.template.md", "perfil.md"),
        ("correos.template.md", "correos.md"),
        ("preferencias.template.md", "preferencias.md"),
    ):
        _backup(out_dir, out_name, no_backup)
        rendered = render_template(TEMPLATES_DIR / template_name, render_fields)
        (out_dir / out_name).write_text(rendered, encoding="utf-8")
        outputs[out_name.replace(".md", "_path")] = str(out_dir / out_name)
    return outputs
