---
name: formatos
description: "CLI `cli.py` — genera reportes de análisis (markdown | json) deterministas. Lectura de DB."
scope: STRUCTURAL_ONLY
version: 4.1
---

# Formatos de Salida

Este skill es un script determinista. El agente NO redacta el reporte — lo genera el CLI.

## CLI: `skills/formatos/scripts/cli.py`

Lectura de `jobs` + `analyses` (vía `_lib.db`) y `data/perfil.json`. Salida a stdout. Para flags, defaults y formatos, ejecuta `cli.py <command> --help`.

- `main --job <hash>`: reporte individual de un job analizado.
- `all`: análisis completo (todos los jobs). Si no hay análisis: imprime "No hay análisis pendientes" y retorna exit 0 (no falla).
- `list`: listado decorado con campos seleccionables (`--fields`, `--limit`, `--status`).

**Regla anti-improvisación:** Cuando el usuario pide "análisis completo", "muéstrame todo el análisis", o variantes, el agente DEBE invocar `formatos all` — NUNCA improvisar el output.

### Synopsis del flujo (AGENTS.md paso 5)

1. El agente pasa el `job_hash` persistido en el paso 5 (luego de `analysis insert`).
2. El CLI genera el reporte — campos ausentes (`salary`, `url`, `public_date`[→ `created_at`]) se degradan con defaults; `None` nunca aparece en el reporte markdown.
3. El agente muestra en el chat la salida del CLI **tal cual** como reporte final.
4. El agente NO añade texto propio al reporte — es output determinista del script.

### Output Contract

- **Reporte completo:** `main --job <hash>` (un job) o `all` (todos). Se imprime **verbatim**.
- **Listados a medida** (p. ej. «5 jobs con título, link, tldr y %»): `list --limit 5 --fields position,url,tldr,percentage`. Los campos válidos y su orden los documenta `list --help`.
- **La decoración es del CLI.** El emote va ligado al CAMPO y lo emite el script: el agente NUNCA escribe emotes, viñetas ni separadores a mano. Si un campo no se pidió, no aparece; si se pidió, sale con su emote.
- **Comparativa:** bullets `- Requisito | Análisis: evaluación` (pipe literal).
- **Cero citas:** ver `rules/integridad.md`.

### Errores (exit 1, envelope JSON a stderr)

`INVALID_FORMAT` (formato inválido), `JOB_NOT_FOUND` y `ANALYSIS_NOT_FOUND` (heredados del CLI de DB).
