"""Provider detection for CV-Pilot email generation.

Reads preferences from ``data/preferencias.json`` and resolves the active
email provider (gmail or outlook).
"""

from __future__ import annotations

from typing import Optional

from _lib.errors import CV_PilotError

# Value tokens accepted as a boolean "true" in preferencias.json.
_TRUE = {"sí", "si", "yes", "true", "1"}


def detect_provider_optional(prefs: dict, override: Optional[str]) -> Optional[str]:
    """Return the provider name or ``None`` when no provider is configured.

    ``override`` takes precedence over preferences.
    """
    if override:
        return override
    if prefs.get("gmail_drafts"):
        return "gmail"
    if prefs.get("outlook_drafts"):
        return "outlook"
    return None


def detect_provider(prefs: dict, override: Optional[str]) -> str:
    """Return the provider name or raise ``CV_PilotError(NO_PROVIDER)``."""
    prov = detect_provider_optional(prefs, override)
    if prov is None:
        raise CV_PilotError(
            "No provider configured. Set gmail_drafts/outlook_drafts in "
            "preferencias.json or pass --provider.",
            code="NO_PROVIDER",
        )
    return prov
