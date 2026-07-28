"""LLM prompt builder and response parser for CV-Pilot.

Generates the extraction prompt that the orchestrator agent sends to its LLM,
and parses/validates the LLM's JSON response back into canonical CV fields.

The agent (Hermes / CV-Pilot orchestrator) handles the actual LLM call.
This module is PURELY deterministic: it builds prompts and parses responses.
It NEVER makes HTTP calls or requires API keys.

Usage:
    from _lib.llm_extract import build_extraction_prompt, parse_llm_fields

    # Agent builds the prompt:
    prompt = build_extraction_prompt(cv_text)
    # Agent sends prompt to its LLM, gets raw response...
    # Agent parses the response:
    fields = parse_llm_fields(raw_response)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# Default model — cheap, fast, good enough for structured extraction.
DEFAULT_LLM_MODEL = "gpt-4o-mini"

# Canonical fields we expect the LLM to extract.
CANONICAL_FIELDS = [
    "nombre", "correo", "telefono", "linkedin", "github", "cv_url",
    "resumen", "experiencia", "educacion", "skills",
]

# JSON schema we send to the LLM.
CV_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "nombre": {"type": ["string", "null"], "description": "Full name of the person"},
        "correo": {"type": ["string", "null"], "description": "Email address"},
        "telefono": {"type": ["string", "null"], "description": "Phone number with country code if available"},
        "linkedin": {"type": ["string", "null"], "description": "LinkedIn profile URL"},
        "github": {"type": ["string", "null"], "description": "GitHub profile URL"},
        "cv_url": {"type": ["string", "null"], "description": "Link to the original CV document"},
        "resumen": {"type": ["string", "null"], "description": "Professional summary or objective"},
        "experiencia": {"type": ["string", "null"], "description": "Work experience section, full text"},
        "educacion": {"type": ["string", "null"], "description": "Education section, full text"},
        "skills": {"type": ["string", "null"], "description": "Technical skills section, full text"},
    },
    "required": CANONICAL_FIELDS,
    "additionalProperties": False,
}

EXTRACTION_PROMPT = """You are a CV/resume field extractor. Given the following raw text extracted from a CV/resume PDF, extract the specified fields into strict JSON.

RULES:
1. Extract ONLY information that is explicitly present in the text. DO NOT invent or hallucinate any information.
2. If a field is NOT found in the text, set it to null.
3. For "experiencia", "educacion", and "skills", include the FULL section text as it appears.
4. For URLs, extract the complete URL including protocol (https://).
5. Return ONLY valid JSON, no markdown code blocks, no explanations.

CV TEXT:
{text}

JSON SCHEMA:
{schema}

Return the extracted fields as a JSON object matching the schema above."""


def build_extraction_prompt(text: str) -> str:
    """Build the LLM extraction prompt for a given CV text.

    The orchestrator agent sends this prompt to its LLM and passes the raw
    response to ``parse_llm_fields()``.

    Parameters
    ----------
    text : str
        Raw text extracted from a CV/resume PDF.

    Returns
    -------
    str
        Formatted prompt ready to send to an LLM.
    """
    return EXTRACTION_PROMPT.format(
        text=text[:8000],  # Truncate to avoid token limits
        schema=json.dumps(CV_EXTRACTION_SCHEMA, indent=2),
    )


def parse_llm_json(response: str) -> dict:
    """Parse JSON from an LLM response, handling markdown code blocks.

    Parameters
    ----------
    response : str
        Raw LLM response that may contain JSON wrapped in ```json ... ```.

    Returns
    -------
    dict
        Parsed JSON dict.

    Raises
    ------
    ValueError
        If the response cannot be parsed as JSON.
    """
    cleaned = response.strip()

    # Find JSON content — either in code blocks or raw JSON object/array.
    code_block = re.search(r"```(?:json)?\s*\n(.*?)\n?```", cleaned, re.DOTALL)
    if code_block:
        cleaned = code_block.group(1).strip()
    else:
        json_match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
        if json_match:
            cleaned = json_match.group(1).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse LLM response as JSON: {exc}") from exc


def parse_llm_fields(response: str) -> dict[str, Any]:
    """Parse and validate an LLM response into canonical CV fields.

    Parameters
    ----------
    response : str
        Raw LLM response (JSON object, possibly wrapped in markdown code block).

    Returns
    -------
    dict
        Extracted CV fields matching CANONICAL_FIELDS.
        Missing fields default to None.

    Raises
    ------
    ValueError
        If the response cannot be parsed as JSON.
    """
    fields = parse_llm_json(response)

    result: dict[str, Any] = {}
    for key in CANONICAL_FIELDS:
        val = fields.get(key)
        if val is not None and isinstance(val, str):
            val = val.strip()
            if not val:
                val = None
        result[key] = val

    return result


def parse_cv_text_with_regex(text: str, links: list[str] | None = None) -> dict[str, Any]:
    """Extract CV fields using regex/heuristic fallback (from onboarding parser).

    This is the deterministic fallback when no LLM response is available.
    Only extracts contact fields reliably; section-based fields
    (educacion, skills, experiencia) depend on standard header names.

    Parameters
    ----------
    text : str
        Raw text extracted from a CV/resume PDF.
    links : list[str] | None
        Optional list of URLs extracted from the PDF.

    Returns
    -------
    dict
        Extracted fields matching CANONICAL_FIELDS.
    """
    import importlib.util as _ilu

    _agent_root = Path(__file__).resolve().parent.parent
    _parser_path = _agent_root / "skills" / "onboarding" / "scripts" / "_onboarding_internal" / "parser.py"
    _parser_spec = _ilu.spec_from_file_location("_onboarding_parser", str(_parser_path))
    _parser_mod = _ilu.module_from_spec(_parser_spec)
    _parser_spec.loader.exec_module(_parser_mod)
    parsed = _parser_mod.parse_text(text, links=links)
    return parsed["fields"]
