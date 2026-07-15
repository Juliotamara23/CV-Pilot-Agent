"""Unified profile loader for CV-Pilot.

Reads ``data/perfil.json`` (new canonical format) and returns a dict with
the standard profile keys. Falls back to ``data/perfil.md`` if JSON not found
(backward compatibility during migration).

Replaces the old regex-based MD parser.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# Mapping from perfil JSON keys to the standard profile keys used by formatos.
_JSON_TO_PROFILE: dict[str, str] = {
    "nombre": "name",
    "linkedin": "linkedin",
    "github": "github",
    "telefono": "whatsapp",
    "correo": "email",
    "cv_url": "cv_url",
}

# Legacy MD label mapping (fallback).
_LABEL_TO_KEY: dict[str, str] = {
    "Nombre completo": "name",
    "LinkedIn": "linkedin",
    "GitHub": "github",
    "WhatsApp / Teléfono": "whatsapp",
    "Correo electrónico": "email",
    "Link al CV": "cv_url",
}

_PATTERN = re.compile(r"^-\s*\*\*(.+?)\s*:\*\*\s*(.+?)\s*$", re.MULTILINE)


def _load_from_json(agent_root: Path) -> dict | None:
    """Try to load profile from perfil.json. Returns None if not found."""
    path = agent_root / "data" / "perfil.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    profile = {key: None for key in _JSON_TO_PROFILE.values()}
    for json_key, profile_key in _JSON_TO_PROFILE.items():
        val = data.get(json_key)
        if val and isinstance(val, str) and val.strip():
            profile[profile_key] = val.strip()
    return profile


def _load_from_md(agent_root: Path) -> dict:
    """Fallback: load profile from perfil.md using regex."""
    path = agent_root / "data" / "perfil.md"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    profile = {key: None for key in _LABEL_TO_KEY.values()}
    for label, value in _PATTERN.findall(text):
        key = _LABEL_TO_KEY.get(label)
        if key:
            profile[key] = value.strip()
    return profile


def load_profile(agent_root: Path) -> dict:
    """Load and return the user profile.

    Prefers perfil.json; falls back to perfil.md for backward compatibility.
    Returns a dict with keys: name, linkedin, github, whatsapp, email, cv_url.
    Missing fields are ``None``.
    """
    result = _load_from_json(agent_root)
    if result is not None:
        return result
    return _load_from_md(agent_root)
