# build.ps1 — compila Estela.exe con PyInstaller (un solo binario, sin consola).
# Requiere el venv ya creado: python -m venv .venv ; .venv\Scripts\pip install -r requirements.txt pyinstaller
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "No existe el venv. Crealo con:" -ForegroundColor Yellow
    Write-Host "  python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt pyinstaller"
    exit 1
}

# Cerrar instancia en ejecucion para no bloquear el .exe
Get-Process Estela -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500

& $py -m PyInstaller --noconfirm --clean --name Estela --windowed --onefile `
    --collect-submodules actas -p . run.py

Write-Host ""
Write-Host "Listo: dist\Estela.exe" -ForegroundColor Green
