---
name: apify
description: "Scraping multi-plataforma de vacantes vía el CLI `cli.py`."
scope: SOURCING_PHASE
version: 3.0
---

# Skill: Apify Scraper (CLI `cli.py`)

Documentación del CLI `skills/apify/scripts/cli.py`. Adaptadores: `skills/apify/scripts/platforms/` (Indeed, LinkedIn, Computrabajo).

Para flags, defaults y tipos de cada comando ejecuta `--help` (la ayuda del CLI es la única fuente de verdad de flags):

```bash
python skills/apify/scripts/cli.py --help
python skills/apify/scripts/datasets_cli.py <command> --help
```

## Comando `search`

Búsqueda de dos fases (cost wizard):

| Fase | Flag | Efecto |
| --- | --- | --- |
| Costo | (ninguno) | NO llama al actor; el envelope trae `phase: "cost"` y `cost_usd` real |
| Ejecución | `--confirm` | Corre el actor, normaliza, etiqueta `high\|medium\|low` (no descarta nada) y persiste todo vía `query.py job insert-batch --file <tmp>` |

## Comandos de dataset (recuperación)

Entrypoint distinto: `skills/apify/scripts/datasets_cli.py`. Recuperan datos de runs interrumpidos o inspeccionan datasets sin re-ejecutar el actor.

- `datasets-list`: lista runs recientes de un actor para encontrar el `dataset_id` de un run pasado.
- `datasets-inspect`: cuenta items y muestra las claves del schema; útil antes de hacer fetch.
- `datasets-fetch`: trae items y persiste los que no están ya en la DB (idempotente, no duplica); sirve para recuperar runs interrumpidos.

Ejecuta `datasets_cli.py <command> --help` para ver todos los flags de cada comando (incluye ayuda sobre cuándo usar cada uno).

## Comportamiento

| Condición | Efecto |
| --- | --- |
| Plataforma inválida | `INVALID_PLATFORM`, exit ≠ 0 |
| CLI de Apify ausente | `APIFY_CLI_MISSING` |
| `position` genérico (ej. "developer", "ingeniero") | Advertencia en stderr |
| LinkedIn | Clampea `count` a un mínimo de 10 y advierte |
| 0 resultados | `count: 0`, `persisted: null`, exit 0 |
| Sin `--confirm` | Nunca ejecuta el actor ni gasta dinero |
| Sin runs recientes / dataset vacío | Envelopes con contadores en cero, exit 0 |
| Dataset inexistente o actor inválido | Error en stderr, exit ≠ 0 |
| `datasets-fetch` con campos faltantes | Van a `validation_failures` con índice y error; los válidos no se bloquean |
| Cualquier error | Stderr `{"ok": false, "error": "...", "code": "..."}`, exit ≠ 0 |
