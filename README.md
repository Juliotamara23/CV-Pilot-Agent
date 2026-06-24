<h1 align="center">🤖 CV-Pilot Agent</h1>

**CV-Pilot Agent** es un orquestador inteligente de reclutamiento que busca, analiza y evalúa vacantes contra tu perfil técnico. Funciona en OpenCode, Antigravity, Claude Code y cualquier entorno con agentes de IA. Es la evolución del [CV Pilot (n8n)](https://github.com/Juliotamara23/CV-Pilot), ahora con onboarding conversacional y borradores multi-proveedor.

## ✨ Qué hace

- **Onboarding conversacional**: el agente chatea contigo, extrae tu CV (texto o PDF con PyMuPDF), verifica los datos y genera tu perfil automáticamente. Nunca más repetir el setup.
- **Búsqueda automática multi-plataforma**: Indeed, LinkedIn y Computrabajo con un presupuesto desde $5 USD/mes.
- **Análisis técnico riguroso**: compara cada vacante contra tu CV real, tecnología por tecnología.
- **Borradores en tu correo**: guarda las postulaciones como borrador en Gmail (`gws`) u Outlook (`m365` / Microsoft Graph) para que las revises antes de enviar. HTML con hipervínculos, sin URLs crudas.
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
| **Setup** | Cero | `setup.ps1` / `setup.sh` |

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

```
skills/onboarding/      → Onboarding conversacional y persistencia del perfil
skills/apify/           → Scraping multi-plataforma (Indeed, LinkedIn, Computrabajo)
skills/database/        → Persistencia y deduplicación en SQLite
skills/contacto/        → Extracción de datos y auto-sanación
skills/formatos/        → Reportes estructurados y opciones de postulación
skills/mimetismo/       → Redacción personalizada con estilo del usuario
skills/gmail/           → Borradores en Gmail vía gws CLI
skills/outlook/         → Borradores en Outlook vía Microsoft Graph
scripts/                → pdf_parser (PyMuPDF), setup (.venv), init (DB)
data/                   → Perfil, correos de ejemplo y preferencias (local, gitignored)
```

## 📦 Versiones

| Versión | Fecha | Cambios |
|---------|-------|---------|
| **v2.0.0** | Junio 2026 | Onboarding conversacional, borradores Gmail + Outlook, venv aislado, skills modernizadas |
| **v1.0.0** | Junio 2026 | Búsqueda multi-plataforma, SQLite, Apify, tests automatizados |
