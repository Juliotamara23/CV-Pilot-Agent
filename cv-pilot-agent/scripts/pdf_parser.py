"""Extracción de texto y enlaces desde un PDF usando PyMuPDF (fitz).

Uso:
    # Con venv (recomendado), Windows:
    cv-pilot-agent\\.venv\\Scripts\\python.exe pdf_parser.py <ruta_al_pdf>
    # Con venv (recomendado), Unix:
    cv-pilot-agent/.venv/bin/python pdf_parser.py <ruta_al_pdf>
    # Sin venv (fallback), Windows:
    python pdf_parser.py <ruta_al_pdf>
    # Sin venv (fallback), Unix:
    python3 pdf_parser.py <ruta_al_pdf>

Salida (JSON a stdout):
    {
        "text": "<texto completo>",
        "links": ["https://...", "https://..."],
        "ok": true
    }

Si la extracción falla o el PDF no contiene texto, devuelve ok=false para que
el flujo de onboarding ofrezca el camino manual (pegar texto/enlaces).
"""

import json
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


def extract(pdf_path: str) -> dict:
    """Extrae texto y enlaces de un PDF.

    Devuelve un dict con:
        text:  texto completo del PDF (str)
        links: lista de URLs (list[str])
        ok:    True si se extrajo texto, False si falló o vacío
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
    except Exception as exc:  # PDF corrupto o no soportado
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
