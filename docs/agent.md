# CV-Pilot Agent — Manual de Usuario

CV-Pilot Agent es un orquestador inteligente de reclutamiento que busca, analiza y evalúa vacantes contra tu perfil técnico. Funciona en OpenCode, Antigravity, Claude Code y cualquier entorno con agentes.

---

## Requisitos

### SQLite CLI

Persistencia de vacantes y análisis.

| OS | Comando |
|----|---------|
| Windows | `winget install -e --id SQLite.SQLite` |
| macOS | `brew install sqlite3` |
| Linux (Debian/Ubuntu) | `sudo apt install sqlite3` |

El agente detecta si `sqlite3` está disponible y pregunta antes de instalar (nunca instala sin permiso).

### Python + PyMuPDF (soporte PDF opcional)

El Camino B del onboarding (subir un PDF en lugar de pegar el texto del CV) requiere un entorno virtual de Python con `pymupdf` instalado. El agente configura el venv por su cuenta la primera vez (hasta 3 reintentos automáticos) llamando a `scripts/venv_setup.py`; solo te avisa si fallan los 3 intentos.

| OS | Comando manual (opcional) |
|----|---------|
| Windows (PowerShell) | `pwsh -File cv-pilot-agent/scripts/setup.ps1` (o `.\scripts\setup.ps1` desde `cv-pilot-agent/`) |
| Linux / macOS | `bash cv-pilot-agent/scripts/setup.sh` |

Los scripts `setup.ps1` y `setup.sh` son alternativas legacy; el método actual es `scripts/venv_setup.py`, que el agente invoca automáticamente. Todos crean `cv-pilot-agent/.venv/`, instalan las dependencias de `cv-pilot-agent/requirements.txt` y verifican PyMuPDF. Requieren Python 3.9+ en el PATH. Si el venv no se puede crear, el agente continúa con el Camino A (pegar el CV manualmente).

### Apify CLI

Búsqueda automática en Indeed, LinkedIn y Computrabajo.

| OS | Comando | Recomendado |
|----|---------|-------------|
| Windows | `irm https://apify.com/install-cli.ps1 \| iex` | ✅ |
| macOS | `brew install apify-cli` | ✅ |
| Cualquiera | `npm install -g apify-cli` | ❌ (mejor deja de usar npm) |

### Token Apify

1. Crea una cuenta en [Apify](https://apify.com).
2. Genera un token en [Settings > Integrations](https://console.apify.com/settings/integrations).
3. Configúralo:
```
apify login --token TU_TOKEN
```

---

## Instalación del agente

1. Clona o descarga el repositorio.
2. La estructura debe quedar así:

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
│   │   │   └── cli.py         # onboard.py (extract, parse, generate, full)
│   │   └── templates/
│   ├── apify/
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       ├── cli.py         # search_jobs.py
│   │       └── platforms/     # indeed.py, linkedin.py, computrabajo.py
│   ├── database/
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       └── query.py       # ORM (list, insert, status, analysis)
│   ├── mimetismo/
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       └── cli.py         # mimetismo.py (email, question, cover-letter)
│   └── formatos/
│       ├── SKILL.md
│       └── scripts/
│           └── cli.py         # format_report.py
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
│   └── cleanup.py             # Limpieza de archivos temporales
├── db/
│   └── cv-pilot.db            # Base SQLite (local)
└── data/                      # Perfil del usuario (gitignored, local)
    ├── perfil.md              # Generado por onboard.py
    ├── correos.md             # Generado por onboard.py
    └── preferencias.md        # Generado por onboard.py
```

3. **Onboarding conversacional** (obligatorio la primera vez): el agente detecta que `data/perfil.md` no existe y arranca el flujo guiado invocando `onboard.py`. Puedes pasarle tu CV en PDF (Camino B, requiere venv con PyMuPDF) o pegar el texto directamente (Camino A, sin dependencias). El agente verifica los datos contigo y persiste el perfil en `data/`.
4. **Configurar soporte PDF** (opcional, solo Camino B): si vas a subir el CV en PDF y quieres ahorrarte la pregunta del agente, ejecuta manualmente `cv-pilot-agent/scripts/venv_setup.py` o uno de los scripts legacy. Si omites este paso, el agente lo configura automáticamente la primera vez que lo necesite.
5. **Configurar Apify** (solo si vas a usar búsqueda automática): sigue los pasos de "Token Apify" más arriba. Para análisis manual de vacantes no hace falta.

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

- **Postulación con email:** el agente usa el provider configurado en `data/preferencias.md` (Gmail u Outlook) y genera un borrador formal con enlace `mailto:` directo. Puedes sobrescribir el provider pasando `--provider gmail|outlook` al comando de `mimetismo`. El setup de Gmail/Outlook es **opcional**: solo lo necesitas si quieres que el agente guarde borradores en tu correo. Si no lo configuras, puedes seguir usando la carta de presentación manual (siguiente bullet).
- **Postulación en portal:** el agente entrega una carta de presentación para copiar y pegar.
- **Modo Discusión:** después de cualquier análisis puedes pedir orientación estratégica.

### Configuración de proveedores de correo (opcional)

| Proveedor | Guía | Cuándo se usa |
|-----------|------|---------------|
| **Gmail** (`gws`) | [docs/gws-setup.md](docs/gws-setup.md) | Si quieres que el agente guarde borradores en Gmail |
| **Outlook** (`m365` + Graph) | [docs/outlook-setup.md](docs/outlook-setup.md) | Si quieres que el agente guarde borradores en Outlook |

El agente **pregunta antes de instalar** cualquier CLI externa; nunca lo hace sin tu confirmación.

---

## Privacidad

Todos los datos (CV, identidad, análisis) se almacenan localmente en `db/cv-pilot.db` y `data/`. Para máxima privacidad, usa LLMs locales con Ollama o LM Studio.

---

*¿Dudas? Pregunta al agente.*
