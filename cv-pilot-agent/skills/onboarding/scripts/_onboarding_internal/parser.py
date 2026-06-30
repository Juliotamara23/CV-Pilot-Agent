"""Regex-based CV text parser for CV-Pilot onboarding.

Extracts structured fields from raw CV text using regex patterns
and section-header heuristics.
"""

from __future__ import annotations

import re
from typing import Optional

REGEX = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    # Phone: require a '+' prefix or a separator (space/paren) so pure dates
    # like "2020-2024" do not match.
    "phone": re.compile(r"\+?\d[\d\s().-]{7,}\d"),
    "linkedin": re.compile(
        r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w-]+/?", re.IGNORECASE
    ),
    "github": re.compile(
        r"(?:https?://)?(?:www\.)?github\.com/[\w-]+/?", re.IGNORECASE
    ),
    "url": re.compile(r"https?://[^\s)\]]+"),
}

# Fields the script treats as essential; absence is reported in ``missing``.
REQUIRED = ("nombre", "linkedin", "github", "telefono", "correo")

# Normalized section header labels (lowercase, no '#'/':'). A line is a header
# when its normalized form equals one of these labels.
_SECTION_HEADERS = {
    "experiencia": ("experiencia", "experience", "experiencia profesional"),
    "educacion": ("educacion", "education", "formacion", "formación academica"),
    "skills": ("skills", "habilidades", "competencias", "tech stack"),
    "resumen": ("resumen", "summary", "perfil profesional", "perfil", "about"),
    "contacto": ("contacto", "contact", "datos de contacto"),
}


def _normalize_header(line: str) -> str:
    return line.strip().lstrip("#").strip().rstrip(":").strip().lower()


def _is_header(line: str, keys: tuple[str, ...]) -> bool:
    return _normalize_header(line) in keys


def _find_first(text: str, pattern: re.Pattern) -> str:
    match = pattern.search(text)
    return match.group(0).strip() if match else ""


def _find_phone(text: str) -> str:
    """Pick the best phone match: prefer those with a '+' prefix, then any."""
    matches = REGEX["phone"].findall(text)
    if not matches:
        return ""
    with_plus = [m for m in matches if m.strip().startswith("+")]
    return (with_plus or matches)[0].strip()


def _extract_nombre(text: str) -> str:
    label = re.search(r"(?:^|\n)\s*Nombre(?:\s+completo)?\s*:\s*(.+)", text, re.IGNORECASE)
    if label:
        return label.group(1).strip()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if REGEX["email"].search(stripped) or stripped.startswith(("#", "##")):
            continue
        if any(_is_header(stripped, keys) for keys in _SECTION_HEADERS.values()):
            continue
        return stripped
    return ""


def _extract_section(text: str, keys: tuple[str, ...]) -> str:
    """Return the body of a section identified by an exact header-line match."""
    all_headers = [keys_set for keys_set in _SECTION_HEADERS.values()]
    lines = text.splitlines()
    start: Optional[int] = None
    for i, ln in enumerate(lines):
        if _is_header(ln, keys):
            start = i + 1
            break
    if start is None:
        return ""
    body: list[str] = []
    for ln in lines[start:]:
        if any(_is_header(ln, h) for h in all_headers):
            break
        if ln.strip():
            body.append(ln)
    return "\n".join(body)


def _classify_links(links: list[str]) -> dict:
    fields: dict = {"linkedin": "", "github": "", "cv_url": ""}
    for link in links:
        if REGEX["linkedin"].search(link) and not fields["linkedin"]:
            fields["linkedin"] = link
        elif REGEX["github"].search(link) and not fields["github"]:
            fields["github"] = link
        elif not fields["cv_url"]:
            fields["cv_url"] = link
    return fields


def parse_text(text: str, links: Optional[list[str]] = None) -> dict:
    """Apply regex + heuristics to CV ``text`` and merged ``links``.

    Returns ``{"fields": {...}, "missing": [required keys absent]}``.
    """
    link_fields = _classify_links(links or [])
    fields: dict = {
        "nombre": _extract_nombre(text),
        "resumen": _extract_section(text, _SECTION_HEADERS["resumen"]),
        "linkedin": link_fields["linkedin"] or _find_first(text, REGEX["linkedin"]),
        "github": link_fields["github"] or _find_first(text, REGEX["github"]),
        "telefono": _find_phone(text),
        "correo": _find_first(text, REGEX["email"]),
        "cv_url": link_fields["cv_url"] or "",
        "experiencia": _extract_section(text, _SECTION_HEADERS["experiencia"]),
        "educacion": _extract_section(text, _SECTION_HEADERS["educacion"]),
        "skills": _extract_section(text, _SECTION_HEADERS["skills"]),
    }
    missing = [k for k in REQUIRED if not fields.get(k)]
    return {"fields": fields, "missing": missing}
