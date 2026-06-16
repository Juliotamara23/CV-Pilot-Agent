import sqlite3
from pathlib import Path

# Ubicación de la base de datos
db_path = Path(__file__).parent.parent / "cv-pilot.db"

def init():
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Esquema definitivo (Idempotente)
        cursor.execute('''CREATE TABLE IF NOT EXISTS jobs (
            job_hash TEXT PRIMARY KEY,
            indeed_id TEXT,
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_hash TEXT,
            verdict TEXT,
            summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(job_hash) REFERENCES jobs(job_hash)
        )''')
        
        conn.commit()
        conn.close()
        print("DB Ready")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    init()
