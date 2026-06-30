---
name: Skill Apify Scraper
description: Scraping multi-plataforma de vacantes vía el CLI `search_jobs.py`.
scope: SOURCING_PHASE
version: 3.0
---

# Skill: Apify Scraper (CLI `search_jobs.py`)

Documentación del CLI `skills/apify/scripts/search_jobs.py`. Adaptadores: `skills/apify/scripts/platforms/` (Indeed, LinkedIn, Computrabajo).

## Comando

```bash
python skills/apify/scripts/search_jobs.py \
  --platform {indeed|linkedin|computrabajo} \
  --position "React Developer" \
  --location "Medellín" \
  --country CO \
  --count 5 \
  [--workplace onsite|remote|hybrid]   # solo LinkedIn
  [--experience entry|mid|senior]      # solo LinkedIn
  [--confirm]
```

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

## Comportamiento

- Plataforma inválida → error `INVALID_PLATFORM` y exit no-cero.
- CLI de Apify ausente → error `APIFY_CLI_MISSING`.
- `position` genérico (ej. "developer", "ingeniero") → advertencia en stderr.
- LinkedIn exige mínimo 10 resultados: el script clampea `count` y advierte.
- Vacío (0 resultados) → `count: 0`, `persisted: null`, exit cero.
- Errores a stderr: `{"ok": false, "error": "...", "code": "..."}` con exit no-cero.