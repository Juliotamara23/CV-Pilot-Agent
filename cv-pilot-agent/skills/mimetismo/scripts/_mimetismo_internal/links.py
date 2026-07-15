"""Link substitution and signature footer for CV-Pilot emails.

Replaces ``[github]``, ``[linkedin]``, ``[cv]``, ``[whatsapp]`` markers in
the body with ``<a>`` tags and builds the HTML signature footer.
"""

from __future__ import annotations

# Profile/draft.json keys reused across link + footer builders.
_LABELS = ("github", "linkedin", "cv_url", "whatsapp")
_LABEL_TEXT = {"github": "GitHub", "linkedin": "LinkedIn", "cv_url": "CV", "whatsapp": "WhatsApp"}


def format_links(body: str, profile: dict) -> str:
    """Replace ``[github]``, ``[linkedin]``, ``[cv]``, ``[whatsapp]`` markers."""
    for key, marker in (("github", "[github]"), ("linkedin", "[linkedin]"),
                        ("cv_url", "[cv]"), ("whatsapp", "[whatsapp]")):
        url = profile.get(key)
        label = _LABEL_TEXT[key]
        tag = f'<a href="{url}">{label}</a>' if url else label
        body = body.replace(marker, tag)
    return body


def signature_footer(profile: dict) -> str:
    """Build the HTML signature block with name and available profile links."""
    links = [
        f'<a href="{profile[key]}">{_LABEL_TEXT[key]}</a>'
        for key in _LABELS if profile.get(key)
    ]
    name = profile.get("name") or ""
    footer = "<br><br>Saludos cordiales,<br>"
    if name:
        footer += f"{name}<br>"
    if links:
        footer += " | ".join(links)
    return footer
