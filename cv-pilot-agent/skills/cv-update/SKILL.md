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

## Flujo: extract → agente → apply

El script maneja operaciones deterministas (PDF→texto, VSI, JSON I/O). El agente (Hermes) maneja la extracción inteligente de campos con su propio LLM. Para flags, argumentos y envelope de salida exacto de cada paso, ejecuta `cli.py <command> --help`.

1. `extract <pdf_path>`: extrae texto del PDF, valida la identidad semántica (VSI) y devuelve `{text, vsi, prompt, ...}`. Si la VSI rechaza el PDF, devuelve `ok:false` con `error:"VSI_REJECTED"` y no continúes.
2. El agente envía el `prompt` de la salida a su LLM y guarda la respuesta JSON (raw o ya parseada) en un archivo temporal.
3. `apply <fields.json> [--data-dir <path>]`: aplica los campos extraídos y reconstruye `perfil.json`. Los campos canónicos no encontrados quedan en `null`; las secciones no canónicas del CV (ej. "Certificaciones") van en `extras`; el resultado incluye `fuente` y `timestamp` (ISO-8601).

## Contrato de Reescritura

- `perfil.json` se genera **desde cero** con los campos del CV nuevo.
- **NO se consulta** el perfil viejo en ningún momento.
- Campos canónicos: `nombre`, `correo`, `telefono`, `linkedin`, `github`, `cv_url`, `resumen`, `experiencia`, `educacion`, `skills`.

## Contrato de archivos

- Toca SOLO `data/perfil.json`.
- NUNCA toca `data/correos.md` ni `data/preferencias.json` (exclusivos de onboarding).
