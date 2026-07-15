"""Tests for `skills/formatos/scripts/cli.py`.

Unit tests target the pure builders (_build_markdown, _build_json,
_format_date, _format_comparativa, _load_profile); CLI tests
cover --help, happy paths (markdown + json), and the stable error envelopes
(JOB_NOT_FOUND, ANALYSIS_NOT_FOUND, INVALID_FORMAT).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from _lib import db
from _lib.models import AnalysisInsert, JobInsert

# Import the cli module (lives in a scripts dir without a parent
# package on sys.path, so insert it explicitly).
_AGENT_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "cv-pilot-agent"
_FMT_DIR = _AGENT_ROOT / "skills" / "formatos" / "scripts"
if str(_FMT_DIR) not in sys.path:
    sys.path.insert(0, str(_FMT_DIR))

import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("format_report_cli", str(_FMT_DIR / "cli.py"))
format_report = _ilu.module_from_spec(_spec)
sys.modules["format_report_cli"] = format_report
_spec.loader.exec_module(format_report)
from _formatos_internal.builders import (  # noqa: E402
    build_json as _build_json,
    build_markdown as _build_markdown,
    format_comparativa as _format_comparativa,
    format_date as _format_date,
)
from _lib.shared.profile_loader import load_profile as _load_profile  # noqa: E402


runner = CliRunner()

# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
PERFIL_JSON = {
    "nombre": "Julio Andrés Támara Hernández",
    "linkedin": "https://linkedin.com/in/example",
    "github": "https://github.com/example",
    "cv_url": "https://drive.google.com/cv",
}

NO_LINKS_JSON = {
    "nombre": "Anónimo",
}


def _write_perfil(tmp_path: Path, perfil: dict | None = None) -> Path:
    """Create a tmp cv-pilot-agent root with data/perfil.json (JSON happy path)."""
    if perfil is None:
        perfil = PERFIL_JSON
    root = tmp_path / "agent-root"
    (root / "data").mkdir(parents=True)
    with (root / "data" / "perfil.json").open("w", encoding="utf-8") as f:
        json.dump(perfil, f, ensure_ascii=False, indent=2)
    return root


def _seed_job(*, url="https://x.com/job", public_date="2026-06-20",
              location="Madrid", company="Acme", position="Backend Dev") -> str:
    res = db.insert_job(JobInsert(
        company=company, position=position, location=location,
        url=url, public_date=public_date, source="apify",
    ))
    return res["hash"]


def _seed_job_no_analysis(**kwargs) -> str:
    return _seed_job(**kwargs)


def _seed_analysis(job_hash: str, **overrides) -> str:
    fields = dict(
        percentage=82.0,
        comparativa="Python | Análisis: sólido\nFastAPI | Análisis: sólido\nDocker | Análisis: básico",
        observaciones="Stack moderno y bien afín al CV.",
        verdict="Apto",
        tldr="Vacante afín, postular directo.",
        contact_method="email",
    )
    fields.update(overrides)
    res = db.insert_analysis(AnalysisInsert(job_hash=job_hash, **fields))
    return res["analysis_id"]


def _load(job_hash: str):
    return db.get_job(job_hash)["job"], db.get_analysis(job_hash)["analysis"]


# --------------------------------------------------------------------------- #
# 3.1 Unit tests — builders
# --------------------------------------------------------------------------- #
class TestFormatDate:
    def test_public_date_takes_precedence(self):
        job = {"public_date": "2026-06-20"}
        analysis = {"created_at": "2026-06-25 10:00:00"}
        assert _format_date(job, analysis) == "2026-06-20"

    def test_falls_back_to_created_at(self):
        job = {"public_date": None}
        analysis = {"created_at": "2026-06-25 10:00:00"}
        assert _format_date(job, analysis) == "2026-06-25 10:00:00"

    def test_both_missing_returns_empty(self):
        assert _format_date({}, {}) == ""


class TestFormatComparativa:
    def test_normalizes_to_bullets(self):
        out = _format_comparativa("X | an\r\nY | bn")
        assert out == "- X | an\n- Y | bn"

    def test_preserves_literal_pipe_separator(self):
        out = _format_comparativa("Requisito | Análisis: eval con | pipe")
        assert "- Requisito | Análisis: eval con | pipe" in out

    def test_already_bulleted(self):
        out = _format_comparativa("- A | x\n- B | y")
        assert out == "- A | x\n- B | y"

    def test_empty_falls_back(self):
        assert _format_comparativa("") == "_(Sin comparativa)_"
        assert _format_comparativa(None) == "_(Sin comparativa)_"

    def test_blank_lines_skipped(self):
        out = _format_comparativa("a | 1\n\n\nb | 2")
        assert "- a | 1" in out and "- b | 2" in out and "\n\n" not in out


class TestBuildMarkdown:
    def test_complete_report_all_sections(self, tmp_db):
        h = _seed_job()
        _seed_analysis(h)
        job, analysis = _load(h)
        md = _build_markdown(job, analysis, {"cv_url": None, "linkedin": None, "github": None})
        # Section emoji headers in order
        expected_headers = [
            "🆔 ID:", "📅 Fecha:", "🔗 Fuente:", "💻 Empresa:", "🚩 Localidad:",
            "🎯 Porcentaje:", "⚖️ Comparativa Técnica:", "💡 Observaciones y Riesgos:",
            "✅ Veredicto:", "🌟 TL;DR:",
        ]
        positions = [md.index(h) for h in expected_headers]
        assert positions == sorted(positions), "sections out of order"
        # Fields
        assert "Acme" in md and "Backend Dev" in md and "Madrid" in md
        assert "82%" in md
        assert "Apto" in md and "Vacante afín, postular directo." in md
        # Comparativa bullets with literal pipe separator
        assert "- Python | Análisis: sólido" in md

    def test_missing_url_shows_manual_origin(self, tmp_db):
        h = _seed_job(url=None, public_date=None)  # url None and no public_date
        _seed_analysis(h)
        job, analysis = _load(h)
        md = _build_markdown(job, analysis, {})
        assert "Origen: Texto manual" in md
        # created_at fallback for date
        assert analysis["created_at"] in md

    def test_no_salary_line_ever_present(self, tmp_db):
        h = _seed_job()
        _seed_analysis(h)
        job, analysis = _load(h)
        md = _build_markdown(job, analysis, {})
        assert "salary" not in md.lower()
        assert "Salario" not in md and "Sal" not in md

    def test_all_optional_missing_degrades_gracefully(self, tmp_db):
        h = _seed_job(url=None, public_date=None)
        _seed_analysis(h, comparativa="", observaciones="", tldr="")
        job, analysis = _load(h)
        md = _build_markdown(job, analysis, {})
        assert "None" not in md
        assert "null" not in md
        assert "[]" not in md
        assert "_(Sin comparativa)_" in md
        assert "_(Sin observaciones)_" in md
        assert analysis["created_at"] in md

    def test_profile_links_not_appended(self, tmp_path, tmp_db):
        # After commit eda461a, profile links no longer appear in the analysis
        # report (they belong in emails/cover-letters, not in the job report).
        h = _seed_job()
        _seed_analysis(h)
        job, analysis = _load(h)
        profile = {"cv_url": "https://cv", "linkedin": "https://li", "github": "https://gh"}
        md = _build_markdown(job, analysis, profile)
        assert '<a href="https://cv">CV</a>' not in md
        assert '<a href="https://li">LinkedIn</a>' not in md
        assert '<a href="https://gh">GitHub</a>' not in md

    def test_no_profile_links_no_section(self, tmp_db):
        h = _seed_job()
        _seed_analysis(h)
        job, analysis = _load(h)
        md = _build_markdown(job, analysis, {"cv_url": None, "linkedin": None, "github": None})
        assert ">CV</a>" not in md
        assert ">LinkedIn</a>" not in md
        assert ">GitHub</a>" not in md

    def test_unicode_preserved(self, tmp_db):
        h = _seed_job(location="Medellín")
        _seed_analysis(h, observaciones="Ñandú con acento y 🎉", tldr="Resumen con émoji")
        job, analysis = _load(h)
        md = _build_markdown(job, analysis, {})
        assert "Medellín" in md
        assert "Ñandú" in md and "🎉" in md and "émoji" in md

    def test_percentage_rounds_to_int(self, tmp_db):
        h = _seed_job()
        _seed_analysis(h, percentage=82.6)
        job, analysis = _load(h)
        md = _build_markdown(job, analysis, {})
        assert "83%" in md

    def test_markdown_syntax_chars_preserved(self, tmp_db):
        h = _seed_job()
        _seed_analysis(
            h,
            observaciones="Usa *patrones* y [referencias]_con_guion. Ver #123.",
            tldr="Stack [moderno] con _énfasis_ y *destreza*.",
        )
        job, analysis = _load(h)
        md = _build_markdown(job, analysis, {})
        assert "*patrones*" in md
        assert "[referencias]_con_guion" in md
        assert "#123" in md
        assert "[moderno]" in md
        assert "_énfasis_" in md
        assert "*destreza*" in md
        assert "🆔 ID:" in md
        assert "⚖️ Comparativa" in md


class TestBuildProfile:
    def test_parses_name_and_links(self, tmp_path, monkeypatch):
        root = _write_perfil(tmp_path)
        p = _load_profile(root)
        assert p["name"] == "Julio Andrés Támara Hernández"
        assert p["linkedin"] == "https://linkedin.com/in/example"
        assert p["github"] == "https://github.com/example"
        assert p["cv_url"] == "https://drive.google.com/cv"

    def test_missing_file_raises_file_not_found(self, tmp_path, monkeypatch):
        root = tmp_path / "no-perfil"
        root.mkdir()
        with pytest.raises(FileNotFoundError):
            _load_profile(root)


class TestBuildJson:
    def test_includes_all_spec_keys(self, tmp_db):
        h = _seed_job()
        _seed_analysis(h)
        job, analysis = _load(h)
        obj = _build_json(job, analysis, {"cv_url": None, "linkedin": None, "github": None})
        required = {
            "analysis_id", "job_hash", "percentage", "comparativa",
            "observaciones", "verdict", "tldr", "contact_method",
            "created_at", "company", "position", "location", "url", "source",
        }
        assert required.issubset(obj.keys())
        assert obj["company"] == "Acme"
        assert obj["contact_method"] == "email"
        assert obj["source"] == "apify"

    def test_null_fields_are_json_null(self):
        job_row = {"company": "Acme", "position": "BE", "location": "Mad", "url": None, "source": "manual"}
        analysis_row = {
            "analysis_id": "id1", "job_hash": "h1", "percentage": None,
            "comparativa": None, "observaciones": None, "verdict": None,
            "tldr": None, "contact_method": None, "created_at": None,
        }
        obj = _build_json(job_row, analysis_row, {})
        serialized = json.loads(json.dumps(obj))
        assert serialized["comparativa"] is None
        assert serialized["observaciones"] is None
        assert serialized["url"] is None
        assert serialized["verdict"] is None
        assert serialized["contact_method"] is None
        # ensure no string "null"/"None" leak in
        assert "None" not in json.dumps(obj)
        assert '"null"' not in json.dumps(obj)


# --------------------------------------------------------------------------- #
# 3.2 CLI tests
# --------------------------------------------------------------------------- #
class TestCLI:
    def test_help_exits_zero(self):
        result = runner.invoke(format_report.app, ["main", "--help"])
        assert result.exit_code == 0
        assert "--job" in result.stdout
        assert "--format" in result.stdout

    def test_default_markdown(self, tmp_db, tmp_path, monkeypatch):
        root = _write_perfil(tmp_path)
        monkeypatch.setattr(format_report, "_AGENT_ROOT", root)
        # Patch the profile loader to use our test root
        import _lib.shared.profile_loader as pl
        monkeypatch.setattr(pl, "load_profile", lambda r=None: _load_profile(root))
        h = _seed_job()
        _seed_analysis(h)
        result = runner.invoke(format_report.app, ["main", "--job", h])
        assert result.exit_code == 0, result.stderr
        out = result.stdout
        assert "🆔 ID:" in out
        assert "Acme" in out and "82%" in out
        assert "Apto" in out
        assert '<a href="https://linkedin.com/in/example">LinkedIn</a>' not in out

    def test_explicit_json(self, tmp_db, tmp_path, monkeypatch):
        root = _write_perfil(tmp_path)
        monkeypatch.setattr(format_report, "_AGENT_ROOT", root)
        import _lib.shared.profile_loader as pl
        monkeypatch.setattr(pl, "load_profile", lambda r=None: _load_profile(root))
        h = _seed_job()
        _seed_analysis(h)
        result = runner.invoke(format_report.app, ["main", "--job", h, "--format", "json"])
        assert result.exit_code == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["format"] == "json"
        report = payload["report"]
        assert report["company"] == "Acme"
        assert report["contact_method"] == "email"
        assert report["source"] == "apify"

    def test_invalid_format(self, tmp_db, tmp_path, monkeypatch):
        root = _write_perfil(tmp_path)
        monkeypatch.setattr(format_report, "_AGENT_ROOT", root)
        import _lib.shared.profile_loader as pl
        monkeypatch.setattr(pl, "load_profile", lambda r=None: _load_profile(root))
        h = _seed_job()
        _seed_analysis(h)
        result = runner.invoke(format_report.app, ["main", "--job", h, "--format", "xml"])
        assert result.exit_code == 1
        err = json.loads(result.stderr)
        assert err["ok"] is False
        assert err["code"] == "INVALID_FORMAT"
        assert "markdown" in err["error"] and "json" in err["error"]

    def test_job_not_found(self, tmp_db, tmp_path, monkeypatch):
        root = _write_perfil(tmp_path)
        monkeypatch.setattr(format_report, "_AGENT_ROOT", root)
        import _lib.shared.profile_loader as pl
        monkeypatch.setattr(pl, "load_profile", lambda r=None: _load_profile(root))
        result = runner.invoke(format_report.app, ["main", "--job", "deadbeef"])
        assert result.exit_code == 1
        err = json.loads(result.stderr)
        assert err["code"] == "JOB_NOT_FOUND"

    def test_analysis_not_found(self, tmp_db, tmp_path, monkeypatch):
        root = _write_perfil(tmp_path)
        monkeypatch.setattr(format_report, "_AGENT_ROOT", root)
        import _lib.shared.profile_loader as pl
        monkeypatch.setattr(pl, "load_profile", lambda r=None: _load_profile(root))
        h = _seed_job_no_analysis()
        result = runner.invoke(format_report.app, ["main", "--job", h])
        assert result.exit_code == 1
        err = json.loads(result.stderr)
        assert err["code"] == "ANALYSIS_NOT_FOUND"

    def test_missing_job_flag_is_usage_error(self, tmp_db):
        result = runner.invoke(format_report.app, ["main"])
        assert result.exit_code != 0
        assert "--job" in (result.stdout + result.stderr)

    def test_markdown_without_profile_links(self, tmp_db, tmp_path, monkeypatch):
        root = _write_perfil(tmp_path, NO_LINKS_JSON)
        monkeypatch.setattr(format_report, "_AGENT_ROOT", root)
        import _lib.shared.profile_loader as pl
        monkeypatch.setattr(pl, "load_profile", lambda r=None: _load_profile(root))
        h = _seed_job()
        _seed_analysis(h)
        result = runner.invoke(format_report.app, ["main", "--job", h])
        assert result.exit_code == 0, result.stderr
        assert ">LinkedIn</a>" not in result.stdout
        assert ">GitHub</a>" not in result.stdout
        assert ">CV</a>" not in result.stdout


# --------------------------------------------------------------------------- #
# 3.3 CLI tests — `all` command
# --------------------------------------------------------------------------- #

_IMPROVISED_PHRASES = [
    "Aquí te muestro",
    "A continuación",
    "Te presento",
    "Aqui tienes",
    "Aquí tienes",
    "Here is",
    "Here are",
    "Below you will find",
    "I'll show you",
]


class TestCLIAll:
    def test_help_exits_zero(self):
        result = runner.invoke(format_report.app, ["all", "--help"])
        assert result.exit_code == 0
        assert "--format" in result.stdout
        assert "--status" in result.stdout
        assert "--limit" in result.stdout

    def test_formatos_all_with_no_jobs(self, tmp_db, tmp_path, monkeypatch):
        """Empty DB -> clear message, exit 0."""
        root = _write_perfil(tmp_path)
        monkeypatch.setattr(format_report, "_AGENT_ROOT", root)
        import _lib.shared.profile_loader as pl
        monkeypatch.setattr(pl, "load_profile", lambda r=None: _load_profile(root))
        result = runner.invoke(format_report.app, ["all"])
        assert result.exit_code == 0, result.stderr
        assert "No hay análisis pendientes" in result.stdout

    def test_formatos_all_with_jobs(self, tmp_db, tmp_path, monkeypatch):
        """DB con 3 jobs analizados → output markdown contiene los 3, secciones correctas."""
        root = _write_perfil(tmp_path)
        monkeypatch.setattr(format_report, "_AGENT_ROOT", root)
        import _lib.shared.profile_loader as pl
        monkeypatch.setattr(pl, "load_profile", lambda r=None: _load_profile(root))

        h1 = _seed_job(company="Alpha", position="Dev", location="Madrid")
        _seed_analysis(h1, percentage=80, verdict="Apto", tldr="Tldr alpha")
        h2 = _seed_job(company="Beta", position="QA", location="Barcelona")
        _seed_analysis(h2, percentage=65, verdict="Apto con reservas", tldr="Tldr beta")
        h3 = _seed_job(company="Gamma", position="Lead", location="Valencia")
        _seed_analysis(h3, percentage=90, verdict="Apto", tldr="Tldr gamma")

        result = runner.invoke(format_report.app, ["all"])
        assert result.exit_code == 0, result.stderr
        out = result.stdout

        # All 3 companies appear
        assert "Alpha" in out
        assert "Beta" in out
        assert "Gamma" in out

        # All 3 verdicts appear
        assert "Tldr alpha" in out
        assert "Tldr beta" in out
        assert "Tldr gamma" in out

        # Section headers appear (from build_markdown)
        assert "🆔 ID:" in out
        assert "✅ Veredicto:" in out

        # Separators between reports
        assert out.count("---") >= 2

    def test_formatos_all_json_format(self, tmp_db, tmp_path, monkeypatch):
        """--format json → JSON parseable con lista de jobs."""
        root = _write_perfil(tmp_path)
        monkeypatch.setattr(format_report, "_AGENT_ROOT", root)
        import _lib.shared.profile_loader as pl
        monkeypatch.setattr(pl, "load_profile", lambda r=None: _load_profile(root))

        h1 = _seed_job(company="Alpha", position="Dev", location="Madrid")
        _seed_analysis(h1, percentage=80)
        h2 = _seed_job(company="Beta", position="QA", location="Barcelona")
        _seed_analysis(h2, percentage=65)

        result = runner.invoke(format_report.app, ["all", "--format", "json"])
        assert result.exit_code == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["format"] == "json"
        assert payload["count"] == 2
        assert len(payload["reports"]) == 2
        # Each entry has job_hash and report
        for entry in payload["reports"]:
            assert "job_hash" in entry
            assert "report" in entry
            assert "company" in entry["report"]

    def test_formatos_all_json_no_jobs(self, tmp_db, tmp_path, monkeypatch):
        """--format json with empty DB -> valid JSON with count 0."""
        root = _write_perfil(tmp_path)
        monkeypatch.setattr(format_report, "_AGENT_ROOT", root)
        import _lib.shared.profile_loader as pl
        monkeypatch.setattr(pl, "load_profile", lambda r=None: _load_profile(root))

        result = runner.invoke(format_report.app, ["all", "--format", "json"])
        assert result.exit_code == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["count"] == 0
        assert payload["reports"] == []

    def test_formatos_all_does_not_improvise(self, tmp_db, tmp_path, monkeypatch):
        """El output NO contiene texto improvisado por el LLM."""
        root = _write_perfil(tmp_path)
        monkeypatch.setattr(format_report, "_AGENT_ROOT", root)
        import _lib.shared.profile_loader as pl
        monkeypatch.setattr(pl, "load_profile", lambda r=None: _load_profile(root))

        h = _seed_job()
        _seed_analysis(h)

        result = runner.invoke(format_report.app, ["all"])
        assert result.exit_code == 0, result.stderr
        out = result.stdout
        for phrase in _IMPROVISED_PHRASES:
            assert phrase not in out, f"LLM-improvised phrase found in output: '{phrase}'"

    def test_formatos_all_respects_limit(self, tmp_db, tmp_path, monkeypatch):
        """--limit 1 → solo 1 reporte."""
        root = _write_perfil(tmp_path)
        monkeypatch.setattr(format_report, "_AGENT_ROOT", root)
        import _lib.shared.profile_loader as pl
        monkeypatch.setattr(pl, "load_profile", lambda r=None: _load_profile(root))

        _seed_analysis(_seed_job(company="A", position="P", location="L"))
        _seed_analysis(_seed_job(company="B", position="Q", location="M"))

        result = runner.invoke(format_report.app, ["all", "--limit", "1", "--format", "json"])
        assert result.exit_code == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["count"] == 1

    def test_formatos_all_deterministic(self, tmp_db, tmp_path, monkeypatch):
        """Mismo input → mismo output byte-a-byte."""
        root = _write_perfil(tmp_path)
        monkeypatch.setattr(format_report, "_AGENT_ROOT", root)
        import _lib.shared.profile_loader as pl
        monkeypatch.setattr(pl, "load_profile", lambda r=None: _load_profile(root))

        h = _seed_job()
        _seed_analysis(h)

        r1 = runner.invoke(format_report.app, ["all"])
        r2 = runner.invoke(format_report.app, ["all"])
        assert r1.stdout == r2.stdout
        assert r1.exit_code == r2.exit_code == 0