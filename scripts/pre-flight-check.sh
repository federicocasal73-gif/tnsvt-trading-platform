#!/usr/bin/env bash
# TNSVT V2 — pre-flight check para go-live LST (bash)
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PASS=0
FAIL=0

check() {
    local name="$1"
    local ok="$2"
    local hint="${3:-}"
    if [ "$ok" = "1" ]; then
        echo "  [PASS] $name"
        PASS=$((PASS+1))
    else
        echo "  [FAIL] $name $hint"
        FAIL=$((FAIL+1))
    fi
}

echo "== TNSVT V2 pre-flight check =="
echo ""

echo "[1/5] Docker"
if command -v docker >/dev/null 2>&1; then
    check "docker command available" 1
    if docker info >/dev/null 2>&1; then
        ver=$(docker info --format '{{.ServerVersion}}' 2>/dev/null || echo "?")
        check "docker daemon responsive (version $ver)" 1
    else
        check "docker daemon responsive" 0 "(Docker Desktop no esta corriendo)"
    fi
else
    check "docker command available" 0 "(instala Docker Desktop)"
fi

echo ""
echo "[2/5] .env file"
if [ -f "$ROOT/.env" ]; then
    check ".env exists" 1
    grep -q "^LST_LOGIN=12345678" "$ROOT/.env" && check "LST_LOGIN=12345678" 1 || check "LST_LOGIN=12345678" 0
    grep -q "^LST_SERVER=YourBroker-MT5" "$ROOT/.env" && check "LST_SERVER=YourBroker-MT5" 1 || check "LST_SERVER=YourBroker-MT5" 0
    grep -qE "^LST_PASSWORD=.+" "$ROOT/.env" && check "LST_PASSWORD set" 1 || check "LST_PASSWORD set" 0
    grep -qE "^DEFAULT_TENANT_ID=[0-9a-f-]{36}" "$ROOT/.env" && check "DEFAULT_TENANT_ID is a valid UUID" 1 || check "DEFAULT_TENANT_ID is a valid UUID" 0
else
    check ".env exists at repo root" 0 "(cp .env.example .env)"
fi

echo ""
echo "[3/5] Critical ports"
PORTS=(5432 6379 4222 8222 8000 8001 8003 8004 8005 8006 8007 8050 8051 8060 8200 8510 8522)
for p in "${PORTS[@]}"; do
    if ss -ltn 2>/dev/null | grep -q ":$p "; then
        check "port $p free" 0 "(ocupado)"
    else
        check "port $p free" 1
    fi
done

echo ""
echo "[4/5] MT5 terminal"
MT5_FOUND=0
for p in "/mnt/c/Program Files/MetaTrader 5/terminal64.exe" \
         "/mnt/c/Program Files/FTMO MetaTrader 5/terminal64.exe"; do
    if [ -f "$p" ]; then
        echo "  [OK] $p"
        MT5_FOUND=1
    fi
done
[ "$MT5_FOUND" = "1" ] && check "MT5 terminal found" 1 || check "MT5 terminal found" 0

echo ""
echo "[5/5] docker-compose sanity"
if [ -f "$ROOT/docker-compose.dev.yml" ]; then
    grep -q "lst-account-bootstrap:" "$ROOT/docker-compose.dev.yml" && check "lst-account-bootstrap service" 1 || check "lst-account-bootstrap service" 0
    grep -q "tnsvt-secrets:" "$ROOT/docker-compose.dev.yml" && check "tnsvt-secrets volume" 1 || check "tnsvt-secrets volume" 0
    grep -q 'DEFAULT_ACCOUNT_ID: ${FTMO_ACCOUNT_ID:-default}' "$ROOT/docker-compose.dev.yml" && check "FTMO_ACCOUNT_ID env wired" 1 || check "FTMO_ACCOUNT_ID env wired" 0
fi

echo ""
echo "================================"
echo "PASS: $PASS"
echo "FAIL: $FAIL"
echo "================================"

if [ "$FAIL" -gt 0 ]; then
    echo ""
    echo "Proximos pasos:"
    [ "$MT5_FOUND" = "0" ] && echo "  - Verifica que el terminal MT5 este instalado (NO reiniciar)"
    exit 1
fi

echo ""
echo "Todo listo para go-live:"
echo "  ./scripts/go-live-lst.sh"
exit 0
