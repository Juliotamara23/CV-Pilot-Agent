# CV-Pilot Agent — Manual de Usuario

CV-Pilot Agent es un orquestador inteligente de reclutamiento que busca, analiza y evalúa vacantes contra tu perfil técnico. Funciona en OpenCode, Antigravity, Claude Code y cualquier entorno con agentes.

---

## Requisitos

- **Python 3.9+** con `pip` en el PATH.
- **Git** (para clonar el repositorio).
- **SQLite**: no requiere instalación — el sistema usa el módulo integrado de Python (`sqlite3`).
- **Opcional — Apify CLI**: solo si vas a usar búsqueda automática de vacantes.
- **Opcional — Gmail/Outlook**: solo si quieres que el agente guarde borradores en tu correo (paso 5 de la instalación).

---

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/Juliotamara23/CV-Pilot-Agent.git
cd CV-Pilot-Agent
```

### 2. Crear el entorno virtual

Instala las dependencias de `cv-pilot-agent/requirements.txt` (PyMuPDF, typer, pydantic, httpx, pytest, pyright):

```bash
python cv-pilot-agent/scripts/venv_setup.py
```

> El agente también crea el venv automáticamente la primera vez (hasta 3 intentos) si no existe. Verifica que quedó listo:
> ```bash
> cv-pilot-agent/.venv/bin/python --version
> ```

### 3. Inicializar la base de datos

```bash
cv-pilot-agent/.venv/bin/python cv-pilot-agent/scripts/init.py
```

Crea `db/cv-pilot.db` con el esquema canónico. Es idempotente: se puede repetir sin riesgo.

### 4. (Opcional) Búsqueda automática — Apify

```bash
apify login --token TU_TOKEN
```

### 5. (Opcional) Borradores en tu correo

- **Gmail**: sigue [gws-setup.md](gws-setup.md).
- **Outlook**: sigue [outlook-setup.md](outlook-setup.md).

### 6. Primer uso

Abre el proyecto en tu entorno de agentes (OpenCode, Claude Code, etc.) y pide al agente analizar una vacante o iniciar el onboarding.

> **Onboarding (obligatorio la primera vez):** el agente detecta que `data/perfil.json` no existe y arranca el flujo guiado. Sube tu CV en **PDF** — el agente valida, extrae y persiste `data/perfil.json` y `data/cv.pdf` (este archivo se adjunta automáticamente a tus borradores). Si no tienes el PDF a mano, puedes pegar el texto del CV y añadir el PDF después con `cv-update`.

---

### Estructura del proyecto

```
cv-pilot-agent/
├── AGENTS.md                  # Contrato del agente (orquestación)
├── requirements.txt           # Dependencias Python
├── rules/                     # Reglas de comportamiento del agente
│   ├── persona.md
│   ├── integridad.md
│   └── code_guard.md
├── skills/                    # Skills como contratos CLI
│   ├── onboarding/
│   │   ├── SKILL.md
│   │   ├── scripts/
│   │   │   └── cli.py         # extract, parse, generate, full
│   │   └── templates/
│   ├── apify/
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       ├── cli.py         # search (indeed, linkedin, computrabajo)
│   │       └── platforms/     # indeed.py, linkedin.py, computrabajo.py
│   ├── database/
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       └── query.py       # ORM (list, insert, status, analysis)
│   ├── mimetismo/
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       └── cli.py         # email, question, cover-letter, mimetismo, cv
│   └── formatos/
│       ├── SKILL.md
│       └── scripts/
│           └── cli.py         # reporte determinista
├── _lib/                      # Utilidades internas compartidas
│   ├── db.py
│   ├── models.py
│   ├── errors.py
│   └── shared/
├── scripts/                   # Utilidades y bootstrap
│   ├── venv_setup.py          # Setup automático del venv (con retry)
│   ├── setup.ps1              # Alternativa legacy para Windows
│   ├── setup.sh               # Alternativa legacy para Linux/macOS
│   ├── pdf_parser.py          # Extracción PDF con PyMuPDF
│   ├── init.py                # Inicialización de la base de datos
│   ├── pre_push_check.py      # Gate de pre-push (refs, skills, pyright)
│   ├── migrate_perfil_to_json.py  # Migración perfil.md → perfil.json
│   └── cleanup.py             # Limpieza de archivos temporales
├── db/
│   └── cv-pilot.db            # Base SQLite (local)
└── data/                      # Perfil del usuario (gitignored, local)
    ├── perfil.json            # Generado por onboarding / cv-update
    ├── correos.md             # Generado por onboarding
    ├── preferencias.json      # Generado por onboarding
    └── cv.pdf                 # Archivo real del CV (persistido al procesar un PDF)
```

---

## Presupuesto

Recomendado: **$5 USD/mes** en Apify. Con uso diario moderado gastarás ~$1.24/mes.

| Plataforma | Costo por resultado |
|-----------|-------------------|
| Indeed | $0.003 |
| LinkedIn | $0.001 (mínimo 10) |
| Computrabajo | $0.00199 + $0.0005 arranque |

El agente consulta el precio real vía API antes de cada ejecución y pide confirmación.

---

## Uso

### Análisis manual

Pega una oferta de trabajo en el chat. El agente la analiza contra tu CV y entrega un reporte con veredicto.

### Búsqueda automática

Ejemplos:

> "Busca 3 trabajos de React en Medellín"

> "Busca 2 trabajos de Python en LinkedIn para Colombia"

> "Busca 1 trabajo de desarrollador en Computrabajo"

El agente:
1. Detecta la plataforma (o pregunta si no la mencionas)
2. Sugiere refinar keywords si son muy genéricas
3. Consulta el costo real y pide confirmación
4. Ejecuta el scraping
5. Valida que los resultados sean relevantes
6. Analiza cada vacante contra tu CV
7. Muestra el reporte con veredicto

### Reporte

Cada análisis incluye:
- Porcentaje de compatibilidad
- Comparativa técnica (tecnología por tecnología)
- Observaciones y riesgos
- Veredicto: Apto / Apto con reservas / No apto
- Opciones: generar carta de presentación o preguntas de entrevista

---

## ¿Cómo interactuar?

- **Postulación con email:** el agente usa el provider configurado en `data/preferencias.json` (Gmail u Outlook) y genera un borrador formal **en tu gestor de correo**. Antes de redactar consulta `cli.py cv` para saber si tu CV real está persistido; si existe, el borrador se crea con el CV adjunto (`attached: true`) y la firma omite el link de Drive (redundante). Puedes sobrescribir el provider pasando `--provider gmail|outlook` al comando de `mimetismo`. El setup de Gmail/Outlook es **opcional**: solo lo necesitas si quieres que el agente guarde borradores en tu correo. Si no lo configuras, puedes seguir usando la carta de presentación manual (siguiente bullet).
- **CV real adjunto:** tu CV en PDF se persiste en `data/cv.pdf` cuando haces onboarding con PDF o `cv-update` (campo `cv_path` en `perfil.json`). Si aún no lo has subido, el agente te lo sugiere al redactar; mientras tanto los correos usan el link de `cv_url` como respaldo.
- **Postulación en portal:** el agente entrega una carta de presentación para copiar y pegar.
- **Modo Discusión:** después de cualquier análisis puedes pedir orientación estratégica.

### Configuración de proveedores de correo (opcional)

| Proveedor | Guía | Cuándo se usa |
|-----------|------|---------------|
| **Gmail** (`gws`) | [gws-setup.md](gws-setup.md) | Si quieres que el agente guarde borradores en Gmail |
| **Outlook** (`m365` + Graph) | [outlook-setup.md](outlook-setup.md) | Si quieres que el agente guarde borradores en Outlook |

El agente **pregunta antes de instalar** cualquier CLI externa; nunca lo hace sin tu confirmación.

---

## Privacidad

Todos los datos (CV, identidad, análisis) se almacenan localmente en `db/cv-pilot.db` y `data/`. Para máxima privacidad, usa LLMs locales con Ollama o LM Studio.

---

*¿Dudas? Pregunta al agente.*
