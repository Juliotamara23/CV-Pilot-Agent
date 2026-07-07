"""End-to-end demo: load real Apify actor output from fixtures and process
it through our platform adapters (the same code that the apify CLI
calls). Prints a summary of the resulting JobInsert rows so a human
can verify the adapters read the dataset correctly.

This is a permanent utility, kept in ``scripts/`` (NOT ``temp/``) because
``scripts/cleanup.py`` deletes everything in ``temp/`` on every run.

For automated regression checks against the same fixtures, see
``test/scenarios/agent-mode/test_apify_fixtures.py``.

Usage:
    python scripts/demo_apify_adapters.py
"""
import json
import sys
from pathlib import Path

# Resolve the project root from this script's location.
#   scripts/demo_apify_adapters.py -> scripts/ -> cv-pilot-agent/ -> repo root
_THIS = Path(__file__).resolve()
_CV_PILOT_ROOT = _THIS.parent.parent
_REPO_ROOT = _CV_PILOT_ROOT.parent

# Make _lib and platforms importable.
_SCRIPTS_DIR = _CV_PILOT_ROOT / "skills" / "apify" / "scripts"
for _p in (_CV_PILOT_ROOT, _SCRIPTS_DIR):
    sys.path.insert(0, str(_p))

from platforms.computrabajo import ComputrabajoAdapter  # noqa: E402
from platforms.indeed import IndeedAdapter  # noqa: E402
from platforms.linkedin import LinkedinAdapter  # noqa: E402

FIXTURES = _REPO_ROOT / "test" / "fixtures" / "apify"

ADAPTERS = {
    "computrabajo.json": (ComputrabajoAdapter(), "apify-computrabajo"),
    "linkedin.json":     (LinkedinAdapter(),     "apify-linkedin"),
    "indeed.json":       (IndeedAdapter(),       "apify-indeed"),
}


def _safe(s: str, width: int) -> str:
    """Truncate to *width* and strip non-ASCII for Windows-cp1252 consoles."""
    if s is None:
        return "?"[:width]
    s = s.encode("ascii", "replace").decode("ascii").replace("?", " ")
    return s[:width]


def main() -> int:
    print("=" * 78)
    print("Adapters reading real Apify actor output (from fixtures)")
    print("=" * 78)
    print()

    for fixture_name, (adapter, source) in ADAPTERS.items():
        path = FIXTURES / fixture_name
        if not path.is_file():
            print(f"MISSING: {path}")
            return 1
        raw = json.loads(path.read_text(encoding="utf-8"))
        print(f"--- {fixture_name} ({len(raw)} items) ---")
        jobs = adapter.normalize_output(raw)
        for i, (r, j) in enumerate(zip(raw, jobs)):
            short_id = _safe(j.external_id or "?", 16)
            desc_len = len(j.description or "")
            salary = j.salary or "-"
            print(
                f"  [{i:>2}] id={short_id:<16} "
                f"pos='{_safe(j.position or '?', 40):<40}' "
                f"co='{_safe(j.company or '?', 20):<20}' "
                f"date={_safe(j.public_date or '-', 25):<25} "
                f"desc={desc_len:>5}ch"
            )
        # Source from JobInsert should be the adapter's platform name.
        assert all(j.source == source for j in jobs), \
            f"Some jobs have wrong source (expected {source!r})"
        print(f"  OK: all {len(jobs)} jobs have source={source!r}")
        print()

    print("=" * 78)
    print("All 3 adapters successfully read their respective real datasets.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
