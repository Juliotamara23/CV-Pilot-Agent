"""Deterministic onboarding CLI for CV-Pilot.

Replaces the conversational ``skills/onboarding/SKILL.md`` flow with a Typer
CLI that extracts CV data from a PDF or text, parses fields via regex, and
generates ``data/perfil.md``, ``data/correos.md``, ``data/preferencias.md``
from the templates in ``skills/onboarding/templates/``.

Invoked by the orchestrator (AGENTS.md step 1) via the venv Python::

    .venv/Scripts/python.exe skills/onboarding/scripts/cli.py <command>

Subcommands: ``extract``, ``parse``, ``generate``, ``full``.
All commands emit JSON to stdout and exit 0 on ``ok: true``, 1 otherwise
(matches ``scripts/pdf_parser.py`` contract).
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

# Make ``cv-pilot-agent/`` importable so ``from pdf_parser import extract``
# works regardless of CWD when the script is run by path or as a module.
_AGENT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_AGENT_ROOT))
sys.path.insert(0, str(_AGENT_ROOT / "_lib"))

import typer  # noqa: E402
from pdf_parser import extract as extract_pdf  # noqa: E402

from _onboarding_internal.extractor import read_text  # noqa: E402
from _onboarding_internal.parser import REQUIRED, parse_text  # noqa: E402
from _onboarding_internal.renderer import email_block, render_template  # noqa: E402
from _onboarding_internal.generator import generate_files  # noqa: E402
from vsi import validate_cv  # noqa: E402

# Canonical rejection message from rules/integridad.md:32.
VSI_REJECTION_MESSAGE = (
    "Este documento no es un perfil profesional válido. Comparte un CV real."
)

app = typer.Typer(
    name="onboard",
    help="CV-Pilot onboarding CLI: extract, parse, generate, full.",
    add_completion=False,
    no_args_is_help=True,
)


def _emit(result: dict) -> None:
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
@app.command()
def extract(pdf_path: Path = typer.Argument(..., help="Path to the PDF file.")) -> None:
    """Extract text and links from a PDF (wraps ``pdf_parser.extract``)."""
    result = extract_pdf(str(pdf_path))
    _emit(result)
    if not result.get("ok"):
        raise typer.Exit(code=1)


@app.command()
def parse(
    source: Path = typer.Argument(..., help="Text file, PDF, or '-' for stdin."),
    links: list[str] = typer.Option(
        [], "--links", help="Extra link to merge (repeatable)."
    ),
) -> None:
    """Parse CV text (or PDF) into structured fields via regex."""
    try:
        text, found_links = read_text(source, links)
    except (RuntimeError, FileNotFoundError) as exc:
        _emit({"fields": {}, "missing": list(REQUIRED), "ok": False, "error": str(exc)})
        raise typer.Exit(code=1)
    parsed = parse_text(text, found_links)
    _emit({"ok": True, **parsed})
    if parsed["missing"]:
        raise typer.Exit(code=1)


@app.command()
def generate(
    fields_file: Path = typer.Option(..., "--fields-file", help="JSON file with parsed fields + extras."),
    out_dir: Path = typer.Option(Path("data"), "--out-dir", help="Output directory (default: data/)."),
    no_backup: bool = typer.Option(False, "--no-backup", help="Skip .bak creation."),
) -> None:
    """Render perfil.md, correos.md, preferencias.md from a fields JSON file."""
    try:
        fields = json.loads(fields_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _emit({"ok": False, "error": f"Cannot read fields file: {exc}"})
        raise typer.Exit(code=1)
    outputs = generate_files(fields, out_dir, no_backup)
    _emit({"ok": True, **outputs})


@app.command()
def full(
    pdf_path: Path = typer.Argument(..., help="Path to the CV PDF."),
    fields_file: Optional[Path] = typer.Option(
        None, "--fields-file", help="JSON file with extras (preferences, email examples)."
    ),
    out_dir: Path = typer.Option(Path("data"), "--out-dir", help="Output directory (default: data/)."),
    no_backup: bool = typer.Option(False, "--no-backup", help="Skip .bak creation."),
) -> None:
    """Extract -> parse -> generate in one shot."""
    extracted = extract_pdf(str(pdf_path))
    if not extracted.get("ok"):
        _emit({"ok": False, "step": "extract", "error": extracted.get("error", "")})
        raise typer.Exit(code=1)

    # VSI — Validate Semantic Identity (integridad.md:26-35)
    vsi_result = validate_cv(extracted.get("text", ""))
    if not vsi_result["is_valid"]:
        _emit({
            "ok": False,
            "step": "vsi",
            "error": "VSI_REJECTED",
            "razon_rechazo": vsi_result["razon_rechazo"],
            "mensaje": VSI_REJECTION_MESSAGE,
        })
        raise typer.Exit(code=1)

    parsed = parse_text(extracted.get("text", ""), extracted.get("links", []))
    fields = dict(parsed["fields"])
    if fields_file and fields_file.is_file():
        try:
            extras = json.loads(fields_file.read_text(encoding="utf-8"))
            fields.update(extras)
        except (OSError, json.JSONDecodeError) as exc:
            _emit({"ok": False, "step": "generate", "error": f"Cannot read fields file: {exc}"})
            raise typer.Exit(code=1)
    outputs = generate_files(fields, out_dir, no_backup)
    _emit({
        "ok": True,
        "step": "full",
        "extract": {"ok": True, "links": extracted.get("links", [])},
        "vsi": {
            "secciones_detectadas": vsi_result["secciones_detectadas"],
            "confianza": vsi_result["confianza"],
        },
        "parse": {"fields": parsed["fields"], "missing": parsed["missing"]},
        "generate": outputs,
    })


if __name__ == "__main__":
    app()
