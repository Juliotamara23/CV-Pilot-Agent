---
name: Regla de Generación de Código
description: Define cuándo y cómo el agente puede generar código como último recurso.
scope: GLOBAL
---

# Safe Guard: Generación de Código

> ⚠️ **Esta regla aplica ÚNICAMENTE a CV-Pilot (el agente en producción).**  
> Los developers del proyecto modifican código, scripts, skills y schema libremente como parte del desarrollo.  
> CV-Pilot NUNCA debe modificar estos archivos por iniciativa propia.

## Regla general
CV-Pilot resuelve tareas usando los scripts existentes (`query.py`, `pdf_parser.py`, etc.). La generación de código es el **último recurso**, solo cuando ningún script puede resolver la tarea.

## Niveles de decisión

```
¿Puede resolverse con skills existentes?
  ├─ Sí → Usarlas. No generar código.
  └─ No → ¿Es escribiendo un script la única forma?
           ├─ Sí → Informar al usuario y pedir aprobación.
           │        "Necesito generar un script para [tarea]. ¿Procedo?"
           │        ├─ Usuario aprueba → Generar, ejecutar, evaluar:
           │        │   ├─ Éxito + reutilizable → Guardar en scripts/ + documentar en la skill
           │        │   └─ Éxito + temporal → Borrar tras completar la tarea
           │        └─ Usuario rechaza → Informar que no se puede resolver.
           └─ No → Informar al usuario que la tarea está fuera del alcance.
```

## Scripts reutilizables
Si un script generado resuelve un vacío permanente en una skill, el agente DEBE:
1. Guardarlo en `scripts/` con nombre descriptivo.
2. Agregar una referencia en la sección "Scripts de Respaldo" de la skill correspondiente.
3. Documentar qué problema resuelve y cuándo se debe usar.

## Scripts temporales
Si un script es un parche único para un caso puntual, el agente DEBE:
1. Ejecutarlo y verificar que la tarea se completó.
2. Borrarlo inmediatamente después.
3. No modificar ninguna skill.

## Restricciones absolutas
- NUNCA ejecutar código generado sin aprobación explícita del usuario.
- NUNCA modificar scripts existentes del sistema (`init.py`, `pdf_parser.py`, `setup.ps1`, `setup.sh`, `cleanup.py`).
- NUNCA modificar skills existentes (`skills/*/SKILL.md`). Las skills son estáticas y diseñadas por el usuario. Si detectas una mejora necesaria, infórmala, no la apliques.
- NUNCA inventar estados de vacante. Solo usar los 5 definidos en `skills/database/SKILL.md`: new, analyzed, discarded, applied, rejected.

## Lecciones aprendidas

### Incidente: Improvisación de código de extracción de CV (2026-07-13)

Un agente improvisó código nuevo para extraer información del CV en vez de reutilizar `pdf_parser.extract()`. Resultado: el campo custom `pdf_soporte: true` en `data/preferencias.md` quedó en riesgo de sobrescritura.

**Regla:** Si necesitás re-extraer info del CV, usá la skill `cv-update`, nunca re-ejecutes `onboarding full` ni improvises código de extracción.

**Principio:** Onboarding ≠ Actualizador. Ambos comparten SOLO la interfaz PDF→MD (`pdf_parser.extract()` + `parser.parse_text()`). Cada uno tiene su responsabilidad única (SRP).

### Regla: cv-update es reescritura completa, no merge (2026-07-14)

Mezclar información de CVs distintos viola fidelidad ATS. Un ATS real (Workday/Greenhouse/Lever) solo conoce el CV enviado en cada postulación. Mezclar campos de un CV anterior genera evaluaciones infladas para RRHH.

**Regla:** `cv-update` reescribe `perfil.md` desde cero con cada nuevo CV. NO preserva campos del perfil viejo. Cada perfil.md es una instantánea independiente del último CV procesado.

## Archivos temporales
- Todo archivo temporal (borradores de correo, código generado, respuestas de scraping, etc.) DEBE guardarse en `cv-pilot-agent/temp/`. Nunca en otra ubicación.
- Al completar la tarea, el agente DEBE ejecutar `python scripts/cleanup.py` para eliminar todo el contenido de `temp/`.
- Si la tarea falla o es cancelada, el agente DEBE ejecutar `cleanup.py` igualmente antes de responder al usuario.
- El usuario nunca debe ver ni preocuparse por archivos temporales.
