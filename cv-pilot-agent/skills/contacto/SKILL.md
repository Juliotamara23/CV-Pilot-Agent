---
name: Skill Contacto
description: Extracción por Regex y gestión de hipervínculos de contacto.
scope: SOURCING_PHASE
---

# Skill: Contacto y Extracción

## ATENCIÓN: PROHIBIDO CITAR ESTE ARCHIVO
Este archivo es una herramienta de proceso, NO una base de conocimiento técnico. NUNCA lo cites para fundamentar análisis.

## Protocolos de Extracción
1. **Detección de Destinatario:**
   - Regex: `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}`
   - Si no hay match, retornar: `PORTAL_POSTULATION`
2. **Auto-Sanación (Prioridad 2):**
   - Si el perfil del usuario tiene campos vacíos, escanea el contexto (RAG) buscando:
     - LinkedIn: `linkedin\.com/in/[a-zA-Z0-9_-]+`
     - GitHub: `github\.com/[a-zA-Z0-9_-]+`
     - Teléfono: `\+?\d{1,3}[\s-]?\d{7,10}`
   - Si encuentra match, actualiza `{CV-Candidato-Activo}` internamente.

## Esquema de Salida Esperado
```json
{
  "email": "destinatario@empresa.com | PORTAL_POSTULATION",
  "linkedin": "url_link",
  "github": "url_link",
  "telefono": "numero"
}
```

## Ejemplos de Interacción (Few-Shot)
- **Input:** "Envía tu CV a recursoshumanos@empresa.com"
- **Acción:** Extracción email.
- **Output:** `{"email": "recursoshumanos@empresa.com"}`

- **Input:** "Aplica en nuestra web"
- **Acción:** Detección de ausencia de email.
- **Output:** `{"email": "PORTAL_POSTULATION"}`

## Instrucciones de Manejo de Errores
- Si la extracción falla o el dato no existe y no es posible la auto-sanación, retornar un error específico de campo faltante para que el orquestador dispare la "Regla de Información Completa".