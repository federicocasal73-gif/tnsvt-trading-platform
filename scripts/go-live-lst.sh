#!/usr/bin/env bash
# TNSVT V2 — go-live LST (YourBroker)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo -e "\033[36m== TNSVT V2 go-live LST ==\033[0m"

echo ""
echo -e "\033[36m[0/4] Pre-flight check...\033[0m"
bash "$ROOT/scripts/pre-flight-check.sh"
if [ $? -ne 0 ]; then
    echo -e "\033[31mPre-flight check fallo. Corrige los problemas y vuelve a intentar.\033[0m"
    exit 1
fi

if [ ! -f .env ]; then
    echo -e "\033[33mNo existe .env; copiando .env.example\033[0m"
    cp .env.example .env
fi

echo -e "\033[36m[1/4] Levantando docker compose...\033[0m"
docker compose -f docker-compose.dev.yml up -d

echo -e "\033[36m[2/4] Esperando health checks...\033[0m"
declare -A services=(
    [postgres]="http://localhost:5432"
    [redis]="http://localhost:6379"
    [nats]="http://localhost:8222/healthz"
    [account-manager]="http://localhost:8510/health"
    [mt5-connector]="http://localhost:8007/health"
    [liquidity-engine]="http://localhost:8050/health"
    [orchestrator]="http://localhost:8060/api/v1/orchestrator/health"
    [news-analyzer]="http://localhost:8051/health"
    [macro-fetcher]="http://localhost:8040/health"
)

for svc in "${!services[@]}"; do
    url="${services[$svc]}"
    ok=0
    for i in $(seq 1 30); do
        code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 "$url" || true)
        if [ -n "$code" ] && [ "$code" -ge 200 ] && [ "$code" -lt 500 ]; then
            echo -e "  $svc: \033[32mOK\033[0m"
            ok=1
            break
        fi
        sleep 2
    done
    if [ "$ok" -eq 0 ]; then
        echo -e "  $svc: \033[31mTIMEOUT\033[0m"
    fi
done

echo -e "\033[36m[3/4] Esperando lst-account-bootstrap...\033[0m"
uuid=""
for i in $(seq 1 60); do
    status=$(docker inspect -f '{{.State.Status}}' tnsvt-lst-account-bootstrap 2>/dev/null || echo "")
    exitCode=$(docker inspect -f '{{.State.ExitCode}}' tnsvt-lst-account-bootstrap 2>/dev/null || echo "")
    if [ "$status" = "exited" ] && [ "$exitCode" = "0" ]; then
        echo -e "  lst-account-bootstrap: \033[32mOK\033[0m"
        break
    fi
    if [ "$status" = "exited" ] && [ "$exitCode" != "0" ] && [ -n "$exitCode" ]; then
        echo -e "  lst-account-bootstrap: \033[31mFAILED\033[0m (exit $exitCode)"
        docker logs --tail 50 tnsvt-lst-account-bootstrap
        exit 1
    fi
    sleep 2
done

if [ -f /var/run/tnsvt/secrets/lst_account_id ]; then
    uuid=$(cat /var/run/tnsvt/secrets/lst_account_id)
    echo -e "  LST account id: \033[36m$uuid\033[0m"
fi

echo -e "\033[36m[4/4] Smoke tests del gateway...\033[0m"
gateway_tests=(
    "news latest|http://localhost:8000/api/v1/news/latest?limit=5"
    "macro indicators|http://localhost:8000/api/v1/macro/indicators"
    "lst zones latest|http://localhost:8000/api/v1/lst/zones/latest?symbol=XAUUSD&timeframe=H1"
    "orchestrator health|http://localhost:8000/api/v1/orchestrator/health"
    "lst health|http://localhost:8000/api/v1/lst/health"
)

for entry in "${gateway_tests[@]}"; do
    name="${entry%%|*}"
    url="${entry##*|}"
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$url" || echo "FAIL")
    echo "  $name: HTTP $code"
done

echo ""
echo -e "\033[36m== go-live completo ==\033[0m"
echo ""
echo -e "\033[33mPróximos pasos:\033[0m"
echo "  1. Compilar EA MQL5: copia apps/broker/mt5-liquidity/MQL5/* a tu terminal"
echo "  2. Tools > Options > Expert Advisors > Allow WebRequest: http://localhost:8050"
echo "  3. Arrastrar EA LiquidityZones al chart XAUUSD H1"
echo "  4. Verificar logs MT5: 'Published N zones to localhost:8050/zones (status=200)'"
echo "  5. Frontend: http://localhost:5180 > Dashboard / News / Macro / Signals"
