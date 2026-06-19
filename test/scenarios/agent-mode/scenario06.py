#!/usr/bin/env python3
"""Scenario 06: Dynamic Apify flow simulation

Simulates the full Apify scraping pipeline with CLI-driven parameters.
Vacancies are generated dynamically, filtered by geographic location,
persisted with SHA-256 dedup, analyzed against a real user stack, and
queried back.

The analysis engine replicates the real CV-Pilot agent:
  - Reads user identity and tech stack from test/cv-test/
  - Compares each vacancy description against the user's stack
  - Calculates percentage, generates comparativa, observaciones, verdict
  - Applies real evaluation rules (not hardcoded "80%" / "Apto")

Usage:
  python scenario06.py --position "desarrollador junior" --location "Medellín, Colombia" --count 3
"""

import argparse
import hashlib
import os
import random
import re
import sqlite3
import uuid
from pathlib import Path

# ── Absolute path definitions ────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
TEST_DIR = SCRIPT_DIR.parent.parent
DB_PATH = TEST_DIR / "cv-pilot-test.db"
CV_TEST_DIR = TEST_DIR / "cv-test"


# ── User data loading from test/cv-test/ ─────────────────────────────

def _parse_identity(path: Path) -> dict:
    """Parse identidad.md to extract user identity fields."""
    text = path.read_text(encoding="utf-8")
    result = {}

    match = re.search(r'\*\*Nombre completo:\*\*\s*(.+)', text)
    if match:
        result["name"] = match.group(1).strip()

    match = re.search(r'\*\*LinkedIn:\*\*\s*\[(.+?)\]', text)
    if match:
        result["linkedin"] = match.group(1).strip()

    match = re.search(r'\*\*GitHub:\*\*\s*\[(.+?)\]', text)
    if match:
        result["github"] = match.group(1).strip()

    return result


# Alias variant map — common alternative spellings / abbreviations
_ALIAS_VARIANTS: dict[str, list[str]] = {
    "react": ["reactjs", "react.js"],
    "next.js": ["nextjs", "next"],
    "node.js": ["nodejs", "node"],
    "typescript": ["ts"],
    "javascript": ["js"],
    "postgresql": ["postgres"],
    "mongodb": ["mongo"],
    "fastapi": ["fast api"],
    "material-ui": ["material ui", "mui"],
    "tailwind css": ["tailwind"],
    "html5/css3": ["html5", "css3", "html", "css"],
    "model context protocol (mcp)": ["mcp", "model context protocol"],
    "llm integration (claude/openai)": ["llm", "claude", "openai"],
    "google cloud platform (networking & ml apis)": ["gcp", "google cloud"],
    "linux server admin": ["linux"],
    "llm integration": ["llm", "claude", "openai"],
    "google cloud platform": ["gcp", "google cloud"],
}

# Tokens that indicate a parenthetical item is a description, not a tech name
_DESCRIPTION_TOKENS = frozenset({
    "networking", "server", "admin", "integration", "apis", "api",
    "tooling", "tool", "platform", "infrastructure",
})

# Database name tokens — used to separate databases from backend
_DB_TOKENS = frozenset({
    "postgresql", "postgres", "mysql", "mongodb", "mongo",
    "sqlite", "redis", "mariadb", "sql server",
})


def _generate_aliases(tech_name: str, sub_items: list[str] | None = None) -> list[str]:
    """Generate case-insensitive aliases for a technology name.

    Produces the lowercase canonical form, common variant spellings,
    and any parenthetical sub-items from the CV.
    Slash-separated items (e.g. "Claude/OpenAI") are split into
    individual aliases. Description fragments are filtered out.
    """
    aliases: list[str] = []
    name_lower = tech_name.lower()

    # Base alias — always include the lowercase name
    aliases.append(name_lower)

    # Known variant spellings
    if name_lower in _ALIAS_VARIANTS:
        for v in _ALIAS_VARIANTS[name_lower]:
            if v not in aliases:
                aliases.append(v)

    # Parenthetical sub-items (e.g. "Python (FastAPI, Pandas)" → add fastapi, pandas)
    if sub_items:
        for raw_item in sub_items:
            # Split slashes: "Claude/OpenAI" → ["Claude", "OpenAI"]
            slash_parts = [p.strip() for p in raw_item.split("/") if p.strip()]
            for part in slash_parts:
                part_lower = part.lower().strip()
                if not part_lower:
                    continue
                # Skip description-like fragments (multi-word non-tech strings)
                tokens = set(part_lower.split())
                if tokens & _DESCRIPTION_TOKENS:
                    continue
                if part_lower not in aliases:
                    aliases.append(part_lower)
                # Also add variant spellings of sub-items
                if part_lower in _ALIAS_VARIANTS:
                    for v in _ALIAS_VARIANTS[part_lower]:
                        if v not in aliases:
                            aliases.append(v)

    return aliases


def _split_tech_items(techs_text: str) -> list[str]:
    """Split a technology list by commas, respecting parenthetical groups."""
    items: list[str] = []
    current = ""
    depth = 0

    for char in techs_text:
        if char == "(":
            depth += 1
            current += char
        elif char == ")":
            depth -= 1
            current += char
        elif char == "," and depth == 0:
            items.append(current.strip())
            current = ""
        else:
            current += char

    if current.strip():
        items.append(current.strip())

    return items


# Category name mapping: CV section header → internal stack key
_CATEGORY_MAP: dict[str, str] = {
    "ia & automatización": "ia_automatizacion",
    "backend": "backend",
    "frontend": "frontend",
    "devops & cloud": "devops_cloud",
}


def _parse_habilidades(text: str) -> dict[str, list[tuple[str, list[str]]]]:
    """Parse the HABILIDADES TÉCNICAS section into stack categories.

    Each CV line like "Backend: Python (FastAPI), PostgreSQL" is split into
    a category key and a list of ``(canonical_name, [aliases])`` tuples.
    Databases are automatically separated from the backend category.
    """
    stack: dict[str, list[tuple[str, list[str]]]] = {}

    # Normalise: collapse continuation lines into single lines per category
    lines = text.split("\n")
    current_cat_header: str | None = None
    current_techs_parts: list[str] = []

    def _flush_category() -> None:
        nonlocal current_cat_header, current_techs_parts
        if current_cat_header is None:
            return
        cat_match = re.match(r'^(.+?):\s*(.*)', current_cat_header)
        if not cat_match:
            current_cat_header = None
            current_techs_parts = []
            return
        cat_name = cat_match.group(1).strip()
        first_techs = cat_match.group(2).strip()
        all_techs_text = first_techs
        if current_techs_parts:
            all_techs_text += " " + " ".join(current_techs_parts)

        cat_key = _CATEGORY_MAP.get(cat_name.lower(), cat_name.lower().replace(" ", "_"))
        entries = _parse_category_techs(all_techs_text)
        if entries:
            stack[cat_key] = entries
        current_cat_header = None
        current_techs_parts = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Detect new category header
        if re.match(r'^(IA & Automatización|Backend|Frontend|DevOps & Cloud)\s*:', stripped, re.IGNORECASE):
            _flush_category()
            current_cat_header = stripped
        elif current_cat_header is not None:
            current_techs_parts.append(stripped)

    _flush_category()

    # Separate databases out of backend into bases_de_datos
    if "backend" in stack:
        db_entries: list[tuple[str, list[str]]] = []
        non_db: list[tuple[str, list[str]]] = []
        for name, aliases in stack["backend"]:
            if name.lower() in _DB_TOKENS:
                db_entries.append((name, aliases))
            else:
                non_db.append((name, aliases))
        if db_entries:
            stack["bases_de_datos"] = db_entries
        if non_db:
            stack["backend"] = non_db
        elif "backend" in stack and not non_db:
            del stack["backend"]

    return stack


def _parse_category_techs(techs_text: str) -> list[tuple[str, list[str]]]:
    """Parse the technology list for a single category."""
    items = _split_tech_items(techs_text)
    entries: list[tuple[str, list[str]]] = []

    for item in items:
        item = item.strip().rstrip(".")
        if not item:
            continue

        # Extract main tech + parenthetical sub-items
        m = re.match(r'^(.+?)\s*\((.+?)\)$', item)
        if m:
            main_tech = m.group(1).strip()
            sub_items = [s.strip() for s in m.group(2).split(",")]
            aliases = _generate_aliases(main_tech, sub_items)
        else:
            main_tech = item
            aliases = _generate_aliases(item)

        entries.append((main_tech, aliases))

    return entries


# Category display labels for observaciones output
_CATEGORY_LABELS: dict[str, str] = {
    "ia_automatizacion": "IA & Automatización",
    "lenguajes": "Lenguajes",
    "frontend": "Frontend",
    "backend": "Backend",
    "bases_de_datos": "Bases de datos",
    "devops_cloud": "DevOps/Cloud",
}


def load_user_data() -> dict:
    """Load user identity and tech stack dynamically from test/cv-test/.

    Reads:
      - identidad.md → name, linkedin, github
      - JulioTamara-CV.md → title, HABILIDADES TÉCNICAS section

    Returns a dict with keys: identity, stack, primary_categories,
    all_aliases, category_labels, total_items.
    """
    # ── Identity from identidad.md ────────────────────────────────────
    identity_path = CV_TEST_DIR / "identidad.md"
    raw_identity = _parse_identity(identity_path)

    # ── CV data from JulioTamara-CV.md ────────────────────────────────
    cv_path = CV_TEST_DIR / "JulioTamara-CV.md"
    cv_text = cv_path.read_text(encoding="utf-8")

    # Extract professional title from the profile line
    title_match = re.search(
        r'(Ingeniero de Sistemas|Desarrollador\w*\s+\w+|Analista\w*\s+\w+)',
        cv_text,
    )
    title = title_match.group(1) if title_match else "Ingeniero de Sistemas"

    # Extract HABILIDADES TÉCNICAS section (everything until next H2 or end)
    hab_match = re.search(
        r'HABILIDADES\s+TÉCNICAS\s*\n(.*?)(?=\n##|\nCERTIFICACIONES|\nIDIOMAS|\Z)',
        cv_text,
        re.DOTALL | re.IGNORECASE,
    )
    habilidades = hab_match.group(1).strip() if hab_match else ""

    # ── Parse stack ───────────────────────────────────────────────────
    stack = _parse_habilidades(habilidades)

    # ── Flatten aliases ───────────────────────────────────────────────
    all_aliases: list[tuple[str, str]] = []
    category_labels: dict[str, str] = {}

    for cat, entries in stack.items():
        category_labels[cat] = _CATEGORY_LABELS.get(cat, cat)
        for name, aliases in entries:
            for alias in aliases:
                all_aliases.append((alias.lower(), name))

    # ── Primary categories — vacancy must match at least one ──────────
    # Mapped to the dynamically-created keys from the CV
    primary_categories: set[str] = set()
    for cat in ("lenguajes", "backend", "frontend", "bases_de_datos"):
        if cat in stack:
            primary_categories.add(cat)
    # Fallback: if CV parsing didn't produce expected keys, use whatever exists
    if not primary_categories and stack:
        # Use first two non-specialty categories as primary
        for cat in stack:
            if cat not in ("ia_automatizacion", "devops_cloud"):
                primary_categories.add(cat)
                if len(primary_categories) >= 2:
                    break

    total_items = sum(len(entries) for entries in stack.values())

    return {
        "identity": {
            "name": raw_identity.get("name", "Usuario"),
            "title": title,
            "linkedin": raw_identity.get("linkedin", ""),
            "github": raw_identity.get("github", ""),
        },
        "stack": stack,
        "primary_categories": primary_categories,
        "all_aliases": all_aliases,
        "category_labels": category_labels,
        "total_items": total_items,
    }


# ── Analysis engine (mirrors real CV-Pilot agent) ────────────────────

def analyze_vacancy(description: str, position: str, user_data: dict) -> dict:
    """Compare a vacancy description against the user's real tech stack.

    The score is computed as: matched / total_detected, where both values
    refer ONLY to technologies from the user's stack that are detectable
    in the vacancy description.  This avoids penalising the candidate for
    technologies the vacancy never mentions.

    Returns a dict with: percentage, matched, missing_by_cat,
    comparativa, observaciones, verdict, tldr.
    """
    stack = user_data["stack"]
    all_aliases = user_data["all_aliases"]
    primary_categories = user_data["primary_categories"]
    category_labels = user_data["category_labels"]

    desc_lower = description.lower()

    # --- Phase 1: Match aliases against description ---
    matched_names: set[str] = set()
    for alias_lower, canonical in all_aliases:
        # Use word-boundary-aware matching to avoid false positives
        # e.g. "js" shouldn't match inside "json"
        pattern = r'(?<![a-z/])' + re.escape(alias_lower) + r'(?![a-z])'
        if re.search(pattern, desc_lower):
            matched_names.add(canonical)

    # --- Phase 2: Detect which user technologies appear in the description ---
    detected_in_desc: set[str] = set()
    matched_by_cat: dict[str, list[str]] = {}
    missing_by_cat: dict[str, list[str]] = {}
    primary_matched = 0

    for cat, entries in stack.items():
        cat_detected = []
        cat_missing = []
        for name, _aliases in entries:
            if name in matched_names:
                detected_in_desc.add(name)
                cat_detected.append(name)
                if cat in primary_categories:
                    primary_matched += 1
            else:
                cat_missing.append(name)
        matched_by_cat[cat] = cat_detected
        missing_by_cat[cat] = cat_missing

    # --- Phase 3: Percentage (denominator = detected, not full stack) ---
    total_detected = len(detected_in_desc)
    matched_count = len(matched_names & detected_in_desc)
    percentage = round((matched_count / total_detected) * 100) if total_detected > 0 else 0

    # --- Phase 4: Verdict (from AGENTS.md rules) ---
    has_primary = primary_matched > 0
    if not has_primary or total_detected == 0:
        verdict = "No apto"
    elif percentage < 60:
        verdict = "No apto"
    elif percentage <= 75:
        verdict = "Apto con reservas"
    else:
        verdict = "Apto"

    # --- Phase 5: Comparativa (human-readable tech breakdown) ---
    # Only list technologies that were actually detected in the description.
    all_matched = sorted(matched_names & detected_in_desc)
    # Technologies in description that we COULD detect but the user doesn't have.
    # Since detected_in_desc only contains user-stack items, this is always empty
    # by construction — but we keep the field for API compatibility.
    all_missing: list[str] = []

    comparativa_parts = []
    if all_matched:
        comparativa_parts.append(
            "Coinciden con la vacante: %s" % ", ".join(all_matched)
        )
    if all_missing:
        comparativa_parts.append(
            "No mencionadas en la vacante: %s" % ", ".join(all_missing)
        )
    comparativa = " | ".join(comparativa_parts) if comparativa_parts else "Sin coincidencias"

    # --- Phase 6: Observaciones (detailed fit analysis) ---
    # Only show categories that have at least one detected technology.
    obs_lines = []
    for cat, entries in stack.items():
        label = category_labels.get(cat, cat)
        cat_detected = matched_by_cat.get(cat, [])
        cat_missing = missing_by_cat.get(cat, [])
        # Skip categories with zero detected technologies
        if not cat_detected:
            continue
        obs_lines.append("  %s [OK]: %s" % (label, ", ".join(cat_detected)))
        # Only list missing from categories where something WAS detected
        if cat_missing:
            obs_lines.append("  %s [--]: %s" % (label, ", ".join(cat_missing)))

    if not has_primary or total_detected == 0:
        core_note = (
            "El candidato NO tiene stack principal (lenguajes/backend/frontend/BD) "
            "alineado con la vacante."
        )
    elif percentage >= 75:
        core_note = (
            "El candidato cumple con %d de %d tecnologías requeridas por la vacante."
            % (matched_count, total_detected)
        )
    elif percentage >= 60:
        core_note = (
            "El candidato tiene base sólida pero faltan tecnologías clave "
            "requeridas por la vacante (%d de %d detectadas)."
            % (matched_count, total_detected)
        )
    else:
        core_note = (
            "El candidato cubre parte del stack pero el encaje es limitado "
            "(%d de %d tecnologías detectadas)." % (matched_count, total_detected)
        )

    observaciones = "%s\n%s" % (core_note, "\n".join(obs_lines))

    # --- Phase 7: TLDR ---
    tldr = "%s - %d%% de coincidencia con el stack del usuario" % (verdict, percentage)

    return {
        "percentage": "%d%%" % percentage,
        "matched": all_matched,
        "missing_by_cat": missing_by_cat,
        "comparativa": comparativa,
        "observaciones": observaciones,
        "verdict": verdict,
        "tldr": tldr,
    }

# ── Mock data generators ─────────────────────────────────────────────

# City-keyed company name pools (rotated to generate plausible names)
COMPANY_POOLS = {
    "Medellín": [
        "Intergrupo Medellín", "Globant Medellín", "Epm Tech",
        "Rappi Medellín", "Sofka Medellín", "Nevera Digital",
        "Koombea Medellín", "Sysdepa", "Vertex Solutions",
        "Digital House Medellín",
    ],
    "Bogotá": [
        "Mercado Libre Bogotá", "Rappi Bogotá", "Davivienda Tech",
        "Bancolombia Digital", "Globant Bogotá", "Tul.co",
        "Addi Tech", "Sempli", "Oasis Coltech", "CloudTech Bogotá",
    ],
    "Cali": [
        "Tul Cali", "Softcaribbean", "InnovateTech Cali",
        "CaliDev Labs", "Pacífico Digital", "Redsis",
        "Colsoft", "SynergySoft Cali", "Nubelía", "DataCali",
    ],
    "Barranquilla": [
        "Gentera Barranquilla", "MercadoLibre BAQ", "Aldelo Tech",
        "SoftManagement", "Grupo Exito Digital", "Cinfo",
        "ArisTech", "NetGroup BAQ", "ByteCode Caribe", "Platanitos Lab",
    ],
}

# Seniority words — if the base position already contains one, we skip prefixing
_SENIORITY_WORDS = {"senior", "junior", "trainee", "semi-senior", "lead", "staff", "principal"}


def _build_position_variants(base: str) -> list[str]:
    """Return a list of position title variants for the given base role.

    If the base already contains a seniority word (e.g. "desarrollador junior"),
    we avoid doubling it — only the bare form is used.
    """
    tokens = set(base.lower().split())
    has_seniority = bool(tokens & _SENIORITY_WORDS)
    if has_seniority:
        return [base.title()]
    return [
        f"Senior {base.title()}",
        f"Junior {base.title()}",
        base.title(),
        f"Trainee {base.title()}",
    ]

# Post dates mimicking Indeed
POSTED_AT_OPTIONS = [
    "Recién publicado", "1 day ago", "2 days ago", "3 days ago",
    "5 days ago", "1 week ago", "2 weeks ago",
]

# Job types
JOB_TYPE_OPTIONS = [
    ["Fulltime"], ["Fulltime", "Remote"], ["Fulltime", "Hybrid"],
    ["Remote"], ["Fulltime", "Parttime"],
]

# Description templates per role family (keyed by common stem)
DESCRIPTION_TEMPLATES = {
    "desarrollador": [
        "Buscamos desarrollador con experiencia en React, Node.js y bases de datos PostgreSQL. "
        "Conocimientos en TypeScript deseables.",
        "Desarrollador para equipo de producto digital. Stack: Python, Django, PostgreSQL. "
        "Experiencia con Docker deseable.",
        "Desarrollador full stack. JavaScript/TypeScript, React, Express, MongoDB. "
        "Conocimientos en CI/CD.",
    ],
    "ingeniero": [
        "Ingeniero de software para equipo de backend. Python, FastAPI, PostgreSQL. "
        "Experiencia con AWS o GCP.",
        "Ingeniero de software con foco en arquitectura de microservicios. Java, Spring Boot, Kafka.",
        "Ingeniero de software para plataforma de datos. Spark, Airflow, Python.",
    ],
    "analista": [
        "Analista de datos con experiencia en SQL, Python y herramientas de visualización. Power BI o Tableau.",
        "Analista de sistemas para soporte y desarrollo. SQL, documentación técnica.",
        "Analista de requisitos para equipos ágiles. Jira, Confluence, UML.",
    ],
    "devops": [
        "DevOps engineer. AWS/GCP, Terraform, Docker, Kubernetes. CI/CD pipelines.",
        "DevOps para equipo de infraestructura. Linux, Ansible, Jenkins, monitoreo.",
        "DevOps con experiencia en plataformas cloud-nativas. Helm, ArgoCD, Prometheus.",
    ],
    "generic": [
        "Perfil versátil para equipo de tecnología. SQL, Python, documentación técnica.",
        "Rol de soporte y desarrollo. Bases de datos, APIs, scripting.",
        "Profesional de tecnología para proyecto de transformación digital.",
    ],
}

# Alternate cities used to generate "out of location" noise
ALL_CITIES = ["Bogotá, Colombia", "Medellín, Colombia", "Cali, Colombia",
              "Barranquilla, Colombia", "Bucaramanga, Colombia",
              "Pereira, Colombia", "Santa Marta, Colombia"]


def _resolve_city_key(location: str) -> str:
    """Extract the short city name from a full location string."""
    for key in COMPANY_POOLS:
        if key.lower() in location.lower():
            return key
    return "Bogotá"  # fallback


def _pick_description(position_lower: str) -> str:
    """Pick a description template based on the position stem."""
    for stem, templates in DESCRIPTION_TEMPLATES.items():
        if stem in position_lower:
            return random.choice(templates)
    return random.choice(DESCRIPTION_TEMPLATES["generic"])


def _matches_location(generated: str, target: str) -> bool:
    """Fuzzy check: the generated city string matches the target location."""
    target_lower = target.lower().strip()
    generated_lower = generated.lower().strip()
    # Both must share the same city name token
    return generated_lower == target_lower


def generate_mock_vacancies(position: str, location: str, count: int) -> list[dict]:
    """Generate a batch of mock Apify-style vacancy dicts.

    - ~60-70% of vacancies match ``location``; the rest are random other cities.
    - Total generated is always >= count so filtering + slicing still yields
      enough results. We generate ``count + extra`` to ensure coverage.
    """
    city_key = _resolve_city_key(location)
    pool = COMPANY_POOLS.get(city_key, COMPANY_POOLS["Bogotá"])
    extra = max(3, count // 2)  # extra noise vacancies
    total = count + extra

    vacancies = []
    for i in range(total):
        # Decide whether this vacancy matches the target location
        if i < count:
            loc = location  # first `count` match the target
        else:
            loc = random.choice([c for c in ALL_CITIES if c != location] or ALL_CITIES)

        company = random.choice(pool)
        variants = _build_position_variants(position)
        variant = random.choice(variants)
        desc = _pick_description(position.lower())
        job_id = hashlib.md5(uuid.uuid4().bytes).hexdigest()[:10]

        vacancies.append({
            "id": job_id,
            "company": company,
            "positionName": variant,
            "location": loc,
            "postedAt": random.choice(POSTED_AT_OPTIONS),
            "jobType": random.choice(JOB_TYPE_OPTIONS),
            "salary": None,
            "rating": round(random.uniform(3.0, 4.8), 1),
            "reviewsCount": random.randint(5, 60),
            "url": f"https://co.indeed.com/viewjob?jk={job_id}",
            "externalApplyLink": (
                f"https://{company.lower().replace(' ', '')}.co/apply/{job_id}"
                if random.random() > 0.4 else None
            ),
            "companyLogo": f"https://d2q79iu7y748jz.cloudfront.net/s/_squarelogo/256x256/{job_id}",
            "description": desc,
            "descriptionHTML": f"<p>{desc}</p>",
            "urlInput": None,
        })

    return vacancies


# ── Database helpers ─────────────────────────────────────────────────

def setup_environment():
    """Creates the test DB schema directly — no init scripts invoked."""
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
    print("DB Ready")


def compute_job_hash(company, position_name, location):
    """SHA-256 business key for idempotent job insertion."""
    raw = (company + position_name + location).encode()
    return hashlib.sha256(raw).hexdigest()


# ── CLI ──────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Dynamic Apify flow simulation — scenario 06"
    )
    parser.add_argument(
        "--position",
        default="desarrollador junior",
        help='Job position to search (default: "desarrollador junior")',
    )
    parser.add_argument(
        "--location",
        default="Medellín, Colombia",
        help='Target location (default: "Medellín, Colombia")',
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of results the user wants returned (default: 1)",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete the test DB after execution (default: keep for audit)",
    )
    return parser.parse_args()


# ── Main flow ────────────────────────────────────────────────────────

def run_scenario():
    args = parse_args()
    position = args.position
    location = args.location
    requested_count = args.count
    do_cleanup = args.cleanup

    # ── Load user data from test/cv-test/ ──────────────────────────
    user_data = load_user_data()
    user_identity = user_data["identity"]
    user_stack = user_data["stack"]

    # ── Pre-execution cleanup: always start fresh ────────────────
    if DB_PATH.exists():
        os.remove(DB_PATH)
        print("DB anterior eliminada — empezando desde 0")

    setup_environment()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # ============================================================
        # PASO 1: Cost Wizard
        # ============================================================
        print()
        print("=" * 60)
        print("PASO 1: WIZARD DE COSTOS (Apify)")
        print("=" * 60)

        actor_id = "misceres/indeed-scraper"
        cost_per_item = 0.0024
        total_cost = requested_count * cost_per_item

        print("  Posición: %s" % position)
        print("  Ubicación: %s" % location)
        print("  Resultados solicitados: %d" % requested_count)
        print("  Actor consultado: %s" % actor_id)
        print("  Costo estimado: $%.4f USD" % total_cost)
        print("  -> USUARIO CONFIRMA")

        # ============================================================
        # PASO 2: Apify Call Execution (dynamic mock data)
        # ============================================================
        print()
        print("=" * 60)
        print("PASO 2: EJECUCION APIFY CALL")
        print("=" * 60)

        apify_response = generate_mock_vacancies(position, location, requested_count)
        print("  [SIMULACION] Generadas %d vacantes desde Apify" % len(apify_response))

        # ============================================================
        # PASO 3: Geographic filtering
        # ============================================================
        print()
        print("=" * 60)
        print("PASO 3: FILTRADO GEOGRÁFICO")
        print("=" * 60)

        kept = []
        for job in apify_response:
            if _matches_location(job["location"], location):
                kept.append(job)
                print("  [INSERT] %s @ %s (%s)" % (
                    job["positionName"], job["company"], job["location"]
                ))
            else:
                print("  [FILTERED] %s - no coincide con %s" % (
                    job["location"], location
                ))

        print("  Vacantes que pasan el filtro: %d de %d" % (len(kept), len(apify_response)))

        if not kept:
            print("\n  [!] Ninguna vacante coincide con la ubicacion solicitada.")
            print("  Simulación terminada sin resultados.")
            return

        # ============================================================
        # PASO 4: Persistence with Deduplication
        # ============================================================
        print()
        print("=" * 60)
        print("PASO 4: PERSISTENCIA EN TABLA JOBS")
        print("=" * 60)

        inserted_count = 0
        skipped_count = 0

        for job in kept:
            job_hash = compute_job_hash(
                job["company"], job["positionName"], job["location"]
            )

            # Idempotent check — skip duplicates
            cursor.execute(
                "SELECT job_hash FROM jobs WHERE job_hash = ?", (job_hash,)
            )
            if cursor.fetchone():
                print("  [SKIP] %s @ %s ya existe en BD" % (
                    job["positionName"], job["company"]
                ))
                skipped_count += 1
                continue

            cursor.execute(
                """INSERT INTO jobs
                   (job_hash, external_id, public_date, url, company,
                    position, location, salary, description)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
            print("  [INSERT] %s @ %s" % (job["positionName"], job["company"]))
            inserted_count += 1

        conn.commit()
        print("  Resumen: %d insertadas, %d duplicadas omitidas" % (
            inserted_count, skipped_count
        ))

        # ============================================================
        # PASO 5: Technical Analysis (real stack comparison)
        # ============================================================
        print()
        print("=" * 60)
        print("PASO 5: ANALISIS TECNICO")
        print("=" * 60)
        print("  Usuario: %s (%s)" % (
            user_identity["name"], user_identity["title"]
        ))
        print("  Stack total: %d tecnologías en %d categorías" % (
            user_data["total_items"], len(user_stack),
        ))
        print()

        cursor.execute(
            "SELECT job_hash, position, company, description "
            "FROM jobs WHERE status = 'new'"
        )
        pendientes = cursor.fetchall()
        print("  Vacantes pendientes de analisis: %d" % len(pendientes))
        print()

        for job in pendientes:
            job_hash, j_position, j_company, j_description = job

            # Real analysis against user stack
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

            # Formatted output per vacancy
            print("  [ANALYZED] %s @ %s" % (j_position, j_company))
            print("    analysis_id    : %s" % analysis_id)
            print("    description    : %s" % j_description[:90])
            print("    verdict        : %s" % analysis["verdict"])
            print("    percentage     : %s" % analysis["percentage"])
            print("    comparativa    : %s" % analysis["comparativa"])
            # observaciones can be multi-line — indent each line
            obs_lines = analysis["observaciones"].split("\n")
            print("    observaciones  :")
            for line in obs_lines:
                print("      %s" % line)
            print("    tldr           : %s" % analysis["tldr"])
            print()

        conn.commit()

        # ============================================================
        # PASO 6: DB Query (respecting --count)
        # ============================================================
        print("=" * 60)
        print("PASO 6: CONSULTA DB")
        print("=" * 60)

        cursor.execute(
            "SELECT j.company, j.position, j.location, j.url, "
            "a.verdict, a.percentage, a.comparativa, a.observaciones, a.tldr "
            "FROM jobs j "
            "JOIN analyses a ON j.job_hash = a.job_hash "
            "WHERE j.status = 'analyzed'"
        )
        all_results = cursor.fetchall()

        # Slice to requested count
        results = all_results[:requested_count]

        print("  Mostrando %d de %d resultados en DB (solicitaste %d):" % (
            len(results), len(all_results), requested_count
        ))

        for row in results:
            company, jp, loc, url, verdict, pct, comp, obs, tldr = row
            print("  ---")
            print("  Empresa: %s" % company)
            print("  Cargo: %s" % jp)
            print("  Ubicacion: %s" % loc)
            print("  URL: %s" % url)
            print("  Veredicto: %s" % verdict)
            print("  Porcentaje: %s" % pct)
            print("  Comparativa: %s" % comp)
            print("  Observaciones: %s" % obs)
            print("  TLDR: %s" % tldr)

        print("  ---")
        print("  Total registros consultados: %d" % len(results))

    finally:
        conn.close()
        if do_cleanup and DB_PATH.exists():
            os.remove(DB_PATH)
            print("\n[--cleanup] DB de prueba eliminada.")


if __name__ == "__main__":
    run_scenario()
