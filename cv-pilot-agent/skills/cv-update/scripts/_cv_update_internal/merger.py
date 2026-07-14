"""Merge logic for cv-update: combines existing perfil.md with new CV fields.

Preserves custom fields (like pdf_soporte) that are not in the canonical
CV field list. Only overwrites CV fields when new data is available.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

# Canonical fields extracted from CV by parser.py.
# These are the ONLY fields that get overwritten on update.
CV_FIELDS = frozenset({
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
})

# Section headers in perfil.md that map 1:1 to CV fields.
# Order matters for serialization.
_SECTION_ORDER = [
    ("nombre", "Nombre completo"),
    ("resumen", "Resumen profesional"),
    ("linkedin", "LinkedIn"),
    ("github", "GitHub"),
    ("telefono", "WhatsApp / Teléfono"),
    ("correo", "Correo electrónico"),
    ("cv_url", "Link al CV"),
]


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Parse YAML frontmatter (simple key: value) and return (meta, body)."""
    meta: dict[str, str] = {}
    if not text.startswith("---"):
        return meta, text
    end = text.find("---", 3)
    if end == -1:
        return meta, text
    block = text[3:end].strip()
    for line in block.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip()
    body = text[end + 3:].strip()
    return meta, body


def _serialize_frontmatter(meta: dict[str, str]) -> str:
    """Serialize meta dict back to YAML frontmatter block."""
    if not meta:
        return ""
    lines = ["---"]
    for k, v in meta.items():
        lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines)


def _extract_bullet_field(body: str, label: str) -> str:
    """Extract value from a line like '- **Label:** value'."""
    pattern = re.compile(
        r"^\s*-\s*\*\*" + re.escape(label) + r":\*\*\s*(.+)$",
        re.MULTILINE | re.IGNORECASE,
    )
    m = pattern.search(body)
    return m.group(1).strip() if m else ""


def _replace_bullet_field(body: str, label: str, new_value: str) -> str:
    """Replace value in a line like '- **Label:** value'."""
    pattern = re.compile(
        r"^(\s*-\s*\*\*" + re.escape(label) + r":\*\*\s*).+$",
        re.MULTILINE | re.IGNORECASE,
    )
    return pattern.sub(r"\g<1>" + new_value, body, count=1)


def _extract_section_block(body: str, header: str) -> str:
    """Extract the body of a ## section (until next ## or end)."""
    pattern = re.compile(
        r"^##\s+" + re.escape(header) + r"\s*\n(.*?)(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(body)
    return m.group(1).strip() if m else ""


def _replace_section_block(body: str, header: str, new_content: str) -> str:
    """Replace the body of a ## section."""
    pattern = re.compile(
        r"(^##\s+" + re.escape(header) + r"\s*\n).*?(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    replacement = r"\g<1>" + new_content + "\n\n"
    result = pattern.sub(replacement, body, count=1)
    return result


def _has_section(body: str, header: str) -> bool:
    """Check if a ## section exists in body."""
    pattern = re.compile(
        r"^##\s+" + re.escape(header) + r"\s*$",
        re.MULTILINE,
    )
    return bool(pattern.search(body))


def _parse_perfil_to_dict(text: str) -> dict:
    """Parse perfil.md content into a flat dict of fields.

    Returns dict with keys matching CV_FIELDS for standard fields,
    plus any custom fields found.
    """
    meta, body = _parse_frontmatter(text)
    fields: dict[str, str] = {}

    # Bullet fields (identity + contact)
    for field_key, label in _SECTION_ORDER:
        val = _extract_bullet_field(body, label)
        if val:
            fields[field_key] = val

    # Section blocks
    for section_key in ("experiencia", "educacion", "skills"):
        val = _extract_section_block(body, section_key.capitalize())
        if section_key == "educacion":
            val = _extract_section_block(body, "Educación") or val
        if section_key == "skills":
            val = _extract_section_block(body, "Skills Técnicos") or val
        if val:
            fields[section_key] = val

    # Preserve extra sections as custom fields
    known_sections = {"Identidad", "Contacto", "Experiencia", "Educación",
                      "Educacion", "Skills Técnicos", "Skills", "Notas"}
    section_pattern = re.compile(r"^##\s+(.+)$", re.MULTILINE)
    for m in section_pattern.finditer(body):
        sec_name = m.group(1).strip()
        if sec_name not in known_sections:
            sec_content = _extract_section_block(body, sec_name)
            if sec_content:
                fields[f"_section:{sec_name}"] = sec_content

    return fields


def _serialize_perfil(fields: dict, meta: Optional[dict] = None) -> str:
    """Serialize fields dict back to perfil.md format.

    Preserves custom sections (prefixed with _section:) and extra bullet fields.
    """
    parts: list[str] = []

    # Frontmatter
    if meta:
        parts.append(_serialize_frontmatter(meta))
        parts.append("")

    parts.append("# Perfil")
    parts.append("")

    # Identity section
    parts.append("## Identidad")
    nombre = fields.get("nombre", "")
    resumen = fields.get("resumen", "")
    parts.append(f"- **Nombre completo:** {nombre}")
    parts.append(f"- **Resumen profesional:** {resumen}")
    parts.append("")

    # Contact section
    parts.append("## Contacto")
    for field_key, label in _SECTION_ORDER[2:]:  # skip nombre, resumen
        val = fields.get(field_key, "")
        if val:
            parts.append(f"- **{label}:** {val}")
    parts.append("")

    # Experiencia
    exp = fields.get("experiencia", "")
    parts.append("## Experiencia")
    parts.append("")
    parts.append(exp)
    parts.append("")

    # Educación
    edu = fields.get("educacion", "")
    parts.append("## Educación")
    parts.append("")
    parts.append(edu)
    parts.append("")

    # Skills
    skills = fields.get("skills", "")
    parts.append("## Skills Técnicos")
    parts.append("")
    parts.append(skills)
    parts.append("")

    # Custom sections (those prefixed with _section:)
    for key, val in fields.items():
        if key.startswith("_section:"):
            sec_name = key.replace("_section:", "")
            parts.append(f"## {sec_name}")
            parts.append("")
            parts.append(val)
            parts.append("")

    # Notas section (if notas field exists)
    notas = fields.get("notas", "")
    if notas:
        parts.append("## Notas")
        parts.append("")
        parts.append(notas)
        parts.append("")

    return "\n".join(parts).rstrip() + "\n"


def merge_profile(old_perfil_text: str, new_fields: dict) -> dict:
    """Merge existing perfil.md content with new CV fields.

    Rules:
    - CV fields (nombre, linkedin, etc.): overwrite if new value is non-empty,
      preserve old value if new is empty.
    - Custom fields (anything NOT in CV_FIELDS): always preserve.
    - Custom sections: always preserve.

    Returns dict with:
        content: str (serialized perfil.md)
        fields_updated: list[str] (fields that were overwritten)
        fields_preserved: list[str] (fields kept from old)
        fields_added: list[str] (fields that were empty before, now filled)
    """
    old_fields = _parse_perfil_to_dict(old_perfil_text)
    meta, _ = _parse_frontmatter(old_perfil_text)

    fields_updated: list[str] = []
    fields_preserved: list[str] = []
    fields_added: list[str] = []

    merged: dict[str, str] = {}

    # Process all old fields first
    for key, old_val in old_fields.items():
        merged[key] = old_val

    # Apply new CV fields
    for key in CV_FIELDS:
        new_val = new_fields.get(key, "").strip()
        old_val = old_fields.get(key, "").strip()

        if new_val:
            if old_val:
                # Both have values: overwrite
                merged[key] = new_val
                fields_updated.append(key)
            else:
                # Only new has value: add
                merged[key] = new_val
                fields_added.append(key)
        else:
            # New is empty: preserve old
            if old_val:
                fields_preserved.append(key)
            # If both empty, nothing to do

    # Preserve all custom fields (not in CV_FIELDS and not _section:)
    for key, val in old_fields.items():
        if key not in CV_FIELDS and not key.startswith("_section:"):
            merged[key] = val

    content = _serialize_perfil(merged, meta)

    return {
        "content": content,
        "fields_updated": fields_updated,
        "fields_preserved": fields_preserved,
        "fields_added": fields_added,
    }
