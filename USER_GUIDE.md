<h1 align="center">📘 Manual de Usuario: CV-Pilot Agent</h1>

**CV-Pilot** es un orquestador inteligente de reclutamiento diseñado para evaluar tu perfil técnico con rigor y gestionar tus postulaciones con estrategia.

## 🚀 Inicio Rápido

1. **Configuración Inicial:** 
   - Abre `rule-identidad.md` y `ejemplo-correos.md` en la raíz.
   - Completa tus datos personales y añade ejemplos de cómo escribes.
   - **IMPORTANTE:** Sube estos archivos a la sección de "Conocimiento" (Knowledge) de tu Gem.

2. **Ejecución:**
   - Inicia un chat y sube tu **CV profesional en PDF**.
   - CV-Pilot realizará una **Validación Semántica (VSI)** inmediata. Si el documento no es un CV profesional, el agente te lo indicará.

3. **Análisis de Vacantes:**
   - Pega la descripción de cualquier oferta de empleo.
   - El agente analizará las brechas técnicas contra tu perfil y te entregará un informe detallado con un veredicto (**Apto / No apto**).

## 🛠️ ¿Cómo interactuar con el agente?

- **Gestión de Postulaciones:** Si la oferta tiene email, el agente te dará un enlace directo (`mailto:`) y el borrador formal. Si es un portal, te entregará una "Carta de presentación" optimizada para copiar y pegar en formularios web.
- **Modo Discusión (Mentor):** Tras cualquier análisis, puedes elegir la opción "Discusión". En este modo, el agente deja de ser un generador de informes y pasa a ser tu mentor senior para asesorarte estratégicamente.

## 🛡️ Reglas de Oro

- **Privacidad Total:** Si buscas privacidad absoluta, puedes montar todo CV-Pilot utilizando LLMs locales (ej. mediante Ollama o LM Studio) para que ningún dato personal salga de tu infraestructura.
- **Fidelidad Técnica:** El agente no suaviza brechas. Si no tienes el stack requerido, el reporte te mostrará el riesgo crítico de forma cruda y sin rodeos.
- **Transparencia:** Toda la evaluación se basa exclusivamente en tu CV y la descripción de la oferta.

---
*¿Tienes dudas? Simplemente pregunta al agente y él te guiará.*
