<#
  Stop the local self-hosted Uptrace started by setup_uptrace_local.ps1.

  By default this stops and removes the containers but KEEPS your data (spans).
  Pass -Wipe to also delete the data volumes (ClickHouse + PostgreSQL).
#>
param([switch]$Wipe)

$Compose = Join-Path (Join-Path $PSScriptRoot "uptrace-local") "docker-compose.yml"

docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] docker compose not found." -ForegroundColor Red
    exit 1
}

if ($Wipe) {
    Write-Host "[WARN]  Stopping Uptrace and DELETING all data volumes (ClickHouse + PostgreSQL) ..." -ForegroundColor Yellow
    docker compose -f $Compose -p uptrace-local down --remove-orphans --volumes
} else {
    Write-Host "[INFO]  Stopping Uptrace (data preserved; pass -Wipe to delete it) ..." -ForegroundColor Green
    docker compose -f $Compose -p uptrace-local down --remove-orphans
}
Write-Host "[INFO]  Done." -ForegroundColor Green
