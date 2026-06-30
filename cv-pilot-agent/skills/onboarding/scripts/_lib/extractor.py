"""Text extraction for CV-Pilot onboarding.

Reads CV text from a file, stdin, or a PDF (delegating to ``pdf_parser``).
"""

from __future__ import annotations

import sys
from pathlib import Path


def _is_pdf(path: Path) -> bool:
    return path.suffix.lower() == ".pdf"


def read_text(source: Path, extra_links: list[str]) -> tuple[str, list[str]]:
    """Return (text, links) from a text file, stdin (``-``), or a PDF.

    For PDFs, delegates to ``pdf_parser.extract``. ``extra_links`` are merged
    into the returned link list (deduplicated, order preserved).
    """
    if str(source) == "-":
        text = sys.stdin.read()
        links: list[str] = []
    elif _is_pdf(source):
        from pdf_parser import extract as extract_pdf
        result = extract_pdf(str(source))
        if not result.get("ok"):
            raise RuntimeError(result.get("error", "PDF extraction failed"))
        text = result.get("text", "")
        links = list(result.get("links", []))
    else:
        text = source.read_text(encoding="utf-8")
        links = []

    merged: list[str] = []
    seen: set[str] = set()
    for link in list(links) + list(extra_links):
        if link and link not in seen:
            seen.add(link)
            merged.append(link)
    return text, merged
