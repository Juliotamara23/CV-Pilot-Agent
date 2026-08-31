# Plan: Knowledge Base Fragmentada — CV-Pilot 3.1.0

> **Estado**: Propuesto (2026-08-04)
> **Version objetivo**: 3.1.0
> **Origen**: Discusión post-refactor Issue #1 (SOLID en apify/mimetismo) + visión de fusión CV-Agent → CV-Pilot

---

## Problema que resuelve

Hoy el agente carga el perfil completo (`data/perfil.json`) en cada análisis, quemando tokens. No existe una fuente única de conocimiento que:

1. Recupere **solo el fragmento relevante** al puesto (ej: vacante QA → busca info de QA, no todo el perfil).
2. Consolide múltiples fuentes (CV, GitHub, LinkedIn, portfolio) en un solo lugar coherente.
3. Detecte y resuelva **conflictos** entre fuentes (mismo dato distinto en CV vs LinkedIn).

## Principio rector

> **Modelo Engram**: SQLite + FTS5 + resolución de conflictos. Sin archivos `.md` esparcidos como fuente de verdad. La DB es la memoria de CV-Pilot.

## Arquitectura objetivo

```
┌─────────────────────────────────────────────┐
│                  AGENTE                      │
│  "Busca trabajos QA en Medellín"             │
│                                              │
│  1. Busca vacantes (Apify)                   │
│  2. Extrae keywords: QA, playwright, pytest  │
│  3. query.py knowledge search "...keywords"  │
│  4. Recibe ~2KB de fragmentos (no 50KB)      │
│  5. Matcha CV vs vacante con contexto justo  │
│  6. Sugiere o aplica                         │
└─────────────────────────────────────────────┘
         │                    │
         ▼                    ▼
   ┌──────────┐      ┌──────────────────┐
   │  Apify   │      │  SSOT (FTS5)     │
   │  actors  │      │  knowledge       │
   └──────────┘      │  knowledge_rels  │
                     │  knowledge_fts   │
                     └──────────────────┘
```

## Modelo de datos

### Tabla `knowledge`

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PK | Identificador interno |
| `domain` | TEXT | Origen: `cv`, `github`, `linkedin`, `portfolio`, `manual` |
| `topic_key` | TEXT | Clave estable por tema (ej: `cv/experiencia`, `cv/skills`) |
| `title` | TEXT | Título corto buscable |
| `content` | TEXT | Contenido completo del fragmento |
| `source` | TEXT | Referencia a la fuente original (archivo/URL) |
| `created_at` | TEXT | ISO 8601 UTC |
| `updated_at` | TEXT | ISO 8601 UTC |

### Tabla `knowledge_relations` (modelo Engram)

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PK | |
| `memory_id_a` | INTEGER FK | Fragmento A |
| `memory_id_b` | INTEGER FK | Fragmento B |
| `relation` | TEXT | `supersedes` \| `conflicts_with` \| `related` \| `compatible` |
| `reason` | TEXT | Justificación del veredicto |
| `confidence` | REAL | 0.0–1.0 |

### Índice FTS5

```sql
CREATE VIRTUAL TABLE knowledge_fts USING fts5(
    title, content, content='knowledge', content_rowid='id'
);
```
Con triggers `INSERT`/`UPDATE`/`DELETE` para sincronización automática.

---

## Fases

### Fase 1 — Knowledge Store (Fundación) 🔴

**Alcance**: Infraestructura de DB + CLI. 100% aditiva — no cambia ningún flujo existente.

| # | Tarea | Detalle | Artefacto |
|---|---|---|---|
| 1.1 | Tablas `knowledge`, `knowledge_relations`, `knowledge_fts` | DDL en `_lib/schema.sql` (la fuente canónica es el `.sql`, NO `_schema.py`) | Permanente |
| 1.2 | Creación de tablas en DBs existentes | **`init.py` crea tablas vía `executescript`; `_ensure_schema` hoy SOLO migra columnas**. Decisión: ampliar `_ensure_schema` a tablas o documentar `init.py` como único punto de creación | Permanente |
| 1.3 | CRUD knowledge en `_lib/db.py` | `knowledge_insert`, `knowledge_get`, `knowledge_search`, `knowledge_upsert` — NO ejecuta DDL (contrato code_guard) | Permanente |
| 1.4 | CLI `query.py knowledge search "<términos>"` | FTS5 rankeado, devuelve fragmentos con preview (no contenido completo). `query.py` ya tiene sub-apps Typer (`job_app`, `analysis_app`) — el patrón existe | Permanente |
| 1.5 | CLI `query.py knowledge get <id>` | Contenido completo de un fragmento | Permanente |
| 1.6 | CLI `query.py knowledge upsert --domain X --topic_key Y` | Upsert por topic_key con detección de conflictos | Permanente |
| 1.7 | Migrar `perfil.json` → `knowledge` | Script temporal `scripts/migrate_perfil_to_knowledge.py` con `--dry-run` + backup | **Temporal** — se borra al completar |
| 1.8 | **Re-ejecutar `init.py` contra `db/cv-pilot.db`** | Obligatorio para que `test_schema_singleton` pase (compara estructura EXACTA de prod vs canónico) | Comando |

**Documentación**: `skills/database/SKILL.md` (el contrato CLI vive ahí, no en AGENTS.md).

**Refactor asociado a Fase 1**:
- R2: Actualizar docstring de `db.py:16-17` (dice "schema lives in scripts/init.py", vive en `_lib/schema.sql`)
- R3: Centralizar `CANONICAL_FIELDS` (definido 3 veces: `llm_extract.py`, `reconstructor.py`, `generator.py`) en un módulo `_lib/profile_domains.py`

**Eliminaciones (Fase 1, limpieza)**:
- `scripts/migrate_perfil_to_json.py` (migración .md→.json completada — usar como plantilla, luego borrar)
- `data/.migration_backup/`, `data/*.bak` (backups de migración completada)
- `data/cvpilot.db` (0 bytes, residuo)
- `test/scenarios/agent-mode/init_test.py` (DDL inline hardcodeado, viola single-source-of-truth)

**No toca**: Apify, LinkedIn, GitHub, flujo de análisis, skills existentes.

**Riesgo**: Mínimo — cambio aditivo, sin cambios destructivos.

---

### Fase 2 — Integración con el flujo de análisis 🟡

**Alcance**: Conectar la knowledge base al matching CV vs vacante.

| # | Tarea |
|---|---|
| 2.1 | `query.py knowledge match <job_hash>` — extrae keywords del job, busca en FTS5, devuelve fragmentos rankeados |
| 2.2 | Actualizar flujo de análisis: el agente usa `knowledge search/match` en vez de cargar `perfil.json` entero |
| 2.3 | Reporte incluye `knowledge_fragments_used` para trazabilidad de tokens |

**Riesgo**: Medio — toca el flujo central de análisis. Requiere tests de regresión.

---

### Fase 3 — Indexado desde fuentes externas 🟡

**Alcance**: Poblar la knowledge base automáticamente.

| # | Tarea | Origen |
|---|---|---|
| 3.1 | GitHub deep sync → `knowledge` (domain=github) | Portar de CV-Agent (`sync-github.ps1` → Python) |
| 3.2 | Deduplicación semántica | Portar `dedup-check.py` de CV-Agent |
| 3.3 | Actualización desde nuevo CV (`cv-update`) → `knowledge` | Integrar con skill existente |

**Riesgo**: Medio — scripts nuevos, patrones probados de CV-Agent.

---

### Fase 4 — LinkedIn Profile Scraper (Issue #6) 🟢

**Alcance**: Extraer perfil LinkedIn → `knowledge` (domain=linkedin) → sugerencias de mejora.

**Dependencia**: Issue #1 mergeado (plugin discovery ya resuelve la integración trivial).

| # | Tarea |
|---|---|
| 4.1 | Skill `apify-linkedin-profile` — CLI que extrae perfil vía Apify y lo indexa en `knowledge` |
| 4.2 | `query.py knowledge diff` — compara fragmentos entre fuentes y señala gaps |
| 4.3 | Pipeline de sugerencias: gaps + vacante → mejoras al CV Y al perfil LinkedIn |

---

### Fase 5 — Adaptación de CV por Oferta 🟢

**Alcance**: Componer CV adaptado usando solo fragmentos relevantes al puesto.

| # | Tarea |
|---|---|
| 5.1 | `query.py knowledge build-cv <job_hash>` — compone CV con fragmentos seleccionados |
| 5.2 | Template Harvard (de CV-Agent) renderizado con fragmentos |
| 5.3 | Control de presupuesto de tokens en `knowledge match` |

---

## Decisiones tomadas

| Decisión | Justificación |
|---|---|
| **No usar `fuentes/*.md`** | Demasiados archivos, búsqueda frágil. Todo en SQLite con FTS5. |
| **Modelo Engram, no Engram** | CV-Pilot tiene su propia DB; replicar el patrón (FTS5 + conflictos) da la misma memoria sin dependencia externa. |
| **AGENTS.md no documenta el CLI** | El contrato vive en `skills/database/SKILL.md` (lección v3.0). |
| **Migración = script temporal** | Patrón ya establecido (`migrate_perfil_to_json.py`): `--dry-run`, backup, se borra al completar. |
| **Fases incrementales** | No mezclar LinkedIn (#6) en la fundación. Cada fase es evaluable y mergeable sola. |

## Decisiones confirmadas (2026-08-04 — revisión de riesgos pre-Fase 1)

> Estas decisiones fueron tomadas en sesión tras el análisis de bloqueantes/ambigüedades. **El plan NO se ejecuta hasta estar 100% validado.**

### D1 — Mapping topic_key: HÍBRIDO
- **Agrupados**: `cv/contacto` (nombre + URLs públicas), `cv/resumen`
- **Granulares (1:N)**: `cv/experiencia/<empleador>`, `cv/educacion/<item>`, `cv/proyectos/<item>`, `cv/certificaciones/<item>`, `cv/skills/<item>`
- Total esperado: ~16-20 topic_keys desde perfil.json real
- Justificación: el ranking FTS5 distingue cada item; buscar "Vepal" devuelve solo esa experiencia

### D2 — Granularidad de migración: 1:N para listas
- `experiencia` → una fila por empleador (~265 tokens c/u, no 794 del bloque completo)
- `proyectos`, `certificaciones` → una fila por item
- Es la premisa del plan: fragmentos ~2KB con recuperación selectiva

### D3 — Semántica de upsert: REPLACE (no versionar)
- `topic_key` es natural key; upsert reemplaza content
- `knowledge_relations` queda **reservado para conflictos ENTRE dominios** (cv vs linkedin vs github) — el caso real de Fases 3-4
- No hay versionado interno en Fase 1

### D4 — PII: TODO entra a la DB, PERO no todo al índice FTS
- **Tabla base `knowledge`**: TODOS los campos de perfil.json, incluido correo y teléfono (una sola fuente de verdad)
- **Índice FTS5**: solo `indexed=1` — experiencia, skills, proyectos, resumen, educacion, URLs públicas
- **No indexados** (`indexed=0`): `correo`, `telefono` — PII de contacto, no se rankean
- Implementación: columna `indexed INTEGER DEFAULT 1` + triggers FTS con condición
- El agente recupera correo/teléfono por topic_key exacto (`knowledge get cv/contacto`), nunca por búsqueda

### D5 — Bloqueante técnico resuelto: `IF NOT EXISTS`
- El DDL del plan original (`CREATE VIRTUAL TABLE knowledge_fts`) **rompe el re-run de init.py** — falta `IF NOT EXISTS`
- **Exigencia**: `CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts` + `CREATE TRIGGER IF NOT EXISTS knowledge_ai/ad/au`
- Sin esto, la tarea 1.8 (re-init) falla en la segunda corrida con `table already exists`

### D6 — `test_schema_singleton` es dependencia HARD de 1.8
- `extract_schema` incluye las shadow tables de FTS5 (`knowledge_fts_data`, `_idx`, `_docsize`, `_config`)
- **1.8 debe ir en el MISMO commit que el DDL**, no después
- `pytest` debe correr con el MISMO venv python que crea la prod DB (las shadow tables cambian entre versiones de sqlite)
- Los triggers NO se comparan en singleton — cubrir sync FTS5 con test funcional aparte

### D7 — Aclaración `_ensure_schema` (tarea 1.2)
- **NO necesita ampliarse para tablas**: `init.py:41` ya crea tablas nuevas vía `executescript` + `IF NOT EXISTS`
- `_ensure_schema` solo existe para columnas (porque CREATE TABLE IF NOT EXISTS no agrega columnas)
- La tarea 1.2 es puramente documental

### D8 — Rendimiento validado (medido 2026-08-04)
- Búsqueda FTS5 a 110 filas: **0.01–0.26 ms**
- Get por topic_key: **0.02 ms** | Upsert: **0.04 ms**
- Tokens: perfil.json completo = **1,486** → recuperación selectiva por oferta ≈ **200** (ahorro 85-87%)
- SQLite FTS5 maneja millones de filas con latencia de ms — velocidad no es preocupación

### D9 — Consumidores de perfil.json (inventario verificado)
- **Readers runtime**: `formatos/cli.py:108,143`, `mimetismo/cli.py:157,205` (email + cover-letter). `mimetismo question` NO usa profile
- **Writers**: `onboarding/generator.py:104-108`, `cv-update/cli.py` + `reconstructor.py`
- **NO consumidores**: `_lib/vsi.py`, `_lib/shared/cli_utils.py`, `_lib/pdf_parser.py`
- **No hay consumidores sin mapear** — inventario completo
- El token burn real es el orquestador leyendo por `AGENTS.md:27` + `persona.md:19-24` + `integridad.md:12` (Fase 2.2)

## Riesgos globales

| Riesgo | Mitigación |
|---|---|
| Fase 2 rompe flujo de análisis | Tests de regresión + feature flag temporal |
| Conflicto de datos CV vs LinkedIn | `knowledge_relations` con resolución explícita (modelo Engram) |
| Crecimiento de la DB | FTS5 es eficiente; fragmentos cortos por diseño |
| Deriva con CV-Agent | CV-Agent es referencia de patrones, no de código a copiar ciegamente |

## Hallazgo clave de la exploración (2026-08-04)

> **Los CLIs actuales NO cargan perfil.json entero.** `formatos` y `mimetismo` solo leen 4-6 campos de contacto vía `load_profile`. El "quema de tokens" real ocurre en el **orquestador** (el agente lee el archivo completo por instrucciones de `AGENTS.md`/`persona.md`).

**Implicación para Fase 2.2**: el mayor ahorro de tokens NO es reescribir los CLIs — es cambiar el **comportamiento documentado del agente** (`AGENTS.md`, `rules/integridad.md`, `rules/persona.md`). La regresión de Fase 2 debe verificar que los fragmentos usados son `cv/contacto` + `cv/skills` + `cv/experiencia`, no el archivo completo.

---

## Criterios de aceptación

- [ ] Fase 1: `query.py knowledge search` devuelve fragmentos rankeados con preview
- [ ] Fase 1: `query.py knowledge upsert` idempotente por topic_key
- [ ] Fase 1: 100% de tests existentes pasan (cero regresiones)
- [ ] Fase 2: análisis de vacante QA consume < 20% de tokens que hoy
- [ ] Fase 3: GitHub sync indexa logros sin duplicados
- [ ] Fase 4: LinkedIn diffs detectan gaps vs CV
- [ ] Fase 5: CV por oferta compone con solo fragmentos relevantes
