<#
  Auto-setup a LOCAL, self-hosted Uptrace for qua-libs telemetry (Windows).

  qua-libs telemetry is OFF BY DEFAULT. This script only stands up a local
  Uptrace instance (ClickHouse + PostgreSQL + Redis + Uptrace, via Docker
  Desktop) so you have somewhere to send spans when you DO turn telemetry on
  for debugging. It does not enable telemetry itself -- see the instructions
  printed at the end.

  Requires Docker Desktop for Windows (with the WSL2 backend).
#>

$ComposeDir = Join-Path $PSScriptRoot "uptrace-local"
$Compose = Join-Path $ComposeDir "docker-compose.yml"

function Info($m) { Write-Host "[INFO]  $m" -ForegroundColor Green }
function Warn($m) { Write-Host "[WARN]  $m" -ForegroundColor Yellow }
function Err($m)  { Write-Host "[ERROR] $m" -ForegroundColor Red }

# 1. Docker (do not auto-install on Windows -- point at Docker Desktop)
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Err "Docker not found. Install Docker Desktop:"
    Err "  https://docs.docker.com/desktop/install/windows-install/"
    exit 1
}
Info ("Docker found: " + (docker --version))

# 2. docker compose v2
docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
    Err "docker compose (v2) not available. Update Docker Desktop."
    exit 1
}

# 3. compose files present
foreach ($f in @("docker-compose.yml", "config.yml")) {
    if (-not (Test-Path (Join-Path $ComposeDir $f))) {
        Err "Missing $f in $ComposeDir"
        exit 1
    }
}

# 4. tear down any previous stack
Info "Stopping any existing uptrace-local containers ..."
docker compose -f $Compose -p uptrace-local down --remove-orphans *> $null

# 5. pull + start
Info "Pulling images ..."
docker compose -f $Compose -p uptrace-local pull
if ($LASTEXITCODE -ne 0) { Err "docker compose pull failed."; exit 1 }
Info "Starting Uptrace stack (ClickHouse + PostgreSQL + Redis + Uptrace) ..."
docker compose -f $Compose -p uptrace-local up -d
if ($LASTEXITCODE -ne 0) { Err "docker compose up failed."; exit 1 }

# 6. wait for Uptrace HTTP to respond (~180s)
Info "Waiting for Uptrace to become ready ..."
$ready = $false
for ($i = 0; $i -lt 90; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:14318" -UseBasicParsing -TimeoutSec 3
        if ($r.StatusCode -eq 200) { $ready = $true; Info ("ready after ~" + ($i * 2) + "s"); break }
    } catch { }
    Start-Sleep -Seconds 2
}
if (-not $ready) {
    Err "Uptrace did not respond within ~180s."
    Err "Logs: docker compose -f `"$Compose`" -p uptrace-local logs uptrace"
    exit 1
}

$dsn = "http://project1_secret@localhost:14318?grpc=14317"

Write-Host ""
Info "=========================================="
Info " Uptrace is running locally!"
Info "=========================================="
Write-Host ""
Write-Host "  UI:    http://localhost:14318   (login: admin@example.com / admin)"
Write-Host "  gRPC:  localhost:14317"
Write-Host "  HTTP:  localhost:14318"
Write-Host ""
Write-Host "  Telemetry is OFF BY DEFAULT. To send qua-libs spans to this local"
Write-Host "  Uptrace, enable it in your shell, then run your nodes:"
Write-Host ""
Write-Host "    `$env:UPTRACE_DSN = `"$dsn`""
Write-Host "    `$env:UPTRACE_ENABLED = `"true`""
Write-Host ""
Write-Host "  Stop:  .\stop_uptrace_local.ps1            (keeps data)"
Write-Host "  Stop:  .\stop_uptrace_local.ps1 -Wipe      (deletes data)"
Write-Host ""
