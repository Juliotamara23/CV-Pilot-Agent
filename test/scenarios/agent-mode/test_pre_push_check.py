"""Tests for `scripts/pre_push_check.py` — the push gate script.

Covers the three check categories plus the entry point:
  Check A: broken path references in orchestrator markdown files
  Check B: bidirectional skill registration between AGENTS.md and skills/
  Check C: Flujo coverage of declared skills

The script is stdlib-only and reads synthetic repo structures from
``tmp_path`` fixtures — no real repository mutation.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

# Load scripts/pre_push_check.py directly (it is not a package module).
_SCRIPTS_DIR = (Path(__file__).resolve().parent.parent.parent.parent / "cv-pilot-agent" / "scripts")
_SCRIPT = importlib.util.spec_from_file_location("pre_push_check", _SCRIPTS_DIR / "pre_push_check.py")
if _SCRIPT is None or _SCRIPT.loader is None:
    raise ImportError(f"could not load pre_push_check from {_SCRIPTS_DIR}")
ppc = importlib.util.module_from_spec(_SCRIPT)
sys.modules["pre_push_check"] = ppc
_SCRIPT.loader.exec_module(ppc)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mini_repo(tmp_path: Path) -> Path:
    """Build a minimal valid repository layout for pre-push checks."""
    agent = tmp_path / "cv-pilot-agent"
    (agent / "rules").mkdir(parents=True)
    (agent / "skills").mkdir()
    (agent / "scripts").mkdir()
    (agent / "AGENTS.md").write_text(
        "# CV-Pilot\n\n"
        "## Skills\n"
        "| Skills | skills/{onboarding,cv-update,database,mimetismo,apify,formatos}/SKILL.md |\n\n"
        "## Flujo\n\n"
        "**1. Inicialización**\n"
        "**2. Detección de intención**\n"
        "**3. Verificar DB**\n"
        "**4a. Sourcing Apify**\n"
        "**4b. Sourcing Manual**\n"
        "**5. Análisis**\n"
        "**6. Redacción**\n"
        "**7. Discusión**\n",
        encoding="utf-8",
    )
    for skill in ["onboarding", "cv-update", "database", "mimetismo", "apify", "formatos"]:
        (agent / "skills" / skill).mkdir(parents=True)
        (agent / "skills" / skill / "SKILL.md").write_text(
            f"---\nname: {skill}\n---\n\n# {skill}\n",
            encoding="utf-8",
        )
    return tmp_path


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

class TestCheckResult:
    def test_passed_true_when_pass(self):
        assert CheckResult("x", "PASS").passed() is True

    def test_passed_false_when_fail(self):
        assert CheckResult("x", "FAIL").passed() is False

    def test_passed_true_when_warn(self):
        assert CheckResult("x", "WARN").passed() is True

    def test_details_default_empty(self):
        assert CheckResult("x", "PASS").details == []


def CheckResult(name, status):
    return ppc.CheckResult(name=name, status=status)


# ---------------------------------------------------------------------------
# Repository discovery
# ---------------------------------------------------------------------------

class TestFindRepoRoot:
    def test_finds_repo_root_from_nested_dir(self, tmp_path):
        root = tmp_path
        (root / ".git").mkdir()
        nested = root / "a" / "b"
        nested.mkdir(parents=True)
        assert ppc.find_repo_root(nested) == root.resolve()

    def test_raises_when_no_git(self, tmp_path):
        with pytest.raises(RuntimeError, match="no .git"):
            ppc.find_repo_root(tmp_path)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_looks_like_url(self):
        assert ppc.looks_like_url("https://example.com") is True
        assert ppc.looks_like_url("http://x.io") is True
        assert ppc.looks_like_url("skills/foo/SKILL.md") is False

    def test_is_bak(self):
        assert ppc.is_bak("file.bak") is True
        assert ppc.is_bak("file.py") is False

    def test_path_token_pattern_matches_common_prefixes(self):
        for token in [
            "./README.md",
            "skills/apify/SKILL.md",
            "rules/persona.md",
            "data/perfil.json",
            "_lib/db.py",
            "scripts/init.py",
            "docs/plan.md",
            "test/scenarios/agent-mode/test_x.py",
            "cv-pilot-agent/AGENTS.md",
        ]:
            assert ppc.PATH_TOKEN_PATTERN.search(token), f"no match for {token}"

    def test_path_token_pattern_does_not_match_urls(self):
        assert ppc.PATH_TOKEN_PATTERN.search("https://example.com") is None

    def test_get_code_spans_detects_fences(self):
        text = "a\n```\nb\n```\nc"
        spans = ppc._get_code_spans(text)
        assert len(spans) == 1
        start, end = spans[0]
        assert text[start:end] == "```\nb\n```"

    def test_is_inside_span(self):
        assert ppc._is_inside_span(2, [(1, 5)]) is True
        assert ppc._is_inside_span(5, [(1, 5)]) is False  # exclusive end
        assert ppc._is_inside_span(0, [(1, 5)]) is False

    def test_is_template_fragment_detects_placeholder(self):
        source = "see skills/<skill>/scripts/cli.py now"
        # The token 'scripts/cli.py' is inside a placeholder run.
        assert ppc._is_template_fragment(source, (9, 22)) is True

    def test_path_exists_on_disk_relative_to_md(self, tmp_path):
        md = tmp_path / "doc" / "readme.md"
        md.parent.mkdir()
        (tmp_path / "doc" / "target.txt").write_text("x")
        md.write_text("x")
        assert ppc._path_exists_on_disk(tmp_path, md, "target.txt") is True
        assert ppc._path_exists_on_disk(tmp_path, md, "missing.txt") is False

    def test_path_exists_on_disk_absolute(self, tmp_path):
        md = tmp_path / "readme.md"
        (tmp_path / "file.txt").write_text("x")
        md.write_text("x")
        assert ppc._path_exists_on_disk(tmp_path, md, str(tmp_path / "file.txt")) is True

    def test_path_exists_on_disk_agent_root(self, tmp_path):
        agent = tmp_path / "cv-pilot-agent"
        agent.mkdir()
        (agent / "perfil.json").write_text("{}")
        md = agent / "rules" / "persona.md"
        md.parent.mkdir(parents=True)
        md.write_text("x")
        # Path referenced from cv-pilot-agent root convention.
        assert ppc._path_exists_on_disk(tmp_path, md, "perfil.json") is True

    def test_is_interesting_token_filters(self):
        assert ppc._is_interesting_token("skills/foo.py") is True
        assert ppc._is_interesting_token("https://x.io") is False
        assert ppc._is_interesting_token("file.bak") is False
        assert ppc._is_interesting_token("skills/") is False


# ---------------------------------------------------------------------------
# Check A: broken references
# ---------------------------------------------------------------------------

class TestCheckBrokenReferences:
    def test_pass_with_no_broken_refs(self, mini_repo):
        result = ppc.check_broken_references(mini_repo)
        assert result.passed()
        assert "no broken refs" in result.details[0]

    def test_fail_when_ref_is_broken(self, mini_repo):
        (mini_repo / "cv-pilot-agent" / "rules" / "persona.md").write_text(
            "Read skills/nonexistent/x.md for more.\n", encoding="utf-8"
        )
        result = ppc.check_broken_references(mini_repo)
        assert result.status == "FAIL"
        assert "skills/nonexistent/x.md" in result.details[0]

    def test_fail_when_ref_broken_inline_backtick(self, mini_repo):
        # Inline backticks are NOT excluded — real references use them.
        (mini_repo / "cv-pilot-agent" / "rules" / "persona.md").write_text(
            "Read `skills/nonexistent/y.md` for more.\n", encoding="utf-8"
        )
        result = ppc.check_broken_references(mini_repo)
        assert result.status == "FAIL"

    def test_warn_when_ref_has_deprecation_hint(self, mini_repo):
        (mini_repo / "cv-pilot-agent" / "rules" / "persona.md").write_text(
            "This file was removed: skills/old/x.md no longer exists.\n", encoding="utf-8"
        )
        result = ppc.check_broken_references(mini_repo)
        assert result.status == "PASS"  # WARN does not fail the check
        assert any("WARN" in d for d in result.details)

    def test_skips_placeholder_templates(self, mini_repo):
        (mini_repo / "cv-pilot-agent" / "rules" / "persona.md").write_text(
            "Run skills/<skill>/scripts/cli.py\n", encoding="utf-8"
        )
        result = ppc.check_broken_references(mini_repo)
        assert result.passed()

    def test_skips_broken_ref_in_shell_example_fence(self, mini_repo):
        # Fenced block that looks like a shell command — excluded.
        (mini_repo / "cv-pilot-agent" / "rules" / "persona.md").write_text(
            "```bash\n$ python skills/nonexistent/cli.py --help\n```\n",
            encoding="utf-8",
        )
        result = ppc.check_broken_references(mini_repo)
        assert result.passed()

    def test_detects_broken_ref_in_plain_fence(self, mini_repo):
        # Fenced block with plain file references — NOT a shell example.
        (mini_repo / "cv-pilot-agent" / "rules" / "persona.md").write_text(
            "```\nskills/nonexistent/cli.py\n```\n",
            encoding="utf-8",
        )
        result = ppc.check_broken_references(mini_repo)
        assert result.status == "FAIL"

    def test_block_is_shell_example(self):
        assert ppc._block_is_shell_example("```\n$ python x.py\n```", (0, 20)) is True
        assert ppc._block_is_shell_example("```\n> echo hi\n```", (0, 20)) is True
        assert ppc._block_is_shell_example("```\nskills/a.md\n```", (0, 20)) is False


# ---------------------------------------------------------------------------
# Check B: bidirectional skill registration
# ---------------------------------------------------------------------------

class TestCheckBidirectionalSkills:
    def test_pass_when_registration_matches(self, mini_repo):
        result = ppc.check_bidirectional_skills(mini_repo)
        assert result.passed()
        assert "6 skills" in result.details[0]

    def test_fail_when_declared_skill_missing_on_disk(self, mini_repo):
        agents = mini_repo / "cv-pilot-agent" / "AGENTS.md"
        agents.write_text(
            agents.read_text().replace(
                "{onboarding,cv-update,database,mimetismo,apify,formatos}",
                "{onboarding,cv-update,database,mimetismo,apify,formatos,ghost}",
            ),
            encoding="utf-8",
        )
        result = ppc.check_bidirectional_skills(mini_repo)
        assert result.status == "FAIL"
        assert "ghost" in result.details[0]

    def test_fail_when_skill_on_disk_not_declared(self, mini_repo):
        (mini_repo / "cv-pilot-agent" / "skills" / "extra").mkdir()
        (mini_repo / "cv-pilot-agent" / "skills" / "extra" / "SKILL.md").write_text(
            "---\nname: extra\n---\n", encoding="utf-8"
        )
        result = ppc.check_bidirectional_skills(mini_repo)
        assert result.status == "FAIL"
        assert "extra" in result.details[0]

    def test_extract_skill_names_from_braces(self, mini_repo):
        agents = mini_repo / "cv-pilot-agent" / "AGENTS.md"
        names = ppc._extract_skill_names_from_skills_row(agents)
        assert set(names) == {
            "onboarding", "cv-update", "database", "mimetismo", "apify", "formatos",
        }


# ---------------------------------------------------------------------------
# Check C: Flujo coverage
# ---------------------------------------------------------------------------

class TestCheckFlujoCoverage:
    def test_pass_when_all_skills_referenced(self, mini_repo):
        result = ppc.check_flujo_coverage(mini_repo)
        assert result.passed()

    def test_warn_when_declared_skill_missing_from_flujo(self, mini_repo):
        agents = mini_repo / "cv-pilot-agent" / "AGENTS.md"
        # Remove all flujo references to 'database' skill.
        text = agents.read_text()
        text = text.replace("**3. Verificar DB**\n", "")
        agents.write_text(text, encoding="utf-8")
        result = ppc.check_flujo_coverage(mini_repo)
        assert result.passed()  # WARN only unless required_in_flujo
        assert any("database" in d for d in result.details)

    def test_fail_when_required_skill_missing(self, mini_repo):
        # Mark 'apify' as required_in_flujo and remove it from Flujo.
        apify_md = mini_repo / "cv-pilot-agent" / "skills" / "apify" / "SKILL.md"
        apify_md.write_text(
            "---\nname: apify\nrequired_in_flujo: true\n---\n\n# apify\n",
            encoding="utf-8",
        )
        agents = mini_repo / "cv-pilot-agent" / "AGENTS.md"
        text = agents.read_text()
        text = text.replace("**4a. Sourcing Apify**\n", "")
        agents.write_text(text, encoding="utf-8")
        result = ppc.check_flujo_coverage(mini_repo)
        assert result.status == "FAIL"
        assert "apify" in result.details[0]

    def test_fail_when_no_flujo_section(self, mini_repo):
        agents = mini_repo / "cv-pilot-agent" / "AGENTS.md"
        agents.write_text("# No flujo here\n", encoding="utf-8")
        result = ppc.check_flujo_coverage(mini_repo)
        assert result.status == "FAIL"

    def test_parse_frontmatter_bool(self, tmp_path):
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            "---\nrequired_in_flujo: true\n---\n", encoding="utf-8"
        )
        assert ppc._parse_frontmatter_bool(skill_md, "required_in_flujo") is True

    def test_parse_frontmatter_bool_false(self, tmp_path):
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            "---\nrequired_in_flujo: false\n---\n", encoding="utf-8"
        )
        assert ppc._parse_frontmatter_bool(skill_md, "required_in_flujo") is False

    def test_parse_frontmatter_bool_missing_key(self, tmp_path):
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("---\nname: x\n---\n", encoding="utf-8")
        assert ppc._parse_frontmatter_bool(skill_md, "required_in_flujo") is None


# ---------------------------------------------------------------------------
# Check F: SKILL.md token budget
# ---------------------------------------------------------------------------

BUDGET_TEST_BODY = ("long contract text telling the agent how to run the CLI. " * 80)


def _write_overbudget_skill(mini_repo, slug="apify"):
    skill_md = mini_repo / "cv-pilot-agent" / "skills" / slug / "SKILL.md"
    skill_md.write_text(
        f"---\nname: {slug}\n---\n\n" + BUDGET_TEST_BODY,
        encoding="utf-8",
    )
    return skill_md


class TestCheckSkillTokenBudget:
    def test_pass_when_all_within_budget(self, mini_repo):
        result = ppc.check_skill_token_budget(mini_repo)
        assert result.status == "PASS"
        assert result.passed()

    def test_fail_when_skill_over_budget(self, mini_repo):
        _write_overbudget_skill(mini_repo)
        result = ppc.check_skill_token_budget(mini_repo)
        assert result.status == "FAIL"
        assert not result.passed()

    def test_fail_detail_names_file_count_budget_estimator_and_guidance(self, mini_repo):
        skill_md = _write_overbudget_skill(mini_repo, "database")
        result = ppc.check_skill_token_budget(mini_repo)
        assert result.status == "FAIL"
        detail = result.details[0]
        assert str(skill_md.relative_to(mini_repo)) in detail
        assert re.search(r"\d+ tokens exceeds budget 700", detail)
        assert "estimator:" in detail
        assert re.search(r"estimator: (tiktoken|len//4)", detail)
        assert "--help" in detail
        assert "flag tables" in detail

    def test_verdict_identical_with_and_without_token_counter(self, mini_repo, monkeypatch):
        """The same over-budget fixture must FAIL under BOTH estimators."""
        _write_overbudget_skill(mini_repo)
        result_with = ppc.check_skill_token_budget(mini_repo)
        assert result_with.status == "FAIL"
        # Simulate an environment without the token counter helper.
        monkeypatch.setattr(ppc, "_load_token_counter", lambda root: None)
        result_without = ppc.check_skill_token_budget(mini_repo)
        assert result_without.status == result_with.status == "FAIL"
        assert "estimator: len//4" in result_without.details[0]
        assert "estimator: tiktoken" in result_with.details[0]

    def test_agents_md_is_not_budgeted(self, mini_repo):
        agents = mini_repo / "cv-pilot-agent" / "AGENTS.md"
        agents.write_text("# CV-Pilot\n\n" + ("filler sentence for budget\n" * 400), encoding="utf-8")
        result = ppc.check_skill_token_budget(mini_repo)
        assert result.status == "PASS"
        assert "AGENTS.md" not in " ".join(result.details)

    def test_main_includes_check_f(self, mini_repo):
        assert ppc.main(["--repo-root", str(mini_repo), "--quiet"]) == 0


# ---------------------------------------------------------------------------
# Check G: AGENTS.md content guard
# ---------------------------------------------------------------------------

def _write_clean_agents_md(agent_dir: Path):
    agent_dir.mkdir(parents=True)
    (agent_dir / "AGENTS.md").write_text(
        "# CV-Pilot\n\nUse `python cv-pilot-agent/scripts/cli.py --help`.\n",
        encoding="utf-8",
    )


class TestCheckAgentsContent:
    def test_pass_when_no_fences_and_only_help_flag(self, tmp_path):
        _write_clean_agents_md(tmp_path / "cv-pilot-agent")
        result = ppc.check_agents_content(tmp_path)
        assert result.status == "PASS"
        assert result.name == "Check G: AGENTS.md content guard"
        assert "no code fences, no CLI flags other than --help" in result.details[0]

    def test_fail_on_fenced_code_block(self, tmp_path):
        agent = tmp_path / "cv-pilot-agent"
        agent.mkdir()
        (agent / "AGENTS.md").write_text(
            "```\npython cli.py upload.jpg --help\n```\n",
            encoding="utf-8",
        )
        result = ppc.check_agents_content(tmp_path)
        assert result.status == "FAIL"
        detail = result.details[0]
        assert "AGENTS.md:1:" in detail
        assert "--help" in detail

    def test_fail_on_cli_flag_other_than_help(self, tmp_path):
        agent = tmp_path / "cv-pilot-agent"
        agent.mkdir()
        (agent / "AGENTS.md").write_text(
            "upload.py --limit 5 per run.\n",
            encoding="utf-8",
        )
        result = ppc.check_agents_content(tmp_path)
        assert result.status == "FAIL"
        detail = result.details[0]
        assert "AGENTS.md:1:" in detail
        assert "--limit" in detail

    def test_help_flag_alone_does_not_fail(self, tmp_path):
        agent = tmp_path / "cv-pilot-agent"
        agent.mkdir()
        (agent / "AGENTS.md").write_text(
            "Run with --help for details, then --help again.\n",
            encoding="utf-8",
        )
        result = ppc.check_agents_content(tmp_path)
        assert result.status == "PASS"

    def test_fail_when_agents_md_missing(self, tmp_path):
        result = ppc.check_agents_content(tmp_path)
        assert result.status == "FAIL"
        detail = result.details[0]
        assert "AGENTS.md not found at cv-pilot-agent/AGENTS.md" in detail

    def test_does_not_scan_flags_inside_fence(self, tmp_path):
        # Rule 1 already fails the fence; the inside must not be scanned.
        agent = tmp_path / "cv-pilot-agent"
        agent.mkdir()
        (agent / "AGENTS.md").write_text(
            "text line\n```\n--limit --flag --x\n```\n",
            encoding="utf-8",
        )
        result = ppc.check_agents_content(tmp_path)
        assert result.status == "FAIL"
        assert len(result.details) == 1  # only the fence
        assert "--limit" not in result.details[0]

    def test_main_wiring_includes_check_g(self, mini_repo, monkeypatch):
        calls = []
        for fn_name in [
            "check_broken_references",
            "check_bidirectional_skills",
            "check_flujo_coverage",
            "check_pyright",
            "check_issue_references",
            "check_skill_token_budget",
            "check_agents_content",
        ]:
            def _recorder(repo_root, _calls=calls, _name=fn_name):
                _calls.append(_name)
                return ppc.CheckResult(name=_name, status="PASS")
            monkeypatch.setattr(ppc, fn_name, _recorder)
        assert ppc.main(["--repo-root", str(mini_repo), "--quiet"]) == 0
        assert "check_agents_content" in calls
        assert calls[-1] == "check_agents_content"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

class TestMain:
    def test_main_exit_zero_on_valid_repo(self, mini_repo):
        assert ppc.main(["--repo-root", str(mini_repo), "--quiet"]) == 0

    def test_main_exit_one_on_broken_ref(self, mini_repo):
        (mini_repo / "cv-pilot-agent" / "rules" / "persona.md").write_text(
            "Broken skills/nope.md\n", encoding="utf-8"
        )
        assert ppc.main(["--repo-root", str(mini_repo), "--quiet"]) == 1

    def test_main_quiet_suppresses_pass_output(self, mini_repo, capsys):
        ppc.main(["--repo-root", str(mini_repo), "--quiet"])
        captured = capsys.readouterr()
        assert "[PASS]" not in captured.out
