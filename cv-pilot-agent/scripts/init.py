import sqlite3
from pathlib import Path

db_path = Path(__file__).parent.parent / "cv-pilot.db"

def init():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Eliminar tablas viejas para asegurar el nuevo esquema
    cursor.execute('DROP TABLE IF EXISTS analyses')
    cursor.execute('DROP TABLE IF EXISTS jobs')
    
    # Crear tabla jobs con Business Key (job_hash)
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
    
    # Crear tabla analyses
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
    print("DB Initialized with new schema")

if __name__ == "__main__":
    init()
