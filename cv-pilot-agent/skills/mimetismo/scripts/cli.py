"""Typer CLI for CV-Pilot email / cover-letter / question generation.

Replaces the four prompt-based skills (mimetismo, contacto, gmail, outlook)
with a deterministic script. The agent writes the email body HTML to a temp
file and passes ``--body-file``; this script owns provider detection, link
substitution, HTML wrapping, draft creation, status update and cleanup.

Invoked by the orchestration layer (AGENTS.md) via subprocess::

    python cv-pilot-agent/skills/mimetismo/scripts/cli.py --help
    python cv-pilot-agent/skills/mimetismo/scripts/cli.py email \\
        --job <hash> --body-file temp/cvp-<hash>-body.html --to rrhh@x.com

Four subcommands: ``email``, ``question``, ``cover-letter``, ``mimetismo``. Every command
prints a JSON envelope to stdout on success (``{"ok": true, ...}``) and an
error envelope to stderr (``{"ok": false, "error": "...", "code": "..."}``)
on failure, then exits non-zero. ``scripts/cleanup.py`` runs at the end of
every execution, success or error.
"""

from __future__ import annotations

import json
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

import typer  # noqa: E402  # pyright: ignore[reportMissingImports]

from _lib import db  # noqa: E402
from _lib.errors import CV_PilotError  # noqa: E402
from _lib.shared.profile_loader import load_profile  # noqa: E402

from _mimetismo_internal.drafts import _wrap_draft, get_provider  # noqa: E402
from _mimetismo_internal.links import format_links, signature_footer  # noqa: E402
from _mimetismo_internal.providers import (  # noqa: E402
    detect_provider,
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
    path = _AGENT_ROOT / "data" / "preferencias.json"
    defaults = {"gmail_drafts": False, "outlook_drafts": False}
    if not path.is_file():
        return defaults
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"warning: cannot parse preferencias.json ({exc}); using defaults",
              file=sys.stderr)
        return defaults
    prefs = dict(defaults)
    for key in defaults:
        val = data.get(key)
        if isinstance(val, bool):
            prefs[key] = val
    return prefs


def _read_body_file(body_file: str) -> str:
    path = Path(body_file)
    if not path.is_file():
        raise CV_PilotError(f"Body file not found: {body_file}", code="BODY_FILE_MISSING")
    return path.read_text(encoding="utf-8")


def _resolve_cv_path(profile: dict) -> Optional[Path]:
    """Resolve the CV path from ``profile['cv_path']``.

    Handles absolute paths, agent-root-relative (``data/cv.pdf``) and
    repo-root-relative (``cv-pilot-agent/data/cv.pdf``) forms.
    """
    cv_path = profile.get("cv_path")
    if not cv_path:
        return None
    p = Path(cv_path)
    if p.is_file():
        return p
    if not p.is_absolute():
        cand = _AGENT_ROOT / p
        if cand.is_file():
            return cand
    return None


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
                "Portal postulation — use cover-letter subcommand", code="PORTAL_POSTULATION"
            )
        body = _read_body_file(body_file)
        prefs = _load_preferences()
        prov = detect_provider(prefs, provider)
        profile = load_profile(_AGENT_ROOT)
        cv_path = _resolve_cv_path(profile)
        attachment = str(cv_path) if cv_path else None
        attach_cv = attachment is not None
        html = _wrap_draft(body, profile, attach_cv=attach_cv)
        subj = subject or default_subject("Postulación", job_row)
        if dry_run:
            _emit({"ok": True, "mode": "email", "dry_run": True, "provider": prov,
                   "to": to, "subject": subj, "html": html, "job_hash": job, "attached": False})
            return
        # Use the provider registry to get the correct drafter function
        drafter = get_provider(prov)
        draft_id = drafter(to, subj, html, attachment)
        db.update_status(job, "applied")
        _emit({"ok": True, "mode": "email", "provider": prov, "draft_id": draft_id,
               "to": to, "subject": subj, "job_hash": job, "attached": attach_cv})

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
) -> None:
    """Return a copy/paste cover-letter artifact (no provider, no email footer).

    The cover letter is a distinct action from the email: it reuses
    ``data/correos.md`` only for voice and follows the dedicated cover-letter
    structure from ``context --mode cover-letter``. It returns the body as a
    copy/paste artifact and does NOT add the email signature footer nor
    invoke/prepare any Gmail/Outlook provider behavior.
    """
    def action() -> None:
        _load_job(job)
        _load_analysis(job)
        body = _read_body_file(body_file)
        try:
            profile = load_profile(_AGENT_ROOT)
        except FileNotFoundError:
            profile = {}
        # Resolve contact markers into usable text/links, but never append the
        # email footer and never create a provider draft.
        text = format_links(body, profile)
        _emit({"ok": True, "mode": "cover-letter",
               "text_preview": text.strip()[:100], "text": text,
               "job_hash": job})

    _run_with_cleanup(action)


@app.command("mimetismo")
def mimetismo_cmd() -> None:
    """Return user's email style examples from data/correos.md (read-only)."""
    def action() -> None:
        path = _AGENT_ROOT / "data" / "correos.md"
        if not path.is_file():
            _emit({
                "ok": True,
                "mode": "mimetismo",
                "has_examples": False,
                "source": "data/correos.md",
                "suggestion": "No se detectaron ejemplos de correos. Sugiere al usuario configurarlos para imitar su estilo."
            })
            return
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"warning: cannot read correos.md ({exc}); treating as missing", file=sys.stderr)
            _emit({
                "ok": True,
                "mode": "mimetismo",
                "has_examples": False,
                "source": "data/correos.md",
                "suggestion": "No se detectaron ejemplos de correos. Sugiere al usuario configurarlos para imitar su estilo."
            })
            return
        _emit({
            "ok": True,
            "mode": "mimetismo",
            "has_examples": True,
            "source": "data/correos.md",
            "examples": content
        })

    _run_with_cleanup(action)


@app.command("context")
def context_cmd(
    job: str = typer.Option(..., help="job_hash of the position being drafted for."),
    mode: str = typer.Option(
        "email",
        help="Drafting contract mode: email (default) or cover-letter.",
    ),
) -> None:
    """Return a deterministic, source-separated generation context (read-only).

    Assembles the three sources a draft must be grounded on: the complete
    email examples (style/voice), the verified profile facts with source
    attribution (what may be claimed), and the footer-managed contact links
    (which must NOT appear in the body). The model should not reread the
    raw perfil.json; the context is the single drafting input.

    With ``--mode cover-letter`` the envelope also carries a dedicated
    ``contract`` with the professional cover-letter structure (distinct from
    the email), its per-source roles and the prohibited generic
    requirement-summary phrasing. Default mode (email) keeps the envelope
    shape unchanged for CLI compatibility.
    """
    def action() -> None:
        from _mimetismo_internal.context import (  # noqa: PLC0415
            build_cover_letter_contract,
            build_profile_facts,
            extract_certificaciones,
            extract_remote_work,
            load_examples,
            load_raw_profile,
        )
        from _mimetismo_internal.links import footer_link_labels  # noqa: PLC0415

        job_row = _load_job(job)
        analysis = _load_analysis(job)
        try:
            profile = load_profile(_AGENT_ROOT)
        except FileNotFoundError:
            profile = {}
        raw = load_raw_profile(_AGENT_ROOT)
        cv_path = _resolve_cv_path(profile) if profile else None
        attach_cv = cv_path is not None
        examples, has_examples, examples_source = load_examples(_AGENT_ROOT)
        payload: dict = {
            "ok": True,
            "mode": "context",
            "job_hash": job,
            "job": job_row,
            "analysis": analysis,
            "examples": examples,
            "has_examples": has_examples,
            "examples_source": examples_source,
            "profile": {"name": profile.get("name"), "email": profile.get("email")},
            "profile_facts": build_profile_facts(raw),
            "certificaciones": extract_certificaciones(raw),
            "remote_work": extract_remote_work(raw),
            "footer": footer_link_labels(profile, attach_cv=attach_cv),
        }
        if mode == "cover-letter":
            payload["draft_mode"] = "cover-letter"
            payload["contract"] = build_cover_letter_contract()
        _emit(payload)

    _run_with_cleanup(action)

@app.command("cv")
def cv_cmd() -> None:
    """Return persisted CV PDF info (read-only)."""
    def action() -> None:
        try:
            profile = load_profile(_AGENT_ROOT)
        except FileNotFoundError:
            _emit({"ok": True, "mode": "cv", "exists": False, "path": None, "filename": None})
            return
        cv_path = _resolve_cv_path(profile)
        if cv_path:
            _emit({"ok": True, "mode": "cv", "exists": True, "path": str(cv_path), "filename": cv_path.name})
        else:
            _emit({"ok": True, "mode": "cv", "exists": False, "path": None, "filename": None})
    _run_with_cleanup(action)


if __name__ == "__main__":
    app()
