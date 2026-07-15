"""Unified profile loader for CV-Pilot.

Loads the user profile from ``data/perfil.json``. Raises ``FileNotFoundError``
if the file is missing.

Replaces the old regex-based MD parser.
"""

from __future__ import annotations

import json
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


def _load_from_json(agent_root: Path) -> dict:
    """Load profile from ``data/perfil.json``.

    Returns a dict with keys: name, linkedin, github, whatsapp, email, cv_url.
    Missing fields are ``None``.
    """
    path = agent_root / "data" / "perfil.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    profile = {key: None for key in _JSON_TO_PROFILE.values()}
    for json_key, profile_key in _JSON_TO_PROFILE.items():
        val = data.get(json_key)
        if val and isinstance(val, str) and val.strip():
            profile[profile_key] = val.strip()
    return profile


def load_profile(agent_root: Path) -> dict:
    """Load profile from ``data/perfil.json``.

    Raises ``FileNotFoundError`` if the file is missing.
    """
    return _load_from_json(agent_root)
