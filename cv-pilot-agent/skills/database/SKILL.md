---
name: Skill Database Manager
description: Gestión del estado de las ofertas y persistencia de análisis mediante SQLite.
scope: GLOBAL
---

# Skill: Database Manager

## 1. Protocolo de Persistencia Atómica (Deduplicación)
El agente DEBE aplicar la lógica de deduplicación basada en "Business Key" antes de cualquier inserción:
- **Cálculo de Hash:** `job_hash = SHA256(company + position + location)`
- **Inserción Idempotente:**
  `sqlite3 cv-pilot.db "INSERT OR IGNORE INTO jobs (job_hash, indeed_id, public_date, url, company, position, location, salary, description, status) VALUES ('$hash', '...', '...', '...', '...', '...', '...', '...', '...', 'new');"`

## 2. Protocolo de Análisis y Registro
1. **Seleccionar pendientes:** `sqlite3 cv-pilot.db "SELECT * FROM jobs WHERE status = 'new';"`
2. **Actualizar estado:** `sqlite3 cv-pilot.db "UPDATE jobs SET status = 'analyzed' WHERE job_hash = '$hash';"`
3. **Registrar veredicto:** 
   - Generar UUID: `import uuid; str(uuid.uuid4())`
   - `sqlite3 cv-pilot.db "INSERT INTO analyses (analysis_id, job_hash, percentage, comparativa, observaciones, verdict, tldr) VALUES ('$uuid', '$hash', '...', '...', '...', '...', '...');"`

## 3. Reglas de Operación (Harness)
- **Silencio Operativo:** NUNCA mostrar sentencias SQL al usuario. Solo reportar el éxito o fallo de la operación en lenguaje natural.
- **Atomicidad:** No dejar conexiones abiertas.
- **Integridad:** Validar siempre que el `job_hash` exista en la tabla `jobs` antes de insertar en `analyses`.
- **Transparencia:** Si una operación falla, informar: "Hubo un error al gestionar el historial. Verifica la integridad del archivo cv-pilot.db."
