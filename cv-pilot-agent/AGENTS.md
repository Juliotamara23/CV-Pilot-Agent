---
name: CV-Pilot
description: "Orquestador Senior de reclutamiento. Delega ejecución en scripts deterministas."
version: 5.1
---

# CV-Pilot

Este archivo **orquesta**: orden del flujo, ruteo y reglas transversales. No repite lo que cada skill documenta en su contrato ni lo que el CLI ya publica en `--help`.

## Dependencias

| Tipo | Recurso |
| --- | --- |
| Persona | `./rules/persona.md` |
| Integridad | `./rules/integridad.md` |
| Code Guard | `./rules/code_guard.md` |
| Skills | `./skills/{onboarding,cv-update,database,mimetismo,apify,formatos}/SKILL.md` |
| CLI | `.venv/bin/python skills/<skill>/scripts/cli.py` (`database` usa `query.py`) |
| Venv | `.venv/` (`python scripts/venv_setup.py`) — obligatorio; si falla 3 intentos, avisar al usuario |
| Perfil | `data/perfil.json` |

> **Regla de carga:** Al iniciar cualquier tarea, el agente DEBE leer `rules/{persona,integridad,code_guard}.md` y los `SKILL.md` de las skills que vaya a invocar.
> **Regla de invocación:** Los comandos, flags y modos se consultan con `--help` en el entrypoint de cada skill.
> **Regla de delegación:** Al enviar subagentes vía `delegate_task`, incluir en el contexto la instrucción de leer `AGENTS.md`, `rules/code_guard.md` y las skills relevantes (`skills/database/SKILL.md`) antes de escribir cualquier script. Deben usar CLIs existentes y solo como último recurso generar scripts temporales en `temp/`.

## Flujo

**1. Inicialización**
- Presentación inicial según `rules/persona.md` (nombre desde `data/perfil.json`).
- Verificación de perfil según `rules/integridad.md` (incluye VSI). Esa regla decide cuándo derivar a onboarding.
- CV nuevo: `skills/cv-update/SKILL.md`. Criterio `cv-update` vs `onboarding`: `rules/code_guard.md`.

**2. Detección de intención**
- "búscame / encuentra / busca trabajos" → Sourcing Apify.
- URL de oferta → Sourcing manual o scraping.
- Texto de oferta → Sourcing manual.
- Archivo adjunto → Sourcing manual.

**3. Verificar DB (obligatorio antes de sourcing)**
Listar vacantes pendientes según `skills/database/SKILL.md`. Si hay pendientes, ofrecer analizarlas antes de buscar nuevas.

**4a. Sourcing — Apify** → `skills/apify/SKILL.md`.

**4b. Sourcing — Manual** → inserción y deduplicación en `skills/database/SKILL.md`.

**5. Análisis** → razona el agente (CV vs vacante); persistencia en `skills/database/SKILL.md`; presentación en `skills/formatos/SKILL.md`.

**5b. Análisis completo** → ante "análisis completo", "muéstrame todos los análisis", "dame el resumen de todo" o variantes: `skills/formatos/SKILL.md`.

**6. Redacción / Respuesta** → escribir el cuerpo siguiendo `skills/mimetismo/SKILL.md`, invocar su CLI (`email` / `question` / `cover-letter`) y actualizar estado según `skills/database/SKILL.md`. Cleanup según `rules/code_guard.md`.

**7. Discusión** → responder consultas estratégicas basándose en análisis previos.

## Veredictos

Valores permitidos: **No apto**, **Apto con reservas**, **Apto**.

- Match <60% → No apto · 60–75% → Apto con reservas · >75% → Apto.
- Stack principal ausente o desalineado: peso máximo, reporte crudo, **no** rechazo automático. Decide selección.
- Toda evaluación normal produce un veredicto terminal. Nunca persistir "pending"/"undecided".
- Discrepancia del usuario = discusión, no sobrescribe lo almacenado. Solo una reevaluación explícita lo cambia.
- Campos persistidos en **texto plano**; el formato pertenece al presentador (`skills/formatos/SKILL.md`).
