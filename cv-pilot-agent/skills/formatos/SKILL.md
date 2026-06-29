---
name: Skill Formatos
description: CLI `format_report.py` — genera reportes de análisis (markdown | json) deterministas. Lectura de DB.
scope: STRUCTURAL_ONLY
version: 4.0
---

# Formatos de Salida

Este skill es ahora un script determinista. El agente NO redacta el reporte — lo genera el CLI.

## CLI: `skills/formatos/scripts/format_report.py`

Lectura de `jobs` + `analyses` (vía `_lib.db`) y `data/perfil.md`. Salida a stdout.

### Uso

```
python skills/formatos/scripts/format_report.py --job <hash> [--format markdown|json]
```

- `--job <hash>` (obligatorio): SHA256 del trabajo analizado (tabla `jobs`).
- `--format` (opcional): `markdown` (default, legible) o `json` (programático).

### Synopsis del flujo (AGENTS.md paso 4d)

1. El agente pasa el `job_hash` persistido en el paso 4c.
2. El CLI genera el reporte — campos ausentes (`salary`, `url`, `public_date`[→ `created_at`]) se degradan con defaults; `None` nunca aparece en el reporte markdown.
3. El agente muestra la salida del CLI al usuario como reporte final.
4. El agente NO añade texto propio al reporte — es output determinista del script.

### Salida markdown — secciones (en orden)

`ID · Fecha · Fuente · Empresa/Cargo · Localidad · Porcentaje · Comparativa Técnica · Observaciones y Riesgos · Veredicto · TL;DR · (links perfil HTML)`

- **Fuente:** campo `url` de `jobs`; si falta → `Origen: Texto manual`.
- **Comparativa:** bullets `- Requisito | Análisis: evaluación` (pipe literal).
- **Links perfil:** si `data/perfil.md` trae CV/LinkedIn/GitHub, se añaden como `<a href="...">texto</a>` al final del reporte.
- **Cero citas:** ver `rules/integridad.md`.

### Errores (exit 1, envelope JSON a stderr)

| code | causa |
|------|-------|
| `INVALID_FORMAT` | `--format` no es `markdown`/`json` |
| `JOB_NOT_FOUND` (heredado) | `--job` no existe en `jobs` |
| `ANALYSIS_NOT_FOUND` (heredado) | el job no tiene análisis asociado |

## Scripts de Respaldo
- `skills/formatos/scripts/format_report.py` — generador de reportes (este skill). Reemplaza el template prompt-based previo (respaldo en `SKILL.md.bak`).