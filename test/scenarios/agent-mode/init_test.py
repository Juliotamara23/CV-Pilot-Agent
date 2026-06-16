import sqlite3
import os
from pathlib import Path

# La DB se crea en la carpeta test para mantenerse fuera del flujo principal
DB_PATH = Path(__file__).parent.parent.parent.parent / "test" / "cv-pilot-test.db"

def init_test_db():
    """Inicializa una base de datos limpia para pruebas."""
    if DB_PATH.exists():
        os.remove(DB_PATH)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE jobs (
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
    
    cursor.execute('''CREATE TABLE analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_hash TEXT,
        verdict TEXT,
        summary TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(job_hash) REFERENCES jobs(job_hash)
    )''')
    
    conn.commit()
    conn.close()
    print(f"TEST_DB_READY: {DB_PATH}")

if __name__ == "__main__":
    init_test_db()
