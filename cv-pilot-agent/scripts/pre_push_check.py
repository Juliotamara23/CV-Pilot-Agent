"""Pre-push check for CV-Pilot Agent.

Validates three categories of breakage that have shipped in past releases:

  Check A: Broken path references in orchestrator markdown files.
  Check B: Bidirectional registration between AGENTS.md and skills/.
  Check C: Flujo coverage of the skills that AGENTS.md declares.

Exit codes:
  0  all checks passed (or only WARN-level issues)
  1  at least one FAIL (push should be blocked)

Usage:
  python cv-pilot-agent/scripts/pre_push_check.py [--repo-root <path>]

Designed to be invoked by .git/hooks/pre-push. Stdlib only.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    """Outcome of a single check."""

    name: str
    status: str  # "PASS", "FAIL", or "WARN"
    details: list[str] = field(default_factory=list)

    def passed(self) -> bool:
        return self.status != "FAIL"


# ---------------------------------------------------------------------------
# Repository discovery
# ---------------------------------------------------------------------------

def find_repo_root(start: Path) -> Path:
    """Walk up until we find a directory containing a .git folder."""
    cur = start.resolve()
    for candidate in [cur, *cur.parents]:
        if (candidate / ".git").exists():
            return candidate
    raise RuntimeError(
        f"Could not locate repo root (no .git found) starting from {start}"
    )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

SKIP_DIRS = {
    ".venv",
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
}

URL_PATTERN = re.compile(r"https?://", re.IGNORECASE)
# Markdown code fences: ``` ... ``` (greedy across lines via DOTALL).
FENCE_PATTERN = re.compile(r"```.*?```", re.DOTALL)
# Inline code spans: `path/like/this`. We strip them so we don't false-positive
# on paths that exist only as illustrative text (e.g. "data/.old-file.md is
# removed in this version"). Single backticks only — no double.
INLINE_CODE_PATTERN = re.compile(r"`[^`\n]+`")
# A path-shaped token inside a markdown file. Conservative on purpose:
# requires either a leading "./", "skills/", "rules/", "data/", "_lib/",
# "scripts/", "docs/" or a "file.ext" with at least one slash.
PATH_TOKEN_PATTERN = re.compile(
    r"(?:"
    r"\./[\w./-]+\.\w+"
    r"|skills/[\w./-]+"
    r"|rules/[\w./-]+"
    r"|data/[\w./-]+"
    r"|_lib/[\w./-]+"
    r"|scripts/[\w./-]+"
    r"|docs/[\w./-]+"
    r"|test/[\w./-]+"
    r"|cv-pilot-agent/[\w./-]+"
    r")"
)
# A <placeholder> token in a template path like `skills/<skill>/scripts/cli.py`.
TEMPLATE_PLACEHOLDER = re.compile(r"<[^<>\s]+>")
# Words that signal "this file is intentionally not present" (deprecation,
# removal, historical context). When a broken ref is in a line with one of
# these, we WARN instead of FAIL.
DEPRECATION_HINT = re.compile(
    r"\b(se\s+elimina|se\s+remueve|removed|removido|deprecated|deprecated|hist[oó]rico|legacy|ya\s+no\s+existe|does\s+not\s+exist|no\s+longer\s+exists)\b",
    re.IGNORECASE,
)


def strip_code_blocks(markdown_text: str) -> str:
    """Remove fenced code blocks and inline code spans before path extraction.

    Both can contain paths that are illustrative rather than real references
    (e.g. "this file is removed in this version").
    """
    text = FENCE_PATTERN.sub("", markdown_text)
    text = INLINE_CODE_PATTERN.sub("", text)
    return text


def _is_template_fragment(source_text: str, span: tuple[int, int]) -> bool:
    """Return True if the match at `span` is part of a `<placeholder>` template.

    Walks back to the start of the current whitespace-free run and forward to
    its end, then checks whether the run contains a `<...>` placeholder. This
    catches `scripts/cli.py` extracted from `skills/<skill>/scripts/cli.py`.
    """
    start, end = span
    # Find the start of the contiguous non-space character run.
    run_start = start
    while run_start > 0 and not source_text[run_start - 1].isspace():
        run_start -= 1
    run_end = end
    while run_end < len(source_text) and not source_text[run_end].isspace():
        run_end += 1
    run = source_text[run_start:run_end]
    return bool(TEMPLATE_PLACEHOLDER.search(run))


def looks_like_url(token: str) -> bool:
    return bool(URL_PATTERN.search(token))


def is_bak(token: str) -> bool:
    return token.endswith(".bak")


# ---------------------------------------------------------------------------
# Check A: broken references
# ---------------------------------------------------------------------------

def _candidate_resolves(repo_root: Path, source_file: Path, token: str) -> bool:
    """Return True if `token` (a path-shaped string) resolves on disk.

    Resolution order:
      1. Absolute paths -> resolve from repo_root.
      2. Relative paths -> try the markdown file's directory first.
      3. Then try the repo root.
      4. Then try cv-pilot-agent/ (this project's convention: markdown
         inside cv-pilot-agent/ uses paths relative to that directory).

    `source_file` is the markdown file we extracted the token from.
    """
    clean = token.rstrip(".,;:)\"'>")
    # Strip leading "./" so pathlib treats it as a regular relative path.
    if clean.startswith("./"):
        clean = clean[2:]
    # Already absolute paths (rare in our docs) — resolve from repo_root.
    if clean.startswith("/") or re.match(r"^[a-zA-Z]:[\\/]", clean):
        return (repo_root / clean.lstrip("/\\")).exists()
    # Default: resolve relative to the markdown file's directory.
    base = source_file.parent
    if (base / clean).exists():
        return True
    if (repo_root / clean).exists():
        return True
    agent_root = repo_root / "cv-pilot-agent"
    if agent_root.is_dir() and (agent_root / clean).exists():
        return True
    return False


def _is_interesting_token(token: str) -> bool:
    """Filter out tokens we don't want to treat as filesystem references."""
    if looks_like_url(token):
        return False
    if is_bak(token):
        return False
    # Pure placeholders or partial fragments.
    if token.endswith("/") or token.startswith("<") or token.startswith("["):
        return False
    return True


def check_broken_references(repo_root: Path) -> CheckResult:
    result = CheckResult(name="Check A: broken references", status="PASS")
    target_paths = [
        repo_root / "cv-pilot-agent" / "AGENTS.md",
    ]
    rules_dir = repo_root / "cv-pilot-agent" / "rules"
    if rules_dir.is_dir():
        target_paths.extend(sorted(rules_dir.glob("*.md")))
    skills_dir = repo_root / "cv-pilot-agent" / "skills"
    if skills_dir.is_dir():
        for skill_dir in sorted(skills_dir.iterdir()):
            if skill_dir.is_dir():
                skill_md = skill_dir / "SKILL.md"
                if skill_md.exists():
                    target_paths.append(skill_md)

    for md_file in target_paths:
        original_text = md_file.read_text(encoding="utf-8", errors="replace")
        searchable_text = strip_code_blocks(original_text)
        for match in PATH_TOKEN_PATTERN.finditer(searchable_text):
            token = match.group(0).strip()
            if not _is_interesting_token(token):
                continue
            if _candidate_resolves(repo_root, md_file, token):
                continue
            # Skip template fragments like `scripts/cli.py` from
            # `skills/<skill>/scripts/cli.py`. The `<placeholder>` makes the
            # path a template, not a real reference.
            if _is_template_fragment(searchable_text, match.span()):
                continue
            # Downgrade to WARN when the surrounding line says the file was
            # removed / deprecated. We look at the line in the ORIGINAL text
            # (before stripping code spans) so the disambiguating word is
            # visible.
            line_start = original_text.rfind("\n", 0, match.start()) + 1
            line_end = original_text.find("\n", match.end())
            if line_end == -1:
                line_end = len(original_text)
            line_text = original_text[line_start:line_end]
            if DEPRECATION_HINT.search(line_text):
                result.details.append(
                    f"  WARN: {md_file.relative_to(repo_root)}: ref {token!r}"
                    f" does not resolve (line documents removal/deprecation)"
                )
                continue
            result.status = "FAIL"
            result.details.append(
                f"  {md_file.relative_to(repo_root)}: unresolvable ref {token!r}"
            )

    if result.status == "PASS" and not result.details:
        result.details.append(
            f"  scanned {len(target_paths)} markdown files, no broken refs"
        )
    return result


# ---------------------------------------------------------------------------
# Check B: bidirectional skill registration
# ---------------------------------------------------------------------------

# Match a markdown table row whose first cell mentions "Skills" (case
# insensitive) and grab everything in the second cell. Example target:
# | Skills | ./skills/{onboarding,cv-update,database,mimetismo,apify,formatos}/SKILL.md | ...
SKILLS_ROW_PATTERN = re.compile(
    r"^\|\s*Skills\s*\|\s*([^|]+?)\s*\|",
    re.IGNORECASE | re.MULTILINE,
)


def _extract_skill_names_from_skills_row(agents_md: Path) -> list[str]:
    """Parse the Skills cell of the AGENTS.md Dependencias table."""
    text = agents_md.read_text(encoding="utf-8", errors="replace")
    match = SKILLS_ROW_PATTERN.search(text)
    if not match:
        return []
    cell = match.group(1)
    # Strip shell brace expansion like "{onboarding,cv-update,database}".
    if "{" in cell and "}" in cell:
        inner = cell[cell.index("{") + 1 : cell.rindex("}")]
        names = [n.strip() for n in inner.split(",") if n.strip()]
    else:
        # Fall back to "skills/<name>/SKILL.md" tokens.
        names = re.findall(r"skills/([\w-]+)/SKILL\.md", cell)
    return [n for n in names if n]


def check_bidirectional_skills(repo_root: Path) -> CheckResult:
    result = CheckResult(name="Check B: bidirectional skill registration", status="PASS")
    agents_md = repo_root / "cv-pilot-agent" / "AGENTS.md"
    declared = set(_extract_skill_names_from_skills_row(agents_md))

    skills_dir = repo_root / "cv-pilot-agent" / "skills"
    on_disk: set[str] = set()
    if skills_dir.is_dir():
        for child in skills_dir.iterdir():
            if child.is_dir() and (child / "SKILL.md").exists():
                on_disk.add(child.name)

    # Forward: declared -> on disk
    for name in sorted(declared - on_disk):
        result.status = "FAIL"
        result.details.append(
            f"  AGENTS.md declares {name!r} but cv-pilot-agent/skills/{name}/SKILL.md is missing"
        )
    # Reverse: on disk -> declared
    for name in sorted(on_disk - declared):
        result.status = "FAIL"
        result.details.append(
            f"  cv-pilot-agent/skills/{name}/SKILL.md exists but AGENTS.md does not register it"
        )

    if not result.details:
        result.details.append(
            f"  {len(declared & on_disk)} skills registered bidirectionally"
        )
    return result


# ---------------------------------------------------------------------------
# Check C: Flujo coverage
# ---------------------------------------------------------------------------

# Skills that MUST be referenced in ## Flujo. The two main entry points.
REQUIRED_FLUJO_SKILLS = {"onboarding", "cv-update"}

FLUJO_SECTION_PATTERN = re.compile(
    r"^##\s*Flujo\s*$(.*?)(?=^##\s|\Z)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)


def check_flujo_coverage(repo_root: Path) -> CheckResult:
    """WARN if a declared skill is missing from ## Flujo, FAIL for required ones."""
    result = CheckResult(name="Check C: Flujo coverage", status="PASS")
    agents_md = repo_root / "cv-pilot-agent" / "AGENTS.md"
    text = agents_md.read_text(encoding="utf-8", errors="replace")
    declared = set(_extract_skill_names_from_skills_row(agents_md))
    if not declared:
        result.status = "FAIL"
        result.details.append("  could not parse the Skills row in AGENTS.md")
        return result

    flujo_match = FLUJO_SECTION_PATTERN.search(text)
    if not flujo_match:
        result.status = "FAIL"
        result.details.append("  could not find a '## Flujo' section in AGENTS.md")
        return result
    flujo_body = flujo_match.group(1).lower()

    for name in sorted(declared):
        present = name.lower() in flujo_body
        if name in REQUIRED_FLUJO_SKILLS and not present:
            result.status = "FAIL"
            result.details.append(
                f"  {name!r} is a required entry point but is not mentioned in ## Flujo"
            )
        elif not present:
            result.details.append(
                f"  WARN: {name!r} is declared but not mentioned in ## Flujo"
            )

    if not result.details:
        result.details.append(
            f"  all {len(declared)} declared skills are referenced in ## Flujo"
        )
    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root (defaults to autodetected from script location).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress the success summary and per-check PASS lines.",
    )
    args = parser.parse_args(argv)

    if args.repo_root is not None:
        repo_root = args.repo_root.resolve()
    else:
        repo_root = find_repo_root(Path(__file__).parent)

    if not args.quiet:
        print(f"[pre-push] repo root: {repo_root}")
    results = [
        check_broken_references(repo_root),
        check_bidirectional_skills(repo_root),
        check_flujo_coverage(repo_root),
    ]
    for r in results:
        # In quiet mode, only print failure details. PASS lines are silent.
        if args.quiet and r.passed():
            continue
        print(f"[{r.status}] {r.name}")
        for line in r.details:
            print(line)

    failed = [r for r in results if not r.passed()]
    if failed:
        print(f"\n[pre-push] {len(failed)} check(s) failed. Push blocked.")
        return 1
    if not args.quiet:
        print("\n[pre-push] all checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
