# Script de Inicialización de Base de Datos - CV-Pilot
# Valida la instalación de sqlite3 e inicializa el esquema atómico.

if (-not (Get-Command sqlite3 -ErrorAction SilentlyContinue)) {
    Write-Error "SQLite3 no está instalado. Instálalo para continuar."
    exit 1
}

$db = "cv-pilot.db"

# Creación de tabla jobs
sqlite3 $db "CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, public_date TEXT, url TEXT, company TEXT, position TEXT, location TEXT, salary TEXT, description TEXT);"

# Creación de tabla analyses
sqlite3 $db "CREATE TABLE IF NOT EXISTS analyses (id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT, verdict TEXT, summary TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(job_id) REFERENCES jobs(id));"

Write-Host "Base de datos inicializada correctamente en $db" -ForegroundColor Green
