---
name: Skill Database Manager
description: Gestión del estado de las ofertas y persistencia de análisis mediante SQLite.
scope: GLOBAL
---

# Skill: Database Manager

## 1. Esquema de Persistencia
El agente debe gestionar dos tablas en `cv-pilot.db`:
- **jobs**: Estado de la oferta (`new`, `analyzed`, `discarded`).
- **analyses**: Historial de veredictos (Foreign Key a `jobs`).

## 2. Protocolos de Ejecución (Comandos Bash/SQLite)

### Consultar ofertas pendientes
`sqlite3 cv-pilot.db "SELECT * FROM jobs WHERE status = 'new';"`
- Úsalo antes de iniciar el análisis técnico.

### Registrar nueva oferta (Deduplicación)
`sqlite3 cv-pilot.db "INSERT OR IGNORE INTO jobs (id, public_date, url, company, position, location, salary, description) VALUES ('...', '...', '...', '...', '...', '...', '...', '...');"`
- **Regla:** Usar `INSERT OR IGNORE` para evitar duplicar ofertas si el scraper las trae de nuevo.

### Registrar veredicto
`sqlite3 cv-pilot.db "UPDATE jobs SET status = 'analyzed' WHERE id = '...';"`
`sqlite3 cv-pilot.db "INSERT INTO analyses (job_id, verdict, summary) VALUES ('...', '...', '...');"`

## 3. Reglas de Operación (Harness)
- **Atomicidad:** Cada interacción es una operación aislada. No dejar la base abierta.
- **Silencio Operativo:** NUNCA mostrar la sentencia SQL al usuario. Reportar el resultado de alto nivel (ej: "Vacante registrada con éxito").
- **Integridad:** Siempre verificar que el `job_id` exista antes de intentar un UPDATE.
- **Transparencia:** Si una query falla (ej. base de datos bloqueada o inexistente), informar al usuario: "Hubo un error al guardar el registro. Verifica el estado de la base de datos."
