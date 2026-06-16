---
name: Skill Database Manager
description: Gestión del estado de las ofertas y persistencia de análisis mediante SQLite.
scope: GLOBAL
---

# Skill: Database Manager

## 1. Protocolo de Inicialización
Para garantizar la persistencia sin importar el entorno:
1. Ejecutar `python3 ./scripts/init.py`.
2. Si falla, avisar: "No he podido inicializar la base de datos. Asegúrate de tener Python 3 instalado."

## 2. Deduplicación (Business Key)
Antes de insertar, el agente DEBE calcular: `job_hash = SHA256(company + position + location)`.
- **Comando Inserción:** `sqlite3 cv-pilot.db "INSERT OR IGNORE INTO jobs (job_hash, indeed_id, public_date, url, company, position, location, salary, description) VALUES ('...', '...', ...);"`

## 3. Protocolos de Ejecución
- **Consultar vacantes nuevas:** `sqlite3 cv-pilot.db "SELECT * FROM jobs WHERE status = 'new';"`
- **Registrar veredicto:** `sqlite3 cv-pilot.db "INSERT INTO analyses (job_hash, verdict, summary) VALUES ('...', '...', '...');"`
- **Actualizar estado:** `sqlite3 cv-pilot.db "UPDATE jobs SET status = 'analyzed' WHERE job_hash = '...';"`

## 4. Reglas de Operación (Harness)
- **Silencio Operativo:** NUNCA mostrar queries al usuario. Reportar resultados finales.
- **Integridad:** Validar `job_hash` antes de actualizar `analyses`.
- **Transparencia:** Si una query falla, informar: "Hubo un error al gestionar el historial. Verifica el archivo cv-pilot.db."
