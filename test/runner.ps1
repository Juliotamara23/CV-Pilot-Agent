# Runner de Pruebas de CV-Pilot

# Este script actúa como tablero de control.
# NO ejecuta el LLM, sino que te indica qué escenario debe verificar el agente.

$scenarios = Get-ChildItem ".\test\scenarios\*.md"

Write-Host "--- CV-Pilot Test Suite ---" -ForegroundColor Yellow
foreach ($scenario in $scenarios) {
    Write-Host "`n[Escenario Detectado]: $($scenario.Name)" -ForegroundColor Cyan
    $content = Get-Content $scenario.FullName
    Write-Host $content -ForegroundColor White
    
    Write-Host "`nPara ejecutar este test, copia el siguiente comando y dáselo al agente:" -ForegroundColor Yellow
    Write-Host "Ejecutar escenario: $($scenario.BaseName)" -ForegroundColor Green
    Read-Host "Presiona Enter para continuar con el siguiente escenario..."
}
