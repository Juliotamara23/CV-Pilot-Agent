---
name: Skill Apify Scraper
description: Scraping multi-plataforma de vacantes vía el CLI `cli.py`.
scope: SOURCING_PHASE
version: 3.0
---

# Skill: Apify Scraper (CLI `cli.py`)

Documentación del CLI `skills/apify/scripts/cli.py`. Adaptadores: `skills/apify/scripts/platforms/` (Indeed, LinkedIn, Computrabajo).

## Comando `search`

```bash
python skills/apify/scripts/cli.py search \
  --platform {indeed|linkedin|computrabajo} \
  --position "React Developer" \
  --location "Medellín" \
  --country CO \
  --count 5 \
  [--workplace onsite|remote|hybrid]   # solo LinkedIn
  [--experience entry|mid|senior]      # solo LinkedIn
  [--confirm]
```

| Flag | Requerido | Default | Descripción |
|---|---|---|---|
| `--platform` | Sí | — | `indeed`, `linkedin` o `computrabajo` |
| `--position` | Sí | — | Título del cargo (evitar palabras genéricas como "developer") |
| `--location` | Sí | — | Ciudad o `Remote` |
| `--country` | No | `CO` | Código de país (CO, AR, MX, PE, CL) |
| `--count` | No | `5` | Máximo de resultados (1–100). LinkedIn exige mínimo 10 |
| `--workplace` | No | — | `onsite`, `remote`, `hybrid` (solo LinkedIn) |
| `--experience` | No | — | `entry`, `mid`, `senior` (solo LinkedIn) |
| `--confirm` | No | `false` | Sin flag: solo reporta costo. Con flag: ejecuta el actor |

## Dos fases (cost wizard)

1. **Sin `--confirm`** — NO llama al actor. Devuelve el costo real en USD:
   ```json
   {"ok": true, "phase": "cost", "actor": "...", "platform": "linkedin",
    "count": 5, "cost_usd": 0.005, "position": "...", "location": "..."}
   ```
2. **Con `--confirm`** — ejecuta el actor, normaliza vía el adapter, etiqueta
   cada resultado `high|medium|low` (NO descarta nada) y persiste TODO vía
   `query.py job insert-batch --file <tmp>`:
   ```json
   {"ok": true, "phase": "done", "platform": "linkedin", "count": 3,
    "cost_usd": 0.005, "relevance": {"high": 2, "medium": 1, "low": 0},
    "persisted": {"ok": true, "inserted": 3, "duplicates": 0}}
   ```

## Comandos de dataset (recuperación)

Estos tres comandos permiten recuperar datos de runs interrumpidos o inspeccionar datasets sin re-ejecutar el actor.

### `datasets-list`

Lista runs recientes de un actor. Sirve para encontrar el `dataset_id` de un run pasado.

```bash
python skills/apify/scripts/cli.py datasets-list \
  --actor <actor-full-name> \
  [--since-minutes 60] \
  [--limit 10]
```

| Flag | Requerido | Default | Descripción |
|---|---|---|---|
| `--actor` | Sí | — | Nombre completo del actor (ej. `curious_coder/linkedin-jobs-scraper`) |
| `--since-minutes` | No | `60` | Solo mostrar runs de los últimos N minutos |
| `--limit` | No | `10` | Máximo de runs a listar |

**Envelope de salida:**
```json
{
  "ok": true,
  "actor": "curious_coder/linkedin-jobs-scraper",
  "since_minutes": 60,
  "count": 2,
  "runs": [
    {
      "run_id": "abc123",
      "dataset_id": "def456",
      "items_count": 15,
      "started_at": "2026-07-08T10:00:00Z",
      "finished_at": "2026-07-08T10:01:30Z",
      "elapsed_seconds": 90.0,
      "status": "SUCCEEDED",
      "usage_total_usd": 0.005
    }
  ]
}
```

**Casos borde:**
- Sin runs recientes → `count: 0`, `runs: []`, exit cero.
- Actor inválido o sin permisos → error `APIFY_RUNS_LS_FAILED`, exit no-cero.

### `datasets-inspect`

Inspeciona un dataset: cuenta items y muestra las claves del schema. Útil para verificar cuántos items tiene antes de hacer fetch.

```bash
python skills/apify/scripts/cli.py datasets-inspect \
  --dataset-id <apify-dataset-id>
```

| Flag | Requerido | Default | Descripción |
|---|---|---|---|
| `--dataset-id` | Sí | — | ID del dataset de Apify |

**Envelope de salida:**
```json
{
  "ok": true,
  "dataset_id": "def456",
  "items_count": 15,
  "schema_keys": ["companyName", "positionName", "location", "link", ...],
  "sample_item_preview": {"companyName": "Acme Corp", "positionName": "React Dev..."}
}
```

**Casos borde:**
- Dataset vacío → `items_count: 0`, `schema_keys: []`, `sample_item_preview: null`.
- Dataset inexistente → error de Apify CLI, exit no-cero.

### `datasets-fetch`

Trae items de un dataset y persiste los que no están ya en la DB (idempotente, no duplica). Sirve para recuperar runs interrumpidos.

```bash
python skills/apify/scripts/cli.py datasets-fetch \
  --dataset-id <apify-dataset-id> \
  [--persist|--no-persist]
```

| Flag | Requerido | Default | Descripción |
|---|---|---|---|
| `--dataset-id` | Sí | — | ID del dataset de Apify |
| `--persist` / `--no-persist` | No | `--persist` | Con `--persist`: inserta items nuevos en DB. Con `--no-persist`: solo retorna sin guardar |

**Envelope de salida:**
```json
{
  "ok": true,
  "dataset_id": "def456",
  "fetched": 15,
  "new": 3,
  "duplicates": 12,
  "validation_failures": [],
  "persisted": {"ok": true, "inserted": 3, "duplicates": 0},
  "cost_usd": null
}
```

**Casos borde:**
- Todos duplicados → `new: 0`, `persisted: null` (no hay nada que insertar).
- Items con campos faltantes → aparecen en `validation_failures` con índice y error; no bloquean los válidos.
- Dataset vacío → `fetched: 0`, `new: 0`, exit cero.

## Comportamiento

- Plataforma inválida → error `INVALID_PLATFORM` y exit no-cero.
- CLI de Apify ausente → error `APIFY_CLI_MISSING`.
- `position` genérico (ej. "developer", "ingeniero") → advertencia en stderr.
- LinkedIn exige mínimo 10 resultados: el script clampea `count` y advierte.
- Vacío (0 resultados) → `count: 0`, `persisted: null`, exit cero.
- Errores a stderr: `{"ok": false, "error": "...", "code": "..."}` con exit no-cero.