"""Link substitution and signature footer for CV-Pilot emails.

Replaces ``[github]``, ``[linkedin]``, ``[cv]``, ``[whatsapp]`` markers in
the body with ``<a>`` tags and builds the HTML signature footer.

When ``attach_cv=True`` (the real CV file is attached to the draft) the
``[cv]`` marker resolves to plain text ``Currículum`` and the signature
footer omits the CV link — there is no point linking the Drive copy when
the PDF is already attached.
"""

from __future__ import annotations
import re

# Profile/draft.json keys reused across link + footer builders.
_LABELS = ("github", "linkedin", "cv_url", "whatsapp")
_LABEL_TEXT = {"github": "GitHub", "linkedin": "LinkedIn", "cv_url": "CV", "whatsapp": "WhatsApp"}


def _whatsapp_tag(phone: str | None) -> str:
    """Build the WhatsApp anchor from a phone number.

    - None/empty  -> plain text "WhatsApp" (no anchor)
    - starts with "http" -> treat as an existing URL, label "WhatsApp"
    - otherwise -> href https://wa.me/<digits-only>, visible text = the original phone string
    """
    if not phone:
        return "WhatsApp"
    if phone.startswith("http"):
        return f'<a href="{phone}">WhatsApp</a>'
    digits = re.sub(r"\D", "", phone)
    if not digits:
        return "WhatsApp"
    return f'<a href="https://wa.me/{digits}">{phone}</a>'


def format_links(body: str, profile: dict, attach_cv: bool = False) -> str:
    """Replace ``[github]``, ``[linkedin]``, ``[cv]``, ``[whatsapp]`` markers.

    When ``attach_cv=True``, the ``[cv]`` marker becomes plain text
    ``Currículum`` (no anchor) regardless of ``cv_url``.
    """
    for key, marker in (("github", "[github]"), ("linkedin", "[linkedin]"),
                        ("cv_url", "[cv]")):
        url = profile.get(key)
        label = _LABEL_TEXT[key]
        if key == "cv_url" and attach_cv:
            tag = "Currículum"
        else:
            tag = f'<a href="{url}">{label}</a>' if url else label
        body = body.replace(marker, tag)

    whatsapp_tag = _whatsapp_tag(profile.get("whatsapp"))
    body = body.replace("[whatsapp]", whatsapp_tag)
    return body


def footer_link_labels(profile: dict, attach_cv: bool = False) -> list[str]:
    """Return the link labels the signature footer will render for *profile*.

    Contact links belong exclusively to the CLI-managed footer. Callers use this
    list so the drafting model never duplicates them inside the email body.
    """
    link_keys = ("github", "linkedin") if attach_cv else ("github", "linkedin", "cv_url")
    labels = [_LABEL_TEXT[key] for key in link_keys if profile.get(key)]
    if profile.get("whatsapp"):
        labels.append("WhatsApp")
    return labels


def signature_footer(profile: dict, attach_cv: bool = False) -> str:
    """Build the HTML signature block with name and available profile links.

    When ``attach_cv=True`` the CV link is omitted (the real PDF is already
    attached to the draft, so linking the Drive copy adds no value).
    """
    link_keys = ("github", "linkedin") if attach_cv else ("github", "linkedin", "cv_url")
    links = [
        f'<a href="{profile[key]}">{_LABEL_TEXT[key]}</a>'
        for key in link_keys if profile.get(key)
    ]
    if profile.get("whatsapp"):
        links.append(_whatsapp_tag(profile["whatsapp"]))

    name = profile.get("name") or ""
    footer = "<br><br>Saludos cordiales,<br>"
    if name:
        footer += f"{name}<br>"
    if links:
        footer += " | ".join(links)
    return footer
