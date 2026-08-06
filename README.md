<h1 align="center">🤖 CV-Pilot Agent</h1>

**CV-Pilot Agent** es un orquestador inteligente de reclutamiento que busca, analiza y evalúa vacantes contra tu perfil técnico. Funciona en OpenCode, Antigravity, Claude Code y cualquier entorno con agentes de IA. Es la evolución del [CV Pilot (n8n)](https://github.com/Juliotamara23/CV-Pilot), ahora con onboarding conversacional y borradores multi-proveedor.

## ✨ Qué hace

- **Onboarding conversacional**: el agente chatea contigo, ejecuta el script de onboarding para extraer tu CV (texto o PDF con PyMuPDF), verifica los datos y genera tu perfil automáticamente. Nunca más repetir el setup.
- **Búsqueda automática multi-plataforma**: Indeed, LinkedIn y Computrabajo con un presupuesto desde $5 USD/mes.
- **Análisis técnico riguroso**: compara cada vacante contra tu CV real, tecnología por tecnología.
- **Borradores en tu correo**: guarda las postulaciones como borrador en Gmail (`gws`) u Outlook (`m365` / Microsoft Graph) para que las revises antes de enviar, con tu **CV real adjunto** en PDF. HTML con hipervínculos, sin URLs crudas.
- **Reportes accionables**: porcentaje de compatibilidad, veredicto, carta de presentación o borrador de email.
- **Privacidad total**: tus datos se almacenan localmente en `data/`. Compatible con LLMs locales.

## 🚀 Empezar

¿Cuál necesitas?

| | ☁️ Web | 🤖 Agent |
|---|---|---|
| **Sin instalar nada** | ✅ Solo el navegador | ❌ Requiere terminal |
| **Búsqueda automática** (Indeed, LinkedIn, Computrabajo) | ❌ | ✅ |
| **Onboarding conversacional** | ❌ Manual | ✅ El agente te guía |
| **PDF con links intactos** | ❌ | ✅ PyMuPDF |
| **Borradores en Gmail** | ❌ | ✅ `gws` CLI |
| **Borradores en Outlook** | ❌ | ✅ `m365` + Graph |
| **Perfil persistente** | ❌ Cada sesión | ✅ `data/` automático |
| **Setup** | Cero | `scripts/venv_setup.py` |

> **Regla simple**: si solo quieres analizar vacantes rápido desde Gemini → **Web**. Si quieres automatización completa, búsqueda en plataformas y borradores en tu correo → **Agent**.

| Modalidad | Guía |
|----------|------|
| ☁️ **Web** | [docs/web.md](docs/web.md) |
| 🤖 **Agent** | [docs/agent.md](docs/agent.md) |

### Configuración de proveedores de correo

| Proveedor | Guía |
|-----------|------|
| **Gmail** (gws) | [docs/gws-setup.md](docs/gws-setup.md) |
| **Outlook** (m365) | [docs/outlook-setup.md](docs/outlook-setup.md) |

## 🧠 Arquitectura

El agente es un **orquestador**: decide e interpreta, pero toda ejecución la delega en **CLIs deterministas** (skills) que devuelven JSON. El agente no improvisa formatos ni escribe SQL; cada skill encapsula su lógica y expone comandos cortos y verificables.

### Flujo de datos

```
onboarding / cv-update ──► data/perfil.json + data/cv.pdf
                                │
sourcing (apify | manual) ──► db/cv-pilot.db ──► análisis (razonamiento del agente)
                                                        │
                                          formatos/cli.py → reporte determinista
                                                        │
                                          mimetismo/cli.py (email, cover-letter, question)
                                                        │
                                          cli.py cv (CV persistido) → borrador Gmail/Outlook
                                                                          con CV adjunto
```

### Skills (contratos CLI)

| Skill | CLI | Propósito |
|-------|-----|-----------|
| `onboarding` | `cli.py`: extract, parse, generate, full | VSI previa + persistencia de perfil en `data/perfil.json` |
| `cv-update` | `cli.py`: extract, apply `--source-pdf` | Reescribe `perfil.json` desde un CV nuevo (fidelidad ATS, no merge) y persiste `data/cv.pdf` + `cv_path` |
| `apify` | `cli.py`: search (indeed, linkedin, computrabajo) | Sourcing multi-plataforma con plugins |
| `database` | `query.py`: list, insert, status, analysis | ORM y deduplicación en SQLite |
| `mimetismo` | `cli.py`: email, question, cover-letter, mimetismo, cv | Redacción con estilo del usuario + borrador en Gmail/Outlook con el CV real adjunto |
| `formatos` | `cli.py`: main `--job`, all | Reporte determinista por vacante o análisis completo |

### Componentes transversales

- **VSI** (`_lib/vsi.py`): Validación Semántica de Identidad. Rechaza archivos no-CV antes de cualquier procesamiento.
- **Pydantic schemas** (`_lib/schemas/`): `PerfilSchema` y `PreferenciasSchema` validan los datos persistidos.
- **LLM extraction** (`_lib/llm_extract.py`, opcional): extracción de campos del CV con un LLM externo cuando se ejecuta sin agente. Cuando se usa dentro del agente, el LLM del chat hace la extracción directamente.
- **Datos** (`data/`, gitignored): `perfil.json`, `preferencias.json` (Pydantic-validated), `correos.md`, `cv.pdf` (CV real persistido).
