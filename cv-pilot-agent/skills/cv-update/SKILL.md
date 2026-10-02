---
name: cv-update
description: "Rewrite perfil.json from scratch using a new CV PDF. Each update is a full snapshot — old fields are never preserved. Ensures ATS fidelity."
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

El script hace lo determinista (PDF→texto, VSI, JSON I/O); el agente hace la extracción inteligente de campos con su LLM. Flags, argumentos y envelope exactos: `cli.py <command> --help`.

| Paso | Quién | Comando | Efecto |
| --- | --- | --- | --- |
| 1 | script | `extract <pdf_path>` | Texto del PDF + VSI + `prompt` → `{text, vsi, prompt, ...}`. Si la VSI rechaza: `ok:false`, `VSI_REJECTED` — no continuar |
| 2 | agente | — | Envía el `prompt` a su LLM y guarda la respuesta JSON en un archivo temporal |
| 3 | script | `apply <fields.json> [--data-dir <path>]` | Reconstruye `perfil.json`. Campos canónicos ausentes → `null`; secciones no canónicas del CV (ej. "Certificaciones") → `extras`; agrega `fuente` y `timestamp` (ISO-8601) |

## Contrato de Reescritura

- `perfil.json` se genera **desde cero** con los campos del CV nuevo.
- **NO se consulta** el perfil viejo en ningún momento.
- Campos canónicos: `nombre`, `correo`, `telefono`, `linkedin`, `github`, `cv_url`, `resumen`, `experiencia`, `educacion`, `skills`.

## Contrato de archivos

- Toca SOLO `data/perfil.json`.
- NUNCA toca `data/correos.md` ni `data/preferencias.json` (exclusivos de onboarding).
