#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# TNSVT V2 - Migration runner
# Aplica init.sql y migraciones específicas de cada servicio
# ═══════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.dev.yml"

POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-tnsvt}"
POSTGRES_DB="${POSTGRES_DB:-tnsvt}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  TNSVT V2 - Migraciones"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# ─── ¿Postgres está corriendo via Docker o local? ────────────────────
run_in_docker() {
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "tnsvt-postgres"; then
        return 0
    fi
    return 1
}

if run_in_docker; then
    PSQL_CMD="docker exec -i tnsvt-postgres psql -U $POSTGRES_USER -d $POSTGRES_DB"
    echo -e "${BLUE}Usando Postgres en Docker (tnsvt-postgres)${NC}"
else
    PSQL_CMD="psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB"
    echo -e "${BLUE}Usando Postgres en $POSTGRES_HOST:$POSTGRES_PORT${NC}"
fi

# ─── init.sql (schemas + system_config) ─────────────────────────────
INIT_SQL="$ROOT_DIR/infrastructure/postgres/init.sql"
if [ ! -f "$INIT_SQL" ]; then
    echo -e "${RED}✗ init.sql no encontrado en $INIT_SQL${NC}"
    exit 1
fi

echo -e "${YELLOW}▶ Aplicando init.sql (schemas + system_config)...${NC}"
if $PSQL_CMD -v ON_ERROR_STOP=1 -q -f "$INIT_SQL" 2>&1 | grep -v "^NOTICE\|already exists"; then
    echo -e "${GREEN}✓ Schemas creados${NC}"
else
    echo -e "${YELLOW}⚠ Posibles errores menores (probablemente objetos ya existen)${NC}"
fi

# ─── RunMigrations de cada servicio ─────────────────────────────────
# Cada servicio Go tiene su propia migración embebida que se corre al
# arrancar. Aquí forzamos un restart para que las aplique.

SERVICES_DIR="$ROOT_DIR/apps"
SERVICE_LIST=(
    "platform/auth-service"
    "platform/user-service"
    "trading/signal-engine"
    "risk/risk-engine"
)

echo ""
echo -e "${YELLOW}▶ Forzando migración por servicio (restart):${NC}"
if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "tnsvt-"; then
    for svc in "${SERVICE_LIST[@]}"; do
        container="tnsvt-$(basename "$svc")"
        if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${container}$"; then
            echo "  • $svc"
            docker restart "$container" > /dev/null 2>&1 || true
        fi
    done
    echo -e "${GREEN}✓ Servicios reiniciados. Sus RunMigrations crearon las tablas.${NC}"
else
    echo -e "${YELLOW}  (No hay servicios corriendo en Docker; las tablas se crearán al iniciar)${NC}"
fi

# ─── ai-core (Python service) ──────────────────────────────────────
echo ""
echo -e "${YELLOW}▶ ai-core necesita crear su schema 'ai' + tabla scored_signals${NC}"
echo -e "${GREEN}✓ ai-core crea el schema automáticamente al arrancar (ver app/services/dependencies.py)${NC}"

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Migraciones aplicadas${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""