#!/usr/bin/env python3
"""Scenario 08: Multi-scraper platform simulation (LinkedIn + Computrabajo)

Simulates the full pipeline for LinkedIn and Computrabajo platforms,
validating platform-specific field mappings, source values, and
URL construction.

Each platform uses its own actor, field names, and source tag.
The analysis engine is shared with scenario06.py.

Usage:
  python scenario08.py --platform linkedin --position "React Developer" --location "Colombia" --count 1
  python scenario08.py --platform computrabajo --position "desarrollador" --location "Medellín, Colombia" --count 1
"""

import argparse
import hashlib
import os
import random
import sqlite3
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scenario06 import load_user_data, analyze_vacancy

# ── Path setup ───────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
TEST_DIR = SCRIPT_DIR.parent.parent
DB_PATH = TEST_DIR / "cv-pilot-test.db"
CV_TEST_DIR = TEST_DIR / "cv-test"

def setup_scenario_db():
    """Creates test DB schema with source column."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS jobs (
        job_hash TEXT PRIMARY KEY,
        external_id TEXT,
        public_date TEXT,
        url TEXT,
        company TEXT,
        position TEXT,
        location TEXT,
        salary TEXT,
        description TEXT,
        source TEXT DEFAULT 'manual',
        status TEXT DEFAULT 'new'
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS analyses (
        analysis_id TEXT PRIMARY KEY,
        job_hash TEXT,
        percentage TEXT,
        comparativa TEXT,
        observaciones TEXT,
        verdict TEXT,
        tldr TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(job_hash) REFERENCES jobs(job_hash)
    )''')

    conn.commit()
    conn.close()
    print("DB Ready (con source)")

# ── Platform definitions ──────────────────────────────────────────────

PLATFORMS = {
    "linkedin": {
        "actor": "curious_coder/linkedin-jobs-scraper",
        "actor_id": "hKByXkMQaC5Qt9UMN",
        "cost_per_result": 0.001,
        "cost_start": 0.0,
        "source": "apify-linkedin",
        # Field mapping: actor output field → DB column
        "field_map": {
            "title": "position",
            "companyName": "company",
            "link": "url",
            "id": "external_id",
            "postedAt": "public_date",
            "location": "location",
            "salary": "salary",
            "description": "description",
        },
        "url_template": "https://www.linkedin.com/jobs/search/?keywords={position}&location={location}",
    },
    "computrabajo": {
        "actor": "shahidirfan/computrabajo-jobs-scraper",
        "actor_id": "270QqNecZlrnDMveb",
        "cost_per_result": 0.00199,
        "cost_start": 0.0005,
        "source": "apify-computrabajo",
        "field_map": {
            "title": "position",
            "companyName": "company",
            "link": "url",
            "id": "external_id",
            "postedAt": "public_date",
            "location": "location",
            "salary": "salary",
            "description": "description",
        },
        "country_subdomains": {
            "CO": "co.computrabajo.com",
            "AR": "ar.computrabajo.com",
            "MX": "mx.computrabajo.com",
            "PE": "pe.computrabajo.com",
            "CL": "cl.computrabajo.com",
        },
        "url_template": "https://{subdomain}/trabajo-de-{position_keyword}-en-{location_keyword}",
    },
}

# ── Mock data per platform ────────────────────────────────────────────

# Job titles pool for LinkedIn-style positions
LINKEDIN_POSITIONS = [
    "React Developer", "Senior React Developer",
    "Full Stack React Engineer", "Frontend Developer (React)",
    "React Native Developer",
]

COMPUTRABAJO_POSITIONS = [
    "Desarrollador de Software", "Desarrollador React",
    "Programador Full Stack", "Ingeniero de Software Senior",
    "Desarrollador Backend",
]

COMPANY_POOL = [
    "TechSolutions Colombia", "SoftwareOne LATAM", "Globant Colombia",
    "DigitalWare", "Intergrupo", "Sofka Technologies",
]

LOCATION_POOL = {
    "Medellín, Colombia": ["Medellín, Antioquia", "Sabaneta, Antioquia"],
    "Colombia": ["Bogotá, Colombia", "Medellín, Colombia", "Cali, Colombia"],
    "Remote": ["Remoto, Colombia", "Remoto"],
}

DESCRIPTIONS = [
    "Buscamos desarrollador con experiencia en React, TypeScript y APIs REST. "
    "Conocimientos en Docker y CI/CD deseables. Trabajo remoto disponible.",

    "Desarrollador para equipo de producto. Stack: React, Node.js, PostgreSQL. "
    "Experiencia con Git y metodologías ágiles.",

    "Full Stack Developer con foco en frontend. React, JavaScript, CSS. "
    "Experiencia con bases de datos relacionales.",
]


def generate_mock_jobs(platform: str, position: str, location: str, count: int) -> list[dict]:
    """Generate mock job items using platform-specific field names."""
    jobs = []

    if "colombia" in location.lower() or "medellín" in location.lower():
        country = "CO"
    else:
        country = "CO"  # default

    for i in range(count):
        if platform == "linkedin":
            title = random.choice(LINKEDIN_POSITIONS)
            company = random.choice(COMPANY_POOL)
            loc = random.choice(LOCATION_POOL.get(location, [location]))
            job_id = hashlib.md5(uuid.uuid4().bytes).hexdigest()[:10]
            desc = random.choice(DESCRIPTIONS)

            jobs.append({
                "title": title,
                "companyName": company,
                "link": f"https://www.linkedin.com/jobs/view/{job_id}",
                "id": job_id,
                "postedAt": "Recién publicado",
                "location": loc,
                "salary": None,
                "description": desc,
                "country": country,
            })

        elif platform == "computrabajo":
            title = random.choice(COMPUTRABAJO_POSITIONS)
            company = random.choice(COMPANY_POOL)
            loc = random.choice(LOCATION_POOL.get(location, [location]))
            job_id = hashlib.md5(uuid.uuid4().bytes).hexdigest()[:10]
            desc = random.choice(DESCRIPTIONS)

            jobs.append({
                "title": title,
                "companyName": company,
                "link": f"https://co.computrabajo.com/ofertas/{job_id}",
                "id": job_id,
                "postedAt": "Recién publicado",
                "location": loc,
                "salary": None,
                "description": desc,
                "country": country,
            })

    return jobs


def build_search_url(platform: str, position: str, location: str) -> str:
    """Build the search URL for a given platform."""
    cfg = PLATFORMS[platform]

    if platform == "linkedin":
        encoded_pos = position.replace(" ", "%20")
        encoded_loc = location.split(",")[0].strip().replace(" ", "%20")
        return cfg["url_template"].format(position=encoded_pos, location=encoded_loc)

    elif platform == "computrabajo":
        subdomain = cfg["country_subdomains"].get("CO", "co.computrabajo.com")
        pos_kw = position.lower().replace(" ", "-")
        loc_kw = location.split(",")[0].strip().lower().replace(" ", "-")
        return cfg["url_template"].format(
            subdomain=subdomain,
            position_keyword=pos_kw,
            location_keyword=loc_kw,
        )

    return ""


def map_to_db(job: dict, platform: str) -> dict:
    """Map platform-specific fields to DB column names."""
    cfg = PLATFORMS[platform]
    field_map = cfg["field_map"]
    mapped = {}
    for src_field, db_field in field_map.items():
        mapped[db_field] = job.get(src_field, "")
    return mapped


def compute_job_hash(company: str, position: str, location: str) -> str:
    raw = (company + position + location).encode()
    return hashlib.sha256(raw).hexdigest()


# ── CLI ──────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Multi-scraper platform simulation — scenario 08/09"
    )
    parser.add_argument(
        "--platform",
        choices=["linkedin", "computrabajo"],
        required=True,
        help="Platform to simulate (linkedin or computrabajo)",
    )
    parser.add_argument(
        "--position",
        default="React Developer",
        help="Job position to search",
    )
    parser.add_argument(
        "--location",
        default="Colombia",
        help="Target location",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of results to generate",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete test DB after execution",
    )
    return parser.parse_args()


# ── Main ─────────────────────────────────────────────────────────────

def run_scenario():
    args = parse_args()
    platform = args.platform
    position = args.position
    location = args.location
    count = args.count
    do_cleanup = args.cleanup

    cfg = PLATFORMS[platform]
    source_tag = cfg["source"]

    # ── Load user data ────────────────────────────────────────────
    user_data = load_user_data()
    user_identity = user_data["identity"]

    # ── Clean slate ───────────────────────────────────────────────
    if DB_PATH.exists():
        os.remove(DB_PATH)
        print("DB anterior eliminada — empezando desde 0")

    setup_scenario_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # ============================================================
        # STEP 1: Platform Selection & Cost
        # ============================================================
        print()
        print("=" * 60)
        print("PASO 1: SELECCIÓN DE PLATAFORMA Y COSTO")
        print("=" * 60)

        total_cost = (count * cfg["cost_per_result"]) + cfg["cost_start"]
        search_url = build_search_url(platform, position, location)
        print(f"  Plataforma detectada: {platform.upper()}")
        print(f"  Actor: {cfg['actor']}")
        print(f"  URL de búsqueda: {search_url}")
        print(f"  Costo por resultado: ${cfg['cost_per_result']:.5f} USD")
        if cfg["cost_start"] > 0:
            print(f"  Costo de arranque: ${cfg['cost_start']:.5f} USD")
        print(f"  Costo total estimado: ${total_cost:.5f} USD")
        print("  -> USUARIO CONFIRMA")

        # ============================================================
        # STEP 2: Mock Apify Call
        # ============================================================
        print()
        print("=" * 60)
        print("PASO 2: EJECUCIÓN APIFY CALL (SIMULADO)")
        print("=" * 60)

        mock_jobs = generate_mock_jobs(platform, position, location, count)
        print(f"  [SIMULACION] {len(mock_jobs)} vacantes generadas desde {platform}")

        # Show raw fields to demonstrate platform-specific mapping
        if mock_jobs:
            sample = mock_jobs[0]
            print(f"  Campos de {platform}:")
            for k, v in sample.items():
                print(f"    {k}: {v}")

        # ============================================================
        # STEP 3: Field Mapping & Normalization
        # ============================================================
        print()
        print("=" * 60)
        print("PASO 3: MAPEO DE CAMPOS A DB")
        print("=" * 60)

        for job in mock_jobs:
            mapped = map_to_db(job, platform)
            print(f"  [MAP] {job.get('title', job.get('positionName', ''))}")
            print(f"    title -> position: {mapped.get('position', '')}")
            print(f"    companyName -> company: {mapped.get('company', '')}")
            print(f"    link -> url: {mapped.get('url', '')}")
            print(f"    source -> {source_tag}")

        # ============================================================
        # STEP 4: Persistence with source tag
        # ============================================================
        print()
        print("=" * 60)
        print("PASO 4: PERSISTENCIA CON SOURCE")
        print("=" * 60)

        inserted = 0
        for job in mock_jobs:
            mapped = map_to_db(job, platform)
            job_hash = compute_job_hash(
                mapped["company"], mapped["position"], mapped["location"]
            )

            # Add source field
            mapped["source"] = source_tag

            cursor.execute(
                """INSERT OR IGNORE INTO jobs
                   (job_hash, external_id, public_date, url, company,
                    position, location, salary, description, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job_hash,
                    mapped.get("external_id", ""),
                    mapped.get("public_date", ""),
                    mapped.get("url", ""),
                    mapped.get("company", ""),
                    mapped.get("position", ""),
                    mapped.get("location", ""),
                    mapped.get("salary", ""),
                    mapped.get("description", ""),
                    source_tag,
                ),
            )
            print(f"  [INSERT] {mapped['position']} @ {mapped['company']} "
                  f"(source={source_tag})")
            inserted += 1

        conn.commit()
        print(f"  Total insertadas: {inserted}")

        # ============================================================
        # STEP 5: Verify source value in DB
        # ============================================================
        print()
        print("=" * 60)
        print("PASO 5: VERIFICACIÓN DE SOURCE EN DB")
        print("=" * 60)

        cursor.execute("SELECT position, company, source, status FROM jobs")
        for row in cursor.fetchall():
            jpos, jcomp, jsrc, jstatus = row
            status_icon = "OK" if jsrc == source_tag else "FAIL"
            print(f"  [{status_icon}] {jpos} @ {jcomp} | source={jsrc} | status={jstatus}")

        # ============================================================
        # STEP 6: Analysis against CV
        # ============================================================
        print()
        print("=" * 60)
        print("PASO 6: ANÁLISIS TÉCNICO")
        print("=" * 60)

        cursor.execute(
            "SELECT job_hash, position, company, description "
            "FROM jobs WHERE status = 'new'"
        )
        pendientes = cursor.fetchall()

        if not pendientes:
            # Mark all as 'new' since we just inserted them
            cursor.execute("UPDATE jobs SET status = 'new'")
            conn.commit()
            cursor.execute(
                "SELECT job_hash, position, company, description FROM jobs"
            )
            pendientes = cursor.fetchall()

        print(f"  Vacantes pendientes: {len(pendientes)}")
        print(f"  Usuario: {user_identity['name']} ({user_identity['title']})")
        print()

        for job in pendientes:
            job_hash, j_position, j_company, j_description = job

            analysis = analyze_vacancy(j_description, j_position, user_data)
            analysis_id = str(uuid.uuid4())

            cursor.execute(
                "INSERT INTO analyses "
                "(analysis_id, job_hash, percentage, comparativa, "
                "observaciones, verdict, tldr) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    analysis_id,
                    job_hash,
                    analysis["percentage"],
                    analysis["comparativa"],
                    analysis["observaciones"],
                    analysis["verdict"],
                    analysis["tldr"],
                ),
            )
            cursor.execute(
                "UPDATE jobs SET status = 'analyzed' WHERE job_hash = ?",
                (job_hash,),
            )

            print(f"  [ANALYZED] {j_position} @ {j_company}")
            print(f"    analysis_id: {analysis_id}")
            print(f"    platform: {platform}")
            print(f"    verdict: {analysis['verdict']}")
            print(f"    percentage: {analysis['percentage']}")
            print(f"    comparativa: {analysis['comparativa']}")
            obs_lines = analysis["observaciones"].split("\n")
            print("    observaciones:")
            for line in obs_lines:
                print(f"      {line}")
            print(f"    tldr: {analysis['tldr']}")
            print()

        conn.commit()

        # ============================================================
        # STEP 7: Final DB query
        # ============================================================
        print("=" * 60)
        print("PASO 7: CONSULTA FINAL DB")
        print("=" * 60)

        cursor.execute(
            "SELECT j.company, j.position, j.source, "
            "a.verdict, a.percentage, a.tldr "
            "FROM jobs j "
            "JOIN analyses a ON j.job_hash = a.job_hash"
        )
        for row in cursor.fetchall():
            company, jp, src, verdict, pct, tldr = row
            print(f"  {company} | {jp} | {src}")
            print(f"    {pct} — {verdict} — {tldr}")

        print()
        print("=" * 60)
        print(f"  PRUEBA {platform.upper()} COMPLETADA")
        print("=" * 60)

    finally:
        conn.close()
        if do_cleanup and DB_PATH.exists():
            os.remove(DB_PATH)
            print("\n[--cleanup] DB de prueba eliminada.")


if __name__ == "__main__":
    run_scenario()
