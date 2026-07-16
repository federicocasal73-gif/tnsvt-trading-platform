#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# TNSVT V2 - Run all tests for one service
# ═══════════════════════════════════════════════════════════════

set -e

if [ -z "$1" ]; then
    echo "Uso: $0 <service-name> [go|python]"
    echo ""
    echo "Servicios disponibles:"
    echo "  signal-engine   execution-engine   copy-trading"
    echo "  risk-engine     mt5-connector      audit-engine"
    echo "  auth-service    user-service       api-gateway"
    echo "  price-feed"
    echo "  ai-core         (python)"
    exit 1
fi

SERVICE=$1
LANG=${2:-go}  # go o python

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Testing service: $SERVICE (lenguaje: $LANG)"
echo "═══════════════════════════════════════════════════════════════"

if [ "$LANG" = "go" ]; then
    # Try the most common Go service locations
    cd "apps/$(echo $SERVICE | cut -d/ -f1)/$(echo $SERVICE | cut -d/ -f2)" 2>/dev/null || \
    cd "apps/platform/$SERVICE" 2>/dev/null || \
    cd "apps/gateway/$SERVICE" 2>/dev/null || \
    cd "apps/trading/$SERVICE" 2>/dev/null || \
    cd "apps/risk/$SERVICE" 2>/dev/null || \
    cd "apps/audit/$SERVICE" 2>/dev/null || \
    cd "apps/broker/$SERVICE" 2>/dev/null || \
    cd "apps/market-data/$SERVICE" 2>/dev/null
    if [ -f go.mod ]; then
        go test ./... -count=1 -v
    else
        echo "ERROR: no go.mod found in $(pwd)"
        exit 1
    fi
elif [ "$LANG" = "python" ]; then
    cd "apps/ai/$SERVICE" 2>/dev/null || \
    cd "apps/market-data/$SERVICE" 2>/dev/null || \
    cd "apps/notification/$SERVICE" 2>/dev/null
    if [ -f pytest.ini ] || [ -f pyproject.toml ]; then
        python -m pytest tests/ -v
    else
        echo "ERROR: no pytest config found in $(pwd)"
        exit 1
    fi
fi