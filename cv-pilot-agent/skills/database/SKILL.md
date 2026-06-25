---
name: Skill Database Manager
description: Persistencia y deduplicación de vacantes mediante el CLI query.py (SQLite).
scope: GLOBAL
---

# Skill: Database Manager

Toda interacción con la base de datos se realiza mediante un único CLI Python
determinista. **No generar SQL ad-hoc.**

## 1. Ubicación de la DB
`cv-pilot-agent/db/cv-pilot.db` (creada por `cv-pilot-agent/scripts/init.py`).

## 2. Invocación del CLI
```
python cv-pilot-agent/skills/database/scripts/query.py <app> <command> [options]
```
`app` ∈ `job`, `analysis`, `status`. Cada comando imprime un envelope JSON a
stdout: `{"ok": true, ...}` en éxito, y `{"ok": false, "error": "...", "code": "..."}`
a stderr con salida non-zero en error.

## 3. Comandos

| Comando | Propósito |
|--------|-----------|
| `job insert` | Insertar/refresh de una vacante (dedup por SHA256 de company+position+location). |
| `job insert-batch --file path.json` | Insertar un array JSON de vacantes. |
| `job list [--status S] [--limit N]` | Listar vacantes (default limit 10). |
| `job get --hash H` | Obtener una vacante por hash. |
| `job delete --status S \| --hash H [--dry-run]` | Borrar; `--dry-run` solo previewea. |
| `analysis insert --job-hash H --percentage ... --comparativa ... --observaciones ... --verdict ... --tldr ...` | Inserta análisis y marca `status='analyzed'`. |
| `analysis get --job-hash H` | Recupera el análisis de una vacante. |
| `status set --hash H --status S` | Actualiza el estado de una vacante. |

## 4. Estados (enum cerrado)
`new`, `analyzed`, `discarded`, `applied`, `rejected`. El CLI valida; lanzar
`INVALID_STATUS` si se pasa un valor fuera del enum.

## 5. Deduplicación / Refresh
- Hash ausente → insert (`is_new=true`).
- Hash presente y `public_date` entrante **estrictamente mayor** → borrar análisis
  previo, resetear `status='new'`, actualizar `public_date`/`url`/`salary`/`description` (`refreshed=true`).
- Caso contrario → no-op (`is_duplicate=true`).

## 6. Borrado y FK
`delete_jobs` borra primero las `analyses` referenciadas y luego los `jobs` en
una misma transacción (no hay `ON DELETE CASCADE`).

## 7. Reglas operativas
- **Silencio operativo:** no mostrar SQL; solo reportar éxito/fallo en lenguaje natural.
- **Atomicidad:** el CLI maneja transacciones; cerrar conexiones tras cada comando.