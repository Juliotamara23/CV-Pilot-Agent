"""PR1 tests — deterministic skill index + schema foundation."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

_AGENT_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "cv-pilot-agent"
if str(_AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(_AGENT_ROOT))

from _lib._schema import get_schema_sql
from _lib.skill_index import (
    SkillIndex, SkillRecord, _derive_triggers, _parse_frontmatter,
    build_index, _to_json,
)

_SKILLS_DIR = _AGENT_ROOT / "skills"


# -- frontmatter parsing --

class TestFrontmatterParsing:
    def test_valid(self):
        fm = _parse_frontmatter("---\nname: T\ndescription: d.\nscope: G\n---\n# B\n")
        assert fm and fm["name"] == "T"

    def test_missing(self):
        assert _parse_frontmatter("# No fm\n") is None

    def test_malformed_yaml(self):
        assert _parse_frontmatter("---\n: [bad\n---\n") is None

    def test_non_dict(self):
        assert _parse_frontmatter("---\n- a\n- b\n---\n") is None


# -- trigger derivation --

class TestTriggerDerivation:
    def test_basic_split(self):
        t = _derive_triggers("CLI query.py para CRUD de vacantes")
        assert "cli" in t and "vacantes" in t
        assert t == sorted(t)

    def test_dedup(self):
        t = _derive_triggers("foo bar foo baz bar")
        assert t.count("foo") == 1 and t.count("bar") == 1

    def test_empty(self):
        assert _derive_triggers("") == []


# -- determinism --

class TestBuildIndexDeterministic:
    def _build(self):
        return build_index(_SKILLS_DIR)

    def test_skills_byte_identical(self):
        d1 = json.loads(_to_json(self._build()))
        d2 = json.loads(_to_json(self._build()))
        assert d1["skills"] == d2["skills"]
        assert d1["source_root"] == d2["source_root"]

    def test_sorted_by_name(self):
        idx = self._build()
        assert [s.name for s in idx.skills] == sorted(s.name for s in idx.skills)


# -- index content --

class TestBuildIndexContent:
    def _build(self):
        return build_index(_SKILLS_DIR)

    def test_six_skills(self):
        idx = self._build()
        names = {s.name for s in idx.skills}
        assert len(idx.skills) == 6
        for n in ["Skill Apify Scraper", "Database Manager", "Mimetismo — Generate CLI",
                   "Onboarding (CLI determinista)", "Skill Formatos", "cv-update"]:
            assert n in names

    def test_required_fields(self):
        for s in self._build().skills:
            assert s.name and s.description and s.scope
            assert s.path.startswith("skills/") and s.path.endswith("/SKILL.md")
            assert isinstance(s.triggers, list) and isinstance(s.subcommands, list)
            assert isinstance(s.required_in_flujo, bool)

    def test_versions(self):
        by_name = {s.name: s for s in self._build().skills}
        assert by_name["Skill Apify Scraper"].version == "3.0"
        assert by_name["Skill Formatos"].version == "4.1"
        assert by_name["Database Manager"].version is None
        assert by_name["Mimetismo — Generate CLI"].version is None

    def test_required_in_flujo(self):
        by_name = {s.name: s for s in self._build().skills}
        assert by_name["Onboarding (CLI determinista)"].required_in_flujo is True
        assert by_name["cv-update"].required_in_flujo is True
        assert by_name["Database Manager"].required_in_flujo is False

    def test_source_root(self):
        assert self._build().source_root == "skills"


# -- malformed frontmatter --

class TestBuildIndexMalformed:
    def test_no_frontmatter(self, tmp_path):
        d = tmp_path / "s"; d.mkdir()
        (d / "SKILL.md").write_text("# text\n")
        assert build_index(tmp_path).skills == []

    def test_bad_yaml_warns(self, tmp_path, capsys):
        d = tmp_path / "s"; d.mkdir()
        (d / "SKILL.md").write_text("---\n: [bad\n---\nbody\n")
        assert build_index(tmp_path).skills == []
        assert "warning" in capsys.readouterr().err.lower()

    def test_missing_fields(self, tmp_path):
        d = tmp_path / "s"; d.mkdir()
        (d / "SKILL.md").write_text("---\nname: X\n---\nbody\n")
        assert build_index(tmp_path).skills == []

    def test_valid_alongside_invalid(self, tmp_path):
        bad = tmp_path / "bad"; bad.mkdir()
        (bad / "SKILL.md").write_text("no fm\n")
        good = tmp_path / "good"; good.mkdir()
        (good / "SKILL.md").write_text("---\nname: G\ndescription: d.\nscope: X\n---\nb\n")
        idx = build_index(tmp_path)
        assert len(idx.skills) == 1 and idx.skills[0].name == "G"

    def test_missing_root_exits_1(self, tmp_path):
        with pytest.raises(SystemExit, match="1"):
            build_index(tmp_path / "nope")


# -- rules exclusion --

class TestIndexExcludesRules:
    def test_no_rules_in_real_index(self):
        for s in build_index(_SKILLS_DIR).skills:
            assert "rules/" not in s.path

    def test_rules_dir_not_scanned(self, tmp_path):
        sk = tmp_path / "skills"; sk.mkdir()
        d = sk / "s"; d.mkdir()
        (d / "SKILL.md").write_text("---\nname: S\ndescription: d.\nscope: X\n---\nb\n")
        rules = tmp_path / "rules"; rules.mkdir()
        (rules / "persona.md").write_text("---\nname: P\n---\n")
        idx = build_index(sk)
        assert len(idx.skills) == 1


# -- schema: skill_loads table --

class TestSkillLoadsSchema:
    def test_table_exists(self, tmp_db):
        conn = sqlite3.connect(tmp_db)
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='skill_loads'"
        ).fetchone()
        conn.close()
        assert row is not None

    def test_columns(self, tmp_db):
        conn = sqlite3.connect(tmp_db)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(skill_loads)").fetchall()}
        conn.close()
        assert {"skill_name", "version", "loaded_at", "trigger", "session_id", "requested_by"} <= cols

    def test_indexes(self, tmp_db):
        conn = sqlite3.connect(tmp_db)
        idxs = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'ix_skill_loads%'"
        ).fetchall()}
        conn.close()
        assert {"ix_skill_loads_skill", "ix_skill_loads_session"} <= idxs

    def test_insert_roundtrip(self, tmp_db):
        conn = sqlite3.connect(tmp_db)
        conn.execute(
            "INSERT INTO skill_loads VALUES (?,?,?,?,?,?)",
            ("apify", "3.0", "2026-09-03T12:00:00Z", "explicit", "ses_1", "cli"),
        )
        conn.commit()
        rows = conn.execute("SELECT * FROM skill_loads").fetchall()
        conn.close()
        assert len(rows) == 1 and rows[0][0] == "apify"
