#!/usr/bin/env python3
"""Scenario 06: Full Apify flow simulation

Fully self-contained test script. Uses only test infrastructure:
- Initializes via init_test.py (test DB schema)
- Operates exclusively on test/cv-pilot-test.db
- Cleans up the test DB on exit (success or failure)
"""

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

# ── Configuración de aislamiento ──────────────────────────────
# Todas las rutas están anidadas bajo test/. Nunca toca cv-pilot.db (producción).
SCRIPT_DIR = Path(__file__).resolve().parent          # test/scenarios/agent-mode/
TEST_DIR = SCRIPT_DIR.parent.parent                   # test/
DB_PATH = TEST_DIR / "cv-pilot-test.db"


def _cleanup():
    """Borra la DB de pruebas para dejar el entorno limpio."""
    if DB_PATH.exists():
        os.remove(DB_PATH)
        print(f"\n  [CLEANUP] DB de pruebas eliminada: {DB_PATH}")


def run_scenario():
    """Execute the full Apify flow simulation against the test database."""

    # ── STEP 0: Inicializar DB de pruebas ─────────────────────
    subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "init_test.py")],
        check=True,
    )

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # ============================================================
        # STEP B: Apify Cost Wizard
        # ============================================================
        print()
        print("=" * 60)
        print("PASO 1: WIZARD DE COSTOS (Apify)")
        print("=" * 60)

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
        msg = (
            "Para buscar %d empleos, el costo estimado es de $%.4f USD. Confirmas la ejecucion?"
            % (max_items, total_cost)
        )
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
            "followApplyRedirects": False,
        }

        print("  Input construido:")
        print("  %s" % json.dumps(search_input, indent=4, ensure_ascii=False))
        print()
        print("  Comando ejecutado:")
        cmd = (
            "apify call misceres/indeed-scraper -i '%s' --output-dataset --json --silent"
            % json.dumps(search_input)
        )
        print("  %s" % cmd)
        print()
        print("  -> Informando al usuario:")
        print(
            "     'Iniciando busqueda automatizada. Esto tardara unos minutos, te avisare al terminar.'"
        )
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
                "positionName": "Desarrollador Full Stack Junior",
                "salary": "2,500,000 - 3,500,000 COP/mes",
                "jobType": ["Fulltime"],
                "company": "TechCorp Colombia",
                "companyLogo": "https://d2q79iu7y748jz.cloudfront.net/s/_squarelogo/256x256/example1",
                "location": "Bogota, Colombia",
                "rating": 4.2,
                "reviewsCount": 12,
                "url": "https://co.indeed.com/viewjob?jk=abc123",
                "id": "abc123",
                "postedAt": "2 days ago",
                "scrapedAt": "2026-06-16T10:00:00.000Z",
                "description": "Buscamos desarrollador Full Stack Junior con experiencia en React, Node.js y bases de datos PostgreSQL. Conocimientos en TypeScript deseables. Trabajo hibrido 3 dias en oficina.",
                "descriptionHTML": "<p>Buscamos desarrollador Full Stack Junior con experiencia en React, Node.js y bases de datos PostgreSQL.</p>",
                "externalApplyLink": "https://techcorp.co/apply/abc123",
            },
            {
                "positionName": "Ingeniero de Software Junior",
                "salary": "3,000,000 - 4,000,000 COP/mes",
                "jobType": ["Fulltime", "Remote"],
                "company": "DataFlow SA",
                "companyLogo": "https://d2q79iu7y748jz.cloudfront.net/s/_squarelogo/256x256/example2",
                "location": "Medellin, Colombia",
                "rating": 3.8,
                "reviewsCount": 43,
                "url": "https://co.indeed.com/viewjob?jk=def456",
                "id": "def456",
                "postedAt": "1 day ago",
                "scrapedAt": "2026-06-16T10:00:00.000Z",
                "description": "Ingeniero de software junior para equipo de backend. Python, Django, PostgreSQL. Experiencia con Docker deseable. Remoto.",
                "descriptionHTML": "<p>Ingeniero de software junior para equipo de backend. Python, Django, PostgreSQL.</p>",
                "externalApplyLink": "https://dataflow.co/apply/def456",
            },
            {
                "positionName": "Programador Junior",
                "salary": "2,000,000 - 2,800,000 COP/mes",
                "jobType": ["Fulltime"],
                "company": "InnovateTech",
                "companyLogo": "https://d2q79iu7y748jz.cloudfront.net/s/_squarelogo/256x256/example3",
                "location": "Cali, Colombia",
                "rating": 4.0,
                "reviewsCount": 8,
                "url": "https://co.indeed.com/viewjob?jk=ghi789",
                "id": "ghi789",
                "postedAt": "3 days ago",
                "scrapedAt": "2026-06-16T10:00:00.000Z",
                "description": "Programador junior para desarrollo de APIs RESTful. Node.js, Express, MongoDB. Conocimientos en Git. Presencial zona norte.",
                "descriptionHTML": "<p>Programador junior para desarrollo de APIs RESTful. Node.js, Express, MongoDB.</p>",
                "externalApplyLink": None,
            },
            {
                "positionName": "Desarrollador Backend Junior",
                "salary": "3,200,000 - 4,200,000 COP/mes",
                "jobType": ["Fulltime", "Remote"],
                "company": "CloudSys Colombia",
                "companyLogo": "https://d2q79iu7y748jz.cloudfront.net/s/_squarelogo/256x256/example4",
                "location": "Bogota, Colombia",
                "rating": 3.5,
                "reviewsCount": 22,
                "url": "https://co.indeed.com/viewjob?jk=jkl012",
                "id": "jkl012",
                "postedAt": "5 days ago",
                "scrapedAt": "2026-06-16T10:00:00.000Z",
                "description": "Backend developer junior. Python, FastAPI, PostgreSQL. Experiencia con AWS o GCP. Trabajo remoto con reuniones semanales.",
                "descriptionHTML": "<p>Backend developer junior. Python, FastAPI, PostgreSQL.</p>",
                "externalApplyLink": "https://cloudsys.co/apply/jkl012",
            },
            {
                "positionName": "Ingeniero de Sistemas Junior",
                "salary": "2,800,000 - 3,800,000 COP/mes",
                "jobType": ["Fulltime"],
                "company": "SoftDev Group",
                "companyLogo": "https://d2q79iu7y748jz.cloudfront.net/s/_squarelogo/256x256/example5",
                "location": "Barranquilla, Colombia",
                "rating": 4.1,
                "reviewsCount": 15,
                "url": "https://co.indeed.com/viewjob?jk=mno345",
                "id": "mno345",
                "postedAt": "1 week ago",
                "scrapedAt": "2026-06-16T10:00:00.000Z",
                "description": "Ingeniero de sistemas junior para soporte y desarrollo. SQL, Python, documentacion tecnica. Hibrido.",
                "descriptionHTML": "<p>Ingeniero de sistemas junior para soporte y desarrollo. SQL, Python, documentacion tecnica.</p>",
                "externalApplyLink": None,
            },
        ]

        print("  Vacantes recibidas: %d" % len(apify_response))
        print()

        required_fields = ["positionName", "company", "location", "description", "id"]
        all_valid = True
        for i, job in enumerate(apify_response):
            missing = [f for f in required_fields if f not in job or not job[f]]
            if missing:
                print("  WARNING: Vacante %d sin campos: %s" % (i + 1, missing))
                all_valid = False

        if all_valid:
            print("  Integridad del dataset: OK")
        else:
            print("  Integridad del dataset: WARNINGS")

        print()
        print("  Vacantes encontradas:")
        for i, job in enumerate(apify_response, 1):
            print(
                "    %d. %s @ %s (%s)" % (i, job["positionName"], job["company"], job["location"])
            )

        # ============================================================
        # STEP 4: Persistencia en tabla jobs (idempotente)
        # ============================================================
        print()
        print("=" * 60)
        print("PASO 4: PERSISTENCIA EN TABLA JOBS")
        print("=" * 60)

        def compute_job_hash(company, position_name, location):
            """Generate deterministic SHA-256 hash for job deduplication."""
            raw = (company + position_name + location).encode()
            return hashlib.sha256(raw).hexdigest()

        persisted = 0
        skipped = 0

        for job in apify_response:
            job_hash = compute_job_hash(job["company"], job["positionName"], job["location"])

            cursor.execute("SELECT job_hash FROM jobs WHERE job_hash = ?", (job_hash,))
            if cursor.fetchone():
                skipped += 1
                print("  [SKIP] %s @ %s ya existe en BD" % (job["positionName"], job["company"]))
                continue

            cursor.execute(
                """INSERT INTO jobs (job_hash, indeed_id, public_date, url, company, position, location, salary, description, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'new')""",
                (
                    job_hash,
                    job.get("id", ""),
                    job.get("postedAt", ""),
                    job.get("url", ""),
                    job.get("company", ""),
                    job.get("positionName", ""),
                    job.get("location", ""),
                    job.get("salary", ""),
                    job.get("description", ""),
                ),
            )
            persisted += 1
            print(
                "  [INSERT] %s @ %s (hash: %s...)"
                % (job["positionName"], job["company"], job_hash[:12])
            )

        conn.commit()
        print()
        print("  Resumen: %d insertados, %d saltados (duplicados)" % (persisted, skipped))

        # ============================================================
        # STEP 5: Analisis Tecnico (Protocolo 1)
        # ============================================================
        print()
        print("=" * 60)
        print("PASO 5: ANALISIS TECNICO DE VACANTES")
        print("=" * 60)

        cursor.execute(
            "SELECT job_hash, position, company, description FROM jobs WHERE status = 'new'"
        )
        pendientes = cursor.fetchall()

        for job in pendientes:
            job_hash, position, company, description = job
            print("  Analizando vacante: %s en %s..." % (position, company))

            veredicto = (
                "Apto" if "Python" in description or "Node" in description else "No apto"
            )
            summary = (
                "Analisis tecnico para %s: Encaje basado en stack tecnologico detectado en oferta y CV."
                % position
            )

            cursor.execute(
                "INSERT INTO analyses (job_hash, verdict, summary) VALUES (?, ?, ?)",
                (job_hash, veredicto, summary),
            )
            cursor.execute("UPDATE jobs SET status = 'analyzed' WHERE job_hash = ?", (job_hash,))

            print("    [VERDICT] %s" % veredicto)
            print("    [SUMMARY] %s" % summary)

        conn.commit()

        # ============================================================
        # STEP 6: Verificacion y Respuesta Final
        # ============================================================
        print()
        print("=" * 60)
        print("PASO 6: RESPUESTA FINAL AL USUARIO")
        print("=" * 60)

        cursor.execute("SELECT COUNT(*) FROM jobs WHERE status = 'new'")
        total_new = cursor.fetchone()[0]
        print("  Total ofertas nuevas en BD: %d" % total_new)

        print()
        print("  Contenido de la tabla jobs:")
        cursor.execute(
            "SELECT indeed_id, company, position, location, salary FROM jobs WHERE status IN ('new', 'analyzed')"
        )
        rows = cursor.fetchall()
        for row in rows:
            print("    ID: %s | %s | %s | %s | %s" % (row[0], row[1], row[2], row[3], row[4]))

        print()
        print("=" * 60)
        print("RESPUESTA FINAL AL USUARIO")
        print("=" * 60)
        print(
            "  'Busqueda completada. Encontre %d vacantes que coinciden con tu perfil:"
            % len(rows)
        )
        for row in rows:
            print("   - %s en %s (%s)" % (row[2], row[1], row[3]))
        print("   Las ofertas estan guardadas en tu base de datos.")
        print("   Puedes pedirme que analice alguna en particular.'")

    finally:
        conn.close()
        _cleanup()


if __name__ == "__main__":
    try:
        run_scenario()
    except Exception as exc:
        print("\n  [ERROR] Escenario 06 fallo: %s" % exc, file=sys.stderr)
        _cleanup()
        sys.exit(1)

    print()
    print("=" * 60)
    print("SIMULACION ESCENARIO 06 COMPLETADA")
    print("=" * 60)
