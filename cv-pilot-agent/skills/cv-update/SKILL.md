---
name: cv-update
description: Rewrite perfil.json from scratch using a new CV PDF. Each update is a full snapshot — old fields are never preserved. Ensures ATS fidelity.
scope: DATA
version: "3.0"
required_in_flujo: true
---

# CV Update

## Propósito

Reescribir `data/perfil.json` **desde cero** con la información de un nuevo CV PDF. Cada actualización es una **instantánea independiente** — el perfil viejo se descarta completamente. Esto garantiza fidelidad ATS: un ATS real (Workday/Greenhouse/Lever) solo conoce el CV enviado en cada postulación.

**NO es un merge.** Mezclar info de CVs distintos genera evaluaciones infladas para RRHH.

## SRP (Responsabilidad Única)

- **Onboarding**: genera los 3 archivos (`perfil.json`, `correos.md`, `preferencias.json`) desde cero.
- **cv-update**: SOLO reescribe `perfil.json` con datos de un nuevo CV. Nunca consulta el perfil viejo.
- Ambos comparten la interfaz PDF→texto: `pdf_parser.extract()`.
- cv-update NUNCA re-ejecuta onboarding ni modifica los otros archivos de data.

## Flujo en dos pasos

cv-update usa un flujo **extract → agente → apply**. El script maneja operaciones deterministas (PDF→texto, VSI, JSON I/O). El agente (Hermes / orquestador CV-Pilot) maneja la extracción inteligente de campos usando su propio LLM.

### Paso 1: `extract <pdf_path>`

Extrae texto del PDF y valida la identidad semántica (VSI).

```bash
# Desde la raíz del proyecto (con venv):
.venv/bin/python skills/cv-update/scripts/cli.py extract <pdf_path>
```

**Salida JSON:**
```json
{
  "ok": true,
  "step": "extract",
  "text": "<raw CV text>",
  "vsi": {
    "secciones_detectadas": ["experiencia", "educacion", "skills"],
    "confianza": 0.85
  },
  "prompt": "<LLM extraction prompt>",
  "canonical_fields": ["nombre", "correo", "telefono", "linkedin", "github", "cv_url", "resumen", "experiencia", "educacion", "skills"],
  "source_pdf": "path/to/cv.pdf"
}
```

Si la VSI rechaza el PDF:
```json
{
  "ok": false,
  "step": "vsi",
  "error": "VSI_REJECTED",
  "razon_rechazo": "documento_no_cv",
  "mensaje": "Este documento no es un perfil profesional válido. Comparte un CV real."
}
```

### Paso 2: El agente extrae los campos

El agente (Hermes) toma el `prompt` de la salida del paso 1, lo envía a su LLM, y guarda la respuesta JSON en un archivo temporal (ej. `temp/fields.json`). La respuesta del LLM debe ser un objeto JSON con los campos canónicos.

### Paso 3: `apply <fields.json> [--data-dir <path>]`

Aplica los campos extraídos por el agente y reconstruye `perfil.json`.

```bash
.venv/bin/python skills/cv-update/scripts/cli.py apply <fields.json> [--data-dir <path>]
```

El archivo `fields.json` puede contener:
- La respuesta cruda del LLM (con o sin markdown code blocks) — el script la parsea automáticamente.
- Un diccionario JSON ya parseado con los campos canónicos.

**Salida JSON:**
```json
{
  "ok": true,
  "step": "apply",
  "perfil_path": "data/perfil.json",
  "campos_extraidos": ["nombre", "resumen", "linkedin", "github", "telefono", "correo", "experiencia", "educacion", "skills"],
  "campos_no_encontrados": ["cv_url"],
  "fuente": "path/to/cv.pdf",
  "timestamp": "2026-07-28T15:30:00Z"
}
```

## Ejemplo completo (flujo del agente)

```bash
# 1. Extraer texto + prompt
result=$(venv/bin/python skills/cv-update/scripts/cli.py extract cv.pdf)
text=$(echo "$result" | jq -r '.text')
prompt=$(echo "$result" | jq -r '.prompt')

# 2. El agente envía el prompt a su LLM y guarda la respuesta
# (esto lo hace Hermes internamente, no es un comando bash)
echo "$llm_response" > temp/fields.json

# 3. Aplicar los campos extraídos
.venv/bin/python skills/cv-update/scripts/cli.py apply temp/fields.json --data-dir data/
```

## Contrato de Reescritura

- `perfil.json` se genera **desde cero** con los campos del CV nuevo.
- **NO se consulta** el perfil viejo en ningún momento.
- Campos canónicos no encontrados aparecen como `null`.
- Secciones no canónicas del CV (ej. "Certificaciones", "Proyectos") van en `extras`.
- El frontmatter incluye `fuente` (path al PDF) y `generated_at` (timestamp ISO-8601).

## Dependencias Reusadas

| Dependencia | Ubicación | Uso |
|---|---|---|
| `pdf_parser.extract()` | `_lib/pdf_parser.py` | Extracción de texto/links del PDF |
| `llm_extract.build_extraction_prompt()` | `_lib/llm_extract.py` | Construcción del prompt para el agente |
| `llm_extract.parse_llm_fields()` | `_lib/llm_extract.py` | Parseo y validación de respuesta LLM |
| `_cv_update_internal/reconstructor.py` | `skills/cv-update/scripts/` | Reconstrucción de perfil.json (Pydantic) |

## Archivos que Toca

- `data/perfil.json` — SOLO este archivo se modifica.

## Archivos que NUNCA Toca

- `data/correos.md` — exclusivo de onboarding.
- `data/preferencias.json` — exclusivo de onboarding.
