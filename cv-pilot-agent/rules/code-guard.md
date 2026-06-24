---
name: Regla de Generación de Código
description: Define cuándo y cómo el agente puede generar código como último recurso.
scope: GLOBAL
---

# Safe Guard: Generación de Código

## Regla general
CV-Pilot resuelve tareas usando las skills existentes. La generación de código es el **último recurso**, solo cuando ninguna skill puede resolver la tarea.

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
- NUNCA modificar scripts existentes del sistema (`init.py`, `pdf_parser.py`, `setup.ps1`, `setup.sh`).
- NUNCA modificar skills existentes (`skills/*/SKILL.md`). Las skills son estáticas y diseñadas por el usuario. Si detectas una mejora necesaria, infórmala, no la apliques.
- NUNCA generar código por iniciativa propia sin informar al usuario primero.
