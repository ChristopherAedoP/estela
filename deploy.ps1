# deploy.ps1 — sincroniza server/ al servidor por scp.
#
# Configura el destino con variables de entorno (no se hardcodean datos):
#   $env:ESTELA_DEPLOY_HOST = "usuario@host"      # ej: user@servidor
#   $env:ESTELA_DEPLOY_DEST = "/opt/actas-server" # ruta destino (opcional)
#
# Requiere SSH por clave (sin password) y sudo NOPASSWD en el servidor, o ajusta
# los comandos remotos a tu entorno.
#
# Uso:  pwsh -File deploy.ps1
$ErrorActionPreference = "Stop"

$Vm = $env:ESTELA_DEPLOY_HOST
if (-not $Vm) {
    Write-Host "Falta configurar el destino. Define la variable de entorno:" -ForegroundColor Yellow
    Write-Host '  $env:ESTELA_DEPLOY_HOST = "usuario@host"'
    exit 1
}
$dest = if ($env:ESTELA_DEPLOY_DEST) { $env:ESTELA_DEPLOY_DEST } else { "/opt/actas-server" }
$src = Join-Path $PSScriptRoot "server"

Write-Host "Sincronizando $src -> ${Vm}:$dest ..."

ssh $Vm "mkdir -p $dest" 2>&1 | Out-Null

$items = @("app", "tests", "pyproject.toml", "pytest.ini", "actas-server.service", "actas-server-start.sh")
foreach ($it in $items) {
    $p = Join-Path $src $it
    if (Test-Path -LiteralPath $p) {
        scp -q -r $p "${Vm}:$dest/" 2>&1 | Out-Null
    }
}
# scp no preserva el bit de ejecucion al copiar desde Windows.
ssh $Vm "chmod +x $dest/actas-server-start.sh" 2>&1 | Out-Null

Write-Host "Deploy completo. Reinicia el servicio: ssh $Vm 'sudo systemctl restart actas-server'"
Write-Host "NOTA: solo se actualiza el codigo. El venv, el unit de systemd y" -ForegroundColor Yellow
Write-Host "      /etc/actas-server.env se gestionan a mano en el servidor." -ForegroundColor Yellow
