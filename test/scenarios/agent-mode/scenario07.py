import sqlite3
import hashlib
import os
import subprocess
import sys
from pathlib import Path

# Configuración del entorno de prueba
DB_PATH = Path(__file__).parent.parent.parent.parent / "test" / "cv-pilot-test.db"
INIT_SCRIPT = Path(__file__).parent / "init_test.py"


def setup_db():
    """Inicializa la base de datos de prueba usando init_test.py y retorna la conexión."""
    subprocess.run([sys.executable, str(INIT_SCRIPT)], check=True)
    return sqlite3.connect(DB_PATH)


def test_chaos_scenario():
    """Inyecta datos corruptos y valida que la integridad se mantiene."""
    conn = setup_db()
    cursor = conn.cursor()
    print("--- TEST CAOS: Inyectando datos corruptos ---")

    # JSON Malformado/Incompleto (Falta 'description' y 'id')
    corrupted_data = [
        {"positionName": "DevOps", "company": "Empresa X"},
        {"id": "caca-001", "positionName": "Dev", "company": "Empresa Y"},
    ]

    for job in corrupted_data:
        try:
            job_hash = hashlib.sha256(
                (job.get("company", "") + job.get("positionName", "")).encode()
            ).hexdigest()
            cursor.execute(
                "INSERT INTO jobs (job_hash, external_id, position, company) VALUES (?, ?, ?, ?)",
                (job_hash, job.get("id"), job.get("positionName"), job.get("company")),
            )
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
    if DB_PATH.exists():
        os.remove(DB_PATH)
        print("\n--- DB de juguete eliminada. Prueba terminada ---")


if __name__ == "__main__":
    test_chaos_scenario()
