-- Canonical schema for CV-Pilot's SQLite database.
-- This file is the single source of truth. Both scripts/init.py and
-- test/scenarios/agent-mode/conftest.py read from it. Do NOT duplicate
-- the DDL elsewhere — if you add a column here, it propagates automatically
-- to both production init and the test fixture.

CREATE TABLE IF NOT EXISTS jobs (
    job_hash TEXT PRIMARY KEY,
    external_id TEXT,
    public_date TEXT,
    url TEXT,
    company TEXT,
    position TEXT,
    location TEXT,
    salary TEXT,
    description TEXT,
    status TEXT DEFAULT 'new' CHECK(status IN ('new','analyzed','discarded','applied','rejected')),
    source TEXT DEFAULT 'manual'
);

CREATE TABLE IF NOT EXISTS analyses (
    analysis_id TEXT PRIMARY KEY,
    job_hash TEXT,
    percentage REAL,
    comparativa TEXT,
    observaciones TEXT,
    verdict TEXT,
    tldr TEXT,
    contact_method TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(job_hash) REFERENCES jobs(job_hash)
);
