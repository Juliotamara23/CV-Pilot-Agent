"""Typer CLI for CV-Pilot email / cover-letter / question generation.

Replaces the four prompt-based skills (mimetismo, contacto, gmail, outlook)
with a deterministic script. The agent writes the email body HTML to a temp
file and passes ``--body-file``; this script owns provider detection, link
substitution, HTML wrapping, draft creation, status update and cleanup.

Invoked by the orchestration layer (AGENTS.md) via subprocess::

    python cv-pilot-agent/skills/mimetismo/scripts/cli.py --help
    python cv-pilot-agent/skills/mimetismo/scripts/cli.py email \\
        --job <hash> --body-file temp/cvp-<hash>-body.html --to rrhh@x.com

Three subcommands: ``email``, ``question``, ``cover-letter``. Every command
prints a JSON envelope to stdout on success (``{"ok": true, ...}``) and an
error envelope to stderr (``{"ok": false, "error": "...", "code": "..."}``)
on failure, then exits non-zero. ``scripts/cleanup.py`` runs at the end of
every execution, success or error.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Force UTF-8 on the std streams so JSON output (ensure_ascii=False) and error
# envelopes never depend on the host console codepage (e.g. Windows cp1252).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

# Make `cv-pilot-agent/` importable when the script is run by path.
_AGENT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_AGENT_ROOT))

import typer  # noqa: E402

from _lib import db  # noqa: E402
from _lib.errors import CV_PilotError  # noqa: E402
from _lib.shared.profile_loader import load_profile  # noqa: E402

from _mimetismo_internal.drafts import create_draft_gmail, create_draft_outlook  # noqa: E402
from _mimetismo_internal.links import format_links, signature_footer  # noqa: E402
from _mimetismo_internal.providers import (  # noqa: E402
    _TRUE,
    detect_provider,
    detect_provider_optional,
)
from _mimetismo_internal.subject import default_subject  # noqa: E402

app = typer.Typer(
    name="generate",
    help="CV-Pilot email / cover-letter / question generation CLI.",
    add_completion=False,
    no_args_is_help=True,
)


def _emit(payload: dict) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False))


def _emit_error(message: str, code: str) -> None:
    typer.echo(
        json.dumps({"ok": False, "error": message, "code": code}, ensure_ascii=False),
        err=True,
    )


def _run_with_cleanup(action) -> None:
    """Execute an action; map CV_PilotError to the stderr envelope; cleanup always."""
    try:
        action()
    except CV_PilotError as exc:
        _emit_error(exc.message or exc.__class__.__name__, exc.code)
        raise typer.Exit(code=1)
    finally:
        _cleanup()


# --------------------------------------------------------------------------- #
# Loaders
# --------------------------------------------------------------------------- #
def _load_job(job_hash: str) -> dict:
    return db.get_job(job_hash)["job"]


def _load_analysis(job_hash: str) -> dict:
    return db.get_analysis(job_hash)["analysis"]


def _load_preferences() -> dict:
    path = _AGENT_ROOT / "data" / "preferencias.md"
    prefs = {"gmail_drafts": False, "outlook_drafts": False}
    if not path.is_file():
        return prefs
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        match = re.match(r"^\s*(gmail_drafts|outlook_drafts)\s*:\s*(.+?)\s*$", line)
        if match:
            prefs[match.group(1)] = match.group(2).strip().lower() in _TRUE
    return prefs


def _read_body_file(body_file: str) -> str:
    path = Path(body_file)
    if not path.is_file():
        raise CV_PilotError(f"Body file not found: {body_file}", code="BODY_FILE_MISSING")
    return path.read_text(encoding="utf-8")


def _wrap_gmail(body: str, profile: dict) -> str:
    return format_links(body, profile) + signature_footer(profile)


def _wrap_outlook(body: str, profile: dict) -> str:
    # Outlook uses the same HTML body (contentType: HTML) as Gmail.
    return format_links(body, profile) + signature_footer(profile)


def _cleanup() -> None:
    cleanup = _AGENT_ROOT / "scripts" / "cleanup.py"
    if not cleanup.is_file():
        return
    try:
        subprocess.run(
            [sys.executable, str(cleanup)], capture_output=True, text=True
        )
    except OSError:
        # Cleanup is non-blocking — never surface failures to the user.
        pass


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
@app.command("email")
def email_cmd(
    job: str = typer.Option(..., help="job_hash (SHA256) of the job."),
    body_file: str = typer.Option(..., help="Path to the agent-written HTML body file."),
    to: str = typer.Option(..., help="Recipient email address."),
    provider: Optional[str] = typer.Option(None, help="Override provider (gmail|outlook)."),
    subject: Optional[str] = typer.Option(None, help="Email subject (default: Postulación: <position> — <company>)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Emit wrapped HTML without creating a draft."),
) -> None:
    """Generate an email draft via the configured provider."""
    def action() -> None:
        job_row = _load_job(job)
        analysis = _load_analysis(job)
        if analysis.get("contact_method") == "portal":
            raise CV_PilotError(
                "Portal postulation — use --mode cover-letter", code="PORTAL_POSTULATION"
            )
        body = _read_body_file(body_file)
        prefs = _load_preferences()
        prov = detect_provider(prefs, provider)
        profile = load_profile(_AGENT_ROOT)
        html = _wrap_gmail(body, profile) if prov == "gmail" else _wrap_outlook(body, profile)
        subj = subject or default_subject("Postulación", job_row)
        if dry_run:
            _emit({"ok": True, "mode": "email", "dry_run": True, "provider": prov,
                   "to": to, "subject": subj, "html": html, "job_hash": job})
            return
        drafter = create_draft_gmail if prov == "gmail" else create_draft_outlook
        draft_id = drafter(to, subj, html)
        db.update_status(job, "applied")
        _emit({"ok": True, "mode": "email", "provider": prov, "draft_id": draft_id,
               "to": to, "subject": subj, "job_hash": job})

    _run_with_cleanup(action)


@app.command("question")
def question_cmd(
    job: str = typer.Option(..., help="job_hash (SHA256) of the job."),
    body_file: str = typer.Option(..., help="Path to the question text file."),
) -> None:
    """Format and return question text for portal submission (no draft)."""
    def action() -> None:
        _load_job(job)
        text = _read_body_file(body_file)
        if not text.strip():
            raise CV_PilotError("Question is empty", code="EMPTY_QUESTION")
        _emit({"ok": True, "mode": "question", "text_preview": text.strip()[:100],
               "text": text, "job_hash": job})

    _run_with_cleanup(action)


@app.command("cover-letter")
def cover_letter_cmd(
    job: str = typer.Option(..., help="job_hash (SHA256) of the job."),
    body_file: str = typer.Option(..., help="Path to the agent-written HTML body file."),
    provider: Optional[str] = typer.Option(None, help="Override provider (gmail|outlook)."),
    to: Optional[str] = typer.Option(None, help="Recipient email address (required to create a draft)."),
    subject: Optional[str] = typer.Option(None, help="Subject (default: Carta de presentación: <position> — <company>)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Emit wrapped HTML without creating a draft."),
) -> None:
    """Generate a cover letter draft (or return text when no provider / no recipient)."""
    def action() -> None:
        job_row = _load_job(job)
        _load_analysis(job)
        body = _read_body_file(body_file)
        profile = load_profile(_AGENT_ROOT)
        prefs = _load_preferences()
        # Cover letter is the portal fallback — no PORTAL_POSTULATION block.
        prov = detect_provider_optional(prefs, provider)
        wrapped = format_links(body, profile) + signature_footer(profile)
        subj = subject or default_subject("Carta de presentación", job_row)
        if dry_run:
            _emit({"ok": True, "mode": "cover-letter", "dry_run": True,
                   "provider": prov, "html": wrapped, "job_hash": job})
            return
        if prov is not None and to:
            drafter = create_draft_gmail if prov == "gmail" else create_draft_outlook
            draft_id = drafter(to, subj, wrapped)
            db.update_status(job, "applied")
            _emit({"ok": True, "mode": "cover-letter", "provider": prov,
                   "draft_id": draft_id, "to": to, "subject": subj, "job_hash": job})
        else:
            _emit({"ok": True, "mode": "cover-letter", "provider": None,
                   "text_preview": wrapped.strip()[:100], "text": wrapped,
                   "job_hash": job})

    _run_with_cleanup(action)


if __name__ == "__main__":
    app()
