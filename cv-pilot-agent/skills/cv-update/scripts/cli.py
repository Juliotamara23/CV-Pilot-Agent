"""Deterministic CV update CLI for CV-Pilot.

Updates ``data/perfil.md`` from a new CV PDF WITHOUT re-running onboarding.
Preserves custom fields (e.g. ``pdf_soporte: true``) and NEVER touches
``correos.md`` or ``preferencias.md``.

Reuses:
- ``_lib/pdf_parser.py`` for PDF text extraction.
- ``_onboarding_internal/parser.py`` for field parsing (regex/heuristics).

Invoked by the orchestrator via the venv Python::

    .venv/Scripts/python.exe skills/cv-update/scripts/cli.py update <pdf_path>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

# Force UTF-8 on std streams so unicode never depends on host codepage.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

# Make ``cv-pilot-agent/`` and this script's directory importable.
_AGENT_ROOT = Path(__file__).resolve().parents[3]
_SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS_DIR))
sys.path.insert(0, str(_AGENT_ROOT))
sys.path.insert(0, str(_AGENT_ROOT / "_lib"))

import typer  # noqa: E402
from _lib.pdf_parser import extract as extract_pdf  # noqa: E402

# Import parser from onboarding (shared dependency, not duplicated).
# NOTE: add AFTER _SCRIPTS_DIR so our own _cv_update_internal is found first.
_ONBOARDING_SCRIPTS = _AGENT_ROOT / "skills" / "onboarding" / "scripts"
if str(_ONBOARDING_SCRIPTS) not in sys.path:
    sys.path.append(str(_ONBOARDING_SCRIPTS))

from _onboarding_internal.parser import parse_text  # noqa: E402
from _cv_update_internal.merger import merge_profile  # noqa: E402

app = typer.Typer(
    name="cv-update",
    help="CV-Pilot CV update CLI: update perfil.md from a new PDF.",
    add_completion=False,
    no_args_is_help=True,
)


def _emit(result: dict) -> None:
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@app.command()
def update(
    pdf_path: Path = typer.Argument(..., help="Path to the new CV PDF."),
    data_dir: Path = typer.Option(
        Path("data"), "--data-dir", help="Directory containing perfil.md (default: data/)."
    ),
) -> None:
    """Update perfil.md from a new CV PDF.

    Extracts text/links from the PDF, parses CV fields, and merges them
    into the existing perfil.md. Custom fields are preserved. NEVER touches
    correos.md or preferencias.md.
    """
    perfil_path = data_dir / "perfil.md"

    # Step 1: Extract from PDF
    extracted = extract_pdf(str(pdf_path))
    if not extracted.get("ok"):
        _emit({"ok": False, "step": "extract", "error": extracted.get("error", "")})
        raise typer.Exit(code=1)

    # Step 2: Parse CV fields
    parsed = parse_text(extracted.get("text", ""), extracted.get("links", []))
    new_fields = parsed["fields"]

    # Step 3: Load existing perfil.md (if exists)
    old_content = ""
    if perfil_path.is_file():
        old_content = perfil_path.read_text(encoding="utf-8")

    # Step 4: Merge
    result = merge_profile(old_content, new_fields)

    # Step 5: Write updated perfil.md
    data_dir.mkdir(parents=True, exist_ok=True)
    perfil_path.write_text(result["content"], encoding="utf-8")

    # Step 6: Report
    _emit({
        "ok": True,
        "perfil_path": str(perfil_path),
        "fields_updated": result["fields_updated"],
        "fields_preserved": result["fields_preserved"],
        "fields_added": result["fields_added"],
    })


if __name__ == "__main__":
    app()
