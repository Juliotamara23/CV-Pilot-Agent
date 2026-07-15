---
name: Database Manager
description: CLI query.py para CRUD de vacantes y análisis (SQLite).
scope: GLOBAL
---

# query.py CLI

No generar SQL. Usar este CLI.

## Comandos

| App | Comando | Flags |
|---|---|---|
| `job` | `insert` | `--company --position --location [--url --source --public-date ...]` |
| | `insert-batch` | `--file jobs.json` |
| | `list` | `[--status S] [--limit N]` |
| | `get` | `--hash H` |
| | `delete` | `--hash H \| --status S [--dry-run]` |
| `analysis` | `insert` | `--job-hash H --percentage N --comparativa ... --observaciones ... --verdict ... --tldr ... [--contact-method email\|portal]` |
| | `get` | `--job-hash H` |
| `status` | `set` | `--hash H --status S` |

Output: JSON `{"ok":bool,...}` a stdout. Errores a stderr con `{"ok":false,"error":"...","code":"..."}`.

## Estados

`new` | `analyzed` | `discarded` | `applied` | `rejected`

## Dedup

SHA256(company+position+location). Hash nuevo→insert. Hash existe+fecha más nueva→refresh (borra análisis, resetea a `new`). Hash existe+fecha igual→ignora.

## FK

Borrar jobs borra sus analyses en la misma transacción. Cero intervención manual.
