#!/bin/bash

# Validar sqlite3
if ! command -v sqlite3 &> /dev/null; then
    echo "ERROR: sqlite3 no está instalado."
    exit 1
fi

DB="cv-pilot.db"

# Validar tablas
TABLES=$(sqlite3 $DB "SELECT name FROM sqlite_master WHERE type='table';")

if [[ ! $TABLES =~ "jobs" ]] || [[ ! $TABLES =~ "analyses" ]]; then
    sqlite3 $DB <<SQL
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    public_date TEXT,
    url TEXT,
    company TEXT,
    position TEXT,
    location TEXT,
    salary TEXT,
    description TEXT
);
CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT,
    verdict TEXT,
    summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(job_id) REFERENCES jobs(id)
);
SQL
    echo "DB Initialized"
else
    echo "DB Ready"
fi
