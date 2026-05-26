<h1 align="center">🤖 CV Pilot</h1>

**CV Pilot** es un flujo de trabajo automatizado para **n8n** diseñado para actuar como tu coach de carrera personal. Este sistema scrapea ofertas de empleo de Indeed (mas sitios en el futuro), gestiona el registro de usuarios, procesa hojas de vida (CVs) y utiliza Inteligencia Artificial (Google Gemini) para analizar la compatibilidad de tu perfil con múltiples ofertas de trabajo automáticamente.

![Workflow Overview](media/n8n.png)

## ✨ Características Principales (n8n Workflow Original)

- **📝 Sistema de Registro y Onboarding:** Formulario web, carga de CVs (PDF), gestión en Drive.
- **🤖 Análisis Inteligente con IA (Gemini):** Veredicto **APTO/NO APTO**, comparativas, sugerencias.
- **🌐 Integración con Google Workspace:** Drive, Sheets, Docs, Gmail.

---

# 🚀 CV-Pilot (The Agentic Evolution)

Esta versión de **CV-Pilot** es una mejora sustancial que evoluciona el concepto de "workflow" de n8n hacia un **Agente Autónomo (Standalone Agent)** con capacidad de razonamiento, memoria persistente y autogestión.

## 🧠 ¿Qué hace a esta versión superior?

Mientras el sistema original de n8n requiere una infraestructura externa y flujos lineales, **CV-Pilot (Agente)** funciona como una entidad inteligente dentro de tu entorno de desarrollo:

1.  **Agente Autónomo:** No depende de un workflow lineal; utiliza un orquestador senior para delegar tareas y tomar decisiones técnicas en tiempo real.
2.  **Validación Semántica de Identidad (VSI):** Antes de procesar cualquier documento, el agente analiza si realmente es un CV profesional, rechazando documentos irrelevantes (ej. listas de compras).
3.  **Protocolo de Auto-Sanación (Auto-Sanation):** Si faltan datos de contacto (LinkedIn, GitHub) en su estado interno pero existen en el texto del CV (RAG), el agente los extrae y actualiza su memoria de forma silenciosa y automática.
4.  **Mimetismo Estratégico:** Posee una base de conocimientos de tus ejemplos reales (`ejemplo-correos.md`) y utiliza IA para redactar borradores de correo que suenan exactamente como vos, no como un bot genérico.
5.  **Memoria Persistente (Engram):** Aprende de los análisis anteriores, bugs corregidos y decisiones tomadas, mejorando su rendimiento sesión tras sesión.
6.  **Personalidad Senior:** Configurado para actuar como un reclutador implacable con más de 15 años de experiencia, enfocado en el rigor técnico y la calidad de datos.

## 🛠️ Cómo Funciona la Nueva Arquitectura

El agente opera bajo una lógica de orquestación rigurosa:

- **Paso 0:** VSI (Valida el archivo).
- **Paso 1:** Análisis técnico (Protocolo 1).
- **Paso 2:** Auto-Sanación (Prioridad 2 - busca datos si faltan).
- **Paso 3:** Redacción (Mimetismo automático si existen ejemplos en `ejemplo-correos.md`).
- **Seguridad:** Regla de Información Completa (si no hay datos, el agente se detiene y te lo exige).

---

## ⚙️ Configuración e Instalación

1.  **Requisitos:**
    - Entorno compatible con OpenCode (o el orquestador de agentes de tu elección).
    - Acceso a API de LLM (ej. Gemini/GPT) configurado en el agente.
2.  **Instalación:**
    - Clona este repositorio.
    - Asegúrate de tener los archivos `AGENTS.md`, `email-skill.md`, `skills-comunicacion.md`, `skills-formatos.md` y `ejemplo-correos.md` en la raíz.
3.  **Uso:**
    - Simplemente invoca al agente y sube tu CV. El agente te guiará por el proceso de análisis.

---

## 🤝 Contribución

¡Las contribuciones son bienvenidas! Esta evolución hacia sistemas agenticos es el futuro. Si tienes ideas para mejorar los prompts, las reglas de orquestación o los protocolos de auto-sanación, abre un *Issue* o *Pull Request*.
