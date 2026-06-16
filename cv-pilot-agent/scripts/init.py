import sqlite3
from pathlib import Path

db_path = Path(__file__).parent.parent / "cv-pilot.db"

def init():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Verificar si las tablas existen
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    
    if 'jobs' in tables and 'analyses' in tables:
        print("DB Ready")
    else:
        cursor.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, public_date TEXT, url TEXT, company TEXT, position TEXT, location TEXT, salary TEXT, description TEXT);')
        cursor.execute('CREATE TABLE IF NOT EXISTS analyses (id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT, verdict TEXT, summary TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(job_id) REFERENCES jobs(id));')
        conn.commit()
        print("DB Initialized")
    conn.close()

if __name__ == "__main__":
    init()
