# TNSVT V2 — comandos frecuentes

## Tests

```bash
# Unit tests (45 tests)
python -m pytest apps/ai/liquidity-engine/tests apps/integrations/news-bridge/tests apps/integrations/lst-account-bootstrap/tests

# Integration checks (18 checks)
python scripts/integration-check.py

# Go tests
cd apps/trading/execution-engine && go test ./...
cd apps/gateway/api-gateway && go build ./...
cd apps/platform/account-manager && go build ./...
```

## Go-live

```powershell
# Windows (PowerShell)
.\scripts\pre-flight-check.ps1   # valida prerrequisitos
.\scripts\go-live-lst.ps1        # arranca stack + smoke tests
```

```bash
# Linux/WSL
./scripts/pre-flight-check.sh
./scripts/go-live-lst.sh
```

## Cuenta LST manual (sin docker)

```bash
# Levantar account-manager y registrar
python scripts/register_lst_account.py

# Devuelve UUID; poner en .env
export LST_ACCOUNT_ID=<uuid>
```

## Inspeccionar estado

```bash
# NATS: mensajes en tnsvt.lst.signal
curl http://localhost:8222/jsz?streams=tnsvt

# NATS: mensajes en trading.signal.validated
curl http://localhost:8222/jsz?streams=tnsvt

# Health checks
curl http://localhost:8050/api/v1/lst/health
curl http://localhost:8051/health
curl http://localhost:8040/health
curl http://localhost:8060/api/v1/orchestrator/health
curl http://localhost:8510/health
```

## Logs

```bash
docker logs -f tnsvt-liquidity-engine
docker logs -f tnsvt-news-bridge
docker logs -f tnsvt-lst-account-bootstrap
docker logs -f tnsvt-execution-engine
docker logs -f tnsvt-orchestrator
```

## Frontend

```powershell
cd apps/frontend
npm install
npm run dev
# http://localhost:5180
```
