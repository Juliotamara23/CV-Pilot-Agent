"""Unified profile loader for CV-Pilot.

Reads ``data/perfil.md`` and returns a dict with the standard profile keys.
Replaces the duplicated regex parsing in ``generate.py`` and ``format_report.py``.
"""

from __future__ import annotations

import re
from pathlib import Path

# Mapping from perfil.md labels to canonical profile keys.
_LABEL_TO_KEY: dict[str, str] = {
    "Nombre completo": "name",
    "LinkedIn": "linkedin",
    "GitHub": "github",
    "WhatsApp / Teléfono": "whatsapp",
    "Correo electrónico": "email",
    "Link al CV": "cv_url",
}

_PATTERN = re.compile(r"^-\s*\*\*(.+?)\s*:\*\*\s*(.+?)\s*$", re.MULTILINE)


def load_profile(agent_root: Path) -> dict:
    """Load and return the user profile from ``data/perfil.md``.

    Returns a dict with keys: name, linkedin, github, whatsapp, email, cv_url.
    Missing fields are ``None``.
    """
    path = agent_root / "data" / "perfil.md"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    profile = {key: None for key in _LABEL_TO_KEY.values()}
    for label, value in _PATTERN.findall(text):
        key = _LABEL_TO_KEY.get(label)
        if key:
            profile[key] = value.strip()
    return profile
