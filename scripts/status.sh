#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# TNSVT V2 - Status check
# Muestra estado de cada servicio del stack
# ═══════════════════════════════════════════════════════════════

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  TNSVT V2 - Stack Status"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# ─── Docker Compose services ───
if command -v docker &> /dev/null && [ -f docker-compose.dev.yml ]; then
    echo -e "${BLUE}─── Docker Services ───${NC}"
    docker compose -f docker-compose.dev.yml ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || \
    echo -e "${YELLOW}Docker Compose no disponible o no levantado${NC}"
    echo ""
fi

# ─── Health checks endpoints ───
echo -e "${BLUE}─── Service Health ───${NC}"

check_service() {
    local name=$1
    local url=$2
    local timeout=${3:-2}

    local response=$(curl -s -o /dev/null -w "%{http_code}" --max-time $timeout "$url" 2>/dev/null || echo "000")

    if [ "$response" = "200" ] || [ "$response" = "000" -a "$(timeout 1 bash -c "echo > /dev/tcp/localhost/${url##*:}" 2>/dev/null && echo connected)" ]; then
        echo -e "${GREEN}✓${NC} $name ($url) - OK"
    elif [ "$response" = "000" ]; then
        echo -e "${RED}✗${NC} $name ($url) - DOWN"
    else
        echo -e "${YELLOW}⚠${NC} $name ($url) - HTTP $response"
    fi
}

# Infraestructura
check_service "PostgreSQL + TimescaleDB" "http://localhost:5432" 1 || true
check_service "Redis" "http://localhost:6379" 1 || true
check_service "NATS Monitoring" "http://localhost:8222/healthz"
check_service "Ollama" "http://localhost:11434/api/tags"
check_service "Traefik Dashboard" "http://localhost:8080/api/overview"
check_service "Prometheus" "http://localhost:9090/-/healthy"
check_service "Grafana" "http://localhost:3001/api/health"

echo ""
echo -e "${BLUE}─── Servicios de aplicación (próximamente) ───${NC}"
SERVICES=(
    "api-gateway:8000"
    "auth-service:8001"
    "user-service:8002"
    "signal-engine:8003"
    "execution-engine:8004"
    "copy-trading:8005"
    "risk-engine:8006"
    "mt5-connector:8007"
    "audit-engine:8008"
    "ai-core:8010"
    "regime-detector:8011"
    "price-feed:8012"
    "telegram-notifier:8013"
)

for svc in "${SERVICES[@]}"; do
    name=${svc%%:*}
    port=${svc##*:}
    check_service "$name" "http://localhost:$port/health" 1
done

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo -e "  ${GREEN}Status check complete${NC}"
echo "═══════════════════════════════════════════════════════════════"
echo ""