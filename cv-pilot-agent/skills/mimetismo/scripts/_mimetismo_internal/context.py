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


# --------------------------------------------------------------------------- #
# Cover-letter drafting contract
# --------------------------------------------------------------------------- #
# A cover letter is NOT a postulation email with a different subject: it has its
# own professional structure. This contract fixes the ordered sections the model
# must draft and pins each source to its allowed role, mirroring the safeguarded
# context (examples=voice only, profile_facts=single factual source, footer=
# non-duplicable). Each section is defined structurally (what it must contain)
# rather than by a list of banned wordings, so the contract is user-agnostic.
# Only source-grounding safeguards (certifications, remote work, years of
# experience, footer ownership) are enforced as strict rules.

# (key, title, role) — ordered sections of the cover letter.
_COVER_LETTER_STRUCTURE: tuple[tuple[str, str, str], ...] = (
    (
        "presentation",
        "Presentación",
        "Identifica al remitente y la vacante objetivo (posición + empresa del contexto 'job'). "
        "Abre con cortesía siguiendo la voz de 'examples'.",
    ),
    (
        "relevant_experience",
        "Experiencia relevante",
        "Traduce los requisitos de la oferta en evidencia del perfil usando SOLO 'profile_facts'. "
        "Ordena la experiencia que más conecta con el rol; nunca una lista genérica de requisitos.",
    ),
    (
        "connection_to_role",
        "Conexión con el rol",
        "Conecta 'skills'/'experiencia' del perfil con las necesidades específicas de la vacante "
        "(job + analysis). Toda afirmación sobre el perfil debe estar soportada por 'profile_facts'.",
    ),
    (
        "motivation",
        "Motivación",
        "Expresa interés genuino por la empresa y el rol. La motivación es subjetiva y no requiere "
        "evidencia del perfil, pero no inventa hechos sobre la empresa ni el puesto.",
    ),
    (
        "cv_closing",
        "CV y cierre",
        "Menciona el CV una sola vez ('[cv]' se resuelve a texto plano cuando se adjunta). Cierra "
        "con cortesía. NUNCA repetir contactos: pertenecen al 'footer' del CLI.",
    ),
)

# Rules that are enforced regardless of source. These are source-grounding
# safeguards only (claims must be backed by the pinned sources, and footer
# contacts are never repeated in the body). No user- or phrase-specific wording
# is banned: the structure itself (see _COVER_LETTER_STRUCTURE) defines what
# each section must contain, so the contract is user-agnostic.
_COVER_LETTER_PROHIBITED: tuple[str, ...] = (
    "Cada requisito de la oferta se traduce en evidencia de 'profile_facts'; "
    "no se recitan como párrafo-resumen genérico sin respaldo del perfil.",
    "Afirmar certificaciones que no estén en 'certificaciones'.",
    "Afirmar trabajo remoto cuando 'remote_work' es false.",
    "Inflar años de experiencia respecto a lo declarado en 'resumen'.",
    "Duplicar en el cuerpo los enlaces del 'footer' (GitHub, LinkedIn, WhatsApp, CV, email, teléfono).",
)

# Each drafting source and the single role it may play.
_COVER_LETTER_SOURCES: dict[str, dict[str, str]] = {
    "voice": {
        "source": "data/correos.md",
        "usage": "SOLO el tono, saludo, ritmo y cierre (la voz del usuario). Nunca es fuente de "
        "skills, experiencia ni logros.",
    },
    "facts": {
        "source": "profile_facts",
        "usage": "Única fuente de afirmaciones de perfil, con atribución por 'field'. Solo puede "
        "afirmarse lo listado allí.",
    },
    "requirements": {
        "source": "job + analysis",
        "usage": "La vacante y su análisis. Se traducen en evidencia de 'profile_facts'; nunca se "
        "copian como párrafo-resumen genérico.",
    },
    "footer": {
        "usage": "Enlaces de contacto que la CLI añade en la firma. Nunca repetirlos en el cuerpo.",
    },
}

_COVER_LETTER_STRUCTURE_SUMMARY = (
    "Presentación → Experiencia relevante → Conexión con el rol → Motivación → CV y cierre."
)


def build_cover_letter_contract() -> dict:
    """Return the deterministic cover-letter drafting contract.

    The model consumes this contract (with the same context envelope) to draft a
    cover letter whose professional structure is distinct from the postulation
    email and grounded only in the safeguarded sources. The rules are
    structural, not a list of banned wordings, so the contract is user-agnostic.
    """
    return {
        "draft": "cover-letter",
        "structure": [
            {"key": key, "title": title, "role": role}
            for key, title, role in _COVER_LETTER_STRUCTURE
        ],
        "structure_summary": _COVER_LETTER_STRUCTURE_SUMMARY,
        "sources": _COVER_LETTER_SOURCES,
        "prohibited": list(_COVER_LETTER_PROHIBITED),
    }