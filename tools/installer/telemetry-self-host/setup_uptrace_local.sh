#!/usr/bin/env bash
#
# Auto-setup a LOCAL, self-hosted Uptrace for qua-libs telemetry.
#
# qua-libs telemetry is OFF BY DEFAULT. This script only stands up a local
# Uptrace instance (ClickHouse + PostgreSQL + Redis + Uptrace, via Docker) so
# you have somewhere to send spans when you DO turn telemetry on for debugging.
# It does not enable telemetry itself -- see the instructions printed at the end.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="${SCRIPT_DIR}/uptrace-local"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { printf "${GREEN}[INFO]${NC}  %s\n" "$*"; }
warn()  { printf "${YELLOW}[WARN]${NC}  %s\n" "$*"; }
error() { printf "${RED}[ERROR]${NC} %s\n" "$*" >&2; }

# ── 1. Docker ───────────────────────────────────────────────────────
if command -v docker &>/dev/null; then
    info "Docker found: $(docker --version)"
else
    warn "Docker not found. Attempting to install via get.docker.com ..."
    if command -v curl &>/dev/null; then
        curl -fsSL https://get.docker.com | sh
    elif command -v wget &>/dev/null; then
        wget -qO- https://get.docker.com | sh
    else
        error "Neither curl nor wget available. Install Docker manually:"
        error "  https://docs.docker.com/engine/install/"
        exit 1
    fi
    command -v docker &>/dev/null || { error "Docker installation failed. Install it manually and re-run."; exit 1; }
    info "Docker installed: $(docker --version)"
fi

# ── 2. docker compose (v2 plugin or standalone) ─────────────────────
if docker compose version &>/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &>/dev/null; then
    COMPOSE_CMD="docker-compose"
else
    error "docker compose (v2 plugin) or docker-compose (standalone) not found."
    error "  https://docs.docker.com/compose/install/"
    exit 1
fi
info "Using: ${COMPOSE_CMD}"

# ── 3. Verify compose files exist ───────────────────────────────────
for f in docker-compose.yml config.yml; do
    [[ -f "${COMPOSE_DIR}/${f}" ]] || { error "Missing ${COMPOSE_DIR}/${f}"; exit 1; }
done

# ── 4. Tear down any previous stack ─────────────────────────────────
info "Stopping any existing uptrace-local containers ..."
${COMPOSE_CMD} -f "${COMPOSE_DIR}/docker-compose.yml" -p uptrace-local down --remove-orphans 2>/dev/null || true
if docker ps -a --format '{{.Names}}' | grep -qx uptrace; then
    docker rm -f uptrace 2>/dev/null || true
fi

# ── 5. Pull images & start ──────────────────────────────────────────
info "Pulling images ..."
${COMPOSE_CMD} -f "${COMPOSE_DIR}/docker-compose.yml" -p uptrace-local pull
info "Starting Uptrace stack (ClickHouse + PostgreSQL + Redis + Uptrace) ..."
${COMPOSE_CMD} -f "${COMPOSE_DIR}/docker-compose.yml" -p uptrace-local up -d

# ── 6. Wait for Uptrace HTTP to respond ─────────────────────────────
info "Waiting for Uptrace to become ready ..."
MAX_WAIT=180; ELAPSED=0
while ! curl -sf http://localhost:14318 >/dev/null 2>&1; do
    sleep 2; ELAPSED=$((ELAPSED + 2))
    if [[ ${ELAPSED} -ge ${MAX_WAIT} ]]; then
        error "Uptrace did not respond within ${MAX_WAIT}s."
        error "Logs: ${COMPOSE_CMD} -f ${COMPOSE_DIR}/docker-compose.yml -p uptrace-local logs uptrace"
        exit 1
    fi
done

DSN="http://project1_secret@localhost:14318?grpc=14317"

# ── 7. Success + how to enable telemetry (off by default) ───────────
echo ""
info "=========================================="
info " Uptrace is running locally!"
info "=========================================="
echo ""
echo "  UI:    http://localhost:14318   (login: admin@example.com / admin)"
echo "  gRPC:  localhost:14317"
echo "  HTTP:  localhost:14318"
echo ""
echo "  Telemetry in the installer writes .qua-libs/telemetry.toml with enabled=true"
echo "  and a local SQLite store. Add a DSN to also send spans here:"
echo ""
echo "    [telemetry]"
echo "    enabled = true"
echo "    dsn = \"${DSN}\""
echo ""
echo "    [telemetry.local]"
echo "    path = \".qua-libs/traces.sqlite\""
echo ""
echo "    # optional env override"
echo "    export UPTRACE_DSN=\"${DSN}\""
echo "    export UPTRACE_ENABLED=\"true\""
echo ""
echo "    # PowerShell"
echo "    \$env:UPTRACE_DSN = \"${DSN}\""
echo "    \$env:UPTRACE_ENABLED = \"true\""
echo ""
echo "  Stop:  ${COMPOSE_CMD} -f \"${COMPOSE_DIR}/docker-compose.yml\" -p uptrace-local down"
echo "  Logs:  ${COMPOSE_CMD} -f \"${COMPOSE_DIR}/docker-compose.yml\" -p uptrace-local logs -f uptrace"
echo ""
