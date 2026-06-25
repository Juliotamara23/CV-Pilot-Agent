# v3.0.0 — Scriptification Roadmap

## Objetivo

Reducir el consumo de tokens reemplazando skills basadas en Markdown por scripts Python invocables. Cada script encapsula la lógica de una skill y devuelve resultados estructurados. El agente pasa de leer e interpretar instrucciones largas a invocar comandos cortos.

## Principio rector

> "Una skill sin script es una instrucción que el agente debe leer cada vez. Una skill con script es una herramienta que el agente simplemente invoca."

## Métricas esperadas

| Métrica | Hoy | Objetivo v3.0.0 |
|--------|:---:|:---:|
| Tokens por invocación de skill | 800-1200 | 25-50 |
| SQL escrito por el agente | Sí (frágil) | No (encapsulado) |
| Consistencia entre plataformas | Variable | Determinista |
| Mantenibilidad | Editar Markdown + testear agente | Editar Python + test unitario |

---

## Fases

### Fase 1 — Database ORM (`db_query.py`) 🔴

Script más crítico. Hoy el agente escribe SQL a mano. Un error de sintaxis o una inyección y se rompe todo.

```
db_query.py status new          → lista jobs con status='new'
db_query.py analyze <hash>      → INSERT analysis + UPDATE status
db_query.py discard <hash>      → UPDATE status='discarded'
db_query.py apply <hash>        → UPDATE status='applied'
```

**Qué reemplaza:** `skills/database/SKILL.md` (~1.2K tokens)

---

### Fase 2 — Email Generator (`generate_email.py`) 🔴

Skill más compleja. Hoy el agente carga CV, ejemplos, job description y aplica reglas de mimetismo manualmente.

```
generate_email.py --job <hash> --provider gmail  → email HTML listo para draft
generate_email.py --job <hash> --provider outlook
```

**Lógica interna:**
1. Lee `data/perfil.md` y `data/correos.md`
2. Lee job de la DB
3. Aplica matching CV vs requisitos
4. Genera email HTML con estilo mimetismo y links formateados

**Qué reemplaza:** `skills/mimetismo/SKILL.md` (~800 tokens) + parte de `skills/contacto/SKILL.md`

---

### Fase 3 — Report Formatter (`format_report.py`) 🟡

```
format_report.py --analysis <id> --mode email  → reporte con opciones según email/portal
```

**Qué reemplaza:** `skills/formatos/SKILL.md` (~500 tokens)

---

### Fase 4 — Contact Extractor (`extract_contact.py`) 🟡

```
extract_contact.py "texto de oferta..."  → {email: "..." | "PORTAL_POSTULATION"}
```

**Qué reemplaza:** `skills/contacto/SKILL.md` (~300 tokens)

---

### Fase 5 — Job Searcher (`search_jobs.py`) 🟡

```
search_jobs.py --platform linkedin --position "React" --location "Medellín" --count 5
```

**Qué reemplaza:** `skills/apify/SKILL.md` (~900 tokens)

---

### Fase 6 — Onboarding Engine (`onboard.py`) 🟢

```
onboard.py --cv cv.pdf  → perfil.md, correos.md, preferencias.md
```

**Qué reemplaza:** `skills/onboarding/SKILL.md` (~1.5K tokens)

---

## Arquitectura final

```
scripts/
  init.py              ← DB init (existe)
  setup.ps1 / .sh      ← venv (existe)
  pdf_parser.py        ← PDF extraction (existe)
  db_query.py          🆕 DB CRUD
  generate_email.py    🆕 Mimetismo + contacto + generación
  format_report.py     🆕 Formato de reportes
  extract_contact.py   🆕 Extracción de contacto
  search_jobs.py       🆕 Scraping Apify
  onboard.py           🆕 Onboarding automatizado
```

El agente pasa de esto:

```
Leer skills/mimetismo/SKILL.md → interpretar → leer CV → leer job → generar
(~2500 tokens por correo)
```

A esto:

```
python scripts/generate_email.py --job abc123 --provider gmail
(~30 tokens por correo)
```

---

## Orden de implementación (SDD)

| # | Cambio | Dependencias | Impacto |
|---|--------|-------------|:------:|
| 1 | `db_query.py` | Ninguna | 🔴 Más urgente |
| 2 | `generate_email.py` | `db_query.py` | 🔴 Más tokens ahorrados |
| 3 | `format_report.py` | `db_query.py` | 🟡 |
| 4 | `extract_contact.py` | Ninguna | 🟡 |
| 5 | `search_jobs.py` | `db_query.py` | 🟡 |
| 6 | `onboard.py` | `db_query.py`, `pdf_parser.py` | 🟢 |

---

## Principio SDD por cambio

Cada script sigue el ciclo completo:
1. **Explore** — ¿qué hace la skill hoy? ¿qué tokens consume?
2. **Propose** — alcance del script, interfaz CLI
3. **Spec** — escenarios de entrada/salida
4. **Design** — estructura del script, dependencias
5. **Tasks** — implementación en fases
6. **Apply** — código + tests
7. **Verify** — validación contra la skill original
8. **Archive** — documentar y sincronizar specs

---

## Riesgos

| Riesgo | Mitigación |
|--------|-----------|
| Script no cubre edge case de la skill | Tests unitarios + verify contra skill original |
| Skill y script se desincronizan | El script es la fuente de verdad; la skill se actualiza para documentar el script |
| Sobrecarga de scripts | 6 scripts bien definidos con CLI consistente (`--help`, flags estándar) |
