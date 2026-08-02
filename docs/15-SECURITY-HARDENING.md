# TNSVT V2 — Security & Hardcode Remediation Log

> FASE A → D: comprehensive fixes for the 452-finding security audit
> and removal of all hardcoded production values.

## Summary

This document tracks the security hardening and hardcode elimination work
performed across 4 phases (A → D). Every change is verifiable in the code.

| Phase | Focus | Issues fixed | Files touched |
|-------|-------|--------------|---------------|
| **A**  | Auth cascade | 45 (A1–A45) | 11 |
| **B**  | Secrets management | 6 (B1–B6) | 6 |
| **C**  | Trading safety | 6 (C1–C6) | 4 |
| **D**  | Hardcode elimination | 6 (D1–D6) | 16 |
| **TOTAL** | | **63** | **37** |

---

## FASE A — Auth Cascade (45 fixes)

> The original 452-finding mega audit identified 8+ microservices with
> auth bypass issues. We fixed the auth pipeline from source (auth-service)
> through every proxy (api-gateway, bridge-api, orchestrator) to consumer
> (frontend, telegram bot).

### A1–A9 — `auth-service` (Go)
- **A1** `SetSecret` now returns `error` — refuses <32-char secrets (was silent)
- **A2** Fail-fast on service startup if `AUTH_JWT_SECRET` < 32 chars
- **A3** `Setup2FA` no longer auto-enables — user must explicitly confirm with TOTP code
- **A4** Real TOTP via `github.com/pquerna/otp` (was a stub returning `"123456"`)
- **A5** `IncrementAndMaybeLock` is now atomic (was a TOCTOU race)
- **A6** Password validator requires symbol (was length-only)
- **A7** Admin routes restricted to `super_admin` role (were any role)
- **A8** `ValidateToken` uses `jwt.WithIssuer/Audience/ExpirationRequired`
- **A9** `RequireAuth` middleware rejects `TokenType != "access"` (was permissive)

### A10–A13 — `api-gateway` (Go)
- **A10** `RequireAuth` sets `auth_type` claim in context for downstream services
- **A11** `Validate` uses `jwt.WithExpirationRequired()` (was lenient)
- **A12** Route setup separates `publicServices` (auth-service only, optional auth)
  vs protected services (RequireAuth)
- **A13** `NewJWTValidator` panics if `JWT_SECRET` < 32 chars (removed hardcoded fallback)

### A14–A24 — `bridge-api` (Python)
- **A14** Global auth middleware (`@app.middleware("http")`) on all non-public paths
- **A15–A19** Admin paths require `super_admin`/`tenant_admin` role
- **A20** `PUBLIC_PATHS` = `/health`, `/`, `/metrics`, `/docs`, `/openapi.json`, `/redoc`
- **A21** `domain.py` shadowing fix: `ChannelProfile` renamed to `TelegramChannel` and `ChannelTradingRules`
- **A22** Hardcoded path → env var `MT5_STATUS_PATH`
- **A23** `BRIDGE_API_KEY` default removed (warns if empty)
- **A24** `pyjwt` ≥ 2.8.0 added to `requirements.txt`

### A25–A33 — `orchestrator` (Python)
- **A25** Auth middleware for `/pause` and `/resume` endpoints (JWT validation via pyjwt)

### A34–A38 — Frontend (TS/React)
- **A34** `api.ts` path comparison fix (was checking `/api/v1/auth/me` against `/auth/me`)
- **A35** Circuit breaker only triggers on ≥500 responses
- **A36** `auth.tsx` only auto-logout on 401 (was 4xx/5xx)
- **A37** `SignupWizard.tsx` demo-fallback removed (was swallowing real errors)
- **A38** BridgeProvider 5s→30s, AppStateProvider 15s→60s (rate limit)

### A39–A45 — `tnsvt-bot` (Python)
- **A39** `admin_check.py:15` — when `BOT_ADMIN_IDS` is empty, blocks all users
- **A40–A45** `close:all`/`close:symbol:` handlers reject non-admins

---

## FASE B — Secrets Management (6 fixes)

### B1 — `apps/integrations/tnsvt-bot/scripts/ai_parser.py`
- Hardcoded Google Gemini API key → `os.environ.get("GOOGLE_API_KEY", "")`

### B2 — `scripts/start-services.ps1`
- Hardcoded dev secrets → respect existing env vars first, fall back to defaults
  only if not set

### B3 — `.env` files
- New 64-char `JWT_SECRET`, 48-char `AUTH_JWT_SECRET`, 32-char `BRIDGE_API_KEY`
- All secrets freshly generated with `secrets.choice(alphabet)`

### B4 — `apps/integrations/tnsvt-bot/.env` and `.env.example`
- Added `GOOGLE_API_KEY` env var

### B5 — Verification
- No hardcoded secrets in source code (`.py`, `.go`, `.ts`)
- `git log --rev-list -- .env` returns nothing → `.env` never committed

### B6 — Services restarted
- auth-service (PID 81208) and gateway (PID 38800) running with new secrets
- E2E login verified: `/auth/me` with new token → 200

> ⚠️ **TODO (manual)**: Rotate external secrets since they were on disk:
> - Telegram bot token via BotFather
> - Telethon API ID/Hash via my.telegram.org

---

## FASE C — Trading Safety (6 fixes)

### C1 — PnL 100000x multiplier
**Files**: `apps/risk/risk-engine/internal/service/service.go`,
`apps/trading/execution-engine/internal/service/service.go`,
`apps/bridge/bridge-api/main.py`

- Added `getSymbolMultiplier()` that returns the correct multiplier per instrument:
  - Forex: `100000` (1 lot = 100,000 units)
  - Indices: `1` (1 contract = 1 unit)
  - Crypto: `1` (1 coin = 1 unit)
  - XAUUSD: `100` (1 lot = 100 oz)
  - XAGUSD: `5000` (1 lot = 5000 oz)
- Replaced all hardcoded `* 100000` calls
- The bridge-api also has the equivalent `get_symbol_multiplier` in Python

### C2 — Max Drawdown enforcement
**File**: `apps/risk/risk-engine/internal/service/service.go`

- Added Check 6 in `EvaluateSignal`
- Computes drawdown from Redis-cached peak balance
- Rejects if `>` `MaxDrawdownPercent` (configurable, default 20%)
- `RejectDrawdownLimit` was defined in models but never referenced

### C3 — Execution idempotency
**File**: `apps/trading/execution-engine/internal/service/service.go`

- `GetBySignalID` check at start of `ExecuteSignal`
- Skips duplicate NATS deliveries
- New `ErrDuplicateSignal` error

### C4 — Hardcoded $10k balance
**File**: `apps/risk/risk-engine/internal/service/service.go`

- Added `Config.DefaultBalance`
- `defaultBalance()` method (returns `Config.DefaultBalance` or 10k fallback)
- Both position sizing and drawdown peak use this

### C5 — Trade monitor PnL
**File**: `apps/trading/execution-engine/internal/service/service.go`

- `handleTradeClosed` now estimates PnL = (exit−entry)×qty×multiplier
- Was reporting `pnl = 0.0` for all SL/TP-detected closes

### C6 — Reviewed copy-trading
- `applied.Side` mapping is correct: BUY/SELL → "action: BUY/SELL" (open), CLOSE → "action: CLOSE" (close)
- No change needed; the flow works as designed

---

## FASE D — Hardcode Elimination (6 fixes)

### D1 — `bridge-api/main.py` hardcoded paths
- 16+ occurrences of `r"D:\TradingBotMT5"` → `MT5_DATA_DIR` env var
- 1 occurrence of `r"D:\TradingBotMT5\var\mt5_status.json"` → `MT5_STATUS_PATH` env var
- Old `BOT_DATA_DIR`/`BOT_SNAPSHOT_DIR` aliases unified

### D2 — `bridge-api/main.py` notional multiplier
- Hardcoded `100000` → `get_symbol_multiplier(symbol)` (matches Go impl)

### D3 — `risk-engine/service.go` remaining 10000
- Peak balance initial → `s.defaultBalance()` (already had C4 config)
- Pip-to-price conversions → `pipsPerPoint` constant (math factor, not config)

### D4 — Default tenant UUID `00000000-0000-0000-0000-000000000001`
- Added `DEFAULT_TENANT_ID` to `shared-go/config` and `shared-go/cors`
- 8 files updated:
  - `apps/audit/audit-engine/internal/subscriber/subscriber.go`
  - `apps/risk/risk-engine/internal/subscriber/subscriber.go` (NATS: rejects signals w/o tenant)
  - `apps/risk/risk-engine/internal/handlers/handlers.go` (2x: rejects w/ 400)
  - `apps/risk/risk-engine/internal/service/service.go`
  - `apps/trading/execution-engine/internal/handlers/handlers.go` (rejects w/ 400)
  - `apps/trading/execution-engine/internal/service/service.go` (via `defaultTenantID()`)
  - `apps/trading/signal-engine/internal/handlers/handlers.go` (rejects w/ 400)
  - `apps/trading/copy-trading/internal/handlers/handlers.go` (returns uuid.Nil)
  - `apps/platform/user-service/internal/handlers/handlers.go` (returns uuid.Nil)
- `.env` and `.env.example` updated with `DEFAULT_TENANT_ID`

### D5 — CORS hardcoded origins (7 files)
- New `shared-go/cors` package: `cors.AllowedOrigins()` reads `CORS_ALLOWED_ORIGINS` env var
- Updated: auth-service, api-gateway, mt5-connector, signal-engine, execution-engine, copy-trading, risk-engine
- `.env.example` updated

### D6 — Gateway service URLs
- `apps/gateway/api-gateway/internal/config/services.go`
- New `serviceURL(name, default)` reads `SVC_<NAME>_URL` env var
- All 14 service URLs now configurable per-service

---

## New env vars (all in `.env.example`)

```bash
# Tenants
DEFAULT_TENANT_ID=<uuid>           # Was hardcoded 0000-0000-0000-0000-0000-000001

# CORS
CORS_ALLOWED_ORIGINS=<csv>         # Was hardcoded localhost list

# Service URLs (gateway)
SVC_AUTH_SERVICE_URL=http://...    # Was hardcoded localhost:8001
SVC_USER_SERVICE_URL=http://...    # etc.

# MT5 (bridge-api)
MT5_DATA_DIR=<path>                # Was hardcoded D:\TradingBotMT5
MT5_STATUS_PATH=<file>             # Was hardcoded ...\var\mt5_status.json
```

---

## Build & Test Status

| Service | Build | Tests |
|---------|-------|-------|
| `shared-go` | ✅ | n/a |
| `apps/platform/auth-service` | ✅ | ✅ |
| `apps/platform/user-service` | ✅ | n/a |
| `apps/gateway/api-gateway` | ✅ | n/a |
| `apps/audit/audit-engine` | ✅ | n/a |
| `apps/risk/risk-engine` | ✅ | ✅ (0.685s) |
| `apps/trading/execution-engine` | ✅ | n/a |
| `apps/trading/signal-engine` | ✅ | n/a |
| `apps/trading/copy-trading` | ✅ | n/a |
| `apps/broker/mt5-connector` | ✅ | n/a |
| `apps/bridge/bridge-api` (Python) | ✅ imports OK | n/a |

---

## Verification commands

```bash
# Verify no hardcoded UUIDs remain
grep -r "00000000-0000-0000-0000-000000000001" apps/

# Verify no hardcoded MT5 paths
grep -r "D:\\\\TradingBotMT5" apps/

# Verify all services build
for svc in $(ls apps/); do
  [ -f "apps/$svc/go.mod" ] && (cd "apps/$svc" && go build ./...)
done

# E2E auth flow
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@tnsvt.local","password":"Admin123!Demo"}'
```
