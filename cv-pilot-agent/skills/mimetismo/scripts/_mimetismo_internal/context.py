"""Deterministic, source-separated generation context for mimetismo.

The drafting model must not guess from the raw ``perfil.json`` blob: it needs a
curated, verifiable context where each element carries its provenance. This
module separates the three sources the model drafts from:

- STYLE   -> examples (``data/correos.md``): voice, rhythm, connectors, closings.
- FACTS   -> verified profile facts (``perfil.json``) with per-field source
             attribution (``profile_facts``).
- CONTACT -> footer-managed links (see ``links.footer_link_labels``), exposed so
             the model never duplicates them in the body.

Deliberately NOT the raw profile JSON: compensation expectations and contact/link
fields are excluded (private / footer-owned), so the model cannot overstate or
duplicate them. Certifications and remote-work capability are only surfaced when
the profile explicitly declares them; years of experience come verbatim from the
``resumen``.
"""

from __future__ import annotations

import json
from pathlib import Path

# Technical sections of perfil.json that are verbatim, verifiable and may be
# cited in a job-application body. Contact and compensation fields are excluded.
_PROFILE_FACT_SECTIONS: tuple[str, ...] = (
    "resumen",
    "experiencia",
    "educacion",
    "skills",
)

# Nullable ``extras`` fields that are safe for a job-application body. We exclude
# ``expectativa_salarial_usd`` (private compensation) and ``intereses``.
_EXTRA_FACT_FIELDS: tuple[str, ...] = (
    "ubicacion",
    "disponibilidad",
    "idiomas",
    "visa_us",
)

# Markers that indicate remote-work capability in perfil.json.
_REMOTE_MARKERS: tuple[str, ...] = ("remoto", "remote", "remotamente")

_CERT_LINE_PREFIX = "Certificaciones:"

_EXAMPLES_SOURCE = "data/correos.md"


def load_raw_profile(agent_root: Path) -> dict:
    """Return the full ``data/perfil.json`` mapping, or ``{}`` when missing/bad."""
    path = agent_root / "data" / "perfil.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_examples(agent_root: Path) -> tuple[str, bool, str]:
    """Return ``(examples, has_examples, source)`` from ``data/correos.md``."""
    path = agent_root / "data" / "correos.md"
    if not path.is_file():
        return "", False, _EXAMPLES_SOURCE
    try:
        return path.read_text(encoding="utf-8"), True, _EXAMPLES_SOURCE
    except OSError:
        return "", False, _EXAMPLES_SOURCE


def build_profile_facts(raw: dict) -> list[dict]:
    """Return verified, source-attributed profile facts for body drafting.

    Each entry is ``{"field": <perfil.json key>, "fact": <verbatim text>}``.
    Contact/link fields and compensation expectations are excluded (footer-owned /
    private) so the model cannot overstate or duplicate them.
    """
    facts: list[dict] = []
    for key in _PROFILE_FACT_SECTIONS:
        val = raw.get(key)
        if isinstance(val, str) and val.strip():
            facts.append({"field": key, "fact": val.strip()})
    extras = raw.get("extras")
    if isinstance(extras, dict):
        for key in _EXTRA_FACT_FIELDS:
            val = extras.get(key)
            if isinstance(val, str) and val.strip():
                facts.append({"field": f"extras.{key}", "fact": val.strip()})
    return facts


def extract_certificaciones(raw: dict) -> list[str]:
    """Return the certifications explicitly declared by the profile.

    Reads the ``Certificaciones:`` segment of the ``educacion`` field. Returns an
    empty list when the profile declares none, so the model never fabricates a
    certification.
    """
    educacion = raw.get("educacion")
    if not isinstance(educacion, str):
        return []
    out: list[str] = []
    for line in educacion.splitlines():
        line = line.strip()
        if not line.startswith(_CERT_LINE_PREFIX):
            continue
        payload = line[len(_CERT_LINE_PREFIX):].strip()
        for cert in (c.strip() for c in payload.split(",")):
            if cert:
                out.append(cert)
    return out


def extract_remote_work(raw: dict) -> bool:
    """Return True only when the profile explicitly mentions remote work.

    The model may claim remote-work capability only when this is True.
    """
    parts: list[str] = []
    for key in _PROFILE_FACT_SECTIONS:
        val = raw.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(val)
    extras = raw.get("extras")
    if isinstance(extras, dict):
        for key in ("ubicacion", "disponibilidad", "intereses"):
            val = extras.get(key)
            if isinstance(val, str) and val.strip():
                parts.append(val)
    text = " ".join(parts).lower()
    return any(marker in text for marker in _REMOTE_MARKERS)