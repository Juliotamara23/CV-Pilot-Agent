import sqlite3
import os
from pathlib import Path

# Test DB lives under test/ to keep it out of the main flow
DB_PATH = Path(__file__).parent.parent.parent.parent / "test" / "cv-pilot-test.db"

def init_test_db():
    """Initialize a clean test database using the production schema."""
    if DB_PATH.exists():
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''CREATE TABLE jobs (
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

    # Schema must stay in sync with production
    cursor.execute('''CREATE TABLE analyses (
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
    print(f"TEST_DB_READY: {DB_PATH}")

if __name__ == "__main__":
    init_test_db()
