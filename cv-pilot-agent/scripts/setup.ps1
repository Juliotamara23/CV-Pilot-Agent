<#
.SYNOPSIS
    Configura el entorno virtual de Python para CV-Pilot Agent.

.DESCRIPTION
    Crea .venv/ en cv-pilot-agent/, actualiza pip e instala las dependencias
    declaradas en requirements.txt. Validar Python 3.9+. Imprime la ruta del
    venv al terminar. Si algo falla, reporta un error claro y sugiere el
    Camino A (onboarding manual, sin soporte PDF).

.USO
    .\scripts\setup.ps1
    (ejecutar desde cv-pilot-agent/)
#>

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

# Resolver rutas relativas al directorio del script (no al CWD).
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$AgentRoot   = Split-Path -Parent $ScriptDir
$VenvDir     = Join-Path $AgentRoot ".venv"
$VenvPython  = Join-Path $VenvDir "Scripts\python.exe"
$VenvPip     = Join-Path $VenvDir "Scripts\pip.exe"
$Requirements = Join-Path $AgentRoot "requirements.txt"

function Write-Step  { param([string]$msg) Write-Host "[setup] $msg" -ForegroundColor Cyan }
function Write-Ok    { param([string]$msg) Write-Host "[ok]   $msg" -ForegroundColor Green }
function Write-Fail  { param([string]$msg)
    Write-Host "[fail] $msg" -ForegroundColor Red
    Write-Host ""
    Write-Host "No se pudo configurar el entorno. Puede continuar con el Camino A" -ForegroundColor Yellow
    Write-Host "(pegar el CV manualmente, sin soporte PDF)." -ForegroundColor Yellow
    exit 1
}

# 1. Localizar Python 3.9+ en PATH.
Write-Step "Detectando Python..."
$pyCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pyCmd) {
    Write-Fail "Python no esta en PATH. Se requiere Python 3.9+."
}

$versionOutput = & python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Fail "No se pudo obtener la version de Python: $versionOutput"
}

# $versionOutput suele ser "Python 3.x.y".
if ($versionOutput -match "Python (\d+)\.(\d+)") {
    $major = [int]$Matches[1]
    $minor = [int]$Matches[2]
    if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 9)) {
        Write-Fail "Python $major.$minor detectado. Se requiere 3.9 o superior."
    }
} else {
    Write-Fail "Version de Python no reconocida: $versionOutput"
}
Write-Ok "Python detectado: $versionOutput"

# 2. Crear el venv.
if (Test-Path -LiteralPath $VenvPython) {
    Write-Step "El venv ya existe en $VenvDir. Se reutilizara."
} else {
    Write-Step "Creando venv en $VenvDir ..."
    & python -m venv $VenvDir
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $VenvPython)) {
        Write-Fail "No se pudo crear el entorno virtual. Verifique permisos y espacio en disco."
    }
    Write-Ok "Entorno virtual creado."
}

# 3. Actualizar pip.
Write-Step "Actualizando pip..."
& $VenvPython -m pip install --upgrade pip --quiet 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) {
    Write-Fail "No se pudo actualizar pip."
}

# 4. Instalar dependencias.
if (-not (Test-Path -LiteralPath $Requirements)) {
    Write-Fail "No se encontro requirements.txt en $AgentRoot."
}

Write-Step "Instalando dependencias desde requirements.txt ..."
& $VenvPip install -r $Requirements --quiet 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) {
    Write-Fail "La instalacion de dependencias fallo."
}

# 5. Verificar PyMuPDF.
Write-Step "Verificando PyMuPDF..."
& $VenvPython -c "import fitz; print('OK')" 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) {
    Write-Fail "PyMuPDF no se instalo correctamente."
}

Write-Ok "Configuracion completa."
Write-Host ""
Write-Host "Entorno virtual: $VenvDir" -ForegroundColor Green
Write-Host "Python:         $VenvPython" -ForegroundColor Green