<h1 align="center">🤖 CV-Pilot Agentic Evolution</h1>

**CV-Pilot Agent** es un orquestador inteligente de reclutamiento diseñado para ejecutarse de forma **agnóstica** en cualquier entorno que soporte agentes (OpenCode, ChatGPT, Claude Desktop, Ollama, etc.).

Este agente es la evolución lógica del sistema original **[CV-Pilot (n8n Workflow)](https://github.com/Juliotamara23/CV-Pilot)**. Mientras que la versión original se centra en flujos de automatización de infraestructura en n8n, esta versión se enfoca en el **razonamiento autónomo y la validación semántica**.

## 📖 Manual de Usuario
Para instrucciones detalladas sobre cómo configurar tu entorno, subir tu CV y configurar tu identidad profesional para una experiencia personalizada, consulta el [Manual de Usuario](USER_GUIDE.md).

## 🧠 Arquitectura Agéntica
A diferencia de un workflow rígido, este agente utiliza **protocolos de toma de decisiones** que se adaptan al entorno donde se ejecuten:

- **Plataforma Agnostic:** No requiere APIs específicas pre-configuradas en un servidor n8n. Utiliza la capacidad de razonamiento del LLM conectado para evaluar el CV y decidir el siguiente paso.
- **Validación Semántica de Identidad (VSI):** El agente entiende qué es un CV profesional y qué no, rechazando documentos irrelevantes antes de consumir tokens o tiempo.
- **Protocolo de Auto-Sanación:** Si faltan datos en el contexto de la sesión, el agente escaneará activamente el documento (RAG) para extraer información faltante de forma silenciosa.
- **Mimetismo Estratégico:** Aprende tu estilo de escritura a partir de ejemplos reales para redactar correos de postulación que suenan a ti, no a una plantilla genérica.
- **Memoria Persistente:** Gracias al protocolo Engram, el agente recuerda decisiones pasadas, lo que permite que cada interacción sea más precisa que la anterior.

## 🛠️ Estructura Técnica
El agente opera bajo una lógica de orquestación rigurosa definida en:
- `AGENTS.md`: Orquestador principal.
- `rule-*.md`: Reglas de comportamiento e integridad.
- `skill-*.md`: Herramientas tácticas (contacto, redacción, formatos).

## 🤝 Relación con el Proyecto Original
Este agente **no reemplaza** el flujo de trabajo de **[CV-Pilot (n8n)](https://github.com/Juliotamara23/CV-Pilot)**. Son herramientas complementarias:
- Utiliza la versión **n8n** para automatización de infraestructura masiva y procesos programados.
- Utiliza esta **versión Agente** para el análisis inteligente, redacción personalizada y toma de decisiones críticas en tiempo real.

