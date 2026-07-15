# Plan de Evolución: CV-Pilot Generalista

Este plan detalla los pasos para transformar CV-Pilot de un agente especializado en tecnología a un orquestador de reclutamiento generalista, manteniendo su rigor senior.

## 🎯 Objetivo
Hacer que CV-Pilot evalúe perfiles y vacantes de cualquier sector (Geología, Derecho, Finanzas, etc.) eliminando la dependencia rígida de terminología de software (ej. "Stack tecnológico", "TDD", "Docker").

## 🗺️ Mapa de Ruta (Roadmap)

### Fase 1: Abstracción de Terminología (Refactorización)
- **AGENTS.md:** Cambiar "Análisis Técnico" por "Análisis de Competencias".
- **skill-formatos.md:** Renombrar secciones de "Comparativa Técnica" a "Análisis de Perfil".
- **skill-redaccion.md:** Generalizar "Logro técnico" a "Logro profesional".
- **rule-persona.md:** Asegurar que el tono "implacable" no dependa de términos de desarrollo (ej. evitar referencias a código, centrarse en resultados de negocio).

### Fase 2: Detección Dinámica de Dominio (Paso 0)
- Actualizar la lógica de VSI para que el agente primero detecte el *sector* de la vacante (ej: Geología, Medicina, Marketing).
- El agente ajustará su criterio de evaluación basado en el *sector* detectado, en lugar de aplicar una plantilla estática.

### Fase 3: Adaptación del Mimetismo
- Refinar el `ejemplo-correos.md` para que incluya ejemplos de diferentes sectores, o implementar un sistema donde el agente solicite ejemplos específicos del dominio del usuario si este no es técnico.

---

## 🧪 Pruebas de Validación del Enfoque Generalista
Para validar esta fase, realizaremos los siguientes escenarios de test:
1. **Escenario Geo:** Vacante de "Geólogo Senior" + CV de Geología (Verificar que no pida TDD o Python).
2. **Escenario Legal:** Vacante de "Abogado Corporativo" + CV de Derecho (Verificar que se centre en jurisprudencia y no en "Backend").

---
*Este plan queda registrado aquí para futuras implementaciones sin saturar el contexto actual del agente.*
