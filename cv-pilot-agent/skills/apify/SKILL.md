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

1. **Sin `--confirm`** — NO llama al actor. Devuelve el costo real en USD:
   ```json
   {"ok": true, "phase": "cost", "actor": "...", "platform": "linkedin",
    "count": 5, "cost_usd": 0.005, "position": "...", "location": "..."}
   ```
2. **Con `--confirm`** — ejecuta el actor, normaliza vía el adapter, etiqueta
   cada resultado `high|medium|low` (NO descarta nada) y persiste TODO vía
   `query.py job insert-batch --file <tmp>`.

## Comandos de dataset (recuperación)

Entrypoint distinto: `skills/apify/scripts/datasets_cli.py`. Recuperan datos de runs interrumpidos o inspeccionan datasets sin re-ejecutar el actor.

- `datasets-list`: lista runs recientes de un actor para encontrar el `dataset_id` de un run pasado.
- `datasets-inspect`: cuenta items y muestra las claves del schema; útil antes de hacer fetch.
- `datasets-fetch`: trae items y persiste los que no están ya en la DB (idempotente, no duplica); sirve para recuperar runs interrumpidos.

Ejecuta `datasets_cli.py <command> --help` para ver todos los flags de cada comando (incluye ayuda sobre cuándo usar cada uno).

## Comportamiento

- Plataforma inválida → error `INVALID_PLATFORM` y exit no-cero.
- CLI de Apify ausente → error `APIFY_CLI_MISSING`.
- `position` genérico (ej. "developer", "ingeniero") → advertencia en stderr.
- LinkedIn exige mínimo 10 resultados: el script clampea `count` y advierte.
- Vacío (0 resultados) → `count: 0`, `persisted: null`, exit cero.
- Errores a stderr: `{"ok": false, "error": "...", "code": "..."}` con exit no-cero.
- Sin `--confirm` nunca se ejecuta el actor ni se gasta dinero.
- Sin runs recientes / dataset vacío → envelopes con contadores en cero, exit cero.
- Dataset inexistente o actor inválido → error en stderr, exit no-cero.
- `datasets-fetch` con campos faltantes → aparecen en `validation_failures` con índice y error; no bloquean los válidos.
