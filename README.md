<h1 align="center">🤖 CV-Pilot Agentic Evolution</h1>

**CV-Pilot Agent** es un orquestador inteligente de reclutamiento diseñado para ejecutarse de forma **agnóstica** en cualquier entorno que soporte agentes (OpenCode, Antigravity, ChatGPT, Claude Desktop, Ollama, etc.).

Este agente es la evolución lógica del sistema original **[CV-Pilot (n8n Workflow)](https://github.com/Juliotamara23/CV-Pilot)**. Mientras que la versión original se centra en flujos de automatización de infraestructura en n8n, esta versión se enfoca en el **razonamiento conversacional y la validación semántica**.

## 🧠 Arquitectura Agéntica
A diferencia de un workflow rígido, este agente utiliza **protocolos de toma de decisiones** que se adaptan al entorno donde se ejecuten:

- **Plataforma Agnostic:** Utiliza la capacidad de razonamiento del LLM conectado para evaluar el CV y decidir el siguiente paso.
- **Validación Semántica de Identidad (VSI):** El agente entiende qué es un CV profesional y qué no, rechazando documentos irrelevantes antes de consumir tokens o tiempo.
- **Protocolo de Auto-Sanación:** Si faltan datos en el contexto de la sesión, el agente escaneará activamente el documento (RAG) para extraer información faltante de forma silenciosa.
- **Mimetismo Estratégico:** Aprende tu estilo de escritura a partir de ejemplos reales para redactar correos de postulación que suenan a ti, no a una plantilla genérica.

## 🚀 Instalación y Uso
Para saber cómo debes hacer el setup de CV-Pilot según el entorno que prefieras te sugiero seguir la guía de paso por paso: [Manual de Usuario](USER_GUIDE.md).

**TL;DR:**
1. **Elige tu modalidad:** Descarga o clona el repositorio, luego escoge la versión según donde vayas a correr a CV-Pilot (`web` o `agent`).
2. **Configuración de Identidad:** Completa el archivo `user-identidad.md` (o `resources/identidad.md`) con tus datos reales.
3. **Pre-ejecución:** Invoca al agente desde el entorno que hayas escogido y sube tu CV. El sistema realizará la inspección semántica (VSI) automáticamente.
4. **Ejecución:** Copia y pega las vacantes al chat y CV-Pilot hará el resto.

## 🔜 Búsqueda de ofertas automática:
Así como el flujo n8n del CV-Pilot original, se implementará la búsqueda automática de ofertas para que el agente las analice y muestre las más compatibles. Esta funcionalidad se planea integrar próximamente.

---

## 🤝 Relación con el Proyecto Original
Este agente **no reemplaza** el flujo de trabajo de **[CV-Pilot (n8n)](https://github.com/Juliotamara23/CV-Pilot)**. Son herramientas complementarias:
- Utiliza la versión **n8n** para automatización de infraestructura masiva y procesos programados.
- Utiliza esta **versión Agente** para el análisis inteligente, redacción personalizada y toma de decisiones críticas en tiempo real.