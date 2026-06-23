#!/usr/bin/env bash
#
# Configura el entorno virtual de Python para CV-Pilot Agent.
#
# Crea .venv/ en cv-pilot-agent/, actualiza pip e instala las dependencias
# declaradas en requirements.txt. Valida Python 3.9+. Imprime la ruta del
# venv al terminar. Si algo falla, reporta un error claro y sugiere el
# Camino A (onboarding manual, sin soporte PDF).
#
# Uso:
#   bash scripts/setup.sh
#   (ejecutar desde cv-pilot-agent/)
#

set -euo pipefail

# Resolver rutas relativas al directorio del script (no al CWD).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$AGENT_ROOT/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"
REQUIREMENTS="$AGENT_ROOT/requirements.txt"

fail() {
    echo "[fail] $1" >&2
    echo "" >&2
    echo "No se pudo configurar el entorno. Puede continuar con el Camino A" >&2
    echo "(pegar el CV manualmente, sin soporte PDF)." >&2
    exit 1
}

step()  { echo "[setup] $1"; }
okmsg() { echo "[ok]   $1"; }

# 1. Localizar Python 3.9+ en PATH.
step "Detectando Python..."
PY_BIN=""
if command -v python3 >/dev/null 2>&1; then
    PY_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PY_BIN="python"
else
    fail "Python no esta en PATH. Se requiere Python 3.9+."
fi

PY_VERSION="$("$PY_BIN" --version 2>&1 || true)"
# Salida esperada: "Python 3.x.y"
if [[ "$PY_VERSION" =~ Python[[:space:]]+([0-9]+)\.([0-9]+) ]]; then
    MAJOR="${BASH_REMATCH[1]}"
    MINOR="${BASH_REMATCH[2]}"
    if (( MAJOR < 3 )) || (( MAJOR == 3 && MINOR < 9 )); then
        fail "Python $MAJOR.$MINOR detectado. Se requiere 3.9 o superior."
    fi
else
    fail "Version de Python no reconocida: $PY_VERSION"
fi
okmsg "Python detectado: $PY_VERSION"

# 2. Crear el venv.
if [[ -x "$VENV_PYTHON" ]]; then
    step "El venv ya existe en $VENV_DIR. Se reutilizara."
else
    step "Creando venv en $VENV_DIR ..."
    if ! "$PY_BIN" -m venv "$VENV_DIR"; then
        fail "No se pudo crear el entorno virtual. Verifique permisos y espacio en disco."
    fi
    if [[ ! -x "$VENV_PYTHON" ]]; then
        fail "El venv se creo pero no se encontro python en $VENV_PYTHON."
    fi
    okmsg "Entorno virtual creado."
fi

# 3. Actualizar pip.
step "Actualizando pip..."
if ! "$VENV_PYTHON" -m pip install --upgrade pip --quiet; then
    fail "No se pudo actualizar pip."
fi

# 4. Instalar dependencias.
if [[ ! -f "$REQUIREMENTS" ]]; then
    fail "No se encontro requirements.txt en $AGENT_ROOT."
fi

step "Instalando dependencias desde requirements.txt ..."
if ! "$VENV_PIP" install -r "$REQUIREMENTS" --quiet; then
    fail "La instalacion de dependencias fallo."
fi

# 5. Verificar PyMuPDF.
step "Verificando PyMuPDF..."
if ! "$VENV_PYTHON" -c "import fitz; print('OK')"; then
    fail "PyMuPDF no se instalo correctamente."
fi

okmsg "Configuracion completa."
echo ""
echo "Entorno virtual: $VENV_DIR"
echo "Python:         $VENV_PYTHON"