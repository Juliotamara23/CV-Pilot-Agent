"""Draft creation for email providers via external CLIs.

Provider implementations:
- Gmail uses ``gws`` CLI
- Outlook uses ``m365`` CLI + PowerShell Graph API call
- Extensible registry-based architecture
"""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Optional

from _lib.errors import CV_PilotError
from _mimetismo_internal.links import format_links, signature_footer

# Type alias for provider callable
ProviderCallable = Callable[[str, str, str, Optional[str]], str]

# Global registry - providers are auto-registered when imported
_registry: dict[str, ProviderCallable] = {}


def register_provider(name: str):
    """Decorator to register a provider function with the provider registry."""
    def decorator(func: ProviderCallable) -> ProviderCallable:
        _registry[name] = func
        return func
    return decorator


def get_provider(name: str) -> ProviderCallable:
    """Get a provider by name. Raises CV_PilotError if not found."""
    if name not in _registry:
        raise CV_PilotError(
            f"Provider '{name}' not found. Available providers: {list(_registry.keys())}",
            code="PROVIDER_NOT_FOUND",
        )
    return _registry[name]


def list_providers() -> list[str]:
    """Get list of all registered provider names."""
    return list(_registry.keys())


def _wrap_draft(body: str, profile: dict, attach_cv: bool = False) -> str:
    """Apply formatting links and signature footer to a draft body."""
    return format_links(body, profile, attach_cv=attach_cv) + signature_footer(
        profile, attach_cv=attach_cv
    )


@register_provider("gmail")
def create_draft_gmail(to: str, subject: str, body_html: str, attachment: Optional[str] = None) -> str:
    """Create a Gmail draft via ``gws`` CLI. Returns the draft id string.

    On Windows, ``gws`` is distributed as a wrapper script via npm
    (``gws.CMD`` or ``gws.ps1``). Python's ``subprocess.run`` with a bare
    program name does not auto-resolve ``.CMD``/``.BAT`` extensions on
    Windows, and cannot execute ``.ps1`` at all — both cases must be wrapped
    in the appropriate shell. On Linux/macOS, ``gws`` is a native binary
    invoked directly.

    If ``attachment`` is provided, the ``-a`` flag is passed to gws before
    ``--draft`` to attach the file.
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
               "--body", body_html, "--html"]
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
               "--body", body_html, "--html"]
    else:
        # Native binary on Linux/macOS, or .exe on Windows.
        cmd = [gws_path, "gmail", "+send", "--to", to, "--subject", subject,
               "--body", body_html, "--html"]
    if attachment:
        cmd.extend(["-a", attachment])
    cmd.append("--draft")
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise CV_PilotError(
            f"Gmail draft creation failed: {proc.stderr.strip()}", code="DRAFT_FAILED"
        )
    # gws returns a multi-line JSON envelope: {"id": "r-...", "message": {...}}.
    # The top-level "id" is the draft id (confirmed by gws stderr hint).
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        # JSON parsed: trust it. Missing "id" → default (don't fall through
        # to the line-based fallback, which would return the whole JSON blob).
        return payload.get("id", "draft")
    # Non-JSON output (legacy / other CLIs): first non-empty line.
    for line in proc.stdout.splitlines():
        if line.strip():
            return line.strip()
    return "draft"


@register_provider("outlook")
def create_draft_outlook(to: str, subject: str, body_html: str, attachment: Optional[str] = None) -> str:
    """Create an Outlook draft via ``m365`` CLI + PowerShell. Returns the message id.

    If ``attachment`` is provided, after creating the draft the attachment is
    uploaded via a Graph API POST to the draft's attachments endpoint.
    """
    m365_path = shutil.which("m365")
    if m365_path is None:
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
    # Fetch the token in Python so the same m365 session used by the agent
    # (e.g. the Linux m365 under WSL) authenticates the Graph calls. Calling
    # `m365` from inside PowerShell would use the Windows-side m365, whose
    # auth is separate and can hang on an interactive device-code prompt.
    token_proc = subprocess.run(
        [m365_path, "util", "accesstoken", "get",
         "--resource", "https://graph.microsoft.com", "--output", "text"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if token_proc.returncode != 0 or not token_proc.stdout.strip():
        raise CV_PilotError(
            f"m365 token retrieval failed: {token_proc.stderr.strip()[:300]}",
            code="DRAFT_FAILED",
        )
    token = token_proc.stdout.strip()
    payload = json.dumps(
        {"subject": subject, "body": {"contentType": "HTML", "content": body_html},
         "toRecipients": [{"emailAddress": {"address": to}}]},
        ensure_ascii=False,
    )
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
        body_path = fh.name
        fh.write(payload)
    # Windows PowerShell (WSL interop) cannot read Linux /tmp paths — convert
    # to a \\wsl.localhost\... path when wslpath is available.
    body_script_path = body_path
    wslpath = shutil.which("wslpath")
    if wslpath and not sys.platform.startswith("win"):
        conv = subprocess.run(
            [wslpath, "-w", body_path], capture_output=True, text=True
        )
        if conv.returncode == 0 and conv.stdout.strip():
            body_script_path = conv.stdout.strip()
    script = (
        "$ErrorActionPreference='Stop';"
        f"$token = '{token}';"
        f"$body = Get-Content -Path '{body_script_path}' -Raw -Encoding UTF8;"
        "$resp = Invoke-RestMethod -Uri "
        "'https://graph.microsoft.com/v1.0/me/messages' -Method Post "
        "-ContentType 'application/json; charset=utf-8' "
        "-Headers @{Authorization = \"Bearer $token\"} -Body $body;"
        "Write-Output $resp.id;"
    )
    if attachment:
        att_path = Path(attachment)
        filename = att_path.name
        with open(attachment, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        script += (
            "$ErrorActionPreference='Stop';"
            "try {"
            f"$attBody = @{{ '@odata.type' = '#microsoft.graph.fileAttachment'; "
            f"name = '{filename}'; contentBytes = '{b64}' }} | ConvertTo-Json -Depth 3;"
            f"Invoke-RestMethod -Uri (\"https://graph.microsoft.com/v1.0/me/messages/\" + "
            f"$resp.id + \"/attachments\") -Method Post "
            f"-ContentType 'application/json; charset=utf-8' "
            f"-Headers @{{Authorization = \"Bearer $token\"}} -Body $attBody | Out-Null;"
            "} catch {"
            "  $respBody = '';"
            "  if ($_.Exception.Response) {"
            "    try { $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream());"
            "          $respBody = $reader.ReadToEnd() } catch { $respBody = '' }"
            "  }"
            "  throw (\"Graph attachment POST failed: \" + $_.Exception.Message + "
            "         $(if ($respBody) { \" | \" + $respBody } else { '' }));"
            "}"
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
