"""Shared CLI utilities for CV-Pilot scripts.

Eliminates duplication of UTF-8 setup, sys.path insertion, and JSON
envelope emission across all skill CLI entrypoints.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def setup_utf8() -> None:
    """Force UTF-8 on stdout/stderr so JSON output never depends on host codepage."""
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]


def setup_syspath(levels_up: int = 3) -> Path:
    """Insert ``cv-pilot-agent/`` into ``sys.path`` and return its resolved Path.

    Parameters
    ----------
    levels_up:
        How many parent directories to climb from the calling script to reach
        ``cv-pilot-agent/``.  Default 3 works for scripts at
        ``skills/<name>/scripts/<script>.py``.
    """
    caller = Path(sys._getframe(1).f_code.co_filename).resolve()
    agent_root = caller.parents[levels_up]
    if str(agent_root) not in sys.path:
        sys.path.insert(0, str(agent_root))
    return agent_root


def emit_ok(data: dict) -> None:
    """Print a success JSON envelope to stdout and exit 0."""
    import typer
    typer.echo(json.dumps(data, ensure_ascii=False))
    raise typer.Exit(code=0)


def emit_error(error: str, code: str, exit_code: int = 1) -> None:
    """Print an error JSON envelope to stderr and exit with *exit_code*."""
    import typer
    typer.echo(
        json.dumps({"ok": False, "error": error, "code": code}, ensure_ascii=False),
        err=True,
    )
    raise typer.Exit(code=exit_code)


def persist_cv_pdf(
    source_pdf: str | Path,
    dest_dir: Path,
    agent_root: Path,
) -> tuple[Path | None, str | None]:
    """Copy the source PDF to the destination directory preserving the original filename.

    The original basename is used if it ends with ``.pdf`` (case-insensitive).
    Otherwise, falls back to ``cv.pdf``. Path traversal is prevented by using
    only ``Path(source).name``.

    Parameters
    ----------
    source_pdf:
        Path to the source PDF file.
    dest_dir:
        Destination directory where the PDF should be copied.
    agent_root:
        Root path of the agent (used to compute relative ``cv_path``).

    Returns
    -------
    tuple
        (copied_path, cv_path_relative) where:
        - copied_path: Path to the copied file, or None if source doesn't exist
        - cv_path_relative: Relative path from agent_root to copied file for perfil.json,
          or None if source doesn't exist
    """
    source = Path(source_pdf)
    if not source.exists():
        return None, None

    # Use only the basename to prevent path traversal
    basename = source.name
    # Preserve original filename if it ends with .pdf (case-insensitive)
    if basename.lower().endswith(".pdf"):
        dest_name = basename
    else:
        dest_name = "cv.pdf"

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / dest_name
    shutil.copy2(source, dest_path)

    # Compute cv_path relative to agent_root for consistent resolution
    try:
        cv_path = str(dest_path.resolve().relative_to(agent_root.resolve()))
    except ValueError:
        cv_path = str(dest_path)

    return dest_path, cv_path
