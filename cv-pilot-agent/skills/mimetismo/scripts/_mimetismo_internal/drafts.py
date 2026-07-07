"""Draft creation for Gmail and Outlook via external CLIs.

Gmail uses ``gws`` CLI; Outlook uses ``m365`` CLI + PowerShell Graph API call.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from _lib.errors import CV_PilotError


def create_draft_gmail(to: str, subject: str, body_html: str) -> str:
    """Create a Gmail draft via ``gws`` CLI. Returns the draft id string.

    On Windows, ``gws`` is distributed as a wrapper script via npm
    (``gws.CMD`` or ``gws.ps1``). Python's ``subprocess.run`` with a bare
    program name does not auto-resolve ``.CMD``/``.BAT`` extensions on
    Windows, and cannot execute ``.ps1`` at all — both cases must be wrapped
    in the appropriate shell. On Linux/macOS, ``gws`` is a native binary
    invoked directly.
    """
    gws_path = shutil.which("gws")
    if gws_path is None:
        raise CV_PilotError(
            "gws CLI not found. Install and authenticate gws (see docs/gws-setup.md).",
            code="PROVIDER_CLI_MISSING",
        )
    suffix = Path(gws_path).suffix.lower()
    if suffix == ".ps1":
        shell = shutil.which("pwsh") or shutil.which("powershell")
        if shell is None:
            raise CV_PilotError(
                "PowerShell not found (need pwsh or powershell to run gws.ps1).",
                code="PROVIDER_CLI_MISSING",
            )
        cmd = [shell, "-NoProfile", "-File", gws_path,
               "gmail", "+send", "--to", to, "--subject", subject,
               "--body", body_html, "--html", "--draft"]
    elif suffix in (".cmd", ".bat"):
        # Windows shell wrappers from npm: invoke via cmd.exe to ensure
        # PATHEXT resolution and proper argument quoting.
        cmd_path = shutil.which("cmd")
        if cmd_path is None:
            raise CV_PilotError(
                "cmd.exe not found (required to run gws.CMD/gws.BAT wrappers).",
                code="PROVIDER_CLI_MISSING",
            )
        cmd = [cmd_path, "/c", gws_path,
               "gmail", "+send", "--to", to, "--subject", subject,
               "--body", body_html, "--html", "--draft"]
    else:
        # Native binary on Linux/macOS, or .exe on Windows.
        cmd = [gws_path, "gmail", "+send", "--to", to, "--subject", subject,
               "--body", body_html, "--html", "--draft"]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise CV_PilotError(
            f"Gmail draft creation failed: {proc.stderr.strip()}", code="DRAFT_FAILED"
        )
    return (proc.stdout.strip().splitlines() or [""])[0] or "draft"


def create_draft_outlook(to: str, subject: str, body_html: str) -> str:
    """Create an Outlook draft via ``m365`` CLI + PowerShell. Returns the message id."""
    if shutil.which("m365") is None:
        raise CV_PilotError(
            "m365 CLI not found. Install and login to m365 (see docs/outlook-setup.md).",
            code="PROVIDER_CLI_MISSING",
        )
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if shell is None:
        raise CV_PilotError(
            "PowerShell not found (need pwsh or powershell for the Graph API call).",
            code="PROVIDER_CLI_MISSING",
        )
    payload = json.dumps(
        {"subject": subject, "body": {"contentType": "HTML", "content": body_html},
         "toRecipients": [{"emailAddress": {"address": to}}]},
        ensure_ascii=False,
    )
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
        body_path = fh.name
        fh.write(payload)
    script = (
        "$ErrorActionPreference='Stop';"
        "$token = m365 util accesstoken get --resource "
        "'https://graph.microsoft.com' --output text;"
        f"$body = Get-Content -Path '{body_path}' -Raw -Encoding UTF8;"
        "$resp = Invoke-RestMethod -Uri "
        "'https://graph.microsoft.com/v1.0/me/messages' -Method Post "
        "-ContentType 'application/json; charset=utf-8' "
        "-Headers @{Authorization = \"Bearer $token\"} -Body $body;"
        "Write-Output $resp.id"
    )
    try:
        proc = subprocess.run(
            [shell, "-NoProfile", "-Command", script],
            capture_output=True, text=True, encoding="utf-8",
        )
    finally:
        Path(body_path).unlink(missing_ok=True)
    if proc.returncode != 0:
        raise CV_PilotError(
            f"Outlook draft creation failed: {proc.stderr.strip()}", code="DRAFT_FAILED"
        )
    return (proc.stdout.strip().splitlines() or [""])[0] or "draft"
