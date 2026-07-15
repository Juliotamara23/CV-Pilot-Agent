"""Default email subject builder for CV-Pilot."""

from __future__ import annotations


def default_subject(prefix: str, job: dict) -> str:
    """Build a default email subject from a prefix and job fields.

    Format: ``"{prefix}: {position} — {company}"``
    """
    position = (job.get("position") or "").strip()
    company = (job.get("company") or "").strip()
    suffix = f"{position} — {company}"
    return f"{prefix}: {suffix}".strip(" —")
