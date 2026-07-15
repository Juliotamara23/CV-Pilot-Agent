"""LLM-based CV field extraction for CV-Pilot.

Extracts structured CV fields from raw text using an LLM with a JSON schema
prompt. Falls back to regex parser if LLM fails.

Configuration via environment variables:
    CV_PILOT_LLM_API_KEY     — API key (required for LLM mode)
    CV_PILOT_LLM_ENDPOINT    — API endpoint (default: https://api.openai.com/v1)
    CV_PILOT_LLM_MODEL       — Model name (default: gpt-4o-mini)

Usage:
    from _lib.llm_extract import extract_cv_fields

    result = extract_cv_fields(text, source_pdf="cv.pdf")
    # result is a dict with canonical CV fields
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

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


def _call_llm(prompt: str) -> str:
    """Call the LLM API and return the response text.

    Uses httpx to call an OpenAI-compatible API endpoint.
    Configured via environment variables.

    Parameters
    ----------
    prompt : str
        The prompt to send to the LLM.

    Returns
    -------
    str
        The LLM's response text.

    Raises
    ------
    RuntimeError
        If the API call fails or returns an empty response.
    """
    import httpx

    api_key = os.environ.get("CV_PILOT_LLM_API_KEY")
    if not api_key:
        raise RuntimeError(
            "CV_PILOT_LLM_API_KEY environment variable not set. "
            "Set it to your API key or use regex fallback."
        )

    endpoint = os.environ.get("CV_PILOT_LLM_ENDPOINT", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("CV_PILOT_LLM_MODEL", DEFAULT_LLM_MODEL)

    url = f"{endpoint}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a precise CV field extractor. Return only valid JSON."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 4000,
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        raise RuntimeError(f"LLM API call failed: {exc}") from exc

    # Extract the assistant's message content.
    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError("LLM returned empty choices array")

    content = choices[0].get("message", {}).get("content", "")
    if not content.strip():
        raise RuntimeError("LLM returned empty response content")

    return content.strip()


def _parse_llm_json(response: str) -> dict:
    """Parse JSON from LLM response, handling markdown code blocks.

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
    # Strip markdown code blocks if present.
    cleaned = response.strip()
    # Find JSON content — either in code blocks or raw JSON object/array.
    code_block = re.search(r"```(?:json)?\s*\n(.*?)\n?```", cleaned, re.DOTALL)
    if code_block:
        cleaned = code_block.group(1).strip()
    else:
        # Try to find a raw JSON object or array.
        json_match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
        if json_match:
            cleaned = json_match.group(1).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse LLM response as JSON: {exc}") from exc


def extract_cv_fields(text: str, source_pdf: str = None) -> dict[str, Any]:
    """Extract CV fields from raw text using an LLM.

    Parameters
    ----------
    text : str
        Raw text extracted from a CV/resume PDF.
    source_pdf : str, optional
        Path to the source PDF (for metadata).

    Returns
    -------
    dict
        Extracted CV fields matching CANONICAL_FIELDS.

    Raises
    ------
    RuntimeError
        If LLM API is not configured or the call fails.
    ValueError
        If the LLM response cannot be parsed or validated.
    """
    prompt = EXTRACTION_PROMPT.format(
        text=text[:8000],  # Truncate to avoid token limits
        schema=json.dumps(CV_EXTRACTION_SCHEMA, indent=2),
    )

    response = _call_llm(prompt)
    fields = _parse_llm_json(response)

    # Validate: ensure all canonical fields exist (default to None).
    result = {}
    for key in CANONICAL_FIELDS:
        val = fields.get(key)
        if val is not None and isinstance(val, str):
            val = val.strip()
            if not val:
                val = None
        result[key] = val

    return result


def extract_cv_fields_with_fallback(text: str, source_pdf: str = None) -> dict[str, Any]:
    """Extract CV fields, falling back to regex if LLM fails.

    Parameters
    ----------
    text : str
        Raw text extracted from a CV/resume PDF.
    source_pdf : str, optional
        Path to the source PDF (for metadata).

    Returns
    -------
    dict
        Extracted fields with metadata:
        - fields: dict of extracted canonical fields
        - extraccion_metodo: "llm" or "regex_fallback"
        - campos_faltantes: list of fields that are None
        - aviso_usuario: warning message if fields are missing
    """
    campos_faltantes = []
    extraccion_metodo = "llm"

    try:
        fields = extract_cv_fields(text, source_pdf)
    except (RuntimeError, ValueError) as exc:
        # LLM failed — fall back to regex parser.
        extraccion_metodo = "regex_fallback"
        try:
            # Import parser from onboarding (shared dependency).
            import importlib.util as _ilu
            from pathlib import Path as _Path
            _agent_root = _Path(__file__).resolve().parent.parent
            _parser_path = _agent_root / "skills" / "onboarding" / "scripts" / "_onboarding_internal" / "parser.py"
            _parser_spec = _ilu.spec_from_file_location("_onboarding_parser", str(_parser_path))
            _parser_mod = _ilu.module_from_spec(_parser_spec)
            _parser_spec.loader.exec_module(_parser_mod)
            parsed = _parser_mod.parse_text(text)
            fields = parsed["fields"]
        except Exception:
            # Both failed — return empty fields.
            fields = {key: None for key in CANONICAL_FIELDS}

    # Count missing fields.
    campos_faltantes = [
        key for key in CANONICAL_FIELDS
        if not fields.get(key)
    ]

    result = {
        "fields": fields,
        "extraccion_metodo": extraccion_metodo,
        "campos_faltantes": campos_faltantes,
    }

    if campos_faltantes:
        result["aviso_usuario"] = (
            "Algunos campos no se pudieron extraer. "
            "Revise el JSON y complete manualmente."
        )

    return result
