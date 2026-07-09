-- Canonical schema for CV-Pilot's SQLite database.
-- This file is the single source of truth. Both scripts/init.py and
-- test/scenarios/agent-mode/conftest.py read from it. Do NOT duplicate
-- the DDL elsewhere — if you add a column here, it propagates automatically
-- to both production init and the test fixture.
--
-- Source of truth: cv-pilot-agent/db/cv-pilot.db (production).
-- Any structural change must be verified by test_init_script_produces_matching_production_schema.

CREATE TABLE IF NOT EXISTS analyses (
    analysis_id TEXT PRIMARY KEY,
    job_hash TEXT NOT NULL,
    percentage TEXT NOT NULL,
    comparativa TEXT,
    observaciones TEXT,
    verdict TEXT NOT NULL,
    tldr TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    contact_method TEXT,
    FOREIGN KEY(job_hash) REFERENCES jobs(job_hash)
);

CREATE TABLE IF NOT EXISTS jobs (
    job_hash TEXT PRIMARY KEY,
    external_id TEXT,
    public_date TEXT,
    url TEXT,
    company TEXT NOT NULL,
    position TEXT NOT NULL,
    location TEXT,
    salary TEXT,
    description TEXT,
    source TEXT DEFAULT 'manual',
    status TEXT DEFAULT 'new',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
