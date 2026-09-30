---
name: database
description: "CLI query.py para CRUD de vacantes y análisis (SQLite)."
scope: GLOBAL
---

# query.py CLI

El agente NUNCA escribe SQL directo a la DB (ni a la URI en modo escritura). Para analytics/agregaciones (GROUP BY, JOINs, conteos) puede generar SQL de LECTURA (SELECT/WITH) y ejecutarlo SOLO vía `query.py query` (modo read-only, `mode=ro` validado a nivel motor). Escrituras (job/analysis/status) únicamente por comandos nativos de este CLI. SQL crudo fuera de este CLI: prohibido.

## Comando `query` — SQL de solo lectura

Uso: `query.py query "<sql>" [--limit N]` (default 100).

- Solo `SELECT` (o `WITH ... SELECT`) — primera palabra clave validada case-insensitive.
- Conexión SQLite `mode=ro`; una sola sentencia por `execute()`.
- Códigos de error: `QUERY_INVALID_SQL`, `QUERY_WRITE_NOT_ALLOWED`, `DATABASE_ERROR`.

Para el resto de comandos (`job`, `analysis`, `status` con sus subcomandos y flags) ejecuta `query.py <app> --help` o `query.py <app> <cmd> --help`; la ayuda documenta cada flag con su default.

## Estados

`new` | `analyzed` | `discarded` | `applied` | `rejected`

## Dedup

SHA256(company+position+location). Hash nuevo→insert. Hash existe+fecha más nueva→refresh (borra análisis, resetea a `new`). Hash existe+fecha igual→ignora. Los campos identidad (`company`, `position`, `location`) NUNCA se actualizan; `job update` solo toca campos no-identidad y no altera analyses ni status.

## Reevaluación de análisis

Para corregir un análisis existente (veredicto/porcentaje/observaciones) usar `analysis update --job-hash H`, NUNCA `analysis insert` repetido (duplica filas). `analysis update --job-hash` afecta la fila más reciente; `--analysis-id` apunta a una fila concreta.

## FK

Borrar jobs borra sus analyses en la misma transacción. Cero intervención manual.
