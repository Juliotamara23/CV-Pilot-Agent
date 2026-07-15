"""Tests for the onboarding CLI (`skills/onboarding/scripts/cli.py`).

Run with the venv Python:
    .venv/Scripts/python.exe -m pytest test/scenarios/agent-mode/test_onboard.py

Covers: regex parsing, template rendering, missing-field detection, and the
four CLI commands (extract, parse, generate, full) including error paths.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

# Make the scripts dir importable so `import cli` works from anywhere.
_SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "cv-pilot-agent" / "skills" / "onboarding" / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("onboard_cli", str(_SCRIPTS_DIR / "cli.py"))
onboard = _ilu.module_from_spec(_spec)
sys.modules["onboard_cli"] = onboard
_spec.loader.exec_module(onboard)

runner = CliRunner()

# Sample CV text reused across parse tests.
SAMPLE_CV = """\
Nombre: Ana Lopez

Resumen
Backend developer con 5 anos de experiencia en microservicios.

Experiencia
Senior Dev - Acme (2020-2024)
- Lidero equipo de 3
- Migracion a Go

Educacion
Lic. en Informatica - UBA (2015-2020)

Skills
Python, Go, Docker, Kubernetes

Contacto
ana@correo.com
+54 11 1234-5678
https://linkedin.com/in/analopez
https://github.com/analopez
"""


# --------------------------------------------------------------------------- #
# Unit: parse_text — regex + heuristics
# --------------------------------------------------------------------------- #
def test_parse_extracts_email():
    result = onboard.parse_text("Contacto: user@example.com")
    assert result["fields"]["correo"] == "user@example.com"


def test_parse_phone_prefers_plus_over_date():
    # "2020-2024" is a date range, not a phone; the real phone has a '+'.
    result = onboard.parse_text("Periodo (2020-2024)\n+54 11 1234-5678")
    assert result["fields"]["telefono"] == "+54 11 1234-5678"


def test_parse_linkedin_and_github_from_links():
    links = ["https://linkedin.com/in/analopez", "https://github.com/analopez"]
    result = onboard.parse_text("Ana Lopez", links=links)
    assert result["fields"]["linkedin"] == "https://linkedin.com/in/analopez"
    assert result["fields"]["github"] == "https://github.com/analopez"


def test_parse_linkedin_from_text_without_protocol():
    result = onboard.parse_text("linkedin.com/in/analopez")
    assert "linkedin.com/in/analopez" in result["fields"]["linkedin"]


def test_parse_missing_required_fields_reported():
    result = onboard.parse_text("Solo un nombre sin contacto.")
    # nombre is extracted from the first line; everything else is missing.
    assert "linkedin" in result["missing"]
    assert "github" in result["missing"]
    assert "telefono" in result["missing"]
    assert "correo" in result["missing"]
    assert "nombre" not in result["missing"]


def test_parse_section_header_exact_match_avoids_substring_trap():
    # The Resumen line mentions "experiencia" but must NOT be treated as the
    # Experiencia section header.
    result = onboard.parse_text(SAMPLE_CV)
    assert "experiencia en microservicios" in result["fields"]["resumen"]
    assert "Senior Dev - Acme" in result["fields"]["experiencia"]
    assert "Lic. en Informatica" in result["fields"]["educacion"]
    assert "Python, Go" in result["fields"]["skills"]
    # Skills must NOT absorb the Contacto section.
    assert "ana@correo.com" not in result["fields"]["skills"]


def test_parse_nombre_prefers_label():
    result = onboard.parse_text("Nombre: Ana Lopez\nAlgo mas")
    assert result["fields"]["nombre"] == "Ana Lopez"


def test_parse_nombre_falls_back_to_first_line():
    result = onboard.parse_text("Carlos Perez\nExperiencia\nDev")
    assert result["fields"]["nombre"] == "Carlos Perez"


# --------------------------------------------------------------------------- #
# Unit: render_template
# --------------------------------------------------------------------------- #
def test_render_template_replaces_placeholders(tmp_path):
    template = tmp_path / "t.template.md"
    template.write_text("Hola {{nombre}} - {{correo}}", encoding="utf-8")
    out = onboard.render_template(template, {"nombre": "Ana", "correo": "a@b.com"})
    assert out == "Hola Ana - a@b.com"


def test_render_template_missing_field_defaults_empty(tmp_path):
    template = tmp_path / "t.template.md"
    template.write_text("[{{nombre}}][{{falta}}]", encoding="utf-8")
    out = onboard.render_template(template, {"nombre": "Ana"})
    assert out == "[Ana][]"


def test_email_block_with_examples():
    block = onboard.email_block({"email_examples": ["Hola", "Chau"]})
    assert "### Ejemplo 1" in block
    assert "### Ejemplo 2" in block
    assert "Hola" in block


def test_email_block_without_examples():
    block = onboard.email_block({})
    assert "No se proporcionaron" in block


# --------------------------------------------------------------------------- #
# CLI: parse
# --------------------------------------------------------------------------- #
def test_cli_parse_text_file(tmp_path):
    src = tmp_path / "cv.txt"
    src.write_text(SAMPLE_CV, encoding="utf-8")
    result = runner.invoke(onboard.app, ["parse", str(src)])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["fields"]["correo"] == "ana@correo.com"
    assert data["missing"] == []


def test_cli_parse_stdin(tmp_path):
    result = runner.invoke(onboard.app, ["parse", "-"], input=SAMPLE_CV)
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["fields"]["nombre"] == "Ana Lopez"


def test_cli_parse_missing_fields_exits_nonzero(tmp_path):
    src = tmp_path / "cv.txt"
    src.write_text("Solo un nombre suelto.", encoding="utf-8")
    result = runner.invoke(onboard.app, ["parse", str(src)])
    # missing required fields -> exit 1, but JSON still emitted.
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert "correo" in data["missing"]


def test_cli_parse_nonexistent_file(tmp_path):
    result = runner.invoke(onboard.app, ["parse", str(tmp_path / "nope.txt")])
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["ok"] is False


# --------------------------------------------------------------------------- #
# CLI: generate
# --------------------------------------------------------------------------- #
FIELDS = {
    "nombre": "Ana Lopez",
    "resumen": "Backend dev.",
    "linkedin": "https://linkedin.com/in/analopez",
    "github": "https://github.com/analopez",
    "telefono": "+54 11 1234-5678",
    "correo": "ana@correo.com",
    "cv_url": "",
    "experiencia": "Dev - Acme",
    "educacion": "UBA",
    "skills": "Python, Go",
    "sector": "Backend",
    "tono": "tecnico",
    "idioma": "espanol",
    "mimetismo": "si",
    "gmail_drafts": "no",
    "outlook_drafts": "no",
    "email_examples": ["Hola"],
}


def _write_fields(tmp_path):
    fields_path = tmp_path / "fields.json"
    fields_path.write_text(json.dumps(FIELDS), encoding="utf-8")
    return fields_path


def test_cli_generate_writes_three_files(tmp_path):
    fields_path = _write_fields(tmp_path)
    out_dir = tmp_path / "out"
    result = runner.invoke(
        onboard.app,
        ["generate", "--fields-file", str(fields_path), "--out-dir", str(out_dir)],
    )
    assert result.exit_code == 0
    # Now outputs are JSON (perfil.json, preferencias.json) + correos.md
    assert (out_dir / "perfil.json").is_file()
    assert (out_dir / "correos.md").is_file()
    assert (out_dir / "preferencias.json").is_file()
    perfil = json.loads((out_dir / "perfil.json").read_text(encoding="utf-8"))
    assert perfil["nombre"] == "Ana Lopez"
    assert perfil["correo"] == "ana@correo.com"


def test_cli_generate_creates_backup_on_rerun(tmp_path):
    fields_path = _write_fields(tmp_path)
    out_dir = tmp_path / "out"
    runner.invoke(onboard.app, ["generate", "--fields-file", str(fields_path), "--out-dir", str(out_dir)])
    # Second run must back up the existing files.
    result = runner.invoke(onboard.app, ["generate", "--fields-file", str(fields_path), "--out-dir", str(out_dir)])
    assert result.exit_code == 0
    assert (out_dir / "perfil.json.bak").is_file()
    assert (out_dir / "correos.md.bak").is_file()
    assert (out_dir / "preferencias.json.bak").is_file()


def test_cli_generate_no_backup_flag(tmp_path):
    fields_path = _write_fields(tmp_path)
    out_dir = tmp_path / "out"
    runner.invoke(onboard.app, ["generate", "--fields-file", str(fields_path), "--out-dir", str(out_dir)])
    result = runner.invoke(
        onboard.app,
        ["generate", "--fields-file", str(fields_path), "--out-dir", str(out_dir), "--no-backup"],
    )
    assert result.exit_code == 0
    assert not (out_dir / "perfil.json.bak").exists()


def test_cli_generate_invalid_fields_file(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    result = runner.invoke(onboard.app, ["generate", "--fields-file", str(bad), "--out-dir", str(tmp_path)])
    assert result.exit_code == 1


# --------------------------------------------------------------------------- #
# CLI: extract
# --------------------------------------------------------------------------- #
def test_cli_extract_missing_pdf(tmp_path):
    result = runner.invoke(onboard.app, ["extract", str(tmp_path / "nope.pdf")])
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["ok"] is False


# --------------------------------------------------------------------------- #
# CLI: full — end-to-end with a synthetic PDF (requires PyMuPDF)
# --------------------------------------------------------------------------- #
def _make_pdf(path: Path) -> None:
    import fitz  # type: ignore
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (72, 72),
        "Nombre: Ana Lopez\n\nResumen\nBackend dev.\n\nExperiencia\nDev - Acme (2020-2024)\n\nSkills\nPython, Go\n\nContacto\nana@correo.com\n+54 11 1234-5678\nhttps://linkedin.com/in/analopez\nhttps://github.com/analopez",
    )
    doc.save(str(path))
    doc.close()


def test_cli_full_end_to_end(tmp_path):
    pytest.importorskip("fitz")
    pdf = tmp_path / "cv.pdf"
    _make_pdf(pdf)
    fields_path = _write_fields(tmp_path)
    out_dir = tmp_path / "full_out"
    result = runner.invoke(
        onboard.app,
        ["full", str(pdf), "--fields-file", str(fields_path), "--out-dir", str(out_dir)],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["step"] == "full"
    assert data["parse"]["fields"]["correo"] == "ana@correo.com"
    assert (out_dir / "perfil.json").is_file()


def test_cli_full_missing_pdf(tmp_path):
    fields_path = _write_fields(tmp_path)
    result = runner.invoke(
        onboard.app,
        ["full", str(tmp_path / "nope.pdf"), "--fields-file", str(fields_path), "--out-dir", str(tmp_path)],
    )
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert data["step"] == "extract"
