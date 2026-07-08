"""Extract text and links from a PDF using PyMuPDF (fitz).

Usage:
    # With venv (recommended), Windows:
    cv-pilot-agent\\.venv\\Scripts\\python.exe pdf_parser.py <path_to_pdf>
    # With venv (recommended), Unix:
    cv-pilot-agent/.venv/bin/python pdf_parser.py <path_to_pdf>
    # Without venv (fallback), Windows:
    python pdf_parser.py <path_to_pdf>
    # Without venv (fallback), Unix:
    python3 pdf_parser.py <path_to_pdf>

Output (JSON to stdout):
    {
        "text": "<full text>",
        "links": ["https://...", "https://..."],
        "ok": true
    }

If extraction fails or the PDF contains no text, returns ok=false so the
onboarding flow can offer the manual path (paste text/links).
"""

import json
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


def extract(pdf_path: str) -> dict:
    """Extract text and links from a PDF.

    Returns a dict with:
        text:  full PDF text (str)
        links: list of URLs (list[str])
        ok:    True if text was extracted, False if failed or empty
    """
    if fitz is None:
        return {"text": "", "links": [], "ok": False,
                "error": "PyMuPDF no instalado. Ejecute el script de setup "
                         "(scripts/setup.ps1 o scripts/setup.sh) para crear el venv, "
                         "o manualmente: pip install pymupdf"}

    path = Path(pdf_path)
    if not path.exists() or not path.is_file():
        return {"text": "", "links": [], "ok": False,
                "error": f"Archivo no encontrado: {pdf_path}"}

    try:
        doc = fitz.open(path)
    except Exception as exc:  # Corrupted or unsupported PDF
        return {"text": "", "links": [], "ok": False,
                "error": f"No se pudo abrir el PDF: {exc}"}

    text_parts = []
    links = []
    seen = set()

    try:
        for page in doc:
            text_parts.append(page.get_text())
            for link in page.get_links():
                uri = link.get("uri")
                if uri and uri not in seen:
                    seen.add(uri)
                    links.append(uri)
    finally:
        doc.close()

    full_text = "\n".join(text_parts).strip()
    ok = bool(full_text)
    return {"text": full_text, "links": links, "ok": ok}


def main(argv: list) -> int:
    if len(argv) != 2:
        print(json.dumps({"text": "", "links": [], "ok": False,
                          "error": "Uso: python pdf_parser.py <ruta_al_pdf>"},
                         ensure_ascii=False))
        return 1

    result = extract(argv[1])
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
