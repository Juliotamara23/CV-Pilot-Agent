"""Deterministic onboarding CLI for CV-Pilot.

Replaces the conversational ``skills/onboarding/SKILL.md`` flow with a Typer
CLI that extracts CV data from a PDF or text, parses fields via regex, and
generates ``data/perfil.md``, ``data/correos.md``, ``data/preferencias.md``
from the templates in ``skills/onboarding/templates/``.

Invoked by the orchestrator (AGENTS.md step 1) via the venv Python::

    .venv/Scripts/python.exe skills/onboarding/scripts/onboard.py <command>

Subcommands: ``extract``, ``parse``, ``generate``, ``full``.
All commands emit JSON to stdout and exit 0 on ``ok: true``, 1 otherwise
(matches ``scripts/pdf_parser.py`` contract).
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path
from typing import Optional

from _lib.shared.cli_utils import setup_syspath, setup_utf8

# Force UTF-8 on std streams so unicode never depends on host codepage.
setup_utf8()

# Make ``cv-pilot-agent/`` importable so ``from pdf_parser import extract``
# works regardless of CWD when the script is run by path or as a module.
_AGENT_ROOT = setup_syspath(levels_up=3)
sys.path.insert(0, str(_AGENT_ROOT / "scripts"))

import typer  # noqa: E402
from pdf_parser import extract as extract_pdf  # noqa: E402

app = typer.Typer(
    name="onboard",
    help="CV-Pilot onboarding CLI: extract, parse, generate, full.",
    add_completion=False,
    no_args_is_help=True,
)

TEMPLATES_DIR = _AGENT_ROOT / "skills" / "onboarding" / "templates"

REGEX = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    # Phone: require a '+' prefix or a separator (space/paren) so pure dates
    # like "2020-2024" do not match.
    "phone": re.compile(r"\+?\d[\d\s().-]{7,}\d"),
    "linkedin": re.compile(
        r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w-]+/?", re.IGNORECASE
    ),
    "github": re.compile(
        r"(?:https?://)?(?:www\.)?github\.com/[\w-]+/?", re.IGNORECASE
    ),
    "url": re.compile(r"https?://[^\s)\]]+"),
}

# Fields the script treats as essential; absence is reported in ``missing``.
REQUIRED = ("nombre", "linkedin", "github", "telefono", "correo")

# Normalized section header labels (lowercase, no '#'/':'). A line is a header
# when its normalized form equals one of these labels. Exact match avoids the
# substring trap where a body line mentions a section word (e.g. a Resumen line
# containing "experiencia").
_SECTION_HEADERS = {
    "experiencia": ("experiencia", "experience", "experiencia profesional"),
    "educacion": ("educacion", "education", "formacion", "formación academica"),
    "skills": ("skills", "habilidades", "competencias", "tech stack"),
    "resumen": ("resumen", "summary", "perfil profesional", "perfil", "about"),
    "contacto": ("contacto", "contact", "datos de contacto"),
}


def _normalize_header(line: str) -> str:
    return line.strip().lstrip("#").strip().rstrip(":").strip().lower()


def _is_header(line: str, keys: tuple[str, ...]) -> bool:
    return _normalize_header(line) in keys


def _emit(result: dict) -> None:
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


def _is_pdf(path: Path) -> bool:
    return path.suffix.lower() == ".pdf"


def read_text(source: Path, extra_links: list[str]) -> tuple[str, list[str]]:
    """Return (text, links) from a text file, stdin (``-``), or a PDF.

    For PDFs, delegates to ``pdf_parser.extract``. ``extra_links`` are merged
    into the returned link list (deduplicated, order preserved).
    """
    if str(source) == "-":
        text = sys.stdin.read()
        links: list[str] = []
    elif _is_pdf(source):
        result = extract_pdf(str(source))
        if not result.get("ok"):
            raise RuntimeError(result.get("error", "PDF extraction failed"))
        text = result.get("text", "")
        links = list(result.get("links", []))
    else:
        text = source.read_text(encoding="utf-8")
        links = []

    merged: list[str] = []
    seen: set[str] = set()
    for link in list(links) + list(extra_links):
        if link and link not in seen:
            seen.add(link)
            merged.append(link)
    return text, merged


def _find_first(text: str, pattern: re.Pattern) -> str:
    match = pattern.search(text)
    return match.group(0).strip() if match else ""


def _find_phone(text: str) -> str:
    """Pick the best phone match: prefer those with a '+' prefix, then any.

    Pure 4+4 dates like '2020-2024' can still match the loose phone regex, so
    we rank matches by whether they start with '+' and return the best one.
    """
    matches = REGEX["phone"].findall(text)
    if not matches:
        return ""
    with_plus = [m for m in matches if m.strip().startswith("+")]
    return (with_plus or matches)[0].strip()


def _extract_nombre(text: str) -> str:
    # Prefer an explicit "Nombre:" label; fall back to the first non-empty line
    # that does not look like contact info or a section header.
    label = re.search(r"(?:^|\n)\s*Nombre(?:\s+completo)?\s*:\s*(.+)", text, re.IGNORECASE)
    if label:
        return label.group(1).strip()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if REGEX["email"].search(stripped) or stripped.startswith(("#", "##")):
            continue
        if any(_is_header(stripped, keys) for keys in _SECTION_HEADERS.values()):
            continue
        return stripped
    return ""


def _extract_section(text: str, keys: tuple[str, ...]) -> str:
    """Return the body of a section identified by an exact header-line match.

    The body spans from the header line to the next recognized header line or
    end of text. Lines are returned verbatim (non-empty, joined with newlines).
    """
    all_headers = [keys_set for keys_set in _SECTION_HEADERS.values()]
    lines = text.splitlines()
    start: Optional[int] = None
    for i, ln in enumerate(lines):
        if _is_header(ln, keys):
            start = i + 1
            break
    if start is None:
        return ""
    body: list[str] = []
    for ln in lines[start:]:
        if any(_is_header(ln, h) for h in all_headers):
            break
        if ln.strip():
            body.append(ln)
    return "\n".join(body)


def _classify_links(links: list[str]) -> dict:
    fields: dict = {"linkedin": "", "github": "", "cv_url": ""}
    for link in links:
        if REGEX["linkedin"].search(link) and not fields["linkedin"]:
            fields["linkedin"] = link
        elif REGEX["github"].search(link) and not fields["github"]:
            fields["github"] = link
        elif not fields["cv_url"]:
            fields["cv_url"] = link
    return fields


def parse_text(text: str, links: Optional[list[str]] = None) -> dict:
    """Apply regex + heuristics to CV ``text`` and merged ``links``.

    Returns ``{"fields": {...}, "missing": [required keys absent]}``.
    """
    link_fields = _classify_links(links or [])
    fields: dict = {
        "nombre": _extract_nombre(text),
        "resumen": _extract_section(text, _SECTION_HEADERS["resumen"]),
        "linkedin": link_fields["linkedin"] or _find_first(text, REGEX["linkedin"]),
        "github": link_fields["github"] or _find_first(text, REGEX["github"]),
        "telefono": _find_phone(text),
        "correo": _find_first(text, REGEX["email"]),
        "cv_url": link_fields["cv_url"] or "",
        "experiencia": _extract_section(text, _SECTION_HEADERS["experiencia"]),
        "educacion": _extract_section(text, _SECTION_HEADERS["educacion"]),
        "skills": _extract_section(text, _SECTION_HEADERS["skills"]),
    }
    missing = [k for k in REQUIRED if not fields.get(k)]
    return {"fields": fields, "missing": missing}


_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def render_template(template_path: Path, fields: dict) -> str:
    """Read template and replace each ``{{key}}`` with ``fields.get(key, '')``.

    Unknown placeholders (not in ``fields``) are replaced with an empty string
    so the rendered file never leaks a literal ``{{...}}`` token.
    """
    text = template_path.read_text(encoding="utf-8")
    return _PLACEHOLDER.sub(
        lambda m: str(fields.get(m.group(1), "") or ""), text
    )


def _email_block(fields: dict) -> str:
    examples = fields.get("email_examples")
    if isinstance(examples, list) and examples:
        blocks = []
        for idx, ex in enumerate(examples, 1):
            blocks.append(f"### Ejemplo {idx}\n{ex}")
        return "\n\n".join(blocks)
    return "_(No se proporcionaron ejemplos de correos.)_"


def _backup(out_dir: Path, name: str, no_backup: bool) -> None:
    if no_backup:
        return
    target = out_dir / name
    if target.is_file():
        shutil.copy2(target, out_dir / f"{name}.bak")


def generate_files(fields: dict, out_dir: Path, no_backup: bool) -> dict:
    """Render the three templates and write them under ``out_dir``.

    Creates ``out_dir`` if missing. Backs up existing files to ``*.bak`` first
    unless ``no_backup`` is set.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    render_fields = dict(fields)
    render_fields.setdefault("notas", "")
    render_fields.setdefault("notas_adicionales", "")
    render_fields["email_bloque"] = _email_block(fields)

    outputs = {}
    for template_name, out_name in (
        ("perfil.template.md", "perfil.md"),
        ("correos.template.md", "correos.md"),
        ("preferencias.template.md", "preferencias.md"),
    ):
        _backup(out_dir, out_name, no_backup)
        rendered = render_template(TEMPLATES_DIR / template_name, render_fields)
        (out_dir / out_name).write_text(rendered, encoding="utf-8")
        outputs[out_name.replace(".md", "_path")] = str(out_dir / out_name)
    return outputs


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
        "parse": {"fields": parsed["fields"], "missing": parsed["missing"]},
        "generate": outputs,
    })


if __name__ == "__main__":
    app()
