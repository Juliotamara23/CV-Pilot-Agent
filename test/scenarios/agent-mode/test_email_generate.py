"""Tests for `skills/mimetismo/scripts/generate.py`.

Unit tests target the pure helpers (_load_profile, _load_preferences,
_format_links, _detect_provider, _signature_footer); error tests cover the
stable error envelopes; integration tests drive the Typer app in-process
with gws/m365/pwsh + cleanup subprocess calls monkeypatched.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from _lib import db
from _lib.models import AnalysisInsert, JobInsert

# Import the generate module (it lives in a scripts dir without a parent
# package on sys.path, so insert it explicitly).
_AGENT_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "cv-pilot-agent"
_GEN_DIR = _AGENT_ROOT / "skills" / "mimetismo" / "scripts"
if str(_GEN_DIR) not in sys.path:
    sys.path.insert(0, str(_GEN_DIR))

import generate  # type: ignore  # noqa: E402


runner = CliRunner()

# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
PERFIL_MD = """# Perfil

## Identidad
- **Nombre completo:** Julio Andrés Támara Hernández
- **Resumen profesional:** Dev.

## Contacto
- **LinkedIn:** https://linkedin.com/in/example
- **GitHub:** https://github.com/example
- **WhatsApp / Teléfono:** +57 320 5551234
- **Correo electrónico:** julio@example.com
- **Link al CV:** https://drive.google.com/cv
"""


def _write_data(tmp_path: Path, preferencias: str = "gmail_drafts: no\noutlook_drafts: no\n") -> Path:
    """Create a tmp cv-pilot-agent root with data/perfil.md, preferencias.md and a
    scripts/cleanup.py stub so _cleanup() actually invokes subprocess.run (mocked)."""
    root = tmp_path / "agent-root"
    (root / "data").mkdir(parents=True)
    (root / "scripts").mkdir(parents=True)
    (root / "data" / "perfil.md").write_text(PERFIL_MD, encoding="utf-8")
    (root / "data" / "preferencias.md").write_text(preferencias, encoding="utf-8")
    (root / "scripts" / "cleanup.py").write_text("print('cleaned')\n", encoding="utf-8")
    return root


def _seed_job(contact_method: str = "email") -> str:
    res = db.insert_job(JobInsert(company="Acme", position="Backend Dev", location="Madrid"))
    job_hash = res["hash"]
    db.insert_analysis(
        AnalysisInsert(
            job_hash=job_hash, percentage=80.0, comparativa="c",
            observaciones="o", verdict="Apto", tldr="t",
            contact_method=contact_method,
        )
    )
    return job_hash


def _seed_job_no_analysis() -> str:
    return db.insert_job(JobInsert(company="Acme", position="Backend Dev", location="Madrid"))["hash"]


def _fake_run_factory(calls: list):
    """subprocess.run replacement that records calls and returns success."""
    def _fake_run(args, **kwargs):
        calls.append(list(args))
        joined = " ".join(str(a) for a in args)
        # Outlook draft is created via a PowerShell Graph POST (Invoke-RestMethod).
        stdout = "msg-graph-id-456\n" if "Invoke-RestMethod" in joined else "draft-id-123\n"
        return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")
    return _fake_run


def _patch_environment(monkeypatch, root: Path, *, which=None, run=None):
    """Point generate.py at a tmp agent root + stub provider/shell helpers."""
    monkeypatch.setattr(generate, "_AGENT_ROOT", root)
    if which is not None:
        monkeypatch.setattr(generate.shutil, "which", which)
    if run is not None:
        monkeypatch.setattr(generate.subprocess, "run", run)


# --------------------------------------------------------------------------- #
# 3.1 Unit tests
# --------------------------------------------------------------------------- #
class TestLoadProfile:
    def test_parses_contact_fields(self, tmp_path, monkeypatch):
        root = _write_data(tmp_path)
        monkeypatch.setattr(generate, "_AGENT_ROOT", root)
        profile = generate._load_profile()
        assert profile["name"] == "Julio Andrés Támara Hernández"
        assert profile["linkedin"] == "https://linkedin.com/in/example"
        assert profile["github"] == "https://github.com/example"
        assert profile["whatsapp"] == "+57 320 5551234"
        assert profile["email"] == "julio@example.com"
        assert profile["cv_url"] == "https://drive.google.com/cv"

    def test_missing_file_returns_none_profile(self, tmp_path, monkeypatch):
        root = tmp_path / "no-data-root"
        root.mkdir()
        monkeypatch.setattr(generate, "_AGENT_ROOT", root)
        profile = generate._load_profile()
        assert profile["name"] is None
        assert profile["github"] is None


class TestLoadPreferences:
    @pytest.mark.parametrize("token", ["sí", "si", "yes", "true", "1"])
    def test_true_tokens(self, tmp_path, monkeypatch, token):
        root = _write_data(tmp_path, preferencias=f"gmail_drafts: {token}\n")
        monkeypatch.setattr(generate, "_AGENT_ROOT", root)
        assert generate._load_preferences()["gmail_drafts"] is True

    @pytest.mark.parametrize("token", ["no", "false", "", "0", "n/a"])
    def test_false_tokens(self, tmp_path, monkeypatch, token):
        root = _write_data(tmp_path, preferencias=f"gmail_drafts: {token}\n")
        monkeypatch.setattr(generate, "_AGENT_ROOT", root)
        assert generate._load_preferences()["gmail_drafts"] is False

    def test_missing_file_returns_false(self, tmp_path, monkeypatch):
        root = tmp_path / "no-data"
        root.mkdir()
        monkeypatch.setattr(generate, "_AGENT_ROOT", root)
        assert generate._load_preferences() == {"gmail_drafts": False, "outlook_drafts": False}

    def test_outlook_detected(self, tmp_path, monkeypatch):
        root = _write_data(tmp_path, preferencias="outlook_drafts: sí\n")
        monkeypatch.setattr(generate, "_AGENT_ROOT", root)
        prefs = generate._load_preferences()
        assert prefs["outlook_drafts"] is True
        assert prefs["gmail_drafts"] is False


class TestDetectProvider:
    def test_override_wins(self):
        assert generate._detect_provider_optional(
            {"gmail_drafts": True, "outlook_drafts": True}, "outlook"
        ) == "outlook"

    def test_gmail_preferred_when_both_true(self):
        assert generate._detect_provider_optional(
            {"gmail_drafts": True, "outlook_drafts": True}, None
        ) == "gmail"

    def test_only_outlook(self):
        assert generate._detect_provider_optional(
            {"gmail_drafts": False, "outlook_drafts": True}, None
        ) == "outlook"

    def test_none_raises_no_provider(self):
        with pytest.raises(Exception) as exc:
            generate._detect_provider({"gmail_drafts": False, "outlook_drafts": False}, None)
        assert "NO_PROVIDER" in exc.value.code


class TestFormatLinks:
    def test_markers_replaced_with_anchors(self):
        profile = {
            "github": "https://github.com/x", "linkedin": "https://linkedin.com/in/x",
            "cv_url": "https://drive.google.com/cv", "whatsapp": "+57 320 1",
        }
        body = "Visita [github] y [linkedin]; mi [cv] o [whatsapp]."
        out = generate._format_links(body, profile)
        assert '[github]' not in out and '[linkedin]' not in out
        assert '[cv]' not in out and '[whatsapp]' not in out
        assert '<a href="https://github.com/x">GitHub</a>' in out
        assert '<a href="https://linkedin.com/in/x">LinkedIn</a>' in out
        assert '<a href="https://drive.google.com/cv">CV</a>' in out
        assert '<a href="+57 320 1">WhatsApp</a>' in out

    def test_missing_url_falls_back_to_label(self):
        out = generate._format_links("link [github]", {"github": None})
        assert out == "link GitHub"

    def test_special_chars_preserved(self):
        out = generate._format_links("ñ &aacute; &lt;script&gt; [cv]", {"cv_url": None})
        assert "ñ" in out and "&aacute;" in out and "&lt;script&gt;" in out


class TestSignatureFooter:
    def test_includes_name_and_available_links(self):
        profile = {
            "name": "Julio", "github": "https://g", "linkedin": "https://l",
            "cv_url": "https://cv", "whatsapp": None,
        }
        footer = generate._signature_footer(profile)
        assert "Julio" in footer
        assert '<a href="https://g">GitHub</a>' in footer
        assert '<a href="https://l">LinkedIn</a>' in footer
        assert '<a href="https://cv">CV</a>' in footer
        assert "WhatsApp" not in footer  # whatsapp URL was None

    def test_no_name_no_links(self):
        assert generate._signature_footer({}) == "<br><br>Saludos cordiales,<br>"


# --------------------------------------------------------------------------- #
# 3.2 Error tests
# --------------------------------------------------------------------------- #
class TestErrorEnvelopes:
    def test_portal_postulation_blocks_email(self, tmp_db, tmp_path, monkeypatch):
        root = _write_data(tmp_path, preferencias="gmail_drafts: sí\n")
        h = _seed_job(contact_method="portal")
        body = tmp_path / "body.html"; body.write_text("<p>Hola</p>", encoding="utf-8")
        _patch_environment(monkeypatch, root, which=lambda n: f"/fake/{n}")
        result = runner.invoke(generate.app, [
            "email", "--job", h, "--body-file", str(body), "--to", "rrhh@x.com",
        ])
        assert result.exit_code == 1
        payload = json.loads(result.stderr)
        assert payload["ok"] is False
        assert payload["code"] == "PORTAL_POSTULATION"

    def test_job_not_found_email(self, tmp_db, tmp_path, monkeypatch):
        root = _write_data(tmp_path)
        body = tmp_path / "body.html"; body.write_text("x", encoding="utf-8")
        _patch_environment(monkeypatch, root, which=lambda n: f"/fake/{n}")
        result = runner.invoke(generate.app, [
            "email", "--job", "deadbeef", "--body-file", str(body), "--to", "r@x.com",
        ])
        assert result.exit_code == 1
        assert json.loads(result.stderr)["code"] == "JOB_NOT_FOUND"

    def test_job_not_found_question(self, tmp_db, tmp_path, monkeypatch):
        root = _write_data(tmp_path)
        body = tmp_path / "body.html"; body.write_text("x", encoding="utf-8")
        _patch_environment(monkeypatch, root, which=lambda n: f"/fake/{n}")
        result = runner.invoke(generate.app, [
            "question", "--job", "deadbeef", "--body-file", str(body),
        ])
        assert result.exit_code == 1
        assert json.loads(result.stderr)["code"] == "JOB_NOT_FOUND"

    def test_job_not_found_cover_letter(self, tmp_db, tmp_path, monkeypatch):
        root = _write_data(tmp_path)
        body = tmp_path / "body.html"; body.write_text("x", encoding="utf-8")
        _patch_environment(monkeypatch, root, which=lambda n: f"/fake/{n}")
        result = runner.invoke(generate.app, [
            "cover-letter", "--job", "deadbeef", "--body-file", str(body),
        ])
        assert result.exit_code == 1
        assert json.loads(result.stderr)["code"] == "JOB_NOT_FOUND"

    def test_analysis_not_found_email(self, tmp_db, tmp_path, monkeypatch):
        root = _write_data(tmp_path, preferencias="gmail_drafts: sí\n")
        h = _seed_job_no_analysis()
        body = tmp_path / "body.html"; body.write_text("x", encoding="utf-8")
        _patch_environment(monkeypatch, root, which=lambda n: f"/fake/{n}")
        result = runner.invoke(generate.app, [
            "email", "--job", h, "--body-file", str(body), "--to", "r@x.com", "--provider", "gmail",
        ])
        assert result.exit_code == 1
        assert json.loads(result.stderr)["code"] == "ANALYSIS_NOT_FOUND"

    def test_analysis_not_found_cover_letter(self, tmp_db, tmp_path, monkeypatch):
        root = _write_data(tmp_path, preferencias="gmail_drafts: sí\n")
        h = _seed_job_no_analysis()
        body = tmp_path / "body.html"; body.write_text("x", encoding="utf-8")
        _patch_environment(monkeypatch, root, which=lambda n: f"/fake/{n}")
        result = runner.invoke(generate.app, [
            "cover-letter", "--job", h, "--body-file", str(body), "--provider", "gmail", "--to", "r@x.com",
        ])
        assert result.exit_code == 1
        assert json.loads(result.stderr)["code"] == "ANALYSIS_NOT_FOUND"

    def test_no_provider_email(self, tmp_db, tmp_path, monkeypatch):
        root = _write_data(tmp_path, preferencias="gmail_drafts: no\n")  # no outlook either
        h = _seed_job(contact_method="email")
        body = tmp_path / "body.html"; body.write_text("x", encoding="utf-8")
        _patch_environment(monkeypatch, root, which=lambda n: f"/fake/{n}")
        result = runner.invoke(generate.app, [
            "email", "--job", h, "--body-file", str(body), "--to", "r@x.com",
        ])
        assert result.exit_code == 1
        assert json.loads(result.stderr)["code"] == "NO_PROVIDER"

    def test_body_file_missing(self, tmp_db, tmp_path, monkeypatch):
        root = _write_data(tmp_path, preferencias="gmail_drafts: sí\n")
        h = _seed_job(contact_method="email")
        _patch_environment(monkeypatch, root, which=lambda n: f"/fake/{n}")
        result = runner.invoke(generate.app, [
            "email", "--job", h, "--body-file", str(tmp_path / "missing.html"),
            "--to", "r@x.com", "--provider", "gmail",
        ])
        assert result.exit_code == 1
        assert json.loads(result.stderr)["code"] == "BODY_FILE_MISSING"

    def test_empty_question(self, tmp_db, tmp_path, monkeypatch):
        root = _write_data(tmp_path)
        h = _seed_job(contact_method="portal")
        body = tmp_path / "q.html"; body.write_text("   \n  ", encoding="utf-8")
        _patch_environment(monkeypatch, root, which=lambda n: f"/fake/{n}")
        result = runner.invoke(generate.app, [
            "question", "--job", h, "--body-file", str(body),
        ])
        assert result.exit_code == 1
        assert json.loads(result.stderr)["code"] == "EMPTY_QUESTION"

    def test_provider_cli_missing_gmail(self, tmp_db, tmp_path, monkeypatch):
        root = _write_data(tmp_path, preferencias="gmail_drafts: sí\n")
        h = _seed_job(contact_method="email")
        body = tmp_path / "body.html"; body.write_text("x", encoding="utf-8")
        _patch_environment(monkeypatch, root, which=lambda n: None)
        result = runner.invoke(generate.app, [
            "email", "--job", h, "--body-file", str(body), "--to", "r@x.com", "--provider", "gmail",
        ])
        assert result.exit_code == 1
        assert json.loads(result.stderr)["code"] == "PROVIDER_CLI_MISSING"


# --------------------------------------------------------------------------- #
# 3.3 Integration tests (subprocess mocked)
# --------------------------------------------------------------------------- #
class TestIntegration:
    def test_email_gmail_happy_path(self, tmp_db, tmp_path, monkeypatch):
        root = _write_data(tmp_path, preferencias="gmail_drafts: sí\n")
        h = _seed_job(contact_method="email")
        body = tmp_path / "body.html"
        body.write_text(
            "<p>Hola, visita mi [github] y [linkedin].</p>", encoding="utf-8"
        )
        calls = []
        _patch_environment(monkeypatch, root, which=lambda n: f"/fake/{n}",
                           run=_fake_run_factory(calls))
        result = runner.invoke(generate.app, [
            "email", "--job", h, "--body-file", str(body), "--to", "rrhh@acme.com",
        ])
        assert result.exit_code == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["mode"] == "email"
        assert payload["provider"] == "gmail"
        assert payload["to"] == "rrhh@acme.com"
        assert payload["draft_id"] == "draft-id-123"
        assert "Postulación: Backend Dev — Acme" in payload["subject"]
        # gws draft subprocess was invoked and cleanup too
        assert any("gws" in c[0] for c in calls)
        assert any("cleanup.py" in str(c[-1]) for c in calls)
        # status updated to applied
        assert db.get_job(h)["job"]["status"] == "applied"

    def test_email_outlook_happy_path(self, tmp_db, tmp_path, monkeypatch):
        root = _write_data(tmp_path, preferencias="outlook_drafts: sí\n")
        h = _seed_job(contact_method="email")
        body = tmp_path / "body.html"; body.write_text("<p>Hola</p>", encoding="utf-8")
        calls = []
        _patch_environment(monkeypatch, root, which=lambda n: f"/fake/{n}",
                           run=_fake_run_factory(calls))
        result = runner.invoke(generate.app, [
            "email", "--job", h, "--body-file", str(body),
            "--to", "rrhh@acme.com", "--provider", "outlook",
        ])
        assert result.exit_code == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is True and payload["provider"] == "outlook"
        assert payload["draft_id"] == "msg-graph-id-456"
        # graph POST happened via a shell subprocess
        assert any("powershell" in str(c[0]).lower() or "pwsh" in str(c[0]).lower() for c in calls)
        assert db.get_job(h)["job"]["status"] == "applied"

    def test_email_links_substituted(self, tmp_db, tmp_path, monkeypatch):
        root = _write_data(tmp_path, preferencias="gmail_drafts: sí\n")
        h = _seed_job(contact_method="email")
        body = tmp_path / "body.html"
        body.write_text("Visita [github] y [linkedin].", encoding="utf-8")
        _patch_environment(monkeypatch, root, which=lambda n: f"/fake/{n}",
                           run=_fake_run_factory([]))
        result = runner.invoke(generate.app, [
            "email", "--job", h, "--body-file", str(body), "--to", "r@x.com", "--dry-run",
        ])
        assert result.exit_code == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["dry_run"] is True
        html = payload["html"]
        assert '<a href="https://github.com/example">GitHub</a>' in html
        assert '<a href="https://linkedin.com/in/example">LinkedIn</a>' in html
        assert "[github]" not in html and "[linkedin]" not in html
        # dry-run: no status update
        assert db.get_job(h)["job"]["status"] == "analyzed"

    def test_question_returns_text_no_draft(self, tmp_db, tmp_path, monkeypatch):
        root = _write_data(tmp_path)
        h = _seed_job(contact_method="portal")
        body = tmp_path / "q.html"
        body.write_text("¿Qué patrón usaste para el orquestador de IA?", encoding="utf-8")
        calls = []
        _patch_environment(monkeypatch, root, which=lambda n: f"/fake/{n}",
                           run=_fake_run_factory(calls))
        result = runner.invoke(generate.app, [
            "question", "--job", h, "--body-file", str(body),
        ])
        assert result.exit_code == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is True and payload["mode"] == "question"
        assert payload["text_preview"] == payload["text"].strip()[:100]
        assert "orquestador" in payload["text"]
        assert "draft_id" not in payload  # question never creates a draft
        # no gws/m365 invocation — only cleanup
        assert not any("gws" in c[0] or "m365" in " ".join(c) for c in calls)
        assert db.get_job(h)["job"]["status"] == "analyzed"  # untouched

    def test_cover_letter_without_provider(self, tmp_db, tmp_path, monkeypatch):
        root = _write_data(tmp_path, preferencias="gmail_drafts: no\n")  # no provider
        h = _seed_job(contact_method="portal")
        body = tmp_path / "cl.html"; body.write_text("<p>Candidatura.</p>", encoding="utf-8")
        _patch_environment(monkeypatch, root, which=lambda n: f"/fake/{n}",
                           run=_fake_run_factory([]))
        result = runner.invoke(generate.app, [
            "cover-letter", "--job", h, "--body-file", str(body),
        ])
        assert result.exit_code == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is True and payload["mode"] == "cover-letter"
        assert payload["provider"] is None
        assert "body" in payload or "text" in payload
        # no status change (no draft created)
        assert db.get_job(h)["job"]["status"] == "analyzed"

    def test_cover_letter_with_provider(self, tmp_db, tmp_path, monkeypatch):
        root = _write_data(tmp_path, preferencias="gmail_drafts: sí\n")
        h = _seed_job(contact_method="portal")
        body = tmp_path / "cl.html"; body.write_text("<p>Candidatura.</p>", encoding="utf-8")
        calls = []
        _patch_environment(monkeypatch, root, which=lambda n: f"/fake/{n}",
                           run=_fake_run_factory(calls))
        result = runner.invoke(generate.app, [
            "cover-letter", "--job", h, "--body-file", str(body),
            "--to", "rrhh@acme.com",
        ])
        assert result.exit_code == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is True and payload["mode"] == "cover-letter"
        assert payload["provider"] == "gmail"
        assert any("gws" in c[0] for c in calls)
        assert db.get_job(h)["job"]["status"] == "applied"

    def test_cleanup_runs_even_on_error(self, tmp_db, tmp_path, monkeypatch):
        # PORTAL_POSTULATION path: cleanup must still run.
        root = _write_data(tmp_path, preferencias="gmail_drafts: sí\n")
        h = _seed_job(contact_method="portal")
        body = tmp_path / "body.html"; body.write_text("x", encoding="utf-8")
        calls = []
        _patch_environment(monkeypatch, root, which=lambda n: f"/fake/{n}",
                           run=_fake_run_factory(calls))
        result = runner.invoke(generate.app, [
            "email", "--job", h, "--body-file", str(body), "--to", "r@x.com",
        ])
        assert result.exit_code == 1
        assert json.loads(result.stderr)["code"] == "PORTAL_POSTULATION"
        assert any("cleanup.py" in str(c[-1]) for c in calls)

    def test_unicode_body_preserved(self, tmp_db, tmp_path, monkeypatch):
        root = _write_data(tmp_path, preferencias="gmail_drafts: sí\n")
        h = _seed_job(contact_method="email")
        body = tmp_path / "body.html"
        body.write_text("ñ &aacute; &lt;script&gt; José", encoding="utf-8")
        _patch_environment(monkeypatch, root, which=lambda n: f"/fake/{n}",
                           run=_fake_run_factory([]))
        result = runner.invoke(generate.app, [
            "email", "--job", h, "--body-file", str(body), "--to", "r@x.com", "--dry-run",
        ])
        assert result.exit_code == 0, result.stderr
        html = json.loads(result.stdout)["html"]
        assert "ñ" in html and "&aacute;" in html and "&lt;script&gt;" in html and "José" in html