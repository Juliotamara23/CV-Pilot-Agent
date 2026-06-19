---
name: Skill Database Manager
description: Gestión del estado de las ofertas y persistencia de análisis mediante SQLite.
scope: GLOBAL
---

# Skill: Database Manager

## 0. Requisitos

- **SQLite CLI** (`sqlite3`) — necesario para operaciones directas desde consola.
- Compatible con Windows (PowerShell), Linux y macOS (bash).

### Protocolo de instalación (consentimiento obligatorio)

El agente NUNCA instala sqlite3 sin permiso explícito. Seguir este protocolo:

1. **Detectar** si `sqlite3` está disponible (ver detección cross-platform abajo).
2. **Si no está disponible → informar al usuario:**
   > "SQLite CLI no está instalado. Es necesario para operaciones de base de datos.
   > ¿Desea que lo instale automáticamente o prefiere hacerlo manualmente?"
3. **Según la respuesta:**
   - Si acepta instalación automática → ejecutar comando según el OS detectado.
   - Si prefiere hacerlo manual → mostrar los comandos de instalación para su OS.
   - Si dice que no → cancelar la operación que requiere la DB.

### Detección cross-platform

```powershell
# PowerShell (Windows)
$sqlite = if (Get-Command sqlite3 -ErrorAction SilentlyContinue) {
    "sqlite3"
} else {
    # Ruta fallback si winget instaló pero no actualizó PATH
    "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\SQLite.SQLite_Microsoft.Winget.Source_8wekyb3d8bbwe\sqlite3.exe"
}
```

```bash
# bash (Linux / macOS)
SQLITE=$(command -v sqlite3 || echo "")
if [ -z "$SQLITE" ]; then
  echo "sqlite3 no está instalado"
else
  echo "sqlite3 encontrado en: $SQLITE"
fi
```

### Instalación por OS (solo con consentimiento)

| OS | Comando |
|----|---------|
| Windows (winget) | `winget install -e --id SQLite.SQLite` |
| macOS (Homebrew) | `brew install sqlite3` |
| Debian/Ubuntu | `sudo apt install sqlite3` |
| Fedora | `sudo dnf install sqlite` |
| Arch Linux | `sudo pacman -S sqlite` |
| Alpine | `apk add sqlite` |

> **Nota Windows:** Después de winget, reiniciar la terminal o usar la ruta completa de fallback (ver detección arriba).

### Regla crítica: separador

**Siempre** usar `-separator "@@"` en todos los comandos CLI, sin importar el OS. El separador por defecto de sqlite3 (`|`) causa dos problemas:
1. **Pipe en datos:** las descripciones de vacantes contienen `|` que rompe el parsing del resultado.
2. **Encoding:** PowerShell y algunas terminales interpretan pipes en la salida, corrompiendo caracteres UTF-8 como ñ o tildes.

Usar `@@` como separador evita ambos problemas en simultáneo.

### Patterns de consulta CLI

```powershell
# PowerShell — leer un campo individual
$campo = & $sqlite -separator "@@" $db "SELECT field FROM table WHERE condition;"

# PowerShell — leer múltiples campos y dividirlos
$result = & $sqlite -separator "@@" $db "SELECT field1, field2 FROM table;"
$partes = $result -split "@@"
# $partes[0] = field1, $partes[1] = field2
```

```bash
# bash — leer un campo individual
campo=$(sqlite3 -separator "@@" "$db" "SELECT field FROM table WHERE condition;")

# bash — leer múltiples campos y dividirlos
result=$(sqlite3 -separator "@@" "$db" "SELECT field1, field2 FROM table;")
IFS="@@" read -r f1 f2 <<< "$result"
# $f1 = field1, $f2 = field2
```

> **Nota para Linux/Mac:** En estos sistemas `sqlite3` suele estar en PATH por defecto o es fácil de instalar. No requiere ruta fallback.

## 1. Ubicación de la DB
`cv-pilot-agent/db/cv-pilot.db`

## 2. Normalización de Inputs
El agente DEBE normalizar los campos antes de cualquier operación. Los alias (snake_case) permiten mapear desde cualquier fuente (Apify, texto manual, URL):

| Input Key o Alias | DB Column | Regla |
|---|---|---|
| `company` / `company_name` / `empresa` | company | Strip whitespace, title case |
| `position` / `position_name` / `title` / `cargo` | position | Strip whitespace |
| `location` / `ubicacion` / `locality` | location | Strip whitespace |
| `salary` / `salario` / `compensation` | salary | Strip whitespace, preserving original format |
| `description` / `descripcion` / `body` | description | Preserve as-is |
| `url` / `link` / `source_url` | url | Validate URL format |
| `id` / `indeed_id` / `ref_id` / `external_id` | external_id | Strip whitespace |
| `posted_at` / `public_date` / `postedAt` / `fecha` | public_date | Preserve as-is |
| `source` | source | `'manual'`, `'apify-indeed'`, `'apify-linkedin'`, `'apify-computrabajo'` (default: `'manual'`) |

## 3. Deduplicación (Business Key)
Calcular hash antes de insertar:
```
job_hash = SHA256(normalized_company + normalized_position + normalized_location)
```

## 4. Templates de Inserción (Parametrizados)

### Insertar job (idempotente)
```python
INSERT OR IGNORE INTO jobs (job_hash, external_id, public_date, url, company, position, location, salary, description, status, source)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?)
```

### Insertar análisis
```python
INSERT INTO analyses (analysis_id, job_hash, percentage, comparativa, observaciones, verdict, tldr)
VALUES (?, ?, ?, ?, ?, ?, ?)
```

### Actualizar estado del job
```python
UPDATE jobs SET status = 'analyzed' WHERE job_hash = ?
```

## 5. Selección de Pendientes
```python
SELECT * FROM jobs WHERE status = 'new'
```

## 6. Persistencia de Análisis
1. Generar UUID: `str(uuid.uuid4())`
2. Ejecutar INSERT en `analyses` con los 7 campos
3. Ejecutar UPDATE en `jobs` para marcar `status = 'analyzed'`
4. Validar que `job_hash` exista antes de insertar en `analyses`

## 7. Manejo de Errores

| Error | Mensaje al Usuario |
|-------|-------------------|
| DB no encontrada | "No se encontró la base de datos. Ejecutá la inicialización primero." |
| sqlite3 CLI no instalado | "SQLite CLI no está instalado. ¿Desea que lo instale automáticamente o prefiere hacerlo manualmente?" (seguir protocolo de consentimiento) |
| Error de escritura | "Error al guardar. Verificá permisos o espacio en disco." |
| Error de consulta | "Error al consultar la base de datos." |
| Duplicado | Omitir silenciosamente (INSERT OR IGNORE) |

## 8. Reglas de Operación
- **Silencio Operativo:** NUNCA mostrar sentencias SQL al usuario. Solo reportar éxito o fallo en lenguaje natural.
- **Atomicidad:** No dejar conexiones abiertas. Siempre cerrar después de cada operación.
- **Integridad:** Validar que `job_hash` exista en `jobs` antes de insertar en `analyses`.
