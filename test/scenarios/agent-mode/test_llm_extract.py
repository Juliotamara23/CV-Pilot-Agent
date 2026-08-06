"""Tests for LLM prompt building and response parsing.

Covers:
- Prompt building (build_extraction_prompt)
- JSON parsing from LLM responses (parse_llm_json)
- Field parsing and validation (parse_llm_fields)
- Regex fallback extraction (parse_cv_text_with_regex)

The LLM call itself is the agent's responsibility — not tested here.

Run with:
    .venv/bin/python -m pytest test/scenarios/agent-mode/test_llm_extract.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Path setup
_AGENT_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "cv-pilot-agent"
_LIB_DIR = _AGENT_ROOT / "_lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))
if str(_AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(_AGENT_ROOT))

# Import the module under test
import importlib.util as _ilu

_spec = _ilu.spec_from_file_location("llm_extract", str(_LIB_DIR / "llm_extract.py"))
llm_extract = _ilu.module_from_spec(_spec)
sys.modules["llm_extract"] = llm_extract
_spec.loader.exec_module(llm_extract)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_PDF_JOSE = _REPO_ROOT / "test" / "cv-test" / "Hoja de Vida Jose.pdf"


# --------------------------------------------------------------------------- #
# Unit: build_extraction_prompt
# --------------------------------------------------------------------------- #


class TestBuildExtractionPrompt:
    """Tests for building the LLM extraction prompt."""

    def test_prompt_includes_text(self):
        prompt = llm_extract.build_extraction_prompt("John Doe\njohn@example.com")
        assert "John Doe" in prompt
        assert "john@example.com" in prompt

    def test_prompt_includes_schema_keys(self):
        prompt = llm_extract.build_extraction_prompt("test text")
        for field in llm_extract.CANONICAL_FIELDS:
            assert field in prompt, f"Field '{field}' missing from prompt"

    def test_prompt_truncates_long_text(self):
        long_text = "x" * 20000
        prompt = llm_extract.build_extraction_prompt(long_text)
        # Prompt overhead + truncated text (8000 chars) should be under ~15000
        assert len(prompt) < 15000

    def test_prompt_has_json_schema(self):
        prompt = llm_extract.build_extraction_prompt("test")
        assert '"type": "object"' in prompt
        assert '"nombre"' in prompt

    def test_prompt_has_extraction_rules(self):
        prompt = llm_extract.build_extraction_prompt("test")
        assert "DO NOT invent" in prompt
        assert "null" in prompt
        assert "valid JSON" in prompt


# --------------------------------------------------------------------------- #
# Unit: parse_llm_json
# --------------------------------------------------------------------------- #


class TestParseLLMJson:
    """Tests for parsing JSON from LLM responses."""

    def test_parse_clean_json(self):
        response = '{"nombre": "Ana", "correo": "a@b.com"}'
        result = llm_extract.parse_llm_json(response)
        assert result["nombre"] == "Ana"

    def test_parse_json_in_code_block(self):
        response = '```json\n{"nombre": "Ana", "correo": "a@b.com"}\n```'
        result = llm_extract.parse_llm_json(response)
        assert result["correo"] == "a@b.com"

    def test_parse_json_in_plain_code_block(self):
        response = '```\n{"nombre": "Ana"}\n```'
        result = llm_extract.parse_llm_json(response)
        assert result["nombre"] == "Ana"

    def test_parse_json_with_leading_text(self):
        response = 'Here is the extracted data:\n```json\n{"nombre": "Ana"}\n```'
        result = llm_extract.parse_llm_json(response)
        assert result["nombre"] == "Ana"

    def test_parse_invalid_json_raises(self):
        with pytest.raises(ValueError, match="Failed to parse"):
            llm_extract.parse_llm_json("not json at all")


# --------------------------------------------------------------------------- #
# Unit: parse_llm_fields
# --------------------------------------------------------------------------- #

MOCK_LLM_RESPONSE = json.dumps({
    "nombre": "Ana Lopez",
    "correo": "ana@correo.com",
    "telefono": "+57 300 1112233",
    "linkedin": "https://linkedin.com/in/ana-lopez",
    "github": "https://github.com/ana-lopez",
    "cv_url": "https://drive.google.com/file/d/fake-cv-id/view",
    "resumen": "Ingeniero de Sistemas con enfoque en desarrollo Backend y automatización con IA.",
    "experiencia": "Empresa Ficticia\nBackend Developer 2023 – 2024",
    "educacion": "Ingeniería en Sistemas — Universidad Ficticia",
    "skills": "IA & Automatización: n8n, MCP, Integración LLM\nBackend: Python (FastAPI, Pandas, SQLAlchemy)",
})


class TestParseLLMFields:
    """Tests for parse_llm_fields() — parses and validates LLM responses."""

    def test_parse_returns_all_fields(self):
        result = llm_extract.parse_llm_fields(MOCK_LLM_RESPONSE)
        assert result["nombre"] == "Ana Lopez"
        assert result["correo"] == "ana@correo.com"
        assert result["telefono"] == "+57 300 1112233"
        assert "linkedin.com" in result["linkedin"]
        assert "github.com" in result["github"]

    def test_parse_handles_null_fields(self):
        response = json.dumps({
            "nombre": "Ana", "correo": None, "telefono": None,
            "linkedin": None, "github": None, "cv_url": None,
            "resumen": None, "experiencia": None, "educacion": None, "skills": None,
        })
        result = llm_extract.parse_llm_fields(response)
        assert result["nombre"] == "Ana"
        assert result["correo"] is None
        assert result["experiencia"] is None

    def test_parse_strips_whitespace(self):
        response = json.dumps({
            "nombre": "  Ana Lopez  ", "correo": " a@b.com ",
            "telefono": None, "linkedin": None, "github": None, "cv_url": None,
            "resumen": None, "experiencia": None, "educacion": None, "skills": None,
        })
        result = llm_extract.parse_llm_fields(response)
        assert result["nombre"] == "Ana Lopez"
        assert result["correo"] == "a@b.com"

    def test_parse_empty_string_becomes_none(self):
        response = json.dumps({
            "nombre": "", "correo": "  ", "telefono": None,
            "linkedin": None, "github": None, "cv_url": None,
            "resumen": None, "experiencia": None, "educacion": None, "skills": None,
        })
        result = llm_extract.parse_llm_fields(response)
        assert result["nombre"] is None
        assert result["correo"] is None

    def test_parse_code_block_response(self):
        response = f"```json\n{MOCK_LLM_RESPONSE}\n```"
        result = llm_extract.parse_llm_fields(response)
        assert result["nombre"] == "Ana Lopez"

    def test_parse_invalid_json_raises(self):
        with pytest.raises(ValueError, match="Failed to parse"):
            llm_extract.parse_llm_fields("not valid json")

    def test_parse_missing_fields_default_to_none(self):
        """Fields not present in LLM response must default to None."""
        response = json.dumps({"nombre": "Test"})
        result = llm_extract.parse_llm_fields(response)
        assert result["nombre"] == "Test"
        assert result["correo"] is None
        assert result["experiencia"] is None

    def test_parse_preserves_non_canonical_fields(self):
        """Non-canonical fields must pass through — strings, lists, objects."""
        response = json.dumps({
            "nombre": "Test",
            "correo": "test@test.com",
            "certificaciones": ["AWS SA", "CKAD"],
            "proyectos": {"destacado": "CV-Pilot"},
            "idiomas": "Inglés C1",
        })
        result = llm_extract.parse_llm_fields(response)
        # Canonical fields normalized
        assert result["nombre"] == "Test"
        assert result["correo"] == "test@test.com"
        # Non-canonical fields preserved as-is
        assert result["certificaciones"] == ["AWS SA", "CKAD"]
        assert result["proyectos"] == {"destacado": "CV-Pilot"}
        assert result["idiomas"] == "Inglés C1"


# --------------------------------------------------------------------------- #
# Unit: parse_cv_text_with_regex (fallback)
# --------------------------------------------------------------------------- #


class TestParseCVTextWithRegex:
    """Tests for the regex-based fallback extraction."""

    def test_extracts_contact_fields(self):
        cv_text = """Nombre: Ana Lopez
ana@correo.com
+54 11 1234-5678
https://linkedin.com/in/analopez
https://github.com/analopez
Resumen
Backend developer.
Experiencia
Dev - Acme (2020-2024)
Educacion
UBA
Skills
Python, Go
"""
        result = llm_extract.parse_cv_text_with_regex(cv_text)
        assert result["correo"] == "ana@correo.com"
        assert result["nombre"] is not None

    def test_handles_minimal_text(self):
        result = llm_extract.parse_cv_text_with_regex("just a name\nAna")
        assert isinstance(result, dict)
        # All canonical fields must be present (even if None/empty)
        for key in llm_extract.CANONICAL_FIELDS:
            assert key in result, f"Missing canonical field: {key}"

    def test_extracts_linkedin_from_text(self):
        cv_text = "linkedin.com/in/testuser\nemail@test.com"
        result = llm_extract.parse_cv_text_with_regex(cv_text)
        assert "linkedin.com/in/testuser" in result["linkedin"]

    def test_extracts_github_from_text(self):
        cv_text = "github.com/testuser\nemail@test.com"
        result = llm_extract.parse_cv_text_with_regex(cv_text)
        assert "github.com/testuser" in result["github"]


# --------------------------------------------------------------------------- #
# E2E: Real CV friend — regex fallback only
# --------------------------------------------------------------------------- #


class TestCVFriendRegex:
    """End-to-end test with the real CV friend PDF using regex fallback only.

    These verify the regex parser handles the real CV at a basic level.
    The LLM extraction is the agent's responsibility.
    """

    @pytest.fixture()
    def jose_text(self):
        if not _PDF_JOSE.exists():
            pytest.skip("CV friend PDF not found")
        # Import pdf_parser
        _pdf_spec = _ilu.spec_from_file_location(
            "pdf_parser", str(_LIB_DIR / "pdf_parser.py")
        )
        pdf_parser = _ilu.module_from_spec(_pdf_spec)
        sys.modules["pdf_parser"] = pdf_parser
        _pdf_spec.loader.exec_module(pdf_parser)

        result = pdf_parser.extract(str(_PDF_JOSE))
        assert result["ok"], f"Failed to extract: {result.get('error')}"
        return result["text"]

    @pytest.mark.skipif(
        not _PDF_JOSE.exists(),
        reason="CV friend PDF not found",
    )
    def test_regex_extracts_contact_fields_from_real_cv(self, jose_text):
        """The regex fallback must extract at least contact fields from Jose's CV."""
        result = llm_extract.parse_cv_text_with_regex(jose_text)

        # Contact fields must be extracted even by regex
        assert result["correo"] is not None, "correo should be extracted"
        assert result["telefono"] is not None, "telefono should be extracted"

    @pytest.mark.skipif(
        not _PDF_JOSE.exists(),
        reason="CV friend PDF not found",
    )
    def test_regex_reports_section_fields_may_be_missing(self, jose_text):
        """Section fields (educacion, skills, experiencia) may be empty with regex.

        Jose's CV uses non-standard headers like "Historial de Empleo"
        which the regex parser doesn't recognize. This is EXPECTED —
        the agent handles these via LLM extraction.
        """
        result = llm_extract.parse_cv_text_with_regex(jose_text)

        # Count how many fields were extracted
        found = [k for k in llm_extract.CANONICAL_FIELDS if result.get(k)]
        # With regex alone, we expect at least contact fields (3-5 fields)
        assert len(found) >= 3, (
            f"Expected at least 3 fields via regex, got {len(found)}: {found}"
        )
