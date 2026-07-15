"""Shared CLI utilities for CV-Pilot scripts.

Eliminates duplication of UTF-8 setup, sys.path insertion, and JSON
envelope emission across all skill CLI entrypoints.
"""

from __future__ import annotations

import json
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
