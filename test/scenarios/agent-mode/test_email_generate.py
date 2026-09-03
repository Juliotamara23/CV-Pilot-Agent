"""Tests for `skills/mimetismo/scripts/cli.py`.

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
from _lib.errors import CV_PilotError
from _lib.models import AnalysisInsert, JobInsert

# Import the cli module (it lives in a scripts dir without a parent
# package on sys.path, so insert it explicitly).
_AGENT_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "cv-pilot-agent"
_GEN_DIR = _AGENT_ROOT / "skills" / "mimetismo" / "scripts"
if str(_GEN_DIR) not in sys.path:
    sys.path.insert(0, str(_GEN_DIR))

import cli as generate  # type: ignore  # noqa: E402
from _mimetismo_internal.links import format_links as _format_links, signature_footer as _signature_footer  # noqa: E402
from _mimetismo_internal.providers import detect_provider_optional as _detect_provider_optional, detect_provider as _detect_provider  # noqa: E402
from _lib.shared.profile_loader import load_profile as _load_profile  # noqa: E402


runner = CliRunner()

# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
PERFIL_JSON = {
    "nombre": "Ana Lopez",
    "resumen": "Dev.",
    "linkedin": "https://linkedin.com/in/example",
    "github": "https://github.com/example",
    "telefono": "+57 320 5551234",
    "correo": "ana@example.com",
    "cv_url": "https://drive.google.com/cv",
}


def _write_data(
    tmp_path: Path,
    preferencias: dict | None = None,
    *,
    perfil: dict | None = None,
    correos: str | None = None,
) -> Path:
    """Create a tmp cv-pilot-agent root with data/perfil.json, preferencias.json
    and a scripts/cleanup.py stub so _cleanup() actually invokes subprocess.run (mocked).
    Optionally writes data/correos.md when `correos` is provided."""
    if preferencias is None:
        preferencias = {"gmail_drafts": False, "outlook_drafts": False}
    if perfil is None:
        perfil = PERFIL_JSON
    root = tmp_path / "agent-root"
    (root / "data").mkdir(parents=True)
    (root / "scripts").mkdir(parents=True)
    with (root / "data" / "perfil.json").open("w", encoding="utf-8") as f:
        json.dump(perfil, f, ensure_ascii=False, indent=2)
    with (root / "data" / "preferencias.json").open("w", encoding="utf-8") as f:
        json.dump(preferencias, f, ensure_ascii=False, indent=2)
    if correos is not None:
        (root / "data" / "correos.md").write_text(correos, encoding="utf-8")
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
    """Point cli.py at a tmp agent root + stub provider/shell helpers."""
    monkeypatch.setattr(generate, "_AGENT_ROOT", root)
    if which is not None:
        monkeypatch.setattr(generate.shutil, "which", which)
        # Also patch shutil in the drafts module where actual CLI checks happen
        import _mimetismo_internal.drafts as drafts_mod
        monkeypatch.setattr(drafts_mod.shutil, "which", which)
    if run is not None:
        monkeypatch.setattr(generate.subprocess, "run", run)
        # Also patch subprocess in the drafts module
        import _mimetismo_internal.drafts as drafts_mod
        monkeypatch.setattr(drafts_mod.subprocess, "run", run)


# --------------------------------------------------------------------------- #
# 3.1 Unit tests
# --------------------------------------------------------------------------- #
class TestLoadProfile:
    def test_parses_contact_fields(self, tmp_path, monkeypatch):
        root = _write_data(tmp_path)
        profile = _load_profile(root)
        assert profile["name"] == "Ana Lopez"
        assert profile["linkedin"] == "https://linkedin.com/in/example"
        assert profile["github"] == "https://github.com/example"
        assert profile["whatsapp"] == "+57 320 5551234"
        assert profile["email"] == "ana@example.com"
        assert profile["cv_url"] == "https://drive.google.com/cv"

    def test_parses_cv_path_when_present(self, tmp_path, monkeypatch):
        """When perfil.json contains cv_path, _load_profile exposes profile['cv_path']."""
        perfil = dict(PERFIL_JSON, cv_path="data/cv.pdf")
        root = _write_data(tmp_path, perfil=perfil)
        profile = _load_profile(root)
        assert profile["cv_path"] == "data/cv.pdf"

    def test_missing_file_raises_file_not_found(self, tmp_path, monkeypatch):
        root = tmp_path / "no-data-root"
        root.mkdir()
        with pytest.raises(FileNotFoundError):
            _load_profile(root)

    def test_all_caps_name_normalized_to_title_case(self, tmp_path, monkeypatch):
        perfil = dict(PERFIL_JSON, nombre="ANA LOPEZ")
        root = _write_data(tmp_path, perfil=perfil)
        profile = _load_profile(root)
        assert profile["name"] == "Ana Lopez"


class TestLoadPreferences:
    def test_true_loaded_from_json(self, tmp_path, monkeypatch):
        root = _write_data(tmp_path, preferencias={"gmail_drafts": True, "outlook_drafts": False})
        monkeypatch.setattr(generate, "_AGENT_ROOT", root)
        assert generate._load_preferences()["gmail_drafts"] is True

    def test_false_loaded_from_json(self, tmp_path, monkeypatch):
        root = _write_data(tmp_path, preferencias={"gmail_drafts": False, "outlook_drafts": False})
        monkeypatch.setattr(generate, "_AGENT_ROOT", root)
        assert generate._load_preferences()["gmail_drafts"] is False

    def test_missing_file_returns_false(self, tmp_path, monkeypatch):
        root = tmp_path / "no-data"
        root.mkdir()
        monkeypatch.setattr(generate, "_AGENT_ROOT", root)
        assert generate._load_preferences() == {"gmail_drafts": False, "outlook_drafts": False}

    def test_outlook_detected(self, tmp_path, monkeypatch):
        root = _write_data(tmp_path, preferencias={"gmail_drafts": False, "outlook_drafts": True})
        monkeypatch.setattr(generate, "_AGENT_ROOT", root)
        prefs = generate._load_preferences()
        assert prefs["outlook_drafts"] is True
        assert prefs["gmail_drafts"] is False

    def test_non_bool_value_keeps_default(self, tmp_path, monkeypatch):
        # Non-boolean values in the JSON (e.g. accidental strings) must be
        # ignored — the loader must not crash and must fall back to the
        # default ``False`` for that key.
        root = _write_data(tmp_path, preferencias={"gmail_drafts": "sí"})
        monkeypatch.setattr(generate, "_AGENT_ROOT", root)
        assert generate._load_preferences()["gmail_drafts"] is False

    def test_malformed_json_returns_defaults(self, tmp_path, monkeypatch):
        root = tmp_path / "agent-root"
        (root / "data").mkdir(parents=True)
        (root / "data" / "preferencias.json").write_text("{not valid json", encoding="utf-8")
        monkeypatch.setattr(generate, "_AGENT_ROOT", root)
        assert generate._load_preferences() == {"gmail_drafts": False, "outlook_drafts": False}


class TestDetectProvider:
    def test_override_wins(self):
        assert _detect_provider_optional(
            {"gmail_drafts": True, "outlook_drafts": True}, "outlook"
        ) == "outlook"

    def test_gmail_preferred_when_both_true(self):
        assert _detect_provider_optional(
            {"gmail_drafts": True, "outlook_drafts": True}, None
        ) == "gmail"

    def test_only_outlook(self):
        assert _detect_provider_optional(
            {"gmail_drafts": False, "outlook_drafts": True}, None
        ) == "outlook"

    def test_none_raises_no_provider(self):
        with pytest.raises(CV_PilotError) as exc:
            _detect_provider({"gmail_drafts": False, "outlook_drafts": False}, None)
        assert "NO_PROVIDER" in exc.value.code


class TestFormatLinks:
    def test_markers_replaced_with_anchors(self):
        profile = {
            "github": "https://github.com/x", "linkedin": "https://linkedin.com/in/x",
            "cv_url": "https://drive.google.com/cv", "whatsapp": "+57 320 1",
        }
        body = "Visita [github] y [linkedin]; mi [cv] o [whatsapp]."
        out = _format_links(body, profile)
        assert '[github]' not in out and '[linkedin]' not in out
        assert '[cv]' not in out and '[whatsapp]' not in out
        assert '<a href="https://github.com/x">GitHub</a>' in out
        assert '<a href="https://linkedin.com/in/x">LinkedIn</a>' in out
        assert '<a href="https://drive.google.com/cv">CV</a>' in out
        assert '<a href="https://wa.me/573201">+57 320 1</a>' in out

    def test_missing_url_falls_back_to_label(self):
        out = _format_links("link [github]", {"github": None})
        assert out == "link GitHub"

    def test_special_chars_preserved(self):
        out = _format_links("ñ &aacute; &lt;script&gt; [cv]", {"cv_url": None})
        assert "ñ" in out and "&aacute;" in out and "&lt;script&gt;" in out

    def test_whatsapp_missing_falls_back_to_plain_text(self):
        out = _format_links("link [whatsapp]", {"whatsapp": None})
        assert out == "link WhatsApp"

    def test_whatsapp_already_url_keeps_label(self):
        out = _format_links("[whatsapp]", {"whatsapp": "https://wa.me/999"})
        assert out == '<a href="https://wa.me/999">WhatsApp</a>'

    def test_whatsapp_phone_no_digits_falls_back_to_plain_text(self):
        out = _format_links("[whatsapp]", {"whatsapp": "???"})
        assert out == "WhatsApp"


class TestSignatureFooter:
    def test_includes_name_and_available_links(self):
        profile = {
            "name": "Ana", "github": "https://g", "linkedin": "https://l",
            "cv_url": "https://cv", "whatsapp": None,
        }
        footer = _signature_footer(profile)
        assert "Ana" in footer
        assert '<a href="https://g">GitHub</a>' in footer
        assert '<a href="https://l">LinkedIn</a>' in footer
        assert '<a href="https://cv">CV</a>' in footer
        assert "WhatsApp" not in footer  # whatsapp URL was None

    def test_footer_includes_whatsapp_number_when_present(self):
        profile = {
            "name": "Ana", "github": "https://g", "linkedin": "https://l",
            "cv_url": "https://cv", "whatsapp": "+57 300 1112233",
        }
        footer = _signature_footer(profile)
        assert "Ana" in footer
        assert '<a href="https://wa.me/573001112233">+57 300 1112233</a>' in footer
        assert "|" in footer

    def test_footer_omits_cv_link_when_attached(self):
        profile = {
            "name": "Ana", "github": "https://g", "linkedin": "https://l",
            "cv_url": "https://drive.google.com/cv", "whatsapp": None,
        }
        footer_attached = _signature_footer(profile, attach_cv=True)
        assert '<a href="https://drive.google.com/cv">CV</a>' not in footer_attached
        assert "CV" not in footer_attached
        assert '<a href="https://g">GitHub</a>' in footer_attached
        assert '<a href="https://l">LinkedIn</a>' in footer_attached

        footer_plain = _signature_footer(profile)
        assert '<a href="https://drive.google.com/cv">CV</a>' in footer_plain

    def test_no_name_no_links(self):
        assert _signature_footer({}) == "<br><br>Saludos cordiales,<br>"


# --------------------------------------------------------------------------- #
# 3.2 Error tests
# --------------------------------------------------------------------------- #
class TestErrorEnvelopes:
    def test_portal_postulation_blocks_email(self, tmp_db, tmp_path, monkeypatch):
        root = _write_data(tmp_path, preferencias={"gmail_drafts": True, "outlook_drafts": False})
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
        root = _write_data(tmp_path, preferencias={"gmail_drafts": True, "outlook_drafts": False})
        h = _seed_job_no_analysis()
        body = tmp_path / "body.html"; body.write_text("x", encoding="utf-8")
        _patch_environment(monkeypatch, root, which=lambda n: f"/fake/{n}")
        result = runner.invoke(generate.app, [
            "email", "--job", h, "--body-file", str(body), "--to", "r@x.com", "--provider", "gmail",
        ])
        assert result.exit_code == 1
        assert json.loads(result.stderr)["code"] == "ANALYSIS_NOT_FOUND"

    def test_analysis_not_found_cover_letter(self, tmp_db, tmp_path, monkeypatch):
        root = _write_data(tmp_path, preferencias={"gmail_drafts": True, "outlook_drafts": False})
        h = _seed_job_no_analysis()
        body = tmp_path / "body.html"; body.write_text("x", encoding="utf-8")
        _patch_environment(monkeypatch, root, which=lambda n: f"/fake/{n}")
        result = runner.invoke(generate.app, [
            "cover-letter", "--job", h, "--body-file", str(body),
        ])
        assert result.exit_code == 1
        assert json.loads(result.stderr)["code"] == "ANALYSIS_NOT_FOUND"

    def test_no_provider_email(self, tmp_db, tmp_path, monkeypatch):
        root = _write_data(tmp_path, preferencias={"gmail_drafts": False, "outlook_drafts": False})  # no provider
        h = _seed_job(contact_method="email")
        body = tmp_path / "body.html"; body.write_text("x", encoding="utf-8")
        _patch_environment(monkeypatch, root, which=lambda n: f"/fake/{n}")
        result = runner.invoke(generate.app, [
            "email", "--job", h, "--body-file", str(body), "--to", "r@x.com",
        ])
        assert result.exit_code == 1
        assert json.loads(result.stderr)["code"] == "NO_PROVIDER"

    def test_body_file_missing(self, tmp_db, tmp_path, monkeypatch):
        root = _write_data(tmp_path, preferencias={"gmail_drafts": True, "outlook_drafts": False})
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
        root = _write_data(tmp_path, preferencias={"gmail_drafts": True, "outlook_drafts": False})
        h = _seed_job(contact_method="email")
        body = tmp_path / "body.html"; body.write_text("x", encoding="utf-8")
        _patch_environment(monkeypatch, root, which=lambda n: None)
        result = runner.invoke(generate.app, [
            "email", "--job", h, "--body-file", str(body), "--to", "r@x.com", "--provider", "gmail",
        ])
        assert result.exit_code == 1
        assert json.loads(result.stderr)["code"] == "PROVIDER_CLI_MISSING"

    def test_outlook_token_failure_raises(self, tmp_db, tmp_path, monkeypatch):
        root = _write_data(tmp_path, preferencias={"gmail_drafts": False, "outlook_drafts": True})
        h = _seed_job(contact_method="email")
        body = tmp_path / "body.html"; body.write_text("<p>Hola</p>", encoding="utf-8")
        def fake_run(args, **kwargs):
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="auth boom")
        _patch_environment(monkeypatch, root, which=lambda n: f"/fake/{n}", run=fake_run)
        result = runner.invoke(generate.app, [
            "email", "--job", h, "--body-file", str(body), "--to", "r@x.com", "--provider", "outlook",
        ])
        assert result.exit_code == 1
        assert json.loads(result.stderr)["code"] == "DRAFT_FAILED"


# --------------------------------------------------------------------------- #
# 3.3 Integration tests (subprocess mocked)
# --------------------------------------------------------------------------- #
class TestIntegration:
    def test_email_gmail_happy_path(self, tmp_db, tmp_path, monkeypatch):
        root = _write_data(tmp_path, preferencias={"gmail_drafts": True, "outlook_drafts": False})
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

    def test_email_gmail_json_output_returns_top_level_id(self, tmp_db, tmp_path, monkeypatch):
        """gws returns a multi-line JSON envelope; the top-level "id" is the draft id.

        Regression: previously the parser took the first line of stdout, which
        was the opening brace ``{`` of the JSON — yielding a useless draft_id.
        """
        root = _write_data(tmp_path, preferencias={"gmail_drafts": True, "outlook_drafts": False})
        h = _seed_job(contact_method="email")
        body = tmp_path / "body.html"
        body.write_text("<p>Hola</p>", encoding="utf-8")

        json_stdout = (
            '{\n'
            '  "id": "r-8927261222089960502",\n'
            '  "message": {\n'
            '    "id": "19f3e459f4275060",\n'
            '    "labelIds": ["DRAFT"],\n'
            '    "threadId": "19f3e459f4275060"\n'
            '  }\n'
            '}\n'
        )

        def fake_which(name):
            return f"/fake/{name}" if name == "gws" else None

        def fake_run(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, stdout=json_stdout, stderr="")

        _patch_environment(monkeypatch, root, which=fake_which, run=fake_run)
        result = runner.invoke(generate.app, [
            "email", "--job", h, "--body-file", str(body), "--to", "rrhh@acme.com",
        ])
        assert result.exit_code == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["provider"] == "gmail"
        # Top-level "id" is the draft id, NOT the opening brace of the JSON.
        assert payload["draft_id"] == "r-8927261222089960502"

    def test_email_gmail_json_without_id_falls_back_to_default(self, tmp_db, tmp_path, monkeypatch):
        """If the JSON envelope has no top-level "id", fall back to default."""
        root = _write_data(tmp_path, preferencias={"gmail_drafts": True, "outlook_drafts": False})
        h = _seed_job(contact_method="email")
        body = tmp_path / "body.html"; body.write_text("<p>x</p>", encoding="utf-8")

        json_stdout = '{"message": {"id": "x"}, "threadId": "y"}\n'

        def fake_which(name):
            return f"/fake/{name}" if name == "gws" else None

        def fake_run(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, stdout=json_stdout, stderr="")

        _patch_environment(monkeypatch, root, which=fake_which, run=fake_run)
        result = runner.invoke(generate.app, [
            "email", "--job", h, "--body-file", str(body), "--to", "r@x.com",
        ])
        assert result.exit_code == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["draft_id"] == "draft"  # fallback default

    def test_email_gmail_ps1_invokes_via_powershell(self, tmp_db, tmp_path, monkeypatch):
        """On Windows, gws is a .ps1 script — must be invoked via pwsh/powershell.

        Regression: previously the script called ``gws`` directly via
        subprocess.run, which fails on Windows with FileNotFoundError because
        Python can't execute .ps1 files without an explicit shell wrapper.
        """
        root = _write_data(tmp_path, preferencias={"gmail_drafts": True, "outlook_drafts": False})
        h = _seed_job(contact_method="email")
        body = tmp_path / "body.html"
        body.write_text("<p>Hola, visita mi [github].</p>", encoding="utf-8")
        calls = []

        def fake_which(name):
            if name == "gws":
                return "/fake/gws.ps1"
            if name in ("pwsh", "powershell"):
                return f"/fake/{name}"
            return None

        _patch_environment(monkeypatch, root, which=fake_which,
                           run=_fake_run_factory(calls))
        result = runner.invoke(generate.app, [
            "email", "--job", h, "--body-file", str(body), "--to", "rrhh@acme.com",
        ])
        assert result.exit_code == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["provider"] == "gmail"
        # Find the gws invocation in the recorded calls; it must be wrapped
        # as [pwsh/powershell, -NoProfile, -File, /fake/gws.ps1, gmail, +send, ...]
        gws_call = next(
            c for c in calls
            if any("gws" in str(a) for a in c) and "gmail" in c
        )
        assert gws_call[0] in ("/fake/pwsh", "/fake/powershell")
        assert gws_call[1] == "-NoProfile"
        assert gws_call[2] == "-File"
        assert gws_call[3] == "/fake/gws.ps1"
        assert gws_call[4] == "gmail"
        assert gws_call[5] == "+send"
        assert db.get_job(h)["job"]["status"] == "applied"

    def test_email_gmail_cmd_invokes_via_cmd_exe(self, tmp_db, tmp_path, monkeypatch):
        """On Windows, npm installs gws as gws.CMD — must be invoked via cmd.exe.

        Regression: previously the script called ``gws`` by name only, which
        fails on Windows because Python's subprocess does not auto-resolve
        ``.CMD`` extensions for the program name.
        """
        root = _write_data(tmp_path, preferencias={"gmail_drafts": True, "outlook_drafts": False})
        h = _seed_job(contact_method="email")
        body = tmp_path / "body.html"
        body.write_text("<p>Hola</p>", encoding="utf-8")
        calls = []

        def fake_which(name):
            if name == "gws":
                return "/fake/gws.CMD"
            if name == "cmd":
                return "/fake/cmd.exe"
            return None

        _patch_environment(monkeypatch, root, which=fake_which,
                           run=_fake_run_factory(calls))
        result = runner.invoke(generate.app, [
            "email", "--job", h, "--body-file", str(body), "--to", "rrhh@acme.com",
        ])
        assert result.exit_code == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["provider"] == "gmail"
        # gws.CMD invocation wrapped as [cmd.exe, /c, gws.CMD, gmail, +send, ...]
        gws_call = next(
            c for c in calls
            if any("gws" in str(a) for a in c) and "gmail" in c
        )
        assert gws_call[0] == "/fake/cmd.exe"
        assert gws_call[1] == "/c"
        assert gws_call[2] == "/fake/gws.CMD"
        assert gws_call[3] == "gmail"
        assert gws_call[4] == "+send"
        assert db.get_job(h)["job"]["status"] == "applied"

    def test_email_gmail_ps1_no_powershell_raises(self, tmp_db, tmp_path, monkeypatch):
        """If gws is .ps1 but no PowerShell is available, fail with PROVIDER_CLI_MISSING."""
        root = _write_data(tmp_path, preferencias={"gmail_drafts": True, "outlook_drafts": False})
        h = _seed_job(contact_method="email")
        body = tmp_path / "body.html"; body.write_text("x", encoding="utf-8")

        def fake_which(name):
            if name == "gws":
                return "/fake/gws.ps1"
            return None  # no pwsh, no powershell

        _patch_environment(monkeypatch, root, which=fake_which,
                           run=_fake_run_factory([]))
        result = runner.invoke(generate.app, [
            "email", "--job", h, "--body-file", str(body), "--to", "r@x.com",
        ])
        assert result.exit_code == 1
        payload = json.loads(result.stderr)
        assert payload["code"] == "PROVIDER_CLI_MISSING"
        assert "PowerShell" in payload["error"]

    def test_email_outlook_happy_path(self, tmp_db, tmp_path, monkeypatch):
        root = _write_data(tmp_path, preferencias={"gmail_drafts": False, "outlook_drafts": True})
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
        root = _write_data(tmp_path, preferencias={"gmail_drafts": True, "outlook_drafts": False})
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

    def test_cover_letter_returns_copy_paste_artifact(self, tmp_db, tmp_path, monkeypatch):
        """Cover letter returns a copy/paste text artifact: no provider, no email
        footer, no draft, and no status change."""
        root = _write_data(tmp_path, preferencias={"gmail_drafts": True, "outlook_drafts": False})
        h = _seed_job(contact_method="portal")
        body = tmp_path / "cl.html"; body.write_text("<p>Candidatura.</p>", encoding="utf-8")
        calls = []
        _patch_environment(monkeypatch, root, which=lambda n: f"/fake/{n}",
                           run=_fake_run_factory(calls))
        result = runner.invoke(generate.app, [
            "cover-letter", "--job", h, "--body-file", str(body),
        ])
        assert result.exit_code == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is True and payload["mode"] == "cover-letter"
        # copy/paste artifact: exposes the text, never a provider draft
        assert "text" in payload
        assert "provider" not in payload
        assert "attached" not in payload
        # no email footer is appended to the artifact
        assert "Saludos cordiales" not in payload["text"]
        # no provider/subprocess draft invocation, only cleanup
        assert not any("gws" in c[0] or "m365" in " ".join(c) for c in calls)
        # no status change (no draft created)
        assert db.get_job(h)["job"]["status"] == "analyzed"

    def test_cover_letter_resolves_contact_markers(self, tmp_db, tmp_path, monkeypatch):
        """Cover letter resolves contact markers into usable text/links but never
        appends the email footer."""
        root = _write_data(tmp_path, preferencias={"gmail_drafts": False, "outlook_drafts": False})
        h = _seed_job(contact_method="portal")
        body = tmp_path / "cl.html"
        body.write_text("Visita [github] y mi [cv].", encoding="utf-8")
        calls = []
        _patch_environment(monkeypatch, root, which=lambda n: f"/fake/{n}",
                           run=_fake_run_factory(calls))
        result = runner.invoke(generate.app, [
            "cover-letter", "--job", h, "--body-file", str(body),
        ])
        assert result.exit_code == 0, result.stderr
        payload = json.loads(result.stdout)
        text = payload["text"]
        assert '<a href="https://github.com/example">GitHub</a>' in text
        assert '<a href="https://drive.google.com/cv">CV</a>' in text
        assert "[github]" not in text and "[cv]" not in text
        assert "Saludos cordiales" not in text  # no email footer
        assert db.get_job(h)["job"]["status"] == "analyzed"

    def test_cleanup_runs_even_on_error(self, tmp_db, tmp_path, monkeypatch):
        # PORTAL_POSTULATION path: cleanup must still run.
        root = _write_data(tmp_path, preferencias={"gmail_drafts": True, "outlook_drafts": False})
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
        root = _write_data(tmp_path, preferencias={"gmail_drafts": True, "outlook_drafts": False})
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


# --------------------------------------------------------------------------- #
# 3.4 Mimetismo source (data/correos.md) — read-only, no DB access
# --------------------------------------------------------------------------- #
class TestMimetismoSource:
    def test_returns_examples_when_correos_exists(self, tmp_path, monkeypatch):
        content = "Buenos días,\n\nMe postulo a la vacante...\n\nQuedo atento.\nSaludos cordiales,\nAna"
        root = _write_data(tmp_path, correos=content)
        monkeypatch.setattr(generate, "_AGENT_ROOT", root)
        result = runner.invoke(generate.app, ["mimetismo"])
        assert result.exit_code == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["mode"] == "mimetismo"
        assert payload["has_examples"] is True
        assert payload["source"] == "data/correos.md"
        assert payload["examples"] == content

    def test_has_examples_false_when_correos_missing(self, tmp_path, monkeypatch):
        root = _write_data(tmp_path)
        monkeypatch.setattr(generate, "_AGENT_ROOT", root)
        result = runner.invoke(generate.app, ["mimetismo"])
        assert result.exit_code == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["mode"] == "mimetismo"
        assert payload["has_examples"] is False
        assert payload["source"] == "data/correos.md"
        assert isinstance(payload["suggestion"], str) and payload["suggestion"]
        assert "examples" not in payload


# --------------------------------------------------------------------------- #
# 3.5 CV command (read-only) — new in Phases B+C
# --------------------------------------------------------------------------- #
class TestCvCommand:
    def test_cv_exists_true_when_file_present(self, tmp_path, monkeypatch):
        """cv command returns exists=true with absolute path and filename when cv_path points to existing file."""
        perfil = dict(PERFIL_JSON, cv_path="data/cv.pdf")
        root = _write_data(tmp_path, perfil=perfil)
        # Create the CV file after _write_data creates the directory structure
        cv_file = root / "data" / "cv.pdf"
        cv_file.write_bytes(b"%PDF-1.4 fake pdf")
        monkeypatch.setattr(generate, "_AGENT_ROOT", root)
        result = runner.invoke(generate.app, ["cv"])
        assert result.exit_code == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["mode"] == "cv"
        assert payload["exists"] is True
        assert payload["path"] == str(cv_file)
        assert payload["filename"] == "cv.pdf"

    def test_cv_exists_false_when_no_cv_path_in_profile(self, tmp_path, monkeypatch):
        """cv command returns exists=false when perfil.json has no cv_path key."""
        root = _write_data(tmp_path, perfil=PERFIL_JSON)  # no cv_path
        monkeypatch.setattr(generate, "_AGENT_ROOT", root)
        result = runner.invoke(generate.app, ["cv"])
        assert result.exit_code == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["mode"] == "cv"
        assert payload["exists"] is False
        assert payload["path"] is None
        assert payload["filename"] is None

    def test_cv_exists_false_when_cv_path_points_to_missing_file(self, tmp_path, monkeypatch):
        """cv command returns exists=false when cv_path exists in profile but file is missing."""
        perfil = dict(PERFIL_JSON, cv_path="data/missing.pdf")
        root = _write_data(tmp_path, perfil=perfil)
        monkeypatch.setattr(generate, "_AGENT_ROOT", root)
        result = runner.invoke(generate.app, ["cv"])
        assert result.exit_code == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["mode"] == "cv"
        assert payload["exists"] is False
        assert payload["path"] is None
        assert payload["filename"] is None


# --------------------------------------------------------------------------- #
# 3.6 format_links attach_cv behavior
# --------------------------------------------------------------------------- #
class TestFormatLinksAttachCv:
    def test_attach_cv_true_replaces_cv_marker_with_plain_text(self):
        """When attach_cv=True, [cv] becomes 'Currículum' (no anchor) even if cv_url exists."""
        profile = {
            "github": "https://github.com/x", "linkedin": "https://linkedin.com/in/x",
            "cv_url": "https://drive.google.com/cv", "whatsapp": None,
        }
        body = "Ver mi [cv] por favor."
        out = _format_links(body, profile, attach_cv=True)
        assert out == "Ver mi Currículum por favor."
        assert "<a" not in out

    def test_attach_cv_false_keeps_anchor_when_cv_url_present(self):
        """When attach_cv=False (default), [cv] becomes anchor if cv_url exists."""
        profile = {"cv_url": "https://drive.google.com/cv"}
        body = "Ver mi [cv]."
        out = _format_links(body, profile, attach_cv=False)
        assert out == 'Ver mi <a href="https://drive.google.com/cv">CV</a>.'

    def test_attach_cv_false_falls_back_to_label_when_no_cv_url(self):
        """When attach_cv=False and no cv_url, [cv] becomes plain label 'CV'."""
        profile = {"cv_url": None}
        body = "Ver mi [cv]."
        out = _format_links(body, profile, attach_cv=False)
        assert out == "Ver mi CV."


# --------------------------------------------------------------------------- #
# 3.7 Integration: Gmail with attachment
# --------------------------------------------------------------------------- #
class TestIntegrationGmailAttachment:
    def test_email_gmail_with_attachment(self, tmp_db, tmp_path, monkeypatch):
        """Gmail email with cv_path in profile -> attached:true and -a flag in gws call."""
        # Create a temp CV file
        cv_file = tmp_path / "cv.pdf"
        cv_file.write_bytes(b"%PDF-1.4 fake pdf")
        perfil = dict(PERFIL_JSON, cv_path=str(cv_file))
        root = _write_data(tmp_path, preferencias={"gmail_drafts": True, "outlook_drafts": False}, perfil=perfil)
        h = _seed_job(contact_method="email")
        body = tmp_path / "body.html"
        body.write_text("<p>Hola, adjunto mi [cv].</p>", encoding="utf-8")
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
        assert payload["attached"] is True
        # Verify -a flag with cv path in gws subprocess call
        gws_calls = [c for c in calls if any("gws" in str(a) for a in c)]
        assert gws_calls, "gws subprocess not invoked"
        gws_args = gws_calls[0]
        # Find -a and the path after it
        assert "-a" in gws_args, f"-a flag not found in gws args: {gws_args}"
        a_idx = gws_args.index("-a")
        assert a_idx + 1 < len(gws_args), "No path after -a flag"
        assert gws_args[a_idx + 1] == str(cv_file), f"Wrong attachment path: {gws_args[a_idx + 1]}"
        assert db.get_job(h)["job"]["status"] == "applied"

    def test_email_gmail_without_cv_path_no_attachment(self, tmp_db, tmp_path, monkeypatch):
        """Gmail email without cv_path -> attached:false and no -a flag."""
        root = _write_data(tmp_path, preferencias={"gmail_drafts": True, "outlook_drafts": False})
        h = _seed_job(contact_method="email")
        body = tmp_path / "body.html"
        body.write_text("<p>Hola, visita mi [cv].</p>", encoding="utf-8")
        calls = []
        _patch_environment(monkeypatch, root, which=lambda n: f"/fake/{n}",
                           run=_fake_run_factory(calls))
        result = runner.invoke(generate.app, [
            "email", "--job", h, "--body-file", str(body), "--to", "rrhh@acme.com",
        ])
        assert result.exit_code == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["attached"] is False
        # Verify no -a flag in gws subprocess call
        gws_calls = [c for c in calls if any("gws" in str(a) for a in c)]
        assert gws_calls, "gws subprocess not invoked"
        gws_args = gws_calls[0]
        assert "-a" not in gws_args, f"Unexpected -a flag in gws args: {gws_args}"
        assert db.get_job(h)["job"]["status"] == "applied"

    def test_email_gmail_dry_run_attached_false(self, tmp_db, tmp_path, monkeypatch):
        """Gmail email dry-run with cv_path -> attached:false in output (no draft created)."""
        cv_file = tmp_path / "cv.pdf"
        cv_file.write_bytes(b"%PDF-1.4 fake pdf")
        perfil = dict(PERFIL_JSON, cv_path=str(cv_file))
        root = _write_data(tmp_path, preferencias={"gmail_drafts": True, "outlook_drafts": False}, perfil=perfil)
        h = _seed_job(contact_method="email")
        body = tmp_path / "body.html"
        body.write_text("<p>Hola.</p>", encoding="utf-8")
        _patch_environment(monkeypatch, root, which=lambda n: f"/fake/{n}",
                           run=_fake_run_factory([]))
        result = runner.invoke(generate.app, [
            "email", "--job", h, "--body-file", str(body), "--to", "r@x.com", "--dry-run",
        ])
        assert result.exit_code == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["dry_run"] is True
        assert payload["attached"] is False
        assert db.get_job(h)["job"]["status"] == "analyzed"


# --------------------------------------------------------------------------- #
# 3.8 Integration: Outlook with attachment
# --------------------------------------------------------------------------- #
class TestIntegrationOutlookAttachment:
    def test_email_outlook_with_attachment(self, tmp_db, tmp_path, monkeypatch):
        """Outlook email with cv_path -> generated PowerShell includes attachment POST."""
        cv_file = tmp_path / "cv.pdf"
        cv_file.write_bytes(b"%PDF-1.4 fake pdf")
        perfil = dict(PERFIL_JSON, cv_path=str(cv_file))
        root = _write_data(tmp_path, preferencias={"gmail_drafts": False, "outlook_drafts": True}, perfil=perfil)
        h = _seed_job(contact_method="email")
        body = tmp_path / "body.html"
        body.write_text("<p>Hola, adjunto mi [cv].</p>", encoding="utf-8")
        calls = []
        _patch_environment(monkeypatch, root, which=lambda n: f"/fake/{n}",
                           run=_fake_run_factory(calls))
        result = runner.invoke(generate.app, [
            "email", "--job", h, "--body-file", str(body),
            "--to", "rrhh@acme.com", "--provider", "outlook",
        ])
        assert result.exit_code == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["provider"] == "outlook"
        assert payload["attached"] is True
        # Find the PowerShell script in the calls
        ps_calls = [c for c in calls if any("powershell" in str(a).lower() or "pwsh" in str(a).lower() for a in c)]
        assert ps_calls, "PowerShell subprocess not invoked"
        # The script is the last argument (after -Command)
        script = " ".join(ps_calls[0])
        assert "/attachments" in script, f"Attachment POST not found in script: {script}"
        assert "cv.pdf" in script, f"Filename not found in attachment POST: {script}"
        assert "contentBytes" in script, f"base64 contentBytes not found in script: {script}"
        assert db.get_job(h)["job"]["status"] == "applied"


# --------------------------------------------------------------------------- #
# 3.9 Integration: Cover-letter copy/paste artifact (no attachment, no provider)
# --------------------------------------------------------------------------- #
class TestIntegrationCoverLetterArtifact:
    def test_cover_letter_no_attachment_semantics(self, tmp_db, tmp_path, monkeypatch):
        """A persisted CV does NOT turn the cover letter into an email draft with
        attachment: the artifact resolves [cv] as a link and never reports an
        'attached' envelope field."""
        cv_file = tmp_path / "cv.pdf"
        cv_file.write_bytes(b"%PDF-1.4 fake pdf")
        perfil = dict(PERFIL_JSON, cv_path=str(cv_file))
        root = _write_data(tmp_path, preferencias={"gmail_drafts": True, "outlook_drafts": False}, perfil=perfil)
        h = _seed_job(contact_method="portal")
        body = tmp_path / "cl.html"
        body.write_text("<p>Candidatura, adjunto mi [cv].</p>", encoding="utf-8")
        calls = []
        _patch_environment(monkeypatch, root, which=lambda n: f"/fake/{n}",
                           run=_fake_run_factory(calls))
        result = runner.invoke(generate.app, [
            "cover-letter", "--job", h, "--body-file", str(body),
        ])
        assert result.exit_code == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["mode"] == "cover-letter"
        # No attachment/draft semantics on the copy/paste artifact.
        assert "attached" not in payload
        assert "provider" not in payload
        # [cv] resolves to the CV link, not to an attachment plain-text marker.
        assert '<a href="https://drive.google.com/cv">CV</a>' in payload["text"]
        assert "Saludos cordiales" not in payload["text"]
        # no provider draft invoked
        assert not any("gws" in c[0] or "m365" in " ".join(c) for c in calls)
        assert db.get_job(h)["job"]["status"] == "analyzed"

    def test_cover_letter_no_cv_uses_label(self, tmp_db, tmp_path, monkeypatch):
        """Without a cv_url, [cv] resolves to the plain label when no CV link exists."""
        perfil = dict(PERFIL_JSON, cv_url=None)
        root = _write_data(tmp_path, preferencias={"gmail_drafts": False, "outlook_drafts": False}, perfil=perfil)
        h = _seed_job(contact_method="portal")
        body = tmp_path / "cl.html"
        body.write_text("Ver mi [cv].", encoding="utf-8")
        _patch_environment(monkeypatch, root, which=lambda n: f"/fake/{n}",
                           run=_fake_run_factory([]))
        result = runner.invoke(generate.app, [
            "cover-letter", "--job", h, "--body-file", str(body),
        ])
        assert result.exit_code == 0, result.stderr
        payload = json.loads(result.stdout)
        assert "Ver mi CV." in payload["text"]


# --------------------------------------------------------------------------- #
# 3.10 Generation context (source-separated) — read-only, no DB mutation
# --------------------------------------------------------------------------- #
class TestGenerationContext:
    """Regression coverage for issue #25: deterministic, source-grounded
    generation context that prevents generic requirement-summary paragraphs,
    unsupported certification/remote claims, and duplicated footer contacts."""
    def _run_context(self, h, mode=None):
        args = ["context", "--job", h]
        if mode is not None:
            args += ["--mode", mode]
        result = runner.invoke(generate.app, args)
        assert result.exit_code == 0, result.stderr
        return json.loads(result.stdout)

    def _rich_perfil(self, education=None, resume=None, extras=None, **overrides):
        perfil = {
            "nombre": "Ana Lopez",
            "correo": "ana@example.com",
            "linkedin": "https://linkedin.com/in/example",
            "github": "https://github.com/example",
            "telefono": "+57 320 5551234",
            "cv_url": "https://drive.google.com/cv",
            "resumen": resume or "Ingeniera de Software con 5+ anios.",
            "experiencia": "Backend Engineer | FinTech | 2020-presente",
            "educacion": education or "M.Sc. | Universidad | 2017",
            "skills": "Python, Go, PostgreSQL, Kafka",
            "extras": extras or {
                "ubicacion": "Bogota, Colombia",
                "disponibilidad": "Inmediata",
                "idiomas": "Espanol (nativo), Ingles (B2)",
                "visa_us": "No requiere patrocinio",
                "expectativa_salarial_usd": "90000-120000",
            },
        }
        perfil.update(overrides)
        return perfil

    def test_exposes_complete_email_examples(self, tmp_db, tmp_path, monkeypatch):
        """Complete current examples are the style source for drafting (voice,
        rhythm, closings) — not just isolated phrases."""
        h = _seed_job()
        content = "Hola Maria,\n\nMe postulo a la vacante de Backend Dev.\n\nUn saludo,\nAna"
        root = _write_data(tmp_path, perfil=self._rich_perfil(), correos=content)
        monkeypatch.setattr(generate, "_AGENT_ROOT", root)
        payload = self._run_context(h)
        assert payload["mode"] == "context"
        assert payload["has_examples"] is True
        assert payload["examples_source"] == "data/correos.md"
        assert payload["examples"] == content

    def test_examples_empty_when_correos_missing(self, tmp_db, tmp_path, monkeypatch):
        h = _seed_job()
        root = _write_data(tmp_path, perfil=self._rich_perfil())
        monkeypatch.setattr(generate, "_AGENT_ROOT", root)
        payload = self._run_context(h)
        assert payload["has_examples"] is False
        assert payload["examples"] == ""

    def test_facts_are_source_attributed_subset_not_full_json(self, tmp_db, tmp_path, monkeypatch):
        """profile_facts is a curated, source-attributed subset: footer-owned contact
        links and private compensation are excluded, and the raw JSON is not the
        drafting input (the model must not reread perfil.json)."""
        h = _seed_job()
        root = _write_data(tmp_path, perfil=self._rich_perfil())
        monkeypatch.setattr(generate, "_AGENT_ROOT", root)
        payload = self._run_context(h)
        facts = payload["profile_facts"]
        assert isinstance(facts, list) and facts
        assert all(isinstance(f, dict) and "field" in f and "fact" in f for f in facts)
        joined = json.dumps(facts)
        # footer-owned contacts must not be emitted as draftable body facts
        assert "linkedin.com/in/example" not in joined
        assert "github.com/example" not in joined
        assert "+57 320 5551234" not in joined
        # private compensation must not leak into the facts
        assert "90000-120000" not in joined
        # profile exposes only identity (footer + greeting), never contact URLs
        assert set(payload["profile"]) == {"name", "email"}
        # the raw full JSON is not echoed as a dedicated field
        assert "experiencia" not in payload
        # job + analysis are exposed for grounding
        assert payload["job"]["position"] == "Backend Dev"
        assert payload["analysis"]["verdict"] == "Apto"

    def test_certifications_only_when_declared(self, tmp_db, tmp_path, monkeypatch):
        """Certifications may only be claimed when the profile declares them."""
        h = _seed_job()
        perfil = self._rich_perfil(education=(
            "M.Sc. | Universidad | 2017\n"
            "Certificaciones: AWS Solutions Architect Associate (2021), CKAD (2022)"
        ))
        root = _write_data(tmp_path, perfil=perfil)
        monkeypatch.setattr(generate, "_AGENT_ROOT", root)
        payload = self._run_context(h)
        assert payload["certificaciones"] == [
            "AWS Solutions Architect Associate (2021)", "CKAD (2022)"
        ]

        h2 = _seed_job()
        root2 = _write_data(tmp_path / "no-cert", perfil=self._rich_perfil(education="B.Sc. | Uni | 2015"))
        monkeypatch.setattr(generate, "_AGENT_ROOT", root2)
        assert self._run_context(h2)["certificaciones"] == []

    def test_remote_work_only_when_supported(self, tmp_db, tmp_path, monkeypatch):
        """Remote-work capability is only surfaced when the profile states it."""
        h = _seed_job()
        root = _write_data(tmp_path, perfil=self._rich_perfil())
        monkeypatch.setattr(generate, "_AGENT_ROOT", root)
        assert self._run_context(h)["remote_work"] is False

        h2 = _seed_job()
        perfil2 = self._rich_perfil(resume="Ingeniera de Software remoto con 5+ anios.")
        root2 = _write_data(tmp_path / "remote", perfil=perfil2)
        monkeypatch.setattr(generate, "_AGENT_ROOT", root2)
        assert self._run_context(h2)["remote_work"] is True

        h3 = _seed_job()
        perfil3 = self._rich_perfil(extras={
            "ubicacion": "Bogota, Colombia (remoto global)",
            "disponibilidad": "Inmediata",
            "idiomas": "Espanol",
            "visa_us": "No requiere patrocinio",
            "expectativa_salarial_usd": "90000-120000",
        })
        root3 = _write_data(tmp_path / "remote-ubicacion", perfil=perfil3)
        monkeypatch.setattr(generate, "_AGENT_ROOT", root3)
        assert self._run_context(h3)["remote_work"] is True

    def test_footer_contract_links_not_duplicated(self, tmp_db, tmp_path, monkeypatch):
        """The context exposes exactly the footer links the CLI will render, so the
        drafting step never repeats them in the body."""
        h = _seed_job()
        root = _write_data(tmp_path, perfil=self._rich_perfil())
        monkeypatch.setattr(generate, "_AGENT_ROOT", root)
        payload = self._run_context(h)
        assert payload["footer"] == ["GitHub", "LinkedIn", "CV", "WhatsApp"]

    def test_job_requirements_are_own_source_not_merged_into_facts(self, tmp_db, tmp_path, monkeypatch):
        """Requirements live in job/analysis sources; the profile facts must not
        bake a generic requirement-summary into the evidence the model drafts from."""
        res = db.insert_job(JobInsert(
            company="Acme", position="Backend Dev", location="Madrid",
            description="Python, Git, 100% remoto, USD, 0-1 anio",
        ))
        h = res["hash"]
        db.insert_analysis(AnalysisInsert(
            job_hash=h, percentage=80.0, comparativa="c", observaciones="o",
            verdict="Apto", tldr="t", contact_method="email",
        ))
        root = _write_data(tmp_path, perfil=self._rich_perfil())
        monkeypatch.setattr(generate, "_AGENT_ROOT", root)
        payload = self._run_context(h)
        assert payload["job"]["description"] == "Python, Git, 100% remoto, USD, 0-1 anio"
        assert "100% remoto" not in json.dumps(payload["profile_facts"])

    # ------------------------------------------------------------------- #
    # Issue #25 — dedicated cover-letter drafting contract
    # ------------------------------------------------------------------- #
    def test_cover_letter_contract_has_professional_structure(self, tmp_db, tmp_path, monkeypatch):
        """--mode cover-letter returns a dedicated contract whose ordered structure
        is distinct from the email: presentation, relevant experience, connection
        to role, motivation, then CV/closing."""
        h = _seed_job()
        content = "Buenos días,\n\nMe postulo a la vacante de Backend Dev.\n\nUn saludo,\nAna"
        root = _write_data(tmp_path, perfil=self._rich_perfil(), correos=content)
        monkeypatch.setattr(generate, "_AGENT_ROOT", root)
        payload = self._run_context(h, mode="cover-letter")
        assert payload["mode"] == "context"
        assert payload["draft_mode"] == "cover-letter"
        contract = payload["contract"]
        assert contract["draft"] == "cover-letter"
        keys = [sec["key"] for sec in contract["structure"]]
        assert keys == [
            "presentation",
            "relevant_experience",
            "connection_to_role",
            "motivation",
            "cv_closing",
        ]
        order = [contract["structure"].index(s) for s in contract["structure"]]
        for idx, key in enumerate(keys):
            assert contract["structure"][idx]["key"] == key
            assert contract["structure"][idx]["title"]
            assert contract["structure"][idx]["role"]
        assert "Presentación" in contract["structure_summary"]
        assert "CV y cierre" in contract["structure_summary"]

    def test_cover_letter_contract_reuses_correos_only_for_voice(self, tmp_db, tmp_path, monkeypatch):
        """The contract reuses data/correos.md only as the voice source; facts and
        requirements keep their own pinned sources."""
        h = _seed_job()
        root = _write_data(tmp_path, perfil=self._rich_perfil(), correos="Hola, un saludo, Ana")
        monkeypatch.setattr(generate, "_AGENT_ROOT", root)
        contract = self._run_context(h, mode="cover-letter")["contract"]
        sources = contract["sources"]
        assert sources["voice"]["source"] == "data/correos.md"
        # voice is the tone, never the technical content
        assert "voz" in sources["voice"]["usage"]
        assert "skills" in sources["voice"]["usage"] or "tono" in sources["voice"]["usage"]
        assert sources["facts"]["source"] == "profile_facts"
        assert sources["requirements"]["source"] == "job + analysis"
        assert "footer" in sources

    def test_cover_letter_contract_enforces_structural_rules_not_wordings(self, tmp_db, tmp_path, monkeypatch):
        """The contract is user-agnostic: each section is defined structurally by
        what it must contain, and the enforced rules are source-grounding
        safeguards (profile_facts evidence, certifications, remote work, years,
        footer ownership) — not a list of banned wordings."""
        h = _seed_job()
        root = _write_data(tmp_path, perfil=self._rich_perfil())
        monkeypatch.setattr(generate, "_AGENT_ROOT", root)
        contract = self._run_context(h, mode="cover-letter")["contract"]
        prohibited = " ".join(contract["prohibited"]).lower()
        # source-grounding guard: requirements must map to profile_facts evidence
        assert "profile_facts" in prohibited
        assert "requis" in prohibited
        # safeguards preserved
        assert "certificaciones" in prohibited
        assert "remote_work" in prohibited
        assert "experiencia" in prohibited
        assert "footer" in prohibited
        # user-agnostic: no user-specific example phrasing is banned
        assert "cumplo con todo lo que buscan" not in prohibited

    def test_cover_letter_contract_preserves_grounded_facts_and_footer(self, tmp_db, tmp_path, monkeypatch):
        """The cover-letter contract keeps the safeguarded context: profile_facts,
        footer ownership and the salvaguardas all remain present alongside the contract."""
        h = _seed_job()
        root = _write_data(tmp_path, perfil=self._rich_perfil())
        monkeypatch.setattr(generate, "_AGENT_ROOT", root)
        payload = self._run_context(h, mode="cover-letter")
        assert payload["profile_facts"]
        assert payload["footer"] == ["GitHub", "LinkedIn", "CV", "WhatsApp"]
        assert "certificaciones" in payload and "remote_work" in payload
        contract = payload["contract"]
        # footer is owned by the CLI, never duplicated in the body
        assert "footer" in contract["sources"]
        assert "repetirlos" in contract["sources"]["footer"]["usage"].lower()

    def test_context_default_mode_email_has_no_contract(self, tmp_db, tmp_path, monkeypatch):
        """CLI compatibility: the default context (email) keeps its envelope shape and
        adds no draft_mode/contract."""
        h = _seed_job()
        root = _write_data(tmp_path, perfil=self._rich_perfil())
        monkeypatch.setattr(generate, "_AGENT_ROOT", root)
        payload = self._run_context(h)  # no --mode
        assert payload["mode"] == "context"
        assert "draft_mode" not in payload
        assert "contract" not in payload
