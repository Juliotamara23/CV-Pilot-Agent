"""Relevance labeling for CV-Pilot job search results.

Labels each job as high/medium/low relevance based on token overlap
with the search position.  The script NEVER discards results: relevance
is a label, not a filter.
"""

from __future__ import annotations

import re

# Single-word positions that tend to yield noisy, low-relevance results.
GENERIC_POSITIONS: set[str] = {
    "developer", "desarrollador", "ingeniero", "engineer", "trabajo",
    "designer", "diseñador", "programador", "programmer", "analista", "analyst",
}

_TOKEN_RE = re.compile(r"[a-z0-9áéíóúñ]+")


def tokens(text: str) -> list[str]:
    """Extract lowercase word tokens from text."""
    return _TOKEN_RE.findall((text or "").lower())


def label_relevance(jobs: list, position: str) -> dict[str, int]:
    """Label each job by relevance and return counts ``{high, medium, low}``."""
    pos_tokens = set(tokens(position))
    counts = {"high": 0, "medium": 0, "low": 0}
    for job in jobs:
        title_tokens = set(tokens(job.position))
        if not pos_tokens:
            counts["low"] += 1
        elif pos_tokens.issubset(title_tokens):
            counts["high"] += 1
        elif title_tokens & pos_tokens:
            counts["medium"] += 1
        else:
            counts["low"] += 1
    return counts
