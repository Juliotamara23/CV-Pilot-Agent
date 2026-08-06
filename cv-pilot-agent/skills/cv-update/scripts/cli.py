"""Deterministic CV update CLI for CV-Pilot.

Two-step workflow — the agent bridges extract and apply with its LLM:

    # Step 1: extract text + VSI + prompt
    cv-update extract cv.pdf

    # Step 2: agent sends prompt to its LLM, saves response as fields.json
    cv-update apply fields.json --data-dir data/

Each update is a FULL snapshot — old fields are NEVER preserved.
This ensures ATS fidelity: a real ATS only knows the CV you submit.

NEVER touches ``correos.md`` or ``preferencias.json``.

Reuses:
- ``_lib/pdf_parser.py`` for PDF text extraction.
- ``_lib/llm_extract.py`` for prompt building and response parsing.
- ``_onboarding_internal/parser.py`` for field parsing (regex/heuristics).
- ``_cv_update_internal/reconstructor.py`` for perfil.json generation.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

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
from _lib.llm_extract import (  # noqa: E402
    build_extraction_prompt,
    parse_llm_fields,
    CANONICAL_FIELDS,
)
from _lib.vsi import validate_cv  # noqa: E402
from _cv_update_internal.reconstructor import reconstruct_profile  # noqa: E402

# Canonical rejection message from rules/integridad.md:32.
VSI_REJECTION_MESSAGE = (
    "Este documento no es un perfil profesional válido. Comparte un CV real."
)

app = typer.Typer(
    name="cv-update",
    help="CV-Pilot CV update CLI: extract fields from PDF, apply extracted fields to perfil.json.",
    add_completion=False,
    no_args_is_help=True,
)


def _emit(result: dict) -> None:
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@app.command()
def extract(
    pdf_path: Path = typer.Argument(..., help="Path to the CV PDF."),
) -> None:
    """Extract text, validate VSI, and build the LLM extraction prompt.

    Outputs JSON with:
    - ok: true/false
    - text: raw extracted text (if ok)
    - vsi: VSI validation result (if ok)
    - prompt: LLM extraction prompt for the agent (if ok)

    The agent sends this prompt to its LLM, then passes the response
    to the ``apply`` command.
    """
    # Step 1: Extract text from PDF
    extracted = extract_pdf(str(pdf_path))
    if not extracted.get("ok"):
        _emit({"ok": False, "step": "extract", "error": extracted.get("error", "")})
        raise typer.Exit(code=1)

    text = extracted.get("text", "")

    # Step 2: VSI — Validate Semantic Identity
    vsi_result = validate_cv(text)
    if not vsi_result["is_valid"]:
        _emit({
            "ok": False,
            "step": "vsi",
            "error": "VSI_REJECTED",
            "razon_rechazo": vsi_result["razon_rechazo"],
            "mensaje": VSI_REJECTION_MESSAGE,
            "secciones_detectadas": vsi_result["secciones_detectadas"],
            "confianza": vsi_result["confianza"],
        })
        raise typer.Exit(code=1)

    # Step 3: Build extraction prompt for the agent's LLM
    prompt = build_extraction_prompt(text)

    _emit({
        "ok": True,
        "step": "extract",
        "text": text,
        "links": extracted.get("links", []),
        "vsi": {
            "secciones_detectadas": vsi_result["secciones_detectadas"],
            "confianza": vsi_result["confianza"],
        },
        "prompt": prompt,
        "canonical_fields": CANONICAL_FIELDS,
        "source_pdf": str(pdf_path),
    })


@app.command()
def apply(
    fields_file: Path = typer.Argument(..., help="Path to JSON file with LLM-extracted fields."),
    data_dir: Path = typer.Option(
        Path("data"), "--data-dir", help="Directory containing perfil.json (default: data/)."
    ),
    source_pdf: str = typer.Option(
        "", "--source-pdf", help="Original PDF path for the 'fuente' field in perfil.json. Also persists the PDF to data_dir/cv.pdf."
    ),
) -> None:
    """Apply LLM-extracted fields to reconstruct perfil.json.

    Reads a JSON file containing either:
    - Raw LLM response (will be parsed via parse_llm_fields)
    - Already-parsed canonical fields dict

    Reconstructs perfil.json from scratch and writes it.
    NEVER touches correos.md or preferencias.json.
    """
    perfil_path = data_dir / "perfil.json"

    # Step 1: Read and parse fields
    try:
        raw = fields_file.read_text(encoding="utf-8")
    except OSError as exc:
        _emit({"ok": False, "step": "read", "error": str(exc)})
        raise typer.Exit(code=1)

    # Try parsing as raw LLM response first, then as plain fields dict
    try:
        new_fields = parse_llm_fields(raw)
    except ValueError:
        try:
            fields_data = json.loads(raw)
            if isinstance(fields_data, dict):
                new_fields = fields_data
            else:
                _emit({"ok": False, "step": "parse", "error": "Fields file must be a JSON object"})
                raise typer.Exit(code=1)
        except json.JSONDecodeError as exc:
            _emit({"ok": False, "step": "parse", "error": f"Invalid JSON: {exc}"})
            raise typer.Exit(code=1)

    source = source_pdf or new_fields.get("fuente", str(fields_file))

    # Persist the real CV PDF to data_dir/cv.pdf and record cv_path
    if source_pdf and Path(source_pdf).exists():
        data_dir.mkdir(parents=True, exist_ok=True)
        cv_dest = data_dir / "cv.pdf"
        shutil.copy2(source_pdf, cv_dest)
        # Store cv_path relative to the agent root when possible so consumers
        # resolve it consistently regardless of the --data-dir value.
        try:
            new_fields["cv_path"] = str(
                cv_dest.resolve().relative_to(_AGENT_ROOT.resolve())
            )
        except ValueError:
            new_fields["cv_path"] = str(cv_dest)

    # Step 2: Reconstruct perfil.json from scratch
    result = reconstruct_profile(new_fields, source_pdf=source)

    # Step 3: Write new perfil.json
    data_dir.mkdir(parents=True, exist_ok=True)
    perfil_path.write_text(
        json.dumps(result["perfil_content"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Step 4: Post-update validation — verify written content matches
    written = json.loads(perfil_path.read_text(encoding="utf-8"))
    if written != result["perfil_content"]:
        import logging
        logging.warning(
            "cv-update: contenido escrito difiere del generado. "
            "Posible race condition o encoding issue."
        )

    # Step 5: Report
    report = {
        "ok": True,
        "step": "apply",
        "perfil_path": str(perfil_path),
        "campos_extraidos": result["campos_extraidos"],
        "campos_no_encontrados": result["campos_no_encontrados"],
        "fuente": result["fuente"],
        "timestamp": result["timestamp"],
    }

    if result["campos_no_encontrados"]:
        report["aviso_usuario"] = (
            "Algunos campos no se pudieron extraer. "
            "Revise el JSON y complete manualmente."
        )

    _emit(report)


if __name__ == "__main__":
    app()
