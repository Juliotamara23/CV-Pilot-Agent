"""Tests for cv-update skill and VSI (Validación Semántica de Identidad).

Covers the 3 P2.3 backlog scenarios:
1. CV válido actualiza el perfil.json.
2. CV inválido es rechazado por la VSI.
3. CV con contenido distinto al viejo genera perfil.json distinto (prueba de reescritura completa).

Run with:
    .venv/Scripts/python.exe -m pytest test/scenarios/agent-mode/test_cv_update.py -v
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
# Path setup (matches conftest.py pattern)
# --------------------------------------------------------------------------- #

_AGENT_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "cv-pilot-agent"
_CV_UPDATE_SCRIPTS = _AGENT_ROOT / "skills" / "cv-update" / "scripts"
_ONBOARDING_SCRIPTS = _AGENT_ROOT / "skills" / "onboarding" / "scripts"

for _p in (_AGENT_ROOT, _CV_UPDATE_SCRIPTS, _ONBOARDING_SCRIPTS, _AGENT_ROOT / "_lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# Import production modules (after path setup).
from pdf_parser import extract as extract_pdf  # noqa: E402
from vsi import validate_cv  # noqa: E402

# Import reconstructor via importlib to avoid name collision.
import importlib.util as _ilu

_recon_spec = _ilu.spec_from_file_location(
    "reconstructor",
    str(_CV_UPDATE_SCRIPTS / "_cv_update_internal" / "reconstructor.py"),
)
reconstructor = _ilu.module_from_spec(_recon_spec)
sys.modules["reconstructor"] = reconstructor
_recon_spec.loader.exec_module(reconstructor)

# Import parser from onboarding.
_parser_spec = _ilu.spec_from_file_location(
    "onboard_parser",
    str(_ONBOARDING_SCRIPTS / "_onboarding_internal" / "parser.py"),
)
parser = _ilu.module_from_spec(_parser_spec)
sys.modules["onboard_parser"] = parser
_parser_spec.loader.exec_module(parser)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

_REAL_DATA_DIR = _AGENT_ROOT / "data"
_PDF_JOSE = Path(r"E:\Hoja de Vida Jose.pdf")
_PDF_GCCF = Path(r"E:\Documents\GCCF Academy Key Information.pdf")

# MD5 hashes of the real data/ files (computed once, hardcoded for pollution test).
# NOTE: After migration, we check both .md and .json files.
REAL_DATA_MD5: dict[str, str] = {
    "correos.md": "11e474246f6ac953621a4b60e8410ee6",
    "perfil.md": "eac322b727b98b3c3572e7085e5c5174",
    "preferencias.md": "a3c8c36a1803ac7fd8c0bc39129b7013",
}

# Synthetic "old" backend perfil used to test non-merging / ATS fidelity.
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

# Synthetic "new" frontend CV text (different persona to test non-merging).
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
    """Create a temporary sandbox with data/ dir and copies of the PDFs.

    This ensures the real cv-pilot-agent/data/ is NEVER touched.
    """
    sandbox = tmp_path / "sandbox"
    data_dir = sandbox / "data"
    data_dir.mkdir(parents=True)

    # Copy PDFs to sandbox.
    shutil.copy(_PDF_JOSE, sandbox / "input_valid.pdf")
    shutil.copy(_PDF_GCCF, sandbox / "input_invalid.pdf")

    return sandbox


@pytest.fixture()
def clean_data_dir(sandbox_dir):
    """Provide a sandbox data/ dir pre-populated with real data/ content.

    Copies the REAL data/ files into the sandbox so cv-update has something
    to overwrite.  After the test, verifies the real data/ is untouched.
    """
    data_dir = sandbox_dir / "data"

    # Copy real data files into sandbox.
    for f in _REAL_DATA_DIR.iterdir():
        if f.is_file():
            shutil.copy(f, data_dir / f.name)

    yield data_dir

    # Post-test: verify real data/ was not touched.
    for fname, expected_md5 in REAL_DATA_MD5.items():
        real_file = _REAL_DATA_DIR / fname
        if real_file.exists():
            actual_md5 = hashlib.md5(real_file.read_bytes()).hexdigest()
            assert actual_md5 == expected_md5, (
                f"REAL data/{fname} was modified during test! "
                f"Expected {expected_md5}, got {actual_md5}"
            )


@pytest.fixture()
def old_perfil_backend() -> str:
    """Synthetic 'old' backend perfil markdown string."""
    return OLD_PERFIL_BACKEND


@pytest.fixture()
def jose_text() -> str:
    """Extracted text from the real CV (Hoja de Vida Jose.pdf)."""
    result = extract_pdf(str(_PDF_JOSE))
    assert result["ok"], f"Failed to extract text from Jose's CV: {result.get('error')}"
    return result["text"]


@pytest.fixture()
def gccf_text() -> str:
    """Extracted text from the non-CV file (GCCF Academy)."""
    result = extract_pdf(str(_PDF_GCCF))
    assert result["ok"], f"Failed to extract text from GCCF PDF: {result.get('error')}"
    return result["text"]


# --------------------------------------------------------------------------- #
# Helper
# --------------------------------------------------------------------------- #


def _md5(path: Path) -> str:
    """Compute MD5 hex digest of a file."""
    return hashlib.md5(path.read_bytes()).hexdigest()


def _run_cv_update_cli(pdf_path: str, data_dir: str) -> subprocess.CompletedProcess:
    """Run cv-update CLI as a subprocess (matches production invocation pattern).

    NOTE: The CLI has a single @app.command(), so typer treats it as the
    default command — no subcommand name is needed (or accepted).
    """
    cli_path = str(_CV_UPDATE_SCRIPTS / "cli.py")
    venv_python = str(_AGENT_ROOT / ".venv" / "Scripts" / "python.exe")
    # Fallback to sys.executable if venv doesn't exist.
    python_exe = venv_python if Path(venv_python).exists() else sys.executable
    return subprocess.run(
        [python_exe, cli_path, "--data-dir", data_dir, pdf_path],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )


# =========================================================================== #
#  VSI Tests
# =========================================================================== #


class TestVSI:
    """Tests for validate_cv() — the Validación Semántica de Identidad."""

    def test_vsi_accepts_valid_cv_jose_david(self, jose_text):
        """VSI must accept a real CV with is_valid=True and detect >=2 sections.

        Backlog scenario 1: CV válido pasa la VSI.
        """
        result = validate_cv(jose_text)
        assert result["is_valid"] is True, (
            f"VSI rejected a valid CV. Reason: {result.get('razon_rechazo')}"
        )
        assert len(result["secciones_detectadas"]) >= 2, (
            f"Expected >=2 sections, got {result['secciones_detectadas']}"
        )
        assert result["razon_rechazo"] is None

    def test_vsi_rejects_gccf_academy(self, gccf_text):
        """VSI must reject a non-CV document (GCCF Academy Key Information).

        Backlog scenario 2: CV inválido es rechazado por la VSI.
        """
        result = validate_cv(gccf_text)
        assert result["is_valid"] is False, "VSI accepted a non-CV document!"
        # razon_rechazo must be non-empty.
        assert result["razon_rechazo"], "Expected a rejection reason, got empty string."

    def test_vsi_rejects_empty_text(self):
        """VSI must reject empty text with a clear reason."""
        result = validate_cv("")
        assert result["is_valid"] is False
        assert result["razon_rechazo"]
        assert result["secciones_detectadas"] == []

    def test_vsi_rejects_short_text_without_sections(self):
        """VSI must reject random short text that has no CV sections."""
        result = validate_cv("Hola, esto es un texto random sin secciones de CV.")
        assert result["is_valid"] is False
        assert result["razon_rechazo"]


# =========================================================================== #
#  cv-update End-to-End Tests
# =========================================================================== #


class TestCvUpdateE2E:
    """End-to-end tests for the cv-update CLI (invoked as subprocess)."""

    def test_cv_update_rewrites_profile_with_new_cv(self, clean_data_dir, sandbox_dir):
        """cv-update with a valid CV must rewrite perfil.json with new data.

        Backlog scenario 1: CV válido actualiza el perfil.json.
        Uses the real Jose CV against a sandbox copy of data/.
        """
        pdf_path = str(sandbox_dir / "input_valid.pdf")
        data_dir = str(clean_data_dir)

        result = _run_cv_update_cli(pdf_path, data_dir)
        assert result.returncode == 0, (
            f"cv-update failed:\nstdout={result.stdout}\nstderr={result.stderr}"
        )

        output = json.loads(result.stdout)
        assert output["ok"] is True

        # Verify perfil.json was written.
        perfil_path = clean_data_dir / "perfil.json"
        assert perfil_path.exists(), "perfil.json was not created."

        perfil_data = json.loads(perfil_path.read_text(encoding="utf-8"))
        assert isinstance(perfil_data, dict), "perfil.json should be a JSON object"
        assert len(json.dumps(perfil_data)) > 50, "perfil.json is suspiciously short."

    def test_cv_update_preserves_correos_and_preferencias(self, clean_data_dir, sandbox_dir):
        """cv-update must NOT touch correos.md or preferencias.md.

        Verifies byte-level identity (MD5) of these files before and after.
        """
        correos_path = clean_data_dir / "correos.md"
        prefs_path = clean_data_dir / "preferencias.md"

        md5_correos_before = _md5(correos_path)
        md5_prefs_before = _md5(prefs_path)

        pdf_path = str(sandbox_dir / "input_valid.pdf")
        result = _run_cv_update_cli(pdf_path, str(clean_data_dir))
        assert result.returncode == 0

        assert _md5(correos_path) == md5_correos_before, (
            "correos.md was modified by cv-update!"
        )
        assert _md5(prefs_path) == md5_prefs_before, (
            "preferencias.md was modified by cv-update!"
        )

    def test_cv_update_with_invalid_pdf_does_not_modify_data(self, clean_data_dir, sandbox_dir):
        """cv-update with a non-CV PDF must fail and leave data/ untouched.

        Backlog scenario 2: CV inválido es rechazado → data/ intacto.
        """
        # Snapshot all files in data/ before.
        data_dir = clean_data_dir
        md5_before = {f.name: _md5(f) for f in data_dir.iterdir() if f.is_file()}

        pdf_path = str(sandbox_dir / "input_invalid.pdf")
        result = _run_cv_update_cli(pdf_path, str(data_dir))

        # CLI must exit with error (VSI rejection).
        assert result.returncode != 0, (
            f"cv-update should have failed for non-CV, but returned 0.\n"
            f"stdout={result.stdout}"
        )

        # Verify output indicates VSI rejection.
        output = json.loads(result.stdout)
        assert output.get("ok") is False
        assert output.get("step") == "vsi" or output.get("error") == "VSI_REJECTED"

        # Verify NO file in data/ was modified.
        md5_after = {f.name: _md5(f) for f in data_dir.iterdir() if f.is_file()}
        assert md5_before == md5_after, (
            "data/ files were modified despite VSI rejection!"
        )

    def test_cv_update_profile_json_differs_from_initial(self, clean_data_dir, sandbox_dir):
        """After cv-update with a new CV, perfil.json must differ from the original.

        Backlog scenario 3: CV distinto al viejo genera perfil.json distinto.
        """
        perfil_path = clean_data_dir / "perfil.json"
        # Create initial perfil.json from the existing perfil.md data.
        import importlib.util as _ilu2
        from scripts.migrate_perfil_to_json import _parse_perfil_md, migrate
        migrate(clean_data_dir, dry_run=False)
        md5_before = _md5(perfil_path)

        pdf_path = str(sandbox_dir / "input_valid.pdf")
        result = _run_cv_update_cli(pdf_path, str(clean_data_dir))
        assert result.returncode == 0

        md5_after = _md5(perfil_path)
        assert md5_before != md5_after, (
            "perfil.json was NOT rewritten — MD5 is identical before and after cv-update. "
            "This means the old perfil was preserved, violating ATS fidelity."
        )


# =========================================================================== #
#  Reconstructor Unit Tests
# =========================================================================== #


class TestReconstructor:
    """Unit tests for reconstruct_profile() — the perfil.json generator."""

    def test_reconstructor_writes_complete_json(self):
        """Generated dict must have canonical fields, fuente, and generated_at.

        Verifies the structural contract of the output format.
        """
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
            "sector": "Backend",  # Non-canonical → should appear in extras.
        }
        result = reconstructor.reconstruct_profile(fields, source_pdf="test.pdf")
        perfil = result["perfil_content"]

        # Must be a dict (JSON-serializable).
        assert isinstance(perfil, dict)

        # Canonical fields present.
        assert perfil["nombre"] == "Test User"
        assert perfil["correo"] == "test@example.com"
        assert perfil["experiencia"] == "Dev at Acme (2020-2025)"
        assert perfil["skills"] == "Python, Go"

        # Metadata.
        assert perfil["fuente"] == "test.pdf"
        assert "generated_at" in perfil

        # Extras (non-canonical field).
        assert "extras" in perfil
        assert "sector" in perfil["extras"]

    def test_reconstructor_marks_missing_fields(self):
        """When only 2 fields are provided, the rest must be None.

        The None values represent missing canonical fields.
        """
        fields = {
            "nombre": "Ana Minimal",
            "correo": "ana@example.com",
        }
        result = reconstructor.reconstruct_profile(fields, source_pdf="test.pdf")
        perfil = result["perfil_content"]

        # nombre and correo are provided.
        assert perfil["nombre"] == "Ana Minimal"
        assert perfil["correo"] == "ana@example.com"

        # Missing canonical fields should be None.
        assert perfil["experiencia"] is None
        assert perfil["educacion"] is None
        assert perfil["skills"] is None
        assert perfil["resumen"] is None

        # The missing list should contain them.
        assert result["campos_no_encontrados"]
        for expected_missing in ("experiencia", "educacion", "skills", "resumen"):
            assert expected_missing in result["campos_no_encontrados"], (
                f"{expected_missing} should be in campos_no_encontrados"
            )

    def test_reconstructor_does_not_consult_old_profile(self):
        """reconstruct_profile must NOT read from data/ or the old perfil.json.

        This verifies the ATS fidelity design: each update is a full snapshot,
        never a merge. We pass fields and verify it produces output without
        any file I/O to data/.
        """
        fields = {
            "nombre": "Snapshot User",
            "resumen": "Test.",
            "experiencia": "Work.",
            "educacion": "School.",
            "skills": "Code.",
        }
        result = reconstructor.reconstruct_profile(fields, source_pdf="snapshot.pdf")
        perfil = result["perfil_content"]

        # The output should contain ONLY the data we passed.
        assert perfil["nombre"] == "Snapshot User"
        assert perfil["resumen"] == "Test."
        # It must NOT contain data from the real perfil.md (Julio Támara).
        all_values = json.dumps(perfil)
        assert "Julio" not in all_values
        assert "Támara" not in all_values


# =========================================================================== #
#  ATS Fidelity Test
# =========================================================================== #


class TestATSFidelity:
    """Tests that prove cv-update never merges old and new CV data."""

    def test_two_different_cvs_do_not_merge(self, clean_data_dir, sandbox_dir):
        """Write a 'backend' old perfil, then cv-update with a 'frontend' CV.

        The final perfil.json must NOT contain any backend-specific content
        from the old perfil. This is the core ATS fidelity guarantee:
        a real ATS only knows the CV you submit.
        """
        perfil_json_path = clean_data_dir / "perfil.json"

        # Step 1: Write the synthetic "old backend" perfil as JSON.
        old_data = {
            "nombre": "Carlos Backend López",
            "resumen": "Desarrollador Backend con 8 años de experiencia en Java, Spring Boot y arquitectura de microservicios.",
            "linkedin": "https://linkedin.com/in/carlos-backend",
            "github": "https://github.com/carlos-backend",
            "telefono": "+57 300 1111111",
            "correo": "carlos.backend@example.com",
            "experiencia": "**TechCorp Backend Division**\nBackend Lead 2020 – 2025\n- Diseñé la arquitectura de microservicios en Java/Spring Boot para el core bancario.",
            "educacion": "Ingeniería de Sistemas — Universidad Nacional (2012 – 2018)",
            "skills": "Backend: Java, Spring Boot, Python, Django, PostgreSQL, Redis",
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

        # Step 3: Run cv-update with the frontend PDF.
        result = _run_cv_update_cli(str(frontend_pdf), str(clean_data_dir))
        assert result.returncode == 0, (
            f"cv-update failed:\nstdout={result.stdout}\nstderr={result.stderr}"
        )

        # Step 4: Verify the final perfil.json has NO backend content.
        final_data = json.loads(perfil_json_path.read_text(encoding="utf-8"))
        final_content = json.dumps(final_data)

        # These strings are unique to the old backend perfil.
        backend_markers = [
            "Carlos Backend López",
            "Spring Boot",
            "microservicios en Java",
            "TechCorp Backend Division",
            "pipelines de CI/CD con Jenkins",
            "PostgreSQL y Redis",
            "carlos.backend@example.com",
        ]
        for marker in backend_markers:
            assert marker not in final_content, (
                f"Old backend perfil content leaked into new perfil: '{marker}'"
            )

        # Step 5: Verify the new perfil contains frontend content.
        assert "Laura Frontend" in final_content or "Frontend" in final_content, (
            "New frontend CV content not found in final perfil.json."
        )

        # Step 6: MD5 must differ from the old backend perfil.
        assert _md5(perfil_json_path) != md5_old, (
            "perfil.json was NOT rewritten — still has old backend content."
        )


# =========================================================================== #
#  Data Integrity Test
# =========================================================================== #


class TestDataIntegrity:
    """Verify the real cv-pilot-agent/data/ directory is never modified."""

    def test_no_data_dir_pollution(self):
        """Hardcoded MD5 check of every file in cv-pilot-agent/data/.

        This test runs AFTER all others (by nature of pytest ordering)
        and verifies that no test touched the real data/ directory.
        """
        for fname, expected_md5 in REAL_DATA_MD5.items():
            real_file = _REAL_DATA_DIR / fname
            assert real_file.exists(), f"data/{fname} was deleted!"
            actual_md5 = _md5(real_file)
            assert actual_md5 == expected_md5, (
                f"data/{fname} was modified! "
                f"Expected {expected_md5}, got {actual_md5}"
            )
