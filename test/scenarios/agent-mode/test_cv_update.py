"""Tests for cv-update skill and VSI (Validación Semántica de Identidad).

Covers the 3 P2.3 backlog scenarios — adapted for the two-step extract+apply flow:
1. CV válido: extract → (agent extracts fields) → apply actualiza perfil.json.
2. CV inválido: extract rechaza por VSI → data/ intacto.
3. CV con contenido distinto al viejo genera perfil.json distinto (ATS fidelity).

Run with:
    .venv/bin/python -m pytest ../test/scenarios/agent-mode/test_cv_update.py -v
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# --------------------------------------------------------------------------- #
# Path setup
# --------------------------------------------------------------------------- #

_AGENT_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "cv-pilot-agent"
_CV_UPDATE_SCRIPTS = _AGENT_ROOT / "skills" / "cv-update" / "scripts"
_ONBOARDING_SCRIPTS = _AGENT_ROOT / "skills" / "onboarding" / "scripts"

for _p in (_AGENT_ROOT, _CV_UPDATE_SCRIPTS, _ONBOARDING_SCRIPTS, _AGENT_ROOT / "_lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from pdf_parser import extract as extract_pdf  # noqa: E402
from vsi import validate_cv  # noqa: E402
from llm_extract import build_extraction_prompt, parse_llm_fields  # noqa: E402

import importlib.util as _ilu

_recon_spec = _ilu.spec_from_file_location(
    "reconstructor",
    str(_CV_UPDATE_SCRIPTS / "_cv_update_internal" / "reconstructor.py"),
)
if _recon_spec is None or _recon_spec.loader is None:
    raise ImportError("Could not load reconstructor module")
reconstructor = _ilu.module_from_spec(_recon_spec)
sys.modules["reconstructor"] = reconstructor
_recon_spec.loader.exec_module(reconstructor)

_parser_spec = _ilu.spec_from_file_location(
    "onboard_parser",
    str(_ONBOARDING_SCRIPTS / "_onboarding_internal" / "parser.py"),
)
if _parser_spec is None or _parser_spec.loader is None:
    raise ImportError("Could not load onboard parser module")
parser = _ilu.module_from_spec(_parser_spec)
sys.modules["onboard_parser"] = parser
_parser_spec.loader.exec_module(parser)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

_REAL_DATA_DIR = _AGENT_ROOT / "data"
_REPO_ROOT = _AGENT_ROOT.parent
_PDF_JOSE = _REPO_ROOT / "test" / "cv-test" / "Hoja de Vida Jose.pdf"
_PDF_GCCF = _REPO_ROOT / "test" / "cv-test" / "GCCF Academy Key Information.pdf"

REAL_DATA_MD5: dict[str, str] = {
    "correos.md": "11e474246f6ac953621a4b60e8410ee6",
}

OLD_PERFIL_BACKEND = """\
---
source: old_cv.pdf
generated: 2025-01-01T00:00:00Z
---

# Perfil

## Identidad
- **Nombre:** Carlos Backend López
- **Resumen profesional:** Desarrollador Backend con 8 años de experiencia en Java, Spring Boot y arquitectura de microservicios. Experto en bases de datos PostgreSQL y sistemas distribuidos de alta disponibilidad.

## Contacto
- **LinkedIn:** https://linkedin.com/in/carlos-backend
- **GitHub:** https://github.com/carlos-backend
- **WhatsApp / Teléfono:** +57 300 1111111
- **Correo electrónico:** carlos.backend@example.com

## Experiencia

**TechCorp Backend Division**
Backend Lead 2020 – 2025
- Diseñé la arquitectura de microservicios en Java/Spring Boot para el core bancario.
- Implementé pipelines de CI/CD con Jenkins y Docker para despliegue continuo.
- Optimicé consultas SQL reduciendo tiempos de respuesta en un 40%.

## Educación
- **Ingeniería de Sistemas** — Universidad Nacional (2012 – 2018)

## Skills Técnicos
- Backend: Java, Spring Boot, Python, Django, PostgreSQL, Redis
- DevOps: Docker, Kubernetes, Jenkins, AWS EC2
- Metodologías: Scrum, Kanban, TDD
"""

FRONTEND_CV_TEXT = """\
Nombre: Laura Frontend García

Resumen
Desarrolladora Frontend con 5 años de experiencia en React, TypeScript y diseño de interfaces de usuario. Apasionada por la accesibilidad web y el rendimiento de aplicaciones SPA.

Experiencia
UI Lead - DesignStudio (2021-2026)
- Lideré el rediseño completo de la plataforma SaaS usando React y Tailwind CSS.
- Implementé sistema de diseño atómico reutilizado por 4 equipos.
- Reduje el bundle size en un 35% con code splitting y lazy loading.

Frontend Dev - WebAgency (2019-2021)
- Desarrollé dashboards interactivos con D3.js y React.
- Migré aplicación legacy de jQuery a React con TypeScript.

Educacion
Lic. en Diseño Digital — Universidad de los Andes (2014 – 2019)

Skills
Frontend: React, TypeScript, Next.js, Tailwind CSS, Figma, Storybook
Testing: Jest, React Testing Library, Cypress
Herramientas: Git, GitHub Actions, Vercel, Netlify

Contacto
laura.frontend@example.com
+57 310 2222222
https://linkedin.com/in/laura-frontend
https://github.com/laura-frontend
"""


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture()
def sandbox_dir(tmp_path):
    """Create a temporary sandbox with data/ dir and copies of the PDFs."""
    sandbox = tmp_path / "sandbox"
    data_dir = sandbox / "data"
    data_dir.mkdir(parents=True)

    shutil.copy(_PDF_JOSE, sandbox / "input_valid.pdf")
    shutil.copy(_PDF_GCCF, sandbox / "input_invalid.pdf")

    return sandbox


@pytest.fixture()
def clean_data_dir(sandbox_dir):
    """Provide a sandbox data/ dir pre-populated with real data/ content."""
    data_dir = sandbox_dir / "data"

    for f in _REAL_DATA_DIR.iterdir():
        # cv.pdf is a user-generated artifact that may or may not exist in
        # the real data dir — do not seed it. Tests create it explicitly
        # when exercising the --source-pdf persistence path.
        if f.is_file() and f.name != "cv.pdf":
            shutil.copy(f, data_dir / f.name)

    yield data_dir

    for fname, expected_md5 in REAL_DATA_MD5.items():
        real_file = _REAL_DATA_DIR / fname
        if real_file.exists():
            actual_md5 = hashlib.md5(real_file.read_bytes()).hexdigest()
            assert actual_md5 == expected_md5, (
                f"REAL data/{fname} was modified during test! "
                f"Expected {expected_md5}, got {actual_md5}"
            )


@pytest.fixture()
def jose_text() -> str:
    """Extracted text from the real CV (Hoja de Vida Jose.pdf)."""
    result = extract_pdf(str(_PDF_JOSE))
    assert result["ok"], f"Failed to extract text: {result.get('error')}"
    return result["text"]


@pytest.fixture()
def gccf_text() -> str:
    """Extracted text from the non-CV file (GCCF Academy)."""
    result = extract_pdf(str(_PDF_GCCF))
    assert result["ok"], f"Failed to extract text: {result.get('error')}"
    return result["text"]


# --------------------------------------------------------------------------- #
# Helpers — two-step CLI: extract + apply
# --------------------------------------------------------------------------- #


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _venv_python() -> str:
    venv_python = str(_AGENT_ROOT / ".venv" / "bin" / "python")
    return venv_python if Path(venv_python).exists() else sys.executable


def _run_extract(pdf_path: str) -> subprocess.CompletedProcess:
    """Run ``cv-update extract <pdf>`` and return the completed process."""
    cli_path = str(_CV_UPDATE_SCRIPTS / "cli.py")
    return subprocess.run(
        [_venv_python(), cli_path, "extract", pdf_path],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )


def _run_apply(fields_file: str, data_dir: str) -> subprocess.CompletedProcess:
    """Run ``cv-update apply <fields.json> --data-dir <dir>``."""
    cli_path = str(_CV_UPDATE_SCRIPTS / "cli.py")
    return subprocess.run(
        [_venv_python(), cli_path, "apply", fields_file, "--data-dir", data_dir],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )


def _simulate_agent_extraction(text: str, sandbox: Path) -> Path:
    """Simulate the agent's LLM extraction by parsing the CV text with regex.

    In production, the agent would send the prompt to its LLM and get back
    a full JSON extraction. Here we use the regex parser as a stand-in,
    which is equivalent to what the old fallback did.
    """
    fields = parser.parse_text(text)["fields"]
    fields_file = sandbox / "fields.json"
    fields_file.write_text(json.dumps(fields, ensure_ascii=False, indent=2), encoding="utf-8")
    return fields_file


# =========================================================================== #
#  VSI Tests
# =========================================================================== #


class TestVSI:
    """Tests for validate_cv() — the Semantic Identity Validation."""

    def test_vsi_accepts_valid_cv_jose_david(self, jose_text):
        result = validate_cv(jose_text)
        assert result["is_valid"] is True, (
            f"VSI rejected a valid CV. Reason: {result.get('razon_rechazo')}"
        )
        assert len(result["secciones_detectadas"]) >= 2

    def test_vsi_rejects_gccf_academy(self, gccf_text):
        result = validate_cv(gccf_text)
        assert result["is_valid"] is False
        assert result["razon_rechazo"]

    def test_vsi_rejects_empty_text(self):
        result = validate_cv("")
        assert result["is_valid"] is False
        assert result["razon_rechazo"]
        assert result["secciones_detectadas"] == []

    def test_vsi_rejects_short_text_without_sections(self):
        result = validate_cv("Hola, esto es un texto random sin secciones de CV.")
        assert result["razon_rechazo"]

    def test_vsi_accepts_cv_mentioning_quotation_project(self):
        # A legit CV describing a "Sistema de Cotizaciones" project must NOT be
        # rejected: the bare word is a false positive (regression for the real
        # CV of the user, which builds a quotation web app).
        cv = (
            "Julio Támara\n"
            "Ingeniero de Sistemas\n"
            "## Experiencia\n"
            "Desarrollador Fullstack\n"
            "Sistema de Cotizaciones: Desarrollé una aplicación web en React para "
            "la generación dinámica de cotizaciones de ventanas y puertas.\n"
            "## Educación\n"
            "Ingeniería de Sistemas\n"
            "## Skills\nPython, React, PostgreSQL\n"
        )
        result = validate_cv(cv)
        assert not result["razon_rechazo"], (
            f"VSI rejected a valid CV mentioning 'cotizaciones': {result.get('razon_rechazo')}"
        )

    def test_vsi_rejects_quotation_document(self):
        # An actual quotation document (with a document number) must be rejected.
        doc = (
            "COTIZACIÓN No. 12345\n"
            "Cliente: Empresa XYZ\n"
            "Total: $1.000.000\n"
        )
        result = validate_cv(doc)
        assert result["razon_rechazo"]


# =========================================================================== #
#  extract command tests
# =========================================================================== #


class TestExtractCommand:
    """Tests for the ``extract`` subcommand."""

    def test_extract_valid_cv_returns_text_and_prompt(self, sandbox_dir):
        """extract on a valid CV must return text, vsi, and prompt."""
        pdf_path = str(sandbox_dir / "input_valid.pdf")
        result = _run_extract(pdf_path)
        assert result.returncode == 0, f"extract failed:\nstderr={result.stderr}"

        output = json.loads(result.stdout)
        assert output["ok"] is True
        assert output["step"] == "extract"
        assert len(output["text"]) > 100, "extracted text is suspiciously short"
        assert "prompt" in output
        assert "canonical_fields" in output
        assert "nombre" in output["prompt"]

    def test_extract_includes_pdf_links(self, sandbox_dir):
        """extract must include PDF hyperlinks so the agent can extract linkedin/github."""
        pdf_path = str(sandbox_dir / "input_valid.pdf")
        result = _run_extract(pdf_path)
        assert result.returncode == 0

        output = json.loads(result.stdout)
        assert "links" in output, "extract output missing 'links' field"
        assert isinstance(output["links"], list)
        # Jose's CV has at least linkedin and github URLs
        linkedin_found = any("linkedin.com" in link for link in output["links"])
        github_found = any("github.com" in link for link in output["links"])
        assert linkedin_found or github_found, (
            f"Expected linkedin/github URLs in links, got: {output['links']}"
        )

    def test_extract_invalid_pdf_rejected_by_vsi(self, sandbox_dir):
        """extract on a non-CV must fail with VSI_REJECTED."""
        pdf_path = str(sandbox_dir / "input_invalid.pdf")
        result = _run_extract(pdf_path)
        assert result.returncode != 0

        output = json.loads(result.stdout)
        assert output["ok"] is False
        assert output["step"] == "vsi"
        assert output["error"] == "VSI_REJECTED"

    def test_extract_nonexistent_file_fails(self, sandbox_dir):
        """extract with a nonexistent file must fail at extraction step."""
        result = _run_extract(str(sandbox_dir / "does_not_exist.pdf"))
        assert result.returncode != 0
        output = json.loads(result.stdout)
        assert output["ok"] is False
        assert output["step"] == "extract"


# =========================================================================== #
#  apply command tests
# =========================================================================== #


class TestApplyCommand:
    """Tests for the ``apply`` subcommand."""

    def test_apply_writes_perfil_json(self, clean_data_dir, sandbox_dir):
        """apply with valid fields must write perfil.json."""
        fields = {
            "nombre": "Test User",
            "resumen": "A short summary.",
            "linkedin": "https://linkedin.com/in/testuser",
            "github": "https://github.com/testuser",
            "telefono": "+57 300 0000000",
            "correo": "test@example.com",
            "cv_url": "",
            "experiencia": "Dev at Acme (2020-2025)",
            "educacion": "Uni (2015-2020)",
            "skills": "Python, Go",
        }
        fields_file = sandbox_dir / "fields.json"
        fields_file.write_text(json.dumps(fields, ensure_ascii=False, indent=2), encoding="utf-8")

        result = _run_apply(str(fields_file), str(clean_data_dir))
        assert result.returncode == 0, f"apply failed:\nstderr={result.stderr}"

        output = json.loads(result.stdout)
        assert output["ok"] is True
        assert output["step"] == "apply"

        perfil_path = clean_data_dir / "perfil.json"
        assert perfil_path.exists()
        perfil_data = json.loads(perfil_path.read_text(encoding="utf-8"))
        assert perfil_data["nombre"] == "Test User"

    def test_apply_preserves_correos(self, clean_data_dir, sandbox_dir):
        """apply must NOT touch correos.md."""
        correos_path = clean_data_dir / "correos.md"
        md5_before = _md5(correos_path)

        fields = {"nombre": "Test", "correo": "test@test.com"}
        fields_file = sandbox_dir / "fields.json"
        fields_file.write_text(json.dumps(fields), encoding="utf-8")

        result = _run_apply(str(fields_file), str(clean_data_dir))
        assert result.returncode == 0

        assert _md5(correos_path) == md5_before, "correos.md was modified by apply!"

    def test_apply_reports_missing_fields(self, clean_data_dir, sandbox_dir):
        """apply with partial fields must report missing fields."""
        fields = {"nombre": "Minimal User"}
        fields_file = sandbox_dir / "fields.json"
        fields_file.write_text(json.dumps(fields), encoding="utf-8")

        result = _run_apply(str(fields_file), str(clean_data_dir))
        assert result.returncode == 0

        output = json.loads(result.stdout)
        assert len(output["campos_no_encontrados"]) > 0
        assert "aviso_usuario" in output

    def test_apply_invalid_json_fails(self, clean_data_dir, sandbox_dir):
        """apply with invalid JSON must fail gracefully."""
        fields_file = sandbox_dir / "bad.json"
        fields_file.write_text("not json {{{")

        result = _run_apply(str(fields_file), str(clean_data_dir))
        assert result.returncode != 0
        output = json.loads(result.stdout)
        assert output["ok"] is False

    def test_apply_nonexistent_file_fails(self, clean_data_dir, sandbox_dir):
        """apply with nonexistent file must fail."""
        result = _run_apply(str(sandbox_dir / "nope.json"), str(clean_data_dir))
        assert result.returncode != 0
        output = json.loads(result.stdout)
        assert output["ok"] is False

    def test_apply_source_pdf_overrides_fuente(self, clean_data_dir, sandbox_dir):
        """--source-pdf must override the fuente field in perfil.json."""
        fields = {"nombre": "Test", "correo": "test@test.com"}
        fields_file = sandbox_dir / "fields.json"
        fields_file.write_text(json.dumps(fields), encoding="utf-8")

        result = subprocess.run(
            [_venv_python(), str(_CV_UPDATE_SCRIPTS / "cli.py"),
             "apply", str(fields_file),
             "--data-dir", str(clean_data_dir),
             "--source-pdf", "cv_original.pdf"],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        assert result.returncode == 0

        perfil_data = json.loads((clean_data_dir / "perfil.json").read_text(encoding="utf-8"))
        assert perfil_data["fuente"] == "cv_original.pdf", (
            f"Expected fuente='cv_original.pdf', got '{perfil_data['fuente']}'"
        )

    def test_apply_with_source_pdf_copies_pdf_and_records_cv_path(self, clean_data_dir, sandbox_dir):
        """apply with --source-pdf must copy the PDF to data_dir/cv.pdf and record cv_path."""
        fields = {"nombre": "Test", "correo": "test@test.com"}
        fields_file = sandbox_dir / "fields.json"
        fields_file.write_text(json.dumps(fields), encoding="utf-8")

        # Use the valid PDF from sandbox
        source_pdf = str(sandbox_dir / "input_valid.pdf")
        result = subprocess.run(
            [_venv_python(), str(_CV_UPDATE_SCRIPTS / "cli.py"),
             "apply", str(fields_file),
             "--data-dir", str(clean_data_dir),
             "--source-pdf", source_pdf],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        assert result.returncode == 0, f"apply failed: {result.stderr}"

        # Verify cv.pdf was created
        cv_pdf_path = clean_data_dir / "cv.pdf"
        assert cv_pdf_path.is_file(), "cv.pdf was not created in data_dir"

        # Verify cv_path recorded in perfil.json
        perfil_data = json.loads((clean_data_dir / "perfil.json").read_text(encoding="utf-8"))
        assert perfil_data.get("cv_path") is not None, "cv_path not recorded in perfil.json"
        assert "cv.pdf" in perfil_data["cv_path"], f"cv_path should reference cv.pdf, got: {perfil_data['cv_path']}"

    def test_apply_without_source_pdf_does_not_create_cv_pdf(self, clean_data_dir, sandbox_dir):
        """apply without --source-pdf must NOT create cv.pdf or record cv_path."""
        fields = {"nombre": "Test", "correo": "test@test.com"}
        fields_file = sandbox_dir / "fields.json"
        fields_file.write_text(json.dumps(fields), encoding="utf-8")

        result = _run_apply(str(fields_file), str(clean_data_dir))
        assert result.returncode == 0

        # Verify cv.pdf was NOT created
        cv_pdf_path = clean_data_dir / "cv.pdf"
        assert not cv_pdf_path.exists(), "cv.pdf should not be created without --source-pdf"

        # Verify cv_path not recorded in perfil.json
        perfil_data = json.loads((clean_data_dir / "perfil.json").read_text(encoding="utf-8"))
        assert "cv_path" not in perfil_data or perfil_data.get("cv_path") is None, (
            f"cv_path should not be recorded without --source-pdf, got: {perfil_data.get('cv_path')}"
        )

    def test_apply_with_nonexistent_source_pdf_does_not_create_cv_pdf(self, clean_data_dir, sandbox_dir):
        """apply with nonexistent --source-pdf must NOT create cv.pdf or record cv_path."""
        fields = {"nombre": "Test", "correo": "test@test.com"}
        fields_file = sandbox_dir / "fields.json"
        fields_file.write_text(json.dumps(fields), encoding="utf-8")

        result = subprocess.run(
            [_venv_python(), str(_CV_UPDATE_SCRIPTS / "cli.py"),
             "apply", str(fields_file),
             "--data-dir", str(clean_data_dir),
             "--source-pdf", "/nonexistent/path.pdf"],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        assert result.returncode == 0

        # Verify cv.pdf was NOT created
        cv_pdf_path = clean_data_dir / "cv.pdf"
        assert not cv_pdf_path.exists(), "cv.pdf should not be created with nonexistent --source-pdf"

        # Verify cv_path not recorded in perfil.json
        perfil_data = json.loads((clean_data_dir / "perfil.json").read_text(encoding="utf-8"))
        assert "cv_path" not in perfil_data or perfil_data.get("cv_path") is None, (
            f"cv_path should not be recorded with nonexistent --source-pdf, got: {perfil_data.get('cv_path')}"
        )


# =========================================================================== #
#  Integration: extract → agent → apply flow
# =========================================================================== #


class TestExtractApplyIntegration:
    """End-to-end tests for the full two-step flow."""

    def test_full_flow_rewrites_profile(self, clean_data_dir, sandbox_dir):
        """extract → (simulated agent) → apply must rewrite perfil.json."""
        pdf_path = str(sandbox_dir / "input_valid.pdf")

        # Step 1: extract
        extract_result = _run_extract(pdf_path)
        assert extract_result.returncode == 0
        extract_output = json.loads(extract_result.stdout)
        assert extract_output["ok"] is True

        # Step 2: simulate agent extraction (regex parser as stand-in)
        fields_file = _simulate_agent_extraction(
            extract_output["text"], sandbox_dir
        )

        # Step 3: apply
        apply_result = _run_apply(str(fields_file), str(clean_data_dir))
        assert apply_result.returncode == 0
        apply_output = json.loads(apply_result.stdout)
        assert apply_output["ok"] is True

        # Verify perfil.json exists and has content
        perfil_path = clean_data_dir / "perfil.json"
        assert perfil_path.exists()
        perfil_data = json.loads(perfil_path.read_text(encoding="utf-8"))
        assert len(json.dumps(perfil_data)) > 50, "perfil.json is suspiciously short"

    def test_full_flow_preserves_correos(self, clean_data_dir, sandbox_dir):
        """Full extract → apply must NOT touch correos.md."""
        correos_path = clean_data_dir / "correos.md"
        md5_before = _md5(correos_path)

        pdf_path = str(sandbox_dir / "input_valid.pdf")
        extract_result = _run_extract(pdf_path)
        assert extract_result.returncode == 0
        extract_output = json.loads(extract_result.stdout)

        fields_file = _simulate_agent_extraction(
            extract_output["text"], sandbox_dir
        )
        apply_result = _run_apply(str(fields_file), str(clean_data_dir))
        assert apply_result.returncode == 0

        assert _md5(correos_path) == md5_before, "correos.md was modified!"

    def test_invalid_pdf_does_not_modify_data(self, clean_data_dir, sandbox_dir):
        """Invalid PDF → extract fails at VSI → data/ untouched."""
        data_dir = clean_data_dir
        md5_before = {f.name: _md5(f) for f in data_dir.iterdir() if f.is_file()}

        pdf_path = str(sandbox_dir / "input_invalid.pdf")
        result = _run_extract(pdf_path)
        assert result.returncode != 0

        output = json.loads(result.stdout)
        assert output["ok"] is False
        assert output["step"] == "vsi"

        md5_after = {f.name: _md5(f) for f in data_dir.iterdir() if f.is_file()}
        assert md5_before == md5_after, "data/ files were modified despite VSI rejection!"

    def test_profile_differs_after_update(self, clean_data_dir, sandbox_dir):
        """After full flow with a new CV, perfil.json must differ from original."""
        perfil_path = clean_data_dir / "perfil.json"

        from scripts.migrate_perfil_to_json import migrate
        migrate(clean_data_dir, dry_run=False)
        md5_before = _md5(perfil_path)

        pdf_path = str(sandbox_dir / "input_valid.pdf")
        extract_result = _run_extract(pdf_path)
        assert extract_result.returncode == 0
        extract_output = json.loads(extract_result.stdout)

        fields_file = _simulate_agent_extraction(
            extract_output["text"], sandbox_dir
        )
        apply_result = _run_apply(str(fields_file), str(clean_data_dir))
        assert apply_result.returncode == 0

        md5_after = _md5(perfil_path)
        assert md5_before != md5_after, (
            "perfil.json was NOT rewritten — same MD5 before and after update."
        )


# =========================================================================== #
#  Reconstructor Unit Tests
# =========================================================================== #


class TestReconstructor:
    """Unit tests for reconstruct_profile()."""

    def test_reconstructor_writes_complete_json(self):
        fields = {
            "nombre": "Test User",
            "resumen": "A short summary.",
            "linkedin": "https://linkedin.com/in/testuser",
            "github": "https://github.com/testuser",
            "telefono": "+57 300 0000000",
            "correo": "test@example.com",
            "cv_url": "",
            "experiencia": "Dev at Acme (2020-2025)",
            "educacion": "Uni (2015-2020)",
            "skills": "Python, Go",
            "sector": "Backend",
        }
        result = reconstructor.reconstruct_profile(fields, source_pdf="test.pdf")
        perfil = result["perfil_content"]

        assert isinstance(perfil, dict)
        assert perfil["nombre"] == "Test User"
        assert perfil["correo"] == "test@example.com"
        assert perfil["experiencia"] == "Dev at Acme (2020-2025)"
        assert perfil["skills"] == "Python, Go"
        assert perfil["fuente"] == "test.pdf"
        assert "generated_at" in perfil
        assert "extras" in perfil
        assert "sector" in perfil["extras"]

    def test_reconstructor_marks_missing_fields(self):
        fields = {"nombre": "Ana Minimal", "correo": "ana@example.com"}
        result = reconstructor.reconstruct_profile(fields, source_pdf="test.pdf")
        perfil = result["perfil_content"]

        assert perfil["nombre"] == "Ana Minimal"
        assert perfil["experiencia"] is None
        assert perfil["educacion"] is None
        assert perfil["skills"] is None

        for expected_missing in ("experiencia", "educacion", "skills", "resumen"):
            assert expected_missing in result["campos_no_encontrados"]

    def test_reconstructor_does_not_consult_old_profile(self):
        fields = {
            "nombre": "Snapshot User", "resumen": "Test.",
            "experiencia": "Work.", "educacion": "School.", "skills": "Code.",
        }
        result = reconstructor.reconstruct_profile(fields, source_pdf="snapshot.pdf")
        perfil = result["perfil_content"]

        assert perfil["nombre"] == "Snapshot User"
        all_values = json.dumps(perfil)
        assert "Julio" not in all_values
        assert "Támara" not in all_values

    def test_reconstructor_accepts_list_extras(self):
        """Non-canonical fields with list/array values must appear in extras."""
        fields = {
            "nombre": "Test User",
            "correo": "test@example.com",
            "certificaciones": ["AWS SA", "CKAD", "Terraform Associate"],
            "idiomas": ["Español nativo", "Inglés C1"],
        }
        result = reconstructor.reconstruct_profile(fields, source_pdf="test.pdf")
        perfil = result["perfil_content"]

        assert "extras" in perfil
        assert perfil["extras"]["certificaciones"] == ["AWS SA", "CKAD", "Terraform Associate"]
        assert perfil["extras"]["idiomas"] == ["Español nativo", "Inglés C1"]

    def test_reconstructor_filters_none_extras(self):
        """None-valued extras must be excluded."""
        fields = {
            "nombre": "Test User",
            "correo": "test@example.com",
            "certificaciones": None,
            "idiomas": "",
        }
        result = reconstructor.reconstruct_profile(fields, source_pdf="test.pdf")
        perfil = result["perfil_content"]

        if "extras" in perfil:
            assert "certificaciones" not in perfil["extras"]
            assert "idiomas" not in perfil["extras"]


# =========================================================================== #
#  ATS Fidelity Test
# =========================================================================== #


class TestATSFidelity:
    """Tests that prove cv-update never merges old and new CV data."""

    def test_two_different_cvs_do_not_merge(self, clean_data_dir, sandbox_dir):
        """Write 'backend' old perfil, then update with 'frontend' CV.

        Final perfil.json must NOT contain backend content from the old perfil.
        """
        perfil_json_path = clean_data_dir / "perfil.json"

        # Step 1: Write the synthetic "old backend" perfil as JSON.
        old_data = {
            "nombre": "Carlos Backend López",
            "resumen": "Desarrollador Backend con 8 años de experiencia.",
            "linkedin": "https://linkedin.com/in/carlos-backend",
            "github": "https://github.com/carlos-backend",
            "telefono": "+57 300 1111111",
            "correo": "carlos.backend@example.com",
            "experiencia": "TechCorp Backend Division\nBackend Lead 2020 – 2025",
            "educacion": "Ingeniería de Sistemas — Universidad Nacional",
            "skills": "Java, Spring Boot, PostgreSQL",
            "fuente": "old_cv.pdf",
            "generated_at": "2025-01-01T00:00:00Z",
        }
        perfil_json_path.write_text(json.dumps(old_data, indent=2), encoding="utf-8")
        md5_old = _md5(perfil_json_path)

        # Step 2: Create a synthetic "frontend" PDF from FRONTEND_CV_TEXT.
        frontend_pdf = sandbox_dir / "frontend_cv.pdf"
        fitz = pytest.importorskip("fitz")
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), FRONTEND_CV_TEXT)
        doc.save(str(frontend_pdf))
        doc.close()

        # Step 3: Extract from frontend PDF.
        extract_result = _run_extract(str(frontend_pdf))
        assert extract_result.returncode == 0
        extract_output = json.loads(extract_result.stdout)

        # Step 4: Simulate agent extracting fields.
        fields_file = _simulate_agent_extraction(
            extract_output["text"], sandbox_dir
        )

        # Step 5: Apply extracted fields.
        apply_result = _run_apply(str(fields_file), str(clean_data_dir))
        assert apply_result.returncode == 0

        # Step 6: Verify no backend content leaked.
        final_data = json.loads(perfil_json_path.read_text(encoding="utf-8"))
        final_content = json.dumps(final_data)

        backend_markers = [
            "Carlos Backend López",
            "Spring Boot",
            "TechCorp Backend Division",
            "carlos.backend@example.com",
        ]
        for marker in backend_markers:
            assert marker not in final_content, (
                f"Old backend perfil content leaked: '{marker}'"
            )

        assert "Laura Frontend" in final_content or "Frontend" in final_content, (
            "New frontend CV content not found in final perfil.json."
        )
        assert _md5(perfil_json_path) != md5_old, "perfil.json was NOT rewritten."


# =========================================================================== #
#  Data Integrity Test
# =========================================================================== #


class TestDataIntegrity:
    """Verify the real cv-pilot-agent/data/ directory is never modified."""

    def test_no_data_dir_pollution(self):
        for fname, expected_md5 in REAL_DATA_MD5.items():
            real_file = _REAL_DATA_DIR / fname
            assert real_file.exists(), f"data/{fname} was deleted!"
            actual_md5 = _md5(real_file)
            assert actual_md5 == expected_md5, (
                f"data/{fname} was modified! "
                f"Expected {expected_md5}, got {actual_md5}"
            )
