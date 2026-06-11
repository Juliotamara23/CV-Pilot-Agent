---
name: Email & Contact Skill
description: Extracción por Regex y gestión de hipervínculos de contacto.
scope: RESTRICTED_TO_PROTOCOL_3
version: 1.5
---

# Herramientas de Extracción

## ATENCIÓN: PROHIBIDO CITAR ESTE ARCHIVO
Este archivo es una herramienta de proceso, NO una base de conocimiento técnico. NUNCA lo cites para fundamentar análisis de habilidades (Java, Spring, React, etc.). Úsalo solo para la lógica de correos.

## Detección de Destinatario y Origen
- **Regex Email:** `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}`
- **Regex URL:** `https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)`
- **Lógica de Procesamiento (Proactiva):** 
    1. Escanear todo el texto de entrada EN EL MOMENTO DEL ANÁLISIS (Protocolo 1).
    2. Si hay email: Etiquetar vacante como "Aplicación vía Email".
    3. Si NO hay email: Etiquetar vacante como "Aplicación vía Portal".
    4. Esta etiqueta debe guardarse en la memoria de la sesión para el Protocolo 3.
- **Prohibido:** Inventar correos corporativos o asumir destinos. Si no es explícito, es Portal/Manual.

## Firma de Contacto (Links Dinámicos)
Extrae de {CV-Candidato-Activo}:
- **WhatsApp:** `https://wa.me/{{CV-Candidato-Activo.telefono}}`
- **Teléfono:** `tel:{{CV-Candidato-Activo.telefono}}`
- **LinkedIn:** [LinkedIn]({{CV-Candidato-Activo.linkedin}})
- **GitHub:** [GitHub]({{CV-Candidato-Activo.github}})
- **Regla de Información Completa:** Ver sección homónima en `AGENTS.md`.

## Protocolo de Auto-Sanación (Prioridad 2)
Si un campo requerido en {CV-Candidato-Activo} está vacío:
1. Escanear el texto del CV disponible en el contexto (RAG).
2. Aplicar los siguientes patrones Regex para rellenar el dato faltante de forma silenciosa:
    - LinkedIn: `linkedin\.com/in/[a-zA-Z0-9_-]+`
    - GitHub: `github\.com/[a-zA-Z0-9_-]+`
    - Teléfono/WhatsApp: `\+?\d{1,3}[\s-]?\d{7,10}`
3. Si la extracción es exitosa, actualizar el objeto de identidad SILENCIOSAMENTE.
4. Si la extracción falla o devuelve null, aplicar la "Regla de Información Completa" (detener flujo y solicitar al usuario).