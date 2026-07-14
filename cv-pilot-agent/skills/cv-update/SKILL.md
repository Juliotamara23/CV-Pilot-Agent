---
name: cv-update
description: Update perfil.md from a new CV PDF without re-running onboarding. Preserves custom fields and never touches correos.md or preferencias.md.
scope: DATA
version: "1.0"
---

# CV Update

## Propósito

Actualizar `data/perfil.md` con información de un nuevo CV PDF **sin re-ejecutar onboarding**. Preserva campos custom del usuario (ej. `pdf_soporte: true`) y NUNCA toca `correos.md` ni `preferencias.md`.

## SRP (Responsabilidad Única)

- **Onboarding**: genera los 3 archivos (`perfil.md`, `correos.md`, `preferencias.md`) desde cero.
- **cv-update**: SOLO actualiza `perfil.md` con datos de un nuevo CV.
- Ambos comparten la interfaz PDF→MD: `pdf_parser.extract()` + `parser.parse_text()`.
- cv-update NUNCA re-ejecuta onboarding ni modifica los otros archivos de data.

## Subcomandos

### `update <pdf_path> [--data-dir <path>]`

Actualiza `perfil.md` con la información extraída de un nuevo CV PDF.

```bash
# Desde la raíz del proyecto (con venv):
.venv/Scripts/python.exe skills/cv-update/scripts/cli.py update path/to/cv.pdf

# Con directorio de datos personalizado:
.venv/Scripts/python.exe skills/cv-update/scripts/cli.py update path/to/cv.pdf --data-dir test/cv-test/_sandbox_p1/data
```

**Salida JSON:**
```json
{
  "ok": true,
  "perfil_path": "data/perfil.md",
  "fields_updated": ["nombre", "experiencia"],
  "fields_preserved": ["linkedin", "github"],
  "fields_added": ["cv_url"]
}
```

## Lógica de Merge

- **Campos del CV** (nombre, resumen, linkedin, github, telefono, correo, cv_url, experiencia, educacion, skills): si el nuevo parse los trae, sobrescribe. Si no, preserva el valor viejo.
- **Campos custom** (cualquiera que NO esté en la lista de campos del CV): preservar siempre. Ejemplo: `pdf_soporte: true` en `preferencias.md`.
- **Secciones custom** en perfil.md (ej. "Proyectos Destacados", "Certificaciones"): preservar siempre.

## Dependencias Reusadas

| Dependencia | Ubicación | Uso |
|---|---|---|
| `pdf_parser.extract()` | `_lib/pdf_parser.py` | Extracción de texto/links del PDF |
| `parser.parse_text()` | `skills/onboarding/scripts/_onboarding_internal/parser.py` | Parsing de campos del CV vía regex |

## Archivos que Toca

- `data/perfil.md` — SOLO este archivo se modifica.

## Archivos que NUNCA Toca

- `data/correos.md` — exclusivo de onboarding.
- `data/preferencias.md` — exclusivo de onboarding. Contiene campos custom del usuario.
