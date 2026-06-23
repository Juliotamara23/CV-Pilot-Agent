# CV-Pilot Agent — Manual de Usuario

CV-Pilot Agent es un orquestador inteligente de reclutamiento que busca, analiza y evalúa vacantes contra tu perfil técnico. Funciona en OpenCode, Codex, Antigravity, Claude Code y cualquier entorno con agentes.

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

### Apify CLI

Búsqueda automática en Indeed, LinkedIn y Computrabajo.

### Python + PyMuPDF (soporte PDF opcional)

El Camino B del onboarding (subir un PDF en lugar de pegar el texto del CV) requiere un entorno virtual de Python con `pymupdf` instalado. El entorno se crea una sola vez:

| OS | Comando |
|----|---------|
| Windows (PowerShell) | `pwsh -File cv-pilot-agent/scripts/setup.ps1` (o `.\scripts\setup.ps1` desde `cv-pilot-agent/`) |
| Linux / macOS | `bash cv-pilot-agent/scripts/setup.sh` |

El script crea `cv-pilot-agent/.venv/`, instala las dependencias declaradas en `cv-pilot-agent/requirements.txt` y verifica PyMuPDF. Requiere Python 3.9+ en el PATH. El agente detecta la ausencia del venv y ofrece configurarlo (una sola pregunta); si el usuario declina, continúa solo con el Camino A (pegar el CV manualmente).

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
├── AGENTS.md
├── requirements.txt
├── rules/
│   ├── persona.md
│   └── integridad.md
├── skills/
│   ├── apify/
│   │   ├── SKILL.md
│   │   └── platforms/
│   │       ├── indeed.md
│   │       ├── linkedin.md
│   │       └── computrabajo.md
│   ├── contacto.md
│   ├── database.md
│   ├── formatos.md
│   └── mimetismo.md
├── scripts/
│   ├── pdf_parser.py
│   ├── setup.ps1
│   └── setup.sh
├── db/
│   └── cv-pilot.db
└── resources/
    ├── identidad.md
    └── ejemplo-correos.md
```

3. **Configura tu identidad**: edita `resources/identidad.md` con tu nombre, LinkedIn, GitHub.
4. **(Opcional) Configura el soporte PDF**: ejecuta el script de setup del Camino B (ver "Python + PyMuPDF" arriba) si quieres subir el CV en PDF en lugar de pegar el texto. Si omites este paso, el agente funcionará solo con el Camino A (texto manual).
5. **Sube tu CV** en formato Markdown a `resources/`. Usa un MCP o herramienta para convertir PDF a Markdown.

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

- **Postulación con email:** El agente genera un borrador formal con enlace `mailto:` directo.
- **Postulación en portal:** El agente entrega una carta de presentación para copiar y pegar.
- **Modo Discusión:** Después de cualquier análisis puedes pedir orientación estratégica.

---

## Privacidad

Todos los datos (CV, identidad, análisis) se almacenan localmente en `db/cv-pilot.db`. Para máxima privacidad, usa LLMs locales con Ollama o LM Studio.

---

*¿Dudas? Pregunta al agente.*
