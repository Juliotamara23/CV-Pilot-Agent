#!/usr/bin/env python3
"""Scenario 06: Full Apify flow simulation"""
import json
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'cv-pilot.db')

# ============================================================
# STEP A: Environment verification
# ============================================================
print("=" * 60)
print("PASO 0: VERIFICACION DE ENTORNO (init.sh)")
print("=" * 60)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cursor.fetchall()]
print("  DB path: %s" % os.path.abspath(DB_PATH))
print("  Tablas detectadas: %s" % ", ".join(tables))
if 'jobs' in tables and 'analyses' in tables:
    print("  Estado: DB Ready")
else:
    print("  Estado: DB Initialized (tablas creadas)")

# ============================================================
# STEP B: Apify Cost Wizard
# ============================================================
print()
print("=" * 60)
print("PASO 1: WIZARD DE COSTOS (Apify)")
print("=" * 60)

# Simulated actor info
actor_id = "misceres/indeed-scraper"
cost_per_item = 0.0024
max_items = 5
total_cost = max_items * cost_per_item

print("  Actor consultado: %s" % actor_id)
print("  Costo por job listing: $%.4f USD" % cost_per_item)
print("  Cantidad solicitada: %d" % max_items)
print("  Costo estimado: $%.4f USD" % total_cost)
print()
print("  -> Informando al usuario:")
msg = "Para buscar %d empleos, el costo estimado es de $%.4f USD. Confirmas la ejecucion?" % (max_items, total_cost)
print("     '%s'" % msg)
print("  -> USUARIO CONFIRMA")

# ============================================================
# STEP C: Execute Apify call (simulated)
# ============================================================
print()
print("=" * 60)
print("PASO 2: EJECUCION APIFY CALL")
print("=" * 60)

search_input = {
    "position": "Desarrollador Junior",
    "country": "Colombia",
    "location": "Bogota",
    "maxItemsPerSearch": max_items,
    "parseCompanyDetails": True,
    "saveOnlyUniqueItems": True,
    "followApplyRedirects": False
}

print("  Input construido:")
print("  %s" % json.dumps(search_input, indent=4, ensure_ascii=False))
print()
print("  Comando ejecutado:")
cmd = "apify call misceres/indeed-scraper -i '%s' --output-dataset --json --silent" % json.dumps(search_input)
print("  %s" % cmd)
print()
print("  -> Informando al usuario:")
print("     'Iniciando busqueda automatizada. Esto tardara unos minutos, te avisare al terminar.'")
print()
print("  [SIMULACION] Dataset recibido de Apify...")

# ============================================================
# STEP D: Process Apify JSON response
# ============================================================
print()
print("=" * 60)
print("PASO 3: PROCESAMIENTO DE RESPUESTA APIFY")
print("=" * 60)

apify_response = [
    {
        "id": "apify-001",
        "title": "Desarrollador Full Stack Junior",
        "companyName": "TechCorp Colombia",
        "location": "Bogota, Colombia",
        "description": "Buscamos desarrollador Full Stack Junior con experiencia en React, Node.js y bases de datos PostgreSQL. Conocimientos en TypeScript deseables. Trabajo hibrido 3 dias en oficina.",
        "url": "https://co.indeed.com/viewjob?jk=abc123",
        "salary": "2,500,000 - 3,500,000 COP/mes",
        "pubDate": "2026-06-15"
    },
    {
        "id": "apify-002",
        "title": "Ingeniero de Software Junior",
        "companyName": "DataFlow SA",
        "location": "Medellin, Colombia",
        "description": "Ingeniero de software junior para equipo de backend. Python, Django, PostgreSQL. Experiencia con Docker deseable. Remoto.",
        "url": "https://co.indeed.com/viewjob?jk=def456",
        "salary": "3,000,000 - 4,000,000 COP/mes",
        "pubDate": "2026-06-14"
    },
    {
        "id": "apify-003",
        "title": "Programador Junior",
        "companyName": "InnovateTech",
        "location": "Cali, Colombia",
        "description": "Programador junior para desarrollo de APIs RESTful. Node.js, Express, MongoDB. Conocimientos en Git. Presencial zona norte.",
        "url": "https://co.indeed.com/viewjob?jk=ghi789",
        "salary": "2,000,000 - 2,800,000 COP/mes",
        "pubDate": "2026-06-13"
    },
    {
        "id": "apify-004",
        "title": "Desarrollador Backend Junior",
        "companyName": "CloudSys Colombia",
        "location": "Bogota, Colombia",
        "description": "Backend developer junior. Python, FastAPI, PostgreSQL. Experiencia con AWS o GCP. Trabajo remoto con reuniones semanales.",
        "url": "https://co.indeed.com/viewjob?jk=jkl012",
        "salary": "3,200,000 - 4,200,000 COP/mes",
        "pubDate": "2026-06-12"
    },
    {
        "id": "apify-005",
        "title": "Ingeniero de Sistemas Junior",
        "companyName": "SoftDev Group",
        "location": "Barranquilla, Colombia",
        "description": "Ingeniero de sistemas junior para soporte y desarrollo. SQL, Python, documentacion tecnica. Hibrido.",
        "url": "https://co.indeed.com/viewjob?jk=mno345",
        "salary": "2,800,000 - 3,800,000 COP/mes",
        "pubDate": "2026-06-11"
    }
]

print("  Vacantes recibidas: %d" % len(apify_response))
print()

# Validate integrity
required_fields = ["title", "companyName", "location", "description"]
all_valid = True
for i, job in enumerate(apify_response):
    missing = [f for f in required_fields if f not in job or not job[f]]
    if missing:
        print("  WARNING: Vacante %d sin campos: %s" % (i+1, missing))
        all_valid = False

if all_valid:
    print("  Integridad del dataset: OK")
else:
    print("  Integridad del dataset: WARNINGS")

print()
print("  Vacantes encontradas:")
for i, job in enumerate(apify_response, 1):
    print("    %d. %s @ %s (%s)" % (i, job["title"], job["companyName"], job["location"]))

# ============================================================
# STEP E: Persist to SQLite
# ============================================================
print()
print("=" * 60)
print("PASO 4: PERSISTENCIA EN SQLite")
print("=" * 60)

inserted = 0
for job in apify_response:
    try:
        cursor.execute(
            "INSERT OR IGNORE INTO jobs (id, public_date, url, company, position, location, salary, description, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'new')",
            (
                job["id"],
                job.get("pubDate", ""),
                job.get("url", ""),
                job.get("companyName", ""),
                job.get("title", ""),
                job.get("location", ""),
                job.get("salary", ""),
                job.get("description", "")
            )
        )
        if cursor.rowcount > 0:
            inserted += 1
            print("  [INSERT] %s - %s" % (job["companyName"], job["title"]))
        else:
            print("  [SKIP] %s - %s (duplicada)" % (job["companyName"], job["title"]))
    except Exception as e:
        print("  [ERROR] %s: %s" % (job["companyName"], str(e)))

conn.commit()
print()
print("  Registros insertados: %d" % inserted)

# ============================================================
# STEP F: Verify persistence + user response
# ============================================================
print()
print("=" * 60)
print("PASO 5: VERIFICACION Y RESPUESTA AL USUARIO")
print("=" * 60)

cursor.execute("SELECT COUNT(*) FROM jobs WHERE status = 'new'")
total_new = cursor.fetchone()[0]
print("  Total ofertas nuevas en BD: %d" % total_new)

print()
print("  Contenido de la tabla jobs:")
cursor.execute("SELECT id, company, position, location, salary FROM jobs WHERE status = 'new'")
rows = cursor.fetchall()
for row in rows:
    print("    ID: %s | %s | %s | %s | %s" % (row[0], row[1], row[2], row[3], row[4]))

print()
print("=" * 60)
print("RESPUESTA FINAL AL USUARIO")
print("=" * 60)
print("  'Busqueda completada. Encontre %d vacantes que coinciden con tu perfil:" % total_new)
for row in rows:
    print("   - %s en %s (%s)" % (row[2], row[1], row[3]))
print("   Las ofertas estan guardadas en tu base de datos.")
print("   Puedes pedirme que analice alguna en particular.'")

conn.close()

print()
print("=" * 60)
print("SIMULACION ESCENARIO 06 COMPLETADA")
print("=" * 60)
