---
name: cv-update
description: Rewrite perfil.md from scratch using a new CV PDF. Each update is a full snapshot — old fields are never preserved. Ensures ATS fidelity.
scope: DATA
version: "2.0"
---

# CV Update

## Propósito

Reescribir `data/perfil.md` **desde cero** con la información de un nuevo CV PDF. Cada actualización es una **instantánea independiente** — el perfil viejo se descarta completamente. Esto garantiza fidelidad ATS: un ATS real (Workday/Greenhouse/Lever) solo conoce el CV enviado en cada postulación.

**NO es un merge.** Mezclar info de CVs distintos genera evaluaciones infladas para RRHH.

## SRP (Responsabilidad Única)

- **Onboarding**: genera los 3 archivos (`perfil.md`, `correos.md`, `preferencias.md`) desde cero.
- **cv-update**: SOLO reescribe `perfil.md` con datos de un nuevo CV. Nunca consulta el perfil viejo.
- Ambos comparten la interfaz PDF→MD: `pdf_parser.extract()` + `parser.parse_text()`.
- cv-update NUNCA re-ejecuta onboarding ni modifica los otros archivos de data.

## Subcomandos

### `<pdf_path> [--data-dir <path>]`

Reescribe `perfil.md` con la información extraída de un nuevo CV PDF.

```bash
# Desde la raíz del proyecto (con venv):
.venv/Scripts/python.exe skills/cv-update/scripts/cli.py <pdf_path>

# Con directorio de datos personalizado:
.venv/Scripts/python.exe skills/cv-update/scripts/cli.py --data-dir test/cv-test/_sandbox_p0/data <pdf_path>
```

**Salida JSON:**
```json
{
  "ok": true,
  "perfil_path": "data/perfil.md",
  "campos_extraidos": ["nombre", "resumen", "linkedin", "github", "telefono", "correo", "experiencia", "educacion", "skills"],
  "campos_no_encontrados": ["cv_url"],
  "fuente": "path/to/cv.pdf",
  "timestamp": "2026-07-14T15:30:00Z"
}
```

## Contrato de Reescritura

- `perfil.md` se genera **desde cero** con los campos del CV nuevo.
- **NO se consulta** el perfil viejo en ningún momento.
- Campos canónicos no encontrados en el CV aparecen con placeholder `_(no detectado)_`.
- Secciones no canónicas del CV (ej. "Certificaciones", "Proyectos") van en `## Extras`.
- El frontmatter incluye `source` (path al PDF) y `generated` (timestamp ISO-8601).

## Dependencias Reusadas

| Dependencia | Ubicación | Uso |
|---|---|---|
| `pdf_parser.extract()` | `_lib/pdf_parser.py` | Extracción de texto/links del PDF |
| `parser.parse_text()` | `skills/onboarding/scripts/_onboarding_internal/parser.py` | Parsing de campos del CV vía regex |

## Archivos que Toca

- `data/perfil.md` — SOLO este archivo se modifica.

## Archivos que NUNCA Toca

- `data/correos.md` — exclusivo de onboarding.
- `data/preferencias.md` — exclusivo de onboarding.
