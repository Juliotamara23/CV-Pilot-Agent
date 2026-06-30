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
    """Create a Gmail draft via ``gws`` CLI. Returns the draft id string."""
    if shutil.which("gws") is None:
        raise CV_PilotError(
            "gws CLI not found. Install and authenticate gws (see docs/gws-setup.md).",
            code="PROVIDER_CLI_MISSING",
        )
    proc = subprocess.run(
        ["gws", "gmail", "+send", "--to", to, "--subject", subject,
         "--body", body_html, "--html", "--draft"],
        capture_output=True, text=True, encoding="utf-8",
    )
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
