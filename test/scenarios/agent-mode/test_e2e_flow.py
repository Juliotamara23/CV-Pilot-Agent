"""End-to-end flow tests for CV-Pilot agent pipeline.

These tests exercise the FULL agent flow from start to finish, not just
isolated components. They prove the deterministic scripts can carry the
process end-to-end so the agent (LLM) can trust them.

Tests cover:
1. Happy path with manual job source
2. Happy path with apify job source (using fixtures, no new runs)
3. Error path with incomplete manual source
4. Error path with apify error items
5. Full flow with onboarding then sourcing (extended primitive test)

Run with:
    cv-pilot-agent/.venv/Scripts/python.exe -m pytest test/scenarios/agent-mode/test_e2e_flow.py -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Make the agent root and apify scripts importable.
_AGENT_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "cv-pilot-agent"
_APIFY_SCRIPTS = _AGENT_ROOT / "skills" / "apify" / "scripts"
for _p in (_AGENT_ROOT, _APIFY_SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _run_query(query_script: str, env: dict, *args: str) -> subprocess.CompletedProcess:
    """Run query.py with the given args and return the process result."""
    return subprocess.run(
        [sys.executable, query_script, *args],
        capture_output=True,
        text=True,
        env=env,
        encoding="utf-8",
    )


def _run_cli(script: str, env: dict, *args: str) -> subprocess.CompletedProcess:
    """Run an arbitrary CLI script with the given args."""
    return subprocess.run(
        [sys.executable, script, *args],
        capture_output=True,
        text=True,
        env=env,
        encoding="utf-8",
    )


def _insert_manual_job(query_script: str, env: dict, **kwargs) -> str:
    """Insert a manual job and return its hash."""
    args = [
        "job", "insert",
        "--company", kwargs.get("company", "Acme Corp"),
        "--position", kwargs.get("position", "Senior Developer"),
        "--location", kwargs.get("location", "Bogota, Colombia"),
        "--source", kwargs.get("source", "manual"),
    ]
    if kwargs.get("public_date"):
        args.extend(["--public-date", kwargs["public_date"]])
    if kwargs.get("url"):
        args.extend(["--url", kwargs["url"]])
    if kwargs.get("salary"):
        args.extend(["--salary", kwargs["salary"]])
    if kwargs.get("description"):
        args.extend(["--description", kwargs["description"]])

    proc = _run_query(query_script, env, *args)
    assert proc.returncode == 0, f"Job insert failed: {proc.stderr}"
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    return data["hash"]


def _insert_analysis(query_script: str, env: dict, job_hash: str, **kwargs) -> str:
    """Insert an analysis and return its id."""
    proc = _run_query(
        query_script, env,
        "analysis", "insert",
        "--job-hash", job_hash,
        "--percentage", str(kwargs.get("percentage", 80)),
        "--comparativa", kwargs.get("comparativa", "Strong match"),
        "--observaciones", kwargs.get("observaciones", "Good fit"),
        "--verdict", kwargs.get("verdict", "Apto"),
        "--tldr", kwargs.get("tldr", "Apply now"),
        "--contact-method", kwargs.get("contact_method", "email"),
    )
    assert proc.returncode == 0, f"Analysis insert failed: {proc.stderr}"
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    return data["analysis_id"]


def _format_report(formatos_script: str, env: dict, job_hash: str) -> str:
    """Run formatos CLI and return the output."""
    proc = _run_cli(formatos_script, env, "--job", job_hash)
    assert proc.returncode == 0, f"Format report failed: {proc.stderr}"
    return proc.stdout


def _generate_email(mimetismo_script: str, env: dict, job_hash: str, body_file: str) -> dict:
    """Run mimetismo CLI in question mode and return the JSON envelope."""
    proc = _run_cli(
        mimetismo_script, env,
        "question", "--job", job_hash, "--body-file", body_file,
    )
    assert proc.returncode == 0, f"Email generation failed: {proc.stderr}"
    return json.loads(proc.stdout)


# --------------------------------------------------------------------------- #
# Test 1: Full happy path with manual job source
# --------------------------------------------------------------------------- #

def test_e2e_happy_manual_source(tmp_db, query_script):
    """Full happy path: manual job → analysis → format report → email draft."""
    env = os.environ.copy()
    formatos_script = str(_AGENT_ROOT / "skills" / "formatos" / "scripts" / "cli.py")
    mimetismo_script = str(_AGENT_ROOT / "skills" / "mimetismo" / "scripts" / "cli.py")

    # Step 1: Insert a manual job
    job_hash = _insert_manual_job(
        query_script, env,
        company="TechCorp",
        position="Full Stack Developer",
        location="Medellin, Colombia",
        public_date="2026-07-08",
        url="https://example.com/job/123",
        salary="$5000 USD",
        description="Building web applications with React and Python.",
    )

    # Step 2: Verify job in DB via list
    proc = _run_query(query_script, env, "job", "list", "--status", "new")
    assert proc.returncode == 0
    listed = json.loads(proc.stdout)
    assert listed["count"] == 1
    assert listed["jobs"][0]["job_hash"] == job_hash
    assert listed["jobs"][0]["company"] == "TechCorp"

    # Step 3: Insert analysis
    analysis_id = _insert_analysis(
        query_script, env, job_hash,
        percentage=85,
        comparativa="Strong match for full stack role",
        observaciones="React + Python experience aligns well",
        verdict="Apto",
        tldr="Strong candidate - apply immediately",
        contact_method="email",
    )

    # Step 4: Verify analysis in DB
    proc = _run_query(query_script, env, "analysis", "get", "--job-hash", job_hash)
    assert proc.returncode == 0
    analysis_data = json.loads(proc.stdout)
    assert analysis_data["ok"] is True
    assert analysis_data["analysis"]["percentage"] == 85.0
    assert analysis_data["analysis"]["verdict"] == "Apto"

    # Step 5: Verify job status changed to 'analyzed'
    proc = _run_query(query_script, env, "job", "get", "--hash", job_hash)
    assert proc.returncode == 0
    job_data = json.loads(proc.stdout)
    assert job_data["job"]["status"] == "analyzed"

    # Step 6: Format report
    report = _format_report(formatos_script, env, job_hash)
    assert "TechCorp" in report or "techcorp" in report.lower()
    assert "Apto" in report or "apto" in report.lower()

    # Step 7: Email generation (question mode for portal)
    body_content = "<p>I am interested in this position.</p>"
    body_file = tmp_db.parent / "body.html"
    body_file.write_text(body_content, encoding="utf-8")

    email_result = _generate_email(mimetismo_script, env, job_hash, str(body_file))
    assert email_result["ok"] is True
    assert email_result["mode"] == "question"
    assert "text" in email_result


# --------------------------------------------------------------------------- #
# Test 2: Happy path with apify job source (using fixtures)
# --------------------------------------------------------------------------- #

def test_e2e_happy_apify_source(tmp_db, query_script):
    """Happy path with apify-sourced data from LinkedIn fixture."""
    env = os.environ.copy()
    formatos_script = str(_AGENT_ROOT / "skills" / "formatos" / "scripts" / "cli.py")
    mimetismo_script = str(_AGENT_ROOT / "skills" / "mimetismo" / "scripts" / "cli.py")

    # Step 1: Load LinkedIn fixture
    fixtures_dir = Path(__file__).resolve().parent.parent.parent / "fixtures" / "apify"
    linkedin_fixture = fixtures_dir / "linkedin.json"
    assert linkedin_fixture.is_file(), f"Fixture not found: {linkedin_fixture}"
    raw_items = json.loads(linkedin_fixture.read_text(encoding="utf-8"))
    assert len(raw_items) >= 1, "LinkedIn fixture is empty"

    # Step 2: Normalize using LinkedinAdapter
    from platforms.linkedin import LinkedinAdapter
    adapter = LinkedinAdapter()
    jobs = adapter.normalize_output(raw_items)
    assert len(jobs) >= 1, "No jobs normalized from fixture"

    # Step 3: Write jobs to a temp file for insert-batch
    batch_file = tmp_db.parent / "linkedin_batch.json"
    batch_data = [job.model_dump() for job in jobs]
    batch_file.write_text(json.dumps(batch_data, ensure_ascii=False), encoding="utf-8")

    # Step 4: Insert via query.py job insert-batch
    proc = _run_query(query_script, env, "job", "insert-batch", "--file", str(batch_file))
    assert proc.returncode == 0, f"Batch insert failed: {proc.stderr}"
    batch_result = json.loads(proc.stdout)
    assert batch_result["persisted"]["inserted"] >= 1

    # Step 5: List jobs and pick the first one
    proc = _run_query(query_script, env, "job", "list", "--status", "new", "--limit", "1")
    assert proc.returncode == 0
    listed = json.loads(proc.stdout)
    assert listed["count"] >= 1
    job_hash = listed["jobs"][0]["job_hash"]

    # Step 6: Insert analysis
    _insert_analysis(
        query_script, env, job_hash,
        percentage=75,
        comparativa="Good match for senior role",
        observaciones="LinkedIn sourced, matches tech stack",
        verdict="Apto con reservas",
        tldr="Consider applying",
        contact_method="email",
    )

    # Step 7: Format report
    report = _format_report(formatos_script, env, job_hash)
    assert len(report) > 0, "Report is empty"

    # Step 8: Email generation
    body_content = "<p>I am interested in this LinkedIn-sourced position.</p>"
    body_file = tmp_db.parent / "body_linkedin.html"
    body_file.write_text(body_content, encoding="utf-8")

    email_result = _generate_email(mimetismo_script, env, job_hash, str(body_file))
    assert email_result["ok"] is True
    assert "text" in email_result


# --------------------------------------------------------------------------- #
# Test 3: Error path with incomplete manual source
# --------------------------------------------------------------------------- #

def test_e2e_error_incomplete_manual_source(tmp_db, query_script):
    """Error path: non-existent job hash, analysis without job, format without job."""
    env = os.environ.copy()
    formatos_script = str(_AGENT_ROOT / "skills" / "formatos" / "scripts" / "cli.py")

    # Step 1: Try to get a non-existent job hash
    proc = _run_query(
        query_script, env,
        "job", "get", "--hash", "nonexistent_hash_12345",
    )
    assert proc.returncode == 1, "Expected non-zero exit for non-existent job"
    error_data = json.loads(proc.stderr)
    assert error_data["ok"] is False
    assert "JOB_NOT_FOUND" in error_data.get("code", "")

    # Verify DB is empty
    proc = _run_query(query_script, env, "job", "list")
    assert proc.returncode == 0
    listed = json.loads(proc.stdout)
    assert listed["count"] == 0, "DB should be empty"

    # Step 2: Try to insert analysis for non-existent job
    proc = _run_query(
        query_script, env,
        "analysis", "insert",
        "--job-hash", "nonexistent_hash_12345",
        "--percentage", "80",
        "--comparativa", "test",
        "--observaciones", "test",
        "--verdict", "test",
        "--tldr", "test",
    )
    assert proc.returncode == 1, "Expected non-zero exit for analysis without job"
    error_data = json.loads(proc.stderr)
    assert error_data["ok"] is False
    assert "JOB_NOT_FOUND" in error_data.get("code", "")

    # Step 3: Insert a valid job
    job_hash = _insert_manual_job(
        query_script, env,
        company="ValidCorp",
        position="Engineer",
        location="Remote",
    )

    # Step 4: Try to get analysis for job that has no analysis yet
    proc = _run_query(
        query_script, env,
        "analysis", "get", "--job-hash", job_hash,
    )
    assert proc.returncode == 1, "Expected non-zero exit for job without analysis"
    error_data = json.loads(proc.stderr)
    assert error_data["ok"] is False
    assert "ANALYSIS_NOT_FOUND" in error_data.get("code", "")

    # Step 5: Try to format a job that has no analysis
    proc = _run_cli(
        formatos_script, env,
        "--job", job_hash,
    )
    assert proc.returncode == 1, "Expected non-zero exit for format without analysis"
    error_data = json.loads(proc.stderr)
    assert error_data["ok"] is False

    # Step 6: Try to format a completely non-existent job hash
    proc = _run_cli(
        formatos_script, env,
        "--job", "nonexistent_hash_12345",
    )
    assert proc.returncode == 1, "Expected non-zero exit for non-existent job"
    error_data = json.loads(proc.stderr)
    assert error_data["ok"] is False
    assert "JOB_NOT_FOUND" in error_data.get("code", "") or "NOT_FOUND" in error_data.get("code", "")


# --------------------------------------------------------------------------- #
# Test 4: Error items from apify
# --------------------------------------------------------------------------- #

def test_e2e_error_apify_error_items(tmp_db, query_script):
    """Error path: apify error items are filtered, only valid jobs persist."""
    env = os.environ.copy()

    # Step 1: Build a list with 1 valid job + 1 error item
    valid_job = {
        "id": "valid_001",
        "title": "Software Engineer",
        "companyName": "GoodCorp",
        "location": "Bogota",
        "postedAt": "2026-07-08",
        "link": "https://example.com/job/valid",
        "descriptionText": "A valid job description.",
    }
    error_item = {
        "error": "FOUND_NO_RESULTS",
        "errorDescription": "No jobs found for this search query",
    }

    # Step 2: Use LinkedinAdapter to filter errors
    from platforms.linkedin import LinkedinAdapter
    adapter = LinkedinAdapter()
    valid, errors = adapter.filter_errors([valid_job, error_item])

    assert len(valid) == 1, f"Expected 1 valid item, got {len(valid)}"
    assert len(errors) == 1, f"Expected 1 error item, got {len(errors)}"
    assert errors[0]["error"] == "FOUND_NO_RESULTS"

    # Step 3: Normalize valid items
    jobs = adapter.normalize_output(valid)
    assert len(jobs) == 1

    # Step 4: Write to batch file and insert
    batch_file = tmp_db.parent / "apify_batch.json"
    batch_data = [job.model_dump() for job in jobs]
    batch_file.write_text(json.dumps(batch_data, ensure_ascii=False), encoding="utf-8")

    proc = _run_query(query_script, env, "job", "insert-batch", "--file", str(batch_file))
    assert proc.returncode == 0, f"Batch insert failed: {proc.stderr}"
    batch_result = json.loads(proc.stdout)
    assert batch_result["persisted"]["inserted"] == 1

    # Step 5: Verify only 1 job in DB
    proc = _run_query(query_script, env, "job", "list")
    assert proc.returncode == 0
    listed = json.loads(proc.stdout)
    assert listed["count"] == 1
    assert listed["jobs"][0]["company"] == "GoodCorp"

    # Step 6: Test with ONLY error items - should fail validation
    only_errors_file = tmp_db.parent / "only_errors.json"
    only_errors_file.write_text(json.dumps([error_item]), encoding="utf-8")

    proc = _run_query(query_script, env, "job", "insert-batch", "--file", str(only_errors_file))
    # The batch file contains a dict without required fields, so Pydantic will reject it
    # This should fail with VALIDATION_ERROR
    assert proc.returncode == 1, "Expected non-zero exit for all-error batch"
    error_data = json.loads(proc.stderr)
    assert error_data["ok"] is False
    assert "VALIDATION_ERROR" in error_data.get("code", "")


# --------------------------------------------------------------------------- #
# Test 5: Full flow with onboarding then sourcing (extended primitive test)
# --------------------------------------------------------------------------- #

def test_e2e_happy_with_onboarding_then_sourcing(tmp_db, query_script, tmp_path):
    """Full pipeline: onboarding → manual job → analysis → format → email."""
    pytest.importorskip("fitz")

    env = os.environ.copy()
    onboard_scripts = str(_AGENT_ROOT / "skills" / "onboarding" / "scripts")
    formatos_script = str(_AGENT_ROOT / "skills" / "formatos" / "scripts" / "cli.py")
    mimetismo_script = str(_AGENT_ROOT / "skills" / "mimetismo" / "scripts" / "cli.py")

    # Step 1: Generate synthetic PDF (following test_onboard.py pattern)
    import fitz
    pdf_path = tmp_path / "cv.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (72, 72),
        "Nombre: Carlos Perez\n\n"
        "Resumen\n"
        "Senior Python developer with 8 years experience.\n\n"
        "Experiencia\n"
        "Lead Dev - TechStart (2018-2026)\n"
        "- Built microservices\n"
        "- Led team of 5\n\n"
        "Educacion\n"
        "MSc Computer Science - MIT (2016)\n\n"
        "Skills\n"
        "Python, Go, Docker, Kubernetes, AWS, React\n\n"
        "Contacto\n"
        "carlos@correo.com\n"
        "+57 300 123-4567\n"
        "https://linkedin.com/in/carlosperez\n"
        "https://github.com/carlosperez",
    )
    doc.save(str(pdf_path))
    doc.close()

    # Step 2: Run onboarding CLI
    fields_data = {
        "nombre": "Carlos Perez",
        "resumen": "Senior Python developer",
        "linkedin": "https://linkedin.com/in/carlosperez",
        "github": "https://github.com/carlosperez",
        "telefono": "+57 300 123-4567",
        "correo": "carlos@correo.com",
        "cv_url": "",
        "experiencia": "Lead Dev - TechStart",
        "educacion": "MSc Computer Science - MIT",
        "skills": "Python, Go, Docker, Kubernetes, AWS, React",
        "sector": "Backend",
        "tono": "tecnico",
        "idioma": "espanol",
        "mimetismo": "si",
        "gmail_drafts": "no",
        "outlook_drafts": "no",
        "email_examples": [],
    }
    fields_file = tmp_path / "fields.json"
    fields_file.write_text(json.dumps(fields_data), encoding="utf-8")
    out_dir = tmp_path / "onboard_out"

    proc = subprocess.run(
        [
            sys.executable,
            str(_AGENT_ROOT / "skills" / "onboarding" / "scripts" / "cli.py"),
            "full",
            str(pdf_path),
            "--fields-file", str(fields_file),
            "--out-dir", str(out_dir),
        ],
        capture_output=True,
        text=True,
        env=env,
        encoding="utf-8",
    )
    assert proc.returncode == 0, f"Onboarding failed: {proc.stderr}"
    onboard_result = json.loads(proc.stdout)
    assert onboard_result["ok"] is True

    # Step 3: Verify the 3 output files exist
    assert (out_dir / "perfil.md").is_file(), "perfil.md not created"
    assert (out_dir / "correos.md").is_file(), "correos.md not created"
    assert (out_dir / "preferencias.md").is_file(), "preferencias.md not created"

    perfil_content = (out_dir / "perfil.md").read_text(encoding="utf-8")
    assert "Carlos Perez" in perfil_content

    # Step 4: Insert a manual job that matches the synthetic profile
    job_hash = _insert_manual_job(
        query_script, env,
        company="PythonShop",
        position="Senior Python Engineer",
        location="Remote",
        public_date="2026-07-08",
        url="https://example.com/python-job",
        salary="$6000 USD",
        description="Looking for senior Python developer with AWS experience.",
    )

    # Step 5: Insert analysis with 80%+ match
    _insert_analysis(
        query_script, env, job_hash,
        percentage=88,
        comparativa="Excellent match for Python senior role",
        observaciones="8 years Python, AWS, team lead experience",
        verdict="Apto",
        tldr="Perfect fit - apply immediately",
        contact_method="email",
    )

    # Step 6: Format report
    report = _format_report(formatos_script, env, job_hash)
    assert "PythonShop" in report or "pythonshop" in report.lower()
    assert "Apto" in report or "apto" in report.lower()

    # Step 7: Generate email draft
    body_content = "<p>I am very interested in the Senior Python Engineer position.</p>"
    body_file = tmp_path / "body.html"
    body_file.write_text(body_content, encoding="utf-8")

    email_result = _generate_email(mimetismo_script, env, job_hash, str(body_file))
    assert email_result["ok"] is True
    assert "text" in email_result

    # Step 8: Verify full pipeline worked - job should be analyzed
    proc = _run_query(query_script, env, "job", "get", "--hash", job_hash)
    assert proc.returncode == 0
    job_data = json.loads(proc.stdout)
    assert job_data["job"]["status"] == "analyzed"
