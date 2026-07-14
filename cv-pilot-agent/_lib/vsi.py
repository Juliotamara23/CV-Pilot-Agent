"""Validación Semántica de Identidad (VSI) for CV-Pilot.

Determines whether extracted text is a professional CV/resume or some other
document (invoice, shopping list, recipe, etc.).

Rules source: ``rules/integridad.md`` lines 26-35.

Usage::

    from vsi import validate_cv

    result = validate_cv(pdf_text)
    if not result["is_valid"]:
        print(result["razon_rechazo"])
"""

from __future__ import annotations

import re

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

# Canonical CV sections and their pattern variants.
# Patterns are anchored to LINE START to avoid false positives from
# words like "experiencia" appearing in running text.
# Each pattern must match a standalone section header (line start,
# optional markdown heading markers, followed by line end, colon, or period).
# NOTE: Trailing punctuation (period, colon) is common in PDF-extracted headers.
CV_SECTION_PATTERNS: dict[str, list[str]] = {
    "experiencia": [
        r"^#{0,3}\s*experiencia\s+laboral\s*[.:]?\s*$",
        r"^#{0,3}\s*experiencia\s+profesional\s*[.:]?\s*$",
        r"^#{0,3}\s*historial\s+de\s+empleo\s*[.:]?\s*$",
        r"^#{0,3}\s*historial\s+laboral\s*[.:]?\s*$",
        r"^#{0,3}\s*employment\s+history\s*[.:]?\s*$",
        r"^#{0,3}\s*work\s+experience\s*[.:]?\s*$",
        r"^#{0,3}\s*professional\s+experience\s*[.:]?\s*$",
        r"^#{0,3}\s*experiencia\s*[.:]?\s*$",
        r"^#{0,3}\s*empleo\s*[.:]?\s*$",
        r"^#{0,3}\s*trayectoria\s+profesional\s*[.:]?\s*$",
        r"^#{0,3}\s*employment\s*[.:]?\s*$",
        r"^#{0,3}\s*work\s+history\s*[.:]?\s*$",
    ],
    "educacion": [
        r"^#{0,3}\s*educaci[oó]n\s*[.:]?\s*$",
        r"^#{0,3}\s*formaci[oó]n\s*[.:]?\s*$",
        r"^#{0,3}\s*formaci[oó]n\s+acad[eé]mica\s*[.:]?\s*$",
        r"^#{0,3}\s*estudios\s*[.:]?\s*$",
        r"^#{0,3}\s*education\s*[.:]?\s*$",
        r"^#{0,3}\s*academic\s+background\s*[.:]?\s*$",
        r"^#{0,3}\s*formaci[oó]n\s+profesional\s*[.:]?\s*$",
    ],
    "skills": [
        r"^#{0,3}\s*habilidades\s+t[eé]cnicas\s*[.:]?\s*$",
        r"^#{0,3}\s*habilidades\s*[.:]?\s*$",
        r"^#{0,3}\s*habilidades\s+en\s*:\s*$",
        r"^#{0,3}\s*competencias\s*[.:]?\s*$",
        r"^#{0,3}\s*conocimientos\s*[.:]?\s*$",
        r"^#{0,3}\s*technical\s+skills\s*[.:]?\s*$",
        r"^#{0,3}\s*skills\s*[.:]?\s*$",
        r"^#{0,3}\s*tech\s*stack\s*[.:]?\s*$",
        r"^#{0,3}\s*tecnolog[ií]as\s*[.:]?\s*$",
        r"^#{0,3}\s*aptitudes\s*[.:]?\s*$",
        r"^#{0,3}\s*skills\s+t[eé]cnicos\s*[.:]?\s*$",
        r"^#{0,3}\s*conocimientos\s+t[eé]cnicos\s*[.:]?\s*$",
    ],
    "contacto": [
        r"^#{0,3}\s*datos\s+de\s+contacto\s*[.:]?\s*$",
        r"^#{0,3}\s*informaci[oó]n\s+de\s+contacto\s*[.:]?\s*$",
        r"^#{0,3}\s*contacto\s*[.:]?\s*$",
        r"^#{0,3}\s*contact\s*[.:]?\s*$",
        r"^#{0,3}\s*datos\s+personales\s*[.:]?\s*$",
        r"^#{0,3}\s*personal\s+info(?:rmation)?\s*[.:]?\s*$",
    ],
}

# Indicators that a document is NOT a CV.  These are checked as
# whole-phrase matches (case-insensitive) anywhere in the text.
# NOTE: Keep indicators SPECIFIC to non-CV documents.  Generic phrases
# like "curso de" or "certificado de" appear legitimately in CV education
# sections and must NOT be listed here.
NON_CV_INDICATORS: list[str] = [
    "lista de compras",
    "shopping list",
    "factura",
    "invoice",
    "receta",
    "recipe",
    "contrato de",
    "acta de",
    "minutes of",
    "boleta de",
    "ticket de compra",
    "purchase order",
    "orden de compra",
    "nota de cr[eé]dito",
    "nota de d[eé]bito",
    "balance general",
    "estado de resultados",
    "estado de cuenta",
    "bank statement",
    "comprobante de pago",
    "payment receipt",
    "carta de renuncia",
    "resignation letter",
    "propuesta comercial",
    "commercial proposal",
    "cotizaci[oó]n",
    "quotation",
    "gu[ií]a de usuario",
    "user guide",
    "google cloud academy",
    "google cloud skills boost",
    "challenge labs",
    "key information",
]

# Minimum canonical sections required for a valid CV.
_MIN_SECTIONS = 2

# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #

_SECTION_RE: dict[str, re.Pattern[str]] = {
    section: re.compile("|".join(patterns), re.IGNORECASE | re.MULTILINE)
    for section, patterns in CV_SECTION_PATTERNS.items()
}

_NON_CV_RE = re.compile(
    "|".join(NON_CV_INDICATORS), re.IGNORECASE | re.MULTILINE
)


def _count_section_matches(text: str) -> dict[str, list[str]]:
    """Return {canonical_name: [matched_variant, ...]} for each found section.

    Section patterns are line-anchored: they only match when the section
    name appears as a standalone header (start of line, optional markdown
    markers, end of line).  This prevents false positives from words like
    "experiencia" appearing inside sentences.
    """
    found: dict[str, list[str]] = {}
    for section, pattern in _SECTION_RE.items():
        matches = pattern.findall(text)
        if matches:
            # Deduplicate while preserving order.
            seen: set[str] = set()
            unique: list[str] = []
            for m in matches:
                normalized = m.strip().lower()
                if normalized not in seen:
                    seen.add(normalized)
                    unique.append(m.strip())
            found[section] = unique
    return found


def _has_non_cv_indicators(text: str) -> str | None:
    """Return the first non-CV indicator found, or None."""
    match = _NON_CV_RE.search(text)
    if match:
        return match.group(0).strip()
    return None


def _compute_confidence(
    sections_found: dict[str, list[str]], text_length: int, non_cv_hit: str | None
) -> float:
    """Heuristic confidence score 0.0–1.0."""
    if non_cv_hit:
        return 0.95  # Very confident it's NOT a CV.

    n = len(sections_found)
    if n >= 4:
        base = 0.95
    elif n == 3:
        base = 0.85
    elif n == 2:
        base = 0.70
    elif n == 1:
        base = 0.35
    else:
        base = 0.10

    # Boost for longer text (more content = more likely a real CV).
    if text_length > 2000:
        base = min(base + 0.05, 1.0)
    elif text_length < 200:
        base = max(base - 0.10, 0.0)

    return round(base, 2)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def validate_cv(text: str) -> dict:
    """Validate whether *text* is a professional CV/resume.

    Parameters
    ----------
    text : str
        Raw text extracted from a PDF or pasted by the user.

    Returns
    -------
    dict with keys:
        is_valid             — True if text passes VSI.
        secciones_detectadas — list of canonical section names found.
        razon_rechazo        — reason string if rejected, else None.
        confianza            — 0.0–1.0 confidence in the decision.
    """
    if not text or not text.strip():
        return {
            "is_valid": False,
            "secciones_detectadas": [],
            "razon_rechazo": "El documento está vacío o no contiene texto legible.",
            "confianza": 0.95,
        }

    # 1. Negative filter — fast path.
    non_cv = _has_non_cv_indicators(text)
    if non_cv:
        return {
            "is_valid": False,
            "secciones_detectadas": [],
            "razon_rechazo": (
                f"El documento contiene el indicador '{non_cv}', "
                "lo que sugiere que no es un CV profesional."
            ),
            "confianza": _compute_confidence({}, len(text), non_cv),
        }

    # 2. Section detection.
    sections = _count_section_matches(text)
    found_names = list(sections.keys())

    # 3. Validate against minimum threshold.
    if len(found_names) < _MIN_SECTIONS:
        detail = ", ".join(found_names) if found_names else "ninguna"
        return {
            "is_valid": False,
            "secciones_detectadas": found_names,
            "razon_rechazo": (
                f"Solo se detectó {len(found_names)} sección canónica ({detail}). "
                f"Se requieren al menos {_MIN_SECTIONS} para considerar el documento "
                "un CV profesional."
            ),
            "confianza": _compute_confidence(sections, len(text), None),
        }

    # 4. Valid CV.
    return {
        "is_valid": True,
        "secciones_detectadas": found_names,
        "razon_rechazo": None,
        "confianza": _compute_confidence(sections, len(text), None),
    }
