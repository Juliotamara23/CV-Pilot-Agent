"""Tests for LLM-based CV field extraction.

Covers:
- LLM extraction with mocked API
- Fallback to regex when LLM fails
- JSON parsing from LLM responses (including markdown code blocks)
- Schema validation
- End-to-end with real CV friend (requires API key)

Run with:
    .venv/Scripts/python.exe -m pytest test/scenarios/agent-mode/test_llm_extract.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

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

# Also import pdf_parser for the real CV test
from pdf_parser import extract as extract_pdf  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_PDF_JOSE = _REPO_ROOT / "test" / "cv-test" / "Hoja de Vida Jose.pdf"


# --------------------------------------------------------------------------- #
# Unit: _parse_llm_json
# --------------------------------------------------------------------------- #

class TestParseLLMJson:
    """Tests for parsing JSON from LLM responses."""

    def test_parse_clean_json(self):
        response = '{"nombre": "Ana", "correo": "a@b.com"}'
        result = llm_extract._parse_llm_json(response)
        assert result["nombre"] == "Ana"

    def test_parse_json_in_code_block(self):
        response = '```json\n{"nombre": "Ana", "correo": "a@b.com"}\n```'
        result = llm_extract._parse_llm_json(response)
        assert result["correo"] == "a@b.com"

    def test_parse_json_in_plain_code_block(self):
        response = '```\n{"nombre": "Ana"}\n```'
        result = llm_extract._parse_llm_json(response)
        assert result["nombre"] == "Ana"

    def test_parse_json_with_leading_text(self):
        response = 'Here is the extracted data:\n```json\n{"nombre": "Ana"}\n```'
        # This should still work because we strip code blocks
        result = llm_extract._parse_llm_json(response)
        assert result["nombre"] == "Ana"

    def test_parse_invalid_json_raises(self):
        with pytest.raises(ValueError, match="Failed to parse"):
            llm_extract._parse_llm_json("not json at all")


# --------------------------------------------------------------------------- #
# Unit: extract_cv_fields (mocked LLM)
# --------------------------------------------------------------------------- #

MOCK_LLM_RESPONSE = json.dumps({
    "nombre": "Julio Andrés Támara Hernández",
    "correo": "julio.tamara23@outlook.com",
    "telefono": "+57 320 7581183",
    "linkedin": "https://linkedin.com/in/julio-andrés-támara-hernández-23z4iz0r",
    "github": "https://github.com/Juliotamara23",
    "cv_url": "https://drive.google.com/file/d/1XawtjXvqr6BP8r6kumbmQKDBufdltOG2/view",
    "resumen": "Ingeniero de Sistemas con enfoque en desarrollo Backend y automatización con IA.",
    "experiencia": "Pocki (C-Pocket)\nBackend Developer Febrero 2026 – Mayo 2026",
    "educacion": "Ingeniería en Sistemas — Corporación Universitaria del Caribe (CECAR)",
    "skills": "IA & Automatización: n8n, MCP, Integración LLM\nBackend: Python (FastAPI, Pandas, SQLAlchemy)",
})


class TestExtractCVFieldsMocked:
    """Tests for extract_cv_fields with mocked LLM API."""

    @patch("llm_extract._call_llm")
    def test_extract_returns_all_fields(self, mock_call):
        mock_call.return_value = MOCK_LLM_RESPONSE
        result = llm_extract.extract_cv_fields("some CV text")
        assert result["nombre"] == "Julio Andrés Támara Hernández"
        assert result["correo"] == "julio.tamara23@outlook.com"
        assert result["telefono"] == "+57 320 7581183"
        assert "linkedin.com" in result["linkedin"]
        assert "github.com" in result["github"]

    @patch("llm_extract._call_llm")
    def test_extract_handles_null_fields(self, mock_call):
        response = json.dumps({
            "nombre": "Ana", "correo": None, "telefono": None,
            "linkedin": None, "github": None, "cv_url": None,
            "resumen": None, "experiencia": None, "educacion": None, "skills": None,
        })
        mock_call.return_value = response
        result = llm_extract.extract_cv_fields("some text")
        assert result["nombre"] == "Ana"
        assert result["correo"] is None
        assert result["experiencia"] is None

    @patch("llm_extract._call_llm")
    def test_extract_strips_whitespace(self, mock_call):
        response = json.dumps({
            "nombre": "  Ana Lopez  ", "correo": " a@b.com ",
            "telefono": None, "linkedin": None, "github": None, "cv_url": None,
            "resumen": None, "experiencia": None, "educacion": None, "skills": None,
        })
        mock_call.return_value = response
        result = llm_extract.extract_cv_fields("some text")
        assert result["nombre"] == "Ana Lopez"
        assert result["correo"] == "a@b.com"

    @patch("llm_extract._call_llm")
    def test_extract_empty_string_becomes_none(self, mock_call):
        response = json.dumps({
            "nombre": "", "correo": "  ", "telefono": None,
            "linkedin": None, "github": None, "cv_url": None,
            "resumen": None, "experiencia": None, "educacion": None, "skills": None,
        })
        mock_call.return_value = response
        result = llm_extract.extract_cv_fields("some text")
        assert result["nombre"] is None
        assert result["correo"] is None

    @patch("llm_extract._call_llm")
    def test_extract_code_block_response(self, mock_call):
        mock_call.return_value = f"```json\n{MOCK_LLM_RESPONSE}\n```"
        result = llm_extract.extract_cv_fields("some text")
        assert result["nombre"] == "Julio Andrés Támara Hernández"


# --------------------------------------------------------------------------- #
# Unit: extract_cv_fields_with_fallback
# --------------------------------------------------------------------------- #

class TestExtractWithFallback:
    """Tests for the fallback mechanism."""

    @patch("llm_extract._call_llm")
    def test_llm_success_method_is_llm(self, mock_call):
        mock_call.return_value = MOCK_LLM_RESPONSE
        result = llm_extract.extract_cv_fields_with_fallback("some text")
        assert result["extraccion_metodo"] == "llm"
        assert result["fields"]["nombre"] is not None

    @patch("llm_extract._call_llm", side_effect=RuntimeError("API key not set"))
    def test_llm_failure_falls_back_to_regex(self, mock_call):
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
        result = llm_extract.extract_cv_fields_with_fallback(cv_text)
        assert result["extraccion_metodo"] == "regex_fallback"
        assert result["fields"]["correo"] == "ana@correo.com"

    @patch("llm_extract._call_llm", side_effect=RuntimeError("timeout"))
    def test_fallback_reports_missing_fields(self, mock_call):
        result = llm_extract.extract_cv_fields_with_fallback("just a name\nAna")
        assert result["extraccion_metodo"] == "regex_fallback"
        assert len(result["campos_faltantes"]) > 0
        assert "aviso_usuario" in result


# --------------------------------------------------------------------------- #
# Prompt content test
# --------------------------------------------------------------------------- #

class TestPromptContent:
    """Verify the prompt includes the JSON schema."""

    @patch("llm_extract._call_llm")
    def test_prompt_includes_schema(self, mock_call):
        mock_call.return_value = MOCK_LLM_RESPONSE
        llm_extract.extract_cv_fields("test text")
        # Verify the prompt was sent to the LLM
        call_args = mock_call.call_args[0][0]
        assert "nombre" in call_args
        assert "correo" in call_args
        assert "experiencia" in call_args
        assert "JSON" in call_args

    @patch("llm_extract._call_llm")
    def test_prompt_truncates_long_text(self, mock_call):
        mock_call.return_value = MOCK_LLM_RESPONSE
        long_text = "x" * 20000
        llm_extract.extract_cv_fields(long_text)
        call_args = mock_call.call_args[0][0]
        # The text should be truncated to 8000 chars
        assert len(call_args) < 15000  # prompt overhead + 8000 chars


# --------------------------------------------------------------------------- #
# E2E: Real CV friend (requires API key)
# --------------------------------------------------------------------------- #

class TestCVFriendE2E:
    """End-to-end test with the real CV friend PDF.

    This test is SKIPPED if CV_PILOT_LLM_API_KEY is not set.
    """

    @pytest.fixture()
    def jose_text(self):
        if not _PDF_JOSE.exists():
            pytest.skip("CV friend PDF not found")
        result = extract_pdf(str(_PDF_JOSE))
        assert result["ok"], f"Failed to extract: {result.get('error')}"
        return result["text"]

    @pytest.mark.skipif(
        not _PDF_JOSE.exists(),
        reason="CV friend PDF not found",
    )
    def test_cv_friend_extracts_10_fields(self, jose_text):
        """The CV friend must extract ALL 10 canonical fields (10/10 = 100%).

        This is the CRITERIO DE ÉXITO for Phase B/D.
        If this test fails, we need to iterate the prompt or schema.
        """
        import os
        if not os.environ.get("CV_PILOT_LLM_API_KEY"):
            pytest.skip("CV_PILOT_LLM_API_KEY not set — skipping LLM E2E test")

        result = llm_extract.extract_cv_fields(jose_text)

        missing = [k for k in llm_extract.CANONICAL_FIELDS if not result.get(k)]
        assert len(missing) == 0, (
            f"CV friend extraction missing {len(missing)}/10 fields: {missing}\n"
            f"Extracted: {json.dumps(result, indent=2, ensure_ascii=False)}"
        )

    @pytest.mark.skipif(
        not _PDF_JOSE.exists(),
        reason="CV friend PDF not found",
    )
    def test_cv_friend_with_fallback_extracts_contact_fields(self, jose_text):
        """The regex fallback must extract at least the contact fields from Jose's CV.

        The CV friend uses non-standard section headers (e.g. "Historial de Empleo"
        instead of "Experiencia"), so the regex parser won't find all sections.
        But contact fields (nombre, correo, telefono) should be extracted.
        """
        result = llm_extract.extract_cv_fields_with_fallback(jose_text)

        fields = result["fields"]
        # Contact fields must be extracted even by regex
        assert fields["correo"] is not None, "correo should be extracted"
        assert fields["telefono"] is not None, "telefono should be extracted"
        # Method should be regex_fallback (no API key in test env)
        assert result["extraccion_metodo"] == "regex_fallback"
