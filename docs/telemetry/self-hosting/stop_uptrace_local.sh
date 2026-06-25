#!/usr/bin/env bash
#
# Stop the local self-hosted Uptrace started by setup_uptrace_local.sh.
#
# By default this stops and removes the containers but KEEPS your data (spans).
# Pass --wipe (or -v) to also delete the data volumes (ClickHouse + PostgreSQL).
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE="${SCRIPT_DIR}/uptrace-local/docker-compose.yml"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info() { printf "${GREEN}[INFO]${NC}  %s\n" "$*"; }
warn() { printf "${YELLOW}[WARN]${NC}  %s\n" "$*"; }

if docker compose version &>/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &>/dev/null; then
    COMPOSE_CMD="docker-compose"
else
    printf "${RED}[ERROR]${NC} docker compose not found.\n" >&2
    exit 1
fi

WIPE=""
if [[ "${1:-}" == "--wipe" || "${1:-}" == "-v" ]]; then
    WIPE="--volumes"
fi

if [[ -n "${WIPE}" ]]; then
    warn "Stopping Uptrace and DELETING all data volumes (ClickHouse + PostgreSQL) ..."
else
    info "Stopping Uptrace (data preserved; pass --wipe to delete it) ..."
fi

${COMPOSE_CMD} -f "${COMPOSE}" -p uptrace-local down --remove-orphans ${WIPE}
info "Done."
