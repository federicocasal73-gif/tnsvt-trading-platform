#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# TNSVT V2 - Run all tests for one service
# ═══════════════════════════════════════════════════════════════

set -e

if [ -z "$1" ]; then
    echo "Uso: $0 <service-name>"
    echo ""
    echo "Servicios disponibles:"
    echo "  signal-engine   execution-engine   copy-trading"
    echo "  risk-engine     mt5-connector      audit-engine"
    echo "  auth-service    user-service       api-gateway"
    echo "  ai-core         regime-detector    price-feed"
    echo "  telegram-notifier"
    exit 1
fi

SERVICE=$1
LANG=${2:-go}  # go o python

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Testing service: $SERVICE (lenguaje: $LANG)"
echo "═══════════════════════════════════════════════════════════════"

if [ "$LANG" = "go" ]; then
    cd "apps/$(dirname $SERVICE)/$SERVICE" 2>/dev/null || \
    cd "apps/platform/$SERVICE" 2>/dev/null || \
    cd "apps/gateway/$SERVICE" 2>/dev/null || \
    cd "apps/infrastructure/$SERVICE" 2>/dev/null
    go test ./... -v
elif [ "$LANG" = "python" ]; then
    cd "apps/ai/$SERVICE" 2>/dev/null || \
    cd "apps/market-data/$SERVICE" 2>/dev/null || \
    cd "apps/notification/$SERVICE" 2>/dev/null
    python -m pytest tests/ -v
fi