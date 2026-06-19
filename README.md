<h1 align="center">🤖 CV-Pilot Agentic Evolution</h1>

**CV-Pilot Agent** es un orquestador inteligente de reclutamiento que busca, analiza y evalúa vacantes contra tu perfil técnico. Funciona en OpenCode, Antigravity, Claude Code, ChatGPT y cualquier entorno con agentes.

## ✨ Qué hace

- **Búsqueda automática multi-plataforma**: Indeed, LinkedIn y Computrabajo con un presupuesto desde $5 USD/mes.
- **Análisis técnico riguroso**: compara cada vacante contra tu CV real, tecnología por tecnología.
- **Reportes accionables**: porcentaje de compatibilidad, veredicto, carta de presentación o borrador de email.
- **Privacidad total**: tus datos se almacenan localmente en SQLite. Compatible con LLMs locales.

## 🚀 Empezar

| Modalidad | Para quién | Guía |
|----------|-----------|------|
| **Web** | Usas Gemini, no querés instalar nada | [USER_GUIDE_WEB.md](USER_GUIDE_WEB.md) |
| **Agent** | Usas OpenCode o terminal, querés búsqueda automática | [USER_GUIDE_AGENT.md](USER_GUIDE_AGENT.md) |

## 🧠 Arquitectura

```
skills/apify/          → Scraping multi-plataforma (Indeed, LinkedIn, Computrabajo)
skills/database/       → Persistencia y deduplicación en SQLite
skills/contacto/       → Extracción de datos y auto-sanación
skills/formatos/       → Reportes estructurados
skills/mimetismo/      → Redacción personalizada
```

## 📦 Versiones

| Versión | Fecha | Cambios |
|---------|-------|---------|
| **v1.0.0** | Junio 2026 | Búsqueda multi-plataforma, SQLite, Apify, tests automatizados |
| v0.x | 2025 | Análisis manual, versión web inicial |

---

*¿Dudas? [Manual de Usuario](USER_GUIDE.md)*
