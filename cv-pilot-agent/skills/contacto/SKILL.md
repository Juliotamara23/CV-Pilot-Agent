---
name: Skill Contacto
description: Extracción de email de contacto de la oferta y auto-sanación de campos del perfil.
scope: SOURCING_PHASE
---

# Skill: Contacto y Extracción

## Detección de Método de Postulación
1. **Detección de Email:**
   - Regex: `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}`
   - Si encuentra email → retornar el email. La oferta permite postulación por correo.
   - Si NO hay match → retornar: `PORTAL_POSTULATION`. La oferta requiere postularse en la plataforma (portal web).
2. **Auto-Sanación de Perfil:**
   - Si `data/perfil.md` tiene campos de contacto vacíos, escanear el contexto buscando:
     - LinkedIn: `linkedin\.com/in/[a-zA-Z0-9_-]+`
     - GitHub: `github\.com/[a-zA-Z0-9_-]+`
     - Teléfono: `\+?\d{1,3}[\s-]?\d{7,10}`
   - Si encuentra match, actualizar `data/perfil.md`.

## Esquema de Salida
```
Email detectado → "rrhh@empresa.com"
Sin email → "PORTAL_POSTULATION"
```

## Instrucciones para el Orquestador
- Usar el resultado de esta skill en `skills/formatos/SKILL.md` para decidir qué opciones de postulación mostrar (correo vs carta de presentación).
- Si la extracción falla y no es posible la auto-sanación, informar al usuario el campo faltante.
## Scripts de Respaldo
*(Vacío — si un script generado resuelve un vacío permanente, se documenta aquí con su propósito y uso.)*
