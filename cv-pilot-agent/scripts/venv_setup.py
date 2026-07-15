"""Create and configure the CV-Pilot virtual environment.

Detects Python, creates .venv/, installs dependencies, and verifies
the installation. Designed to be invoked by the agent when .venv/
is missing — retries up to 3 times before reporting failure.

Outputs JSON to stdout on success, to stderr on failure.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = AGENT_ROOT / ".venv"
REQUIREMENTS = AGENT_ROOT / "requirements.txt"
MIN_PYTHON = (3, 9)


def _find_python() -> str:
    """Locate a Python 3.9+ interpreter in the system PATH."""
    candidates = ["python3", "python"]
    for name in candidates:
        exe = shutil.which(name)
        if exe is None:
            continue
        try:
            out = subprocess.check_output(
                [exe, "--version"], stderr=subprocess.STDOUT, text=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
        m = re.search(r"(\d+)\.(\d+)", out)
        if m and (int(m[1]), int(m[2])) >= MIN_PYTHON:
            return exe
    return ""


def _create_venv(python_exe: str) -> Path:
    """Create .venv/ using the detected Python. Returns Path to venv python."""
    if (VENV_DIR / "Scripts" / "python.exe").exists():
        return VENV_DIR / "Scripts" / "python.exe"
    subprocess.run([python_exe, "-m", "venv", str(VENV_DIR)], check=True)
    venv_python = VENV_DIR / "Scripts" / "python.exe"
    if not venv_python.exists():
        raise RuntimeError(f"venv creation failed — no python at {venv_python}")
    return venv_python


def _install_deps(venv_python: Path) -> None:
    subprocess.run(
        [str(venv_python), "-m", "pip", "install", "--upgrade", "pip", "--quiet"],
        check=True,
    )
    subprocess.run(
        [str(venv_python), "-m", "pip", "install", "-r", str(REQUIREMENTS), "--quiet"],
        check=True,
    )


def _verify(venv_python: Path) -> None:
    subprocess.run(
        [str(venv_python), "-c", "import fitz, typer, pydantic; print('OK')"],
        check=True,
    )


def setup() -> None:
    try:
        python_exe = _find_python()
        if not python_exe:
            raise RuntimeError(
                "Python 3.9+ not found in PATH. Install Python and retry."
            )

        venv_python = _create_venv(python_exe)
        _install_deps(venv_python)
        _verify(venv_python)

        result = {
            "ok": True,
            "venv_python": str(venv_python),
            "venv_dir": str(VENV_DIR),
        }
        print(json.dumps(result, ensure_ascii=False))
    except Exception as exc:
        err = {"ok": False, "error": str(exc), "code": "VENV_SETUP_FAILED"}
        print(json.dumps(err, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    setup()
