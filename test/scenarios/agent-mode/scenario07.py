import sqlite3
import os
from pathlib import Path
import json
import hashlib

import sqlite3
import os
from pathlib import Path
import json
import hashlib
import subprocess

# Configuración del entorno de prueba
DB_PATH = Path(__file__).parent.parent.parent.parent / "test" / "cv-pilot-test.db"

def setup_db():
    # Usar el script unificado de inicialización
    subprocess.run(["python", str(Path(__file__).parent.parent.parent.parent / "cv-pilot-agent" / "scripts" / "init.py")], check=True)
    return sqlite3.connect(DB_PATH)

def test_chaos_scenario():
    conn = setup_db()
    cursor = conn.cursor()
    print("--- TEST CAOS: Inyectando datos corruptos ---")
    # ... (Resto de la lógica) ...

def test_chaos_scenario():
    conn = setup_db()
    cursor = conn.cursor()
    print("--- TEST CAOS: Inyectando datos corruptos ---")

    # JSON Malformado/Incompleto (Falta 'description' y 'id')
    corrupted_data = [
        {"positionName": "DevOps", "company": "Empresa X"}, 
        {"id": "caca-001", "positionName": "Dev", "company": "Empresa Y"}
    ]

    for job in corrupted_data:
        try:
            # Intentar insertar
            job_hash = hashlib.sha256((job.get('company', '') + job.get('positionName', '')).encode()).hexdigest()
            cursor.execute("INSERT INTO jobs (job_hash, indeed_id, position, company) VALUES (?, ?, ?, ?)", 
                           (job_hash, job.get('id'), job.get('positionName'), job.get('company')))
            print(f"  [INSERT] {job.get('company')} - {job.get('positionName')}")
        except Exception as e:
            print(f"  [EXPECTED ERROR] {e}")

    # Validar integridad
    cursor.execute("SELECT * FROM jobs WHERE description IS NULL")
    invalidos = cursor.fetchall()
    print(f"\nTrabajos inválidos detectados: {len(invalidos)}")
    
    conn.commit()
    conn.close()
    
    # Cleanup
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
        print("\n--- DB de juguete eliminada. Prueba terminada ---")

if __name__ == "__main__":
    test_chaos_scenario()
