import sqlite3
from pathlib import Path

# Ubicación de la base de datos
db_path = Path(__file__).parent.parent / "db" / "cv-pilot.db"

def init():
    try:
        # Crear directorio db/ si no existe
        db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Tabla jobs — incluye source para distinguir Apify vs manual
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
            status TEXT DEFAULT 'new',
            source TEXT DEFAULT 'manual'
        )''')
        
        # Tabla analyses — esquema completo con campos de análisis detallado
        cursor.execute('''CREATE TABLE IF NOT EXISTS analyses (
            analysis_id TEXT PRIMARY KEY,
            job_hash TEXT,
            percentage REAL,
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
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    init()
