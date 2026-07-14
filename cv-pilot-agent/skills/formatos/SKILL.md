---
name: Skill Formatos
description: CLI `cli.py` — genera reportes de análisis (markdown | json) deterministas. Lectura de DB.
scope: STRUCTURAL_ONLY
version: 4.1
---

# Formatos de Salida

Este skill es ahora un script determinista. El agente NO redacta el reporte — lo genera el CLI.

## CLI: `skills/formatos/scripts/cli.py`

Lectura de `jobs` + `analyses` (vía `_lib.db`) y `data/perfil.md`. Salida a stdout.

### Comando `main` — reporte individual

```
python skills/formatos/scripts/cli.py main --job <hash> [--format markdown|json]
```

- `--job <hash>` (obligatorio): SHA256 del trabajo analizado (tabla `jobs`).
- `--format` (opcional): `markdown` (default, legible) o `json` (programático).

### Comando `all` — análisis completo (todos los jobs)

```
python skills/formatos/scripts/cli.py all [--format markdown|json] [--status analyzed] [--limit 50]
```

- `--format` (opcional): `markdown` (default) o `json`.
- `--status` (opcional): filtra por status de job (default: `analyzed`).
- `--limit` (opcional): máximo de jobs a retornar (default: 50).
- Si no hay análisis: imprime "No hay análisis pendientes" y retorna exit 0 (no falla).
- En formato markdown: concatena todos los reportes con separadores `---`.
- En formato JSON: retorna `{ok, count, reports: [{job_hash, report}, ...]}`.

**Regla anti-improvisación:** Cuando el usuario pide "análisis completo", "muéstrame todos los análisis", o variantes, el agente DEBE invocar `formatos all` — NUNCA improvisar el output.

### Synopsis del flujo (AGENTS.md paso 5)

1. El agente pasa el `job_hash` persistido en el paso 5 (luego de `analysis insert`).
2. El CLI genera el reporte — campos ausentes (`salary`, `url`, `public_date`[→ `created_at`]) se degradan con defaults; `None` nunca aparece en el reporte markdown.
3. El agente muestra la salida del CLI al usuario como reporte final.
4. El agente NO añade texto propio al reporte — es output determinista del script.

### Salida markdown — secciones (en orden)

`ID · Fecha · Fuente · Empresa/Cargo · Localidad · Porcentaje · Comparativa Técnica · Observaciones y Riesgos · Veredicto · TL;DR`

- **Fuente:** campo `url` de `jobs`; si falta → `Origen: Texto manual`.
- **Comparativa:** bullets `- Requisito | Análisis: evaluación` (pipe literal).
- **Cero citas:** ver `rules/integridad.md`.

### Errores (exit 1, envelope JSON a stderr)

| code | causa |
|------|-------|
| `INVALID_FORMAT` | `--format` no es `markdown`/`json` |
| `JOB_NOT_FOUND` (heredado) | `--job` no existe en `jobs` |
| `ANALYSIS_NOT_FOUND` (heredado) | el job no tiene análisis asociado |

## Scripts de Respaldo
- `skills/formatos/scripts/cli.py` — generador de reportes.