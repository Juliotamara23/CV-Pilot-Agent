---
name: Database Manager
description: CLI query.py para CRUD de vacantes y análisis (SQLite).
scope: GLOBAL
---

# query.py CLI

El agente NUNCA escribe SQL directo a la DB. Para analytics/agregaciones (GROUP BY, JOINs, conteos) puede generar SQL de LECTURA (SELECT/WITH) y ejecutarlo SOLO vía `query.py query` (modo read-only validado). Escrituras (job/analysis/status) únicamente por comandos nativos de este CLI. SQL crudo fuera de este CLI: prohibido.

## Comandos

| App | Comando | Flags |
| --- | --- | --- |
| `job` | `insert` | `--company --position --location [--url --source --public-date ...]` |
| | `insert-batch` | `--file jobs.json` |
| | `list` | `[--status S] [--limit N]` |
| | `get` | `--hash H` |
| | `update` | `--hash H [--public-date --url --salary --description --external-id --source]` |
| | `delete` | `--hash H \| --status S [--dry-run]` |
| `analysis` | `insert` | `--job-hash H --percentage N --comparativa ... --observaciones ... --verdict ... --tldr ... [--contact-method email\|portal]` |
| | `get` | `--job-hash H` |
| | `update` | `--job-hash H \| --analysis-id ID [--percentage --comparativa --observaciones --verdict --tldr --contact-method]` |
| | `delete` | `--job-hash H \| --analysis-id ID` |
| `status` | `set` | `--hash H --status S` |

    | `query` | `(callback)` | `<sql> [--limit N]` |

## query — Arbitrary read-only SQL

    Uso: `query.py query "<sql>" [--limit N]`

    * Solo `SELECT` (o `WITH ... SELECT`) — primera palabra clave validada case-insensitive.
    * Conexión SQLite en modo `mode=ro` (URI) — escrituras fallan nativamente en el motor.
    * Una sola sentencia por `execute()` — driver Python `sqlite3` rechaza multi-statement.
    * `--limit` (default 100) aplica cap en Python tras fetch.
    * Celdas no-JSON (bytes/memoryview) → UTF-8 con replacement.
    * Códigos de error: `QUERY_INVALID_SQL`, `QUERY_WRITE_NOT_ALLOWED`, `DATABASE_ERROR`.

## Estados

`new` | `analyzed` | `discarded` | `applied` | `rejected`

## Dedup

SHA256(company+position+location). Hash nuevo→insert. Hash existe+fecha más nueva→refresh (borra análisis, resetea a `new`). Hash existe+fecha igual→ignora.

## Reevaluación de análisis

Para corregir un análisis existente (veredicto/porcentaje/observaciones) usar `analysis update --job-hash H`, NUNCA `analysis insert` repetido (duplica filas). `analysis update --job-hash` afecta la fila más reciente; `--analysis-id` apunta a una fila concreta. `job update` solo toca campos no-identidad (`public_date/url/salary/description/external_id/source`) y no altera analyses ni status.

## FK

Borrar jobs borra sus analyses en la misma transacción. Cero intervención manual.
