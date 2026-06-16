---
name: Skill Database Manager
description: Gestión del estado de las ofertas y persistencia de análisis mediante SQLite.
scope: GLOBAL
---

# Skill: Database Manager

## 1. Protocolo de Inicialización (Fallback Strategy)
Para garantizar la persistencia sin importar el entorno, el agente debe seguir estrictamente este orden:
1. **Intento Shell:** Ejecutar `bash ./scripts/init.sh`.
2. **Fallback:** Si el comando anterior falla o no es reconocido, ejecutar `python3 ./scripts/init.py`.
3. **Alerta:** Si ambos fallan, informar al usuario: "No he podido inicializar la base de datos. Asegúrate de tener SQLite CLI o Python 3 instalados."

## 2. Protocolos de Ejecución (Comandos)
- **Consultar vacantes nuevas:** `sqlite3 cv-pilot.db "SELECT * FROM jobs WHERE status = 'new';"`
- **Registrar nueva oferta:** `sqlite3 cv-pilot.db "INSERT OR IGNORE INTO jobs ..."`
- **Registrar veredicto:** `sqlite3 cv-pilot.db "INSERT INTO analyses ..."`

## 3. Reglas de Operación (Harness)
- **Atomicidad:** Cada operación es independiente.
- **Silencio Operativo:** NUNCA mostrar la sentencia SQL al usuario. Reportar el resultado de alto nivel (ej: "Trabajo guardado con éxito").
- **Integridad:** Verificar existencia de `job_id` antes de cada `UPDATE` o `INSERT` en la tabla `analyses`.
- **Transparencia:** Si una query falla (ej. base bloqueada), informar: "Hubo un error al acceder al historial. Verifica el estado de cv-pilot.db."
