"""Migration script: convert perfil.md and preferencias.md to JSON.

Creates backups in data/.migration_backup/ before writing JSON files.
Does NOT delete the original .md files — that is done manually after verification.

Usage:
    .venv/Scripts/python.exe scripts/migrate_perfil_to_json.py
    .venv/Scripts/python.exe scripts/migrate_perfil_to_json.py --data-dir path/to/data
    .venv/Scripts/python.exe scripts/migrate_perfil_to_json.py --dry-run
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make cv-pilot-agent/ importable.
_AGENT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_AGENT_ROOT))

from _lib.schemas.perfil_schema import PerfilSchema  # noqa: E402
from _lib.schemas.preferencias_schema import PreferenciasSchema  # noqa: E402


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_perfil_md(text: str) -> dict:
    """Extract fields from the current perfil.md format."""
    fields: dict = {}

    # Source and generated from frontmatter.
    src = re.search(r"^source:\s*(.+)$", text, re.MULTILINE)
    if src:
        fields["fuente"] = src.group(1).strip()

    gen = re.search(r"^generated:\s*(.+)$", text, re.MULTILINE)
    if gen:
        fields["generated_at"] = gen.group(1).strip()

    # Labeled fields: - **Label:** value
    label_map = {
        "Nombre completo": "nombre",
        "Resumen profesional": "resumen",
        "LinkedIn": "linkedin",
        "GitHub": "github",
        "WhatsApp / Teléfono": "telefono",
        "Correo electrónico": "correo",
        "Link al CV": "cv_url",
    }
    for label, key in label_map.items():
        m = re.search(
            rf"^-\s*\*\*{re.escape(label)}:?\*\*\s*(.+)$",
            text, re.MULTILINE,
        )
        if m:
            val = m.group(1).strip()
            if val and val != "_(no detectado)_":
                fields[key] = val

    # Sections: capture body between ## headers.
    section_map = {
        "Experiencia": "experiencia",
        "Educación": "educacion",
        "Skills Técnicos": "skills",
    }
    for section_name, key in section_map.items():
        pattern = rf"^##\s*{re.escape(section_name)}\s*\n(.*?)(?=^##\s|\Z)"
        m = re.search(pattern, text, re.MULTILINE | re.DOTALL)
        if m:
            body = m.group(1).strip()
            if body and body != "_(no detectado)_":
                fields[key] = body

    return fields


def _parse_preferencias_md(text: str) -> dict:
    """Extract fields from the current preferencias.md format."""
    fields: dict = {}

    # Mimetismo: - **Activado:** sí/no
    m = re.search(r"Activado:\*\*\s*(.+)$", text, re.MULTILINE)
    if m:
        val = m.group(1).strip().lower()
        fields["mimetismo"] = val in ("sí", "si", "yes", "true", "1")

    # Sector
    m = re.search(r"^## Sector preferido\s*\n-\s*(.+)$", text, re.MULTILINE)
    if m:
        fields["sector"] = m.group(1).strip()

    # Tono
    m = re.search(r"^## Tono\s*\n-\s*(.+)$", text, re.MULTILINE)
    if m:
        fields["tono"] = m.group(1).strip()

    # Idioma
    m = re.search(r"^## Idioma.*\n-\s*(.+)$", text, re.MULTILINE)
    if m:
        fields["idioma"] = m.group(1).strip()

    # Gmail drafts
    m = re.search(r"gmail_drafts:\s*(.+)$", text, re.MULTILINE)
    if m:
        fields["gmail_drafts"] = m.group(1).strip().lower() in ("yes", "true", "sí", "si", "1")

    # Outlook drafts
    m = re.search(r"outlook_drafts:\s*(.+)$", text, re.MULTILINE)
    if m:
        fields["outlook_drafts"] = m.group(1).strip().lower() in ("yes", "true", "sí", "si", "1")

    # PDF soporte
    m = re.search(r"pdf_soporte:\s*(.+)$", text, re.MULTILINE)
    if m:
        fields["pdf_soporte"] = m.group(1).strip().lower() in ("yes", "true", "sí", "si", "1")

    # Notas adicionales
    m = re.search(r"^## Notas adicionales\s*\n((?:-\s*.+\n?)+)", text, re.MULTILINE)
    if m:
        notes = [line.lstrip("- ").strip() for line in m.group(1).strip().splitlines() if line.strip()]
        fields["notas_adicionales"] = "\n".join(notes)

    return fields


def migrate(data_dir: Path, dry_run: bool = False) -> dict:
    """Run the migration. Returns a report dict."""
    report = {"perfil": False, "preferencias": False, "backups": []}

    # Ensure backup dir exists.
    backup_dir = data_dir / ".migration_backup"
    if not dry_run:
        backup_dir.mkdir(parents=True, exist_ok=True)

    # --- perfil.md -> perfil.json ---
    perfil_md = data_dir / "perfil.md"
    perfil_json = data_dir / "perfil.json"

    if perfil_md.is_file():
        text = perfil_md.read_text(encoding="utf-8")
        fields = _parse_perfil_md(text)
        fields.setdefault("generated_at", _now_iso())

        perfil = PerfilSchema(**fields)
        json_content = perfil.model_dump_json(indent=2, exclude_none=True)

        if dry_run:
            print(f"[DRY RUN] Would write {perfil_json}")
            print(json_content)
        else:
            # Backup
            shutil.copy2(perfil_md, backup_dir / "perfil.md")
            report["backups"].append(str(backup_dir / "perfil.md"))

            # Write JSON
            perfil_json.write_text(json_content, encoding="utf-8")
            report["perfil"] = True
            print(f"[OK] Written: {perfil_json}")
    else:
        print(f"⚠ Not found: {perfil_md}")

    # --- preferencias.md -> preferencias.json ---
    prefs_md = data_dir / "preferencias.md"
    prefs_json = data_dir / "preferencias.json"

    if prefs_md.is_file():
        text = prefs_md.read_text(encoding="utf-8")
        fields = _parse_preferencias_md(text)

        prefs = PreferenciasSchema(**fields)
        json_content = prefs.model_dump_json(indent=2, exclude_none=True)

        if dry_run:
            print(f"[DRY RUN] Would write {prefs_json}")
            print(json_content)
        else:
            # Backup
            shutil.copy2(prefs_md, backup_dir / "preferencias.md")
            report["backups"].append(str(backup_dir / "preferencias.md"))

            # Write JSON
            prefs_json.write_text(json_content, encoding="utf-8")
            report["preferencias"] = True
            print(f"[OK] Written: {prefs_json}")
    else:
        print(f"⚠ Not found: {prefs_md}")

    return report


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Migrate perfil.md/preferencias.md to JSON.")
    parser.add_argument("--data-dir", type=Path, default=_AGENT_ROOT / "data",
                        help="Directory containing the .md files (default: data/)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be done without writing files.")
    args = parser.parse_args()

    report = migrate(args.data_dir, dry_run=args.dry_run)
    print(f"\nMigration report: {json.dumps(report, indent=2)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
