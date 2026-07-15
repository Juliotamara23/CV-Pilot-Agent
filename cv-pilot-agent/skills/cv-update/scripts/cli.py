"""Deterministic CV update CLI for CV-Pilot.

Rewrites ``data/perfil.json`` from scratch using ONLY the new CV PDF.
Each update is a full snapshot — old fields are NEVER preserved.
This ensures ATS fidelity: a real ATS only knows the CV you submit.

NEVER touches ``correos.md`` or ``preferencias.json``.

Reuses:
- ``_lib/pdf_parser.py`` for PDF text extraction.
- ``_onboarding_internal/parser.py`` for field parsing (regex/heuristics).

Invoked by the orchestrator via the venv Python::

    .venv/Scripts/python.exe skills/cv-update/scripts/cli.py <pdf_path>
    .venv/Scripts/python.exe skills/cv-update/scripts/cli.py --data-dir <dir> <pdf_path>
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
from _cv_update_internal.reconstructor import reconstruct_profile  # noqa: E402
from vsi import validate_cv  # noqa: E402

# Canonical rejection message from rules/integridad.md:32.
VSI_REJECTION_MESSAGE = (
    "Este documento no es un perfil profesional válido. Comparte un CV real."
)

app = typer.Typer(
    name="cv-update",
    help="CV-Pilot CV update CLI: update perfil.json from a new PDF.",
    add_completion=False,
    no_args_is_help=True,
)


def _emit(result: dict) -> None:
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@app.command()
def update(
    pdf_path: Path = typer.Argument(..., help="Path to the new CV PDF."),
    data_dir: Path = typer.Option(
        Path("data"), "--data-dir", help="Directory containing perfil.json (default: data/)."
    ),
) -> None:
    """Rewrite perfil.json from scratch with data from a new CV PDF.

    Each update is a FULL snapshot — old perfil.json content is discarded.
    NEVER touches correos.md or preferencias.json.
    """
    perfil_path = data_dir / "perfil.json"

    # Step 1: Extract from PDF
    extracted = extract_pdf(str(pdf_path))
    if not extracted.get("ok"):
        _emit({"ok": False, "step": "extract", "error": extracted.get("error", "")})
        raise typer.Exit(code=1)

    # Step 2: VSI — Validate Semantic Identity (integridad.md:26-35)
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

    # Step 3: Parse CV fields
    parsed = parse_text(extracted.get("text", ""), extracted.get("links", []))
    new_fields = parsed["fields"]

    # Step 4: Reconstruct perfil.json from scratch (NO old data consulted)
    result = reconstruct_profile(new_fields, source_pdf=str(pdf_path))

    # Step 5: Write new perfil.json
    data_dir.mkdir(parents=True, exist_ok=True)
    perfil_path.write_text(
        json.dumps(result["perfil_content"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Step 6: Post-update validation — verify written content matches
    written = json.loads(perfil_path.read_text(encoding="utf-8"))
    if written != result["perfil_content"]:
        import logging
        logging.warning(
            "cv-update: contenido escrito difiere del generado. "
            "Posible race condition o encoding issue."
        )

    # Step 7: Report
    _emit({
        "ok": True,
        "perfil_path": str(perfil_path),
        "campos_extraidos": result["campos_extraidos"],
        "campos_no_encontrados": result["campos_no_encontrados"],
        "fuente": result["fuente"],
        "timestamp": result["timestamp"],
        "vsi": {
            "secciones_detectadas": vsi_result["secciones_detectadas"],
            "confianza": vsi_result["confianza"],
        },
    })


if __name__ == "__main__":
    app()
