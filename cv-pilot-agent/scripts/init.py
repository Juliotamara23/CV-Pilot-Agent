import sqlite3
from pathlib import Path

# Database file location
db_path = Path(__file__).parent.parent / "db" / "cv-pilot.db"


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Idempotent schema migrations — adds missing columns to existing DBs.

    New users get the full schema from the CREATE TABLE statements below.
    Existing DBs opened by this function get missing columns added
    automatically so the init script never needs to be modified for
    additive changes.
    """
    try:
        conn.execute("ALTER TABLE analyses ADD COLUMN contact_method TEXT")
    except sqlite3.OperationalError:
        # Column already exists — safe to ignore.
        pass


def init():
    try:
        # Create db/ directory if it does not exist
        db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # jobs table — strict status validation
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
            status TEXT DEFAULT 'new' CHECK(status IN ('new','analyzed','discarded','applied','rejected')),
            source TEXT DEFAULT 'manual'
        )''')
        
        # analyses table — full schema with detailed analysis fields
        cursor.execute('''CREATE TABLE IF NOT EXISTS analyses (
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
        )''')
        
        conn.commit()

        # Run idempotent migrations for existing databases
        _ensure_schema(conn)

        conn.close()
        print("DB Ready")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    init()
