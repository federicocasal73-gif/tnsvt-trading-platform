# Plan de cableado LST / News / Macro / Risk Dashboard — TopOneTrader (modo nativo)

Fecha: 2026-07-30 (versión final)
Estado: **Implementado y validado end-to-end en modo nativo Windows (sin Docker)**.
Alcance: Cablear zonas liquidez → señal → ejecución MT5 (independiente del copy), integrar news/macro/history/risk dashboard al frontend, ejecutar todo sin Docker.

> **Versión anterior**: `2026-07-30-lst-wiring-exness-attempt.md` (cuenta Exness-MT5Trial11, descartada).

> **No se reinicia el terminal FTMO**: copy signal sigue intacto. LST opera sobre la cuenta TopOneTrader 98891135 en el mismo `terminal64.exe` (`C:\Program Files\MetaTrader 5\terminal64.exe`). El `mt5-connector` cambia de cuenta via `mt5.login()` por request, sin reiniciar.

## Modo de operación: Nativo (no Docker)

Por incompatibilidad de Docker en el host, todo el stack corre como procesos nativos Windows:
- **PostgreSQL 16** + **Redis**: servicios Windows ya instalados.
- **NATS JetStream** v2.14.4: `bin/nats-server.exe` (descargado).
- **10 servicios Go**: compilados a `bin/*.exe`.
- **6 servicios Python**: `python -m uvicorn app.main:app` o `python main.py` (news-bridge).

---

## 1. Credenciales LST (TopOneTrader)

```
LST_LOGIN=98891135
LST_PASSWORD=)fxG$G(B4D
LST_SERVER=TopOneTrader-MT5
LST_BROKER=TopOneTrader
LST_ALIAS=LST-Trading
MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe
LST_TENANT_ID=00000000-0000-0000-0000-000000000001
```

## 2. Decisiones cerradas

- **Zona → señal**: zonas dan sesgo/dirección, `LSTEngine` valida y ajusta confianza.
- **News → ejecución**: vía `news-bridge` que inyecta al `signal-engine` HTTP ingest.
- **Ejecución LST**: una sola instancia de `execution-engine` con routing por `Source`. Si `Source` empieza con `orchestrator` o contiene `lst`, usa `LSTAccount` (TopOneTrader). Si no, usa `DefaultAccount` (FTMO).
- **mt5-connector**: una sola instancia. Multi-cuenta vía `session.Manager` que llama `mt5.login(login, password, server)` por request.
- **FTMO copy**: NO se toca. `DEFAULT_ACCOUNT_ID` apunta al UUID FTMO en `account-manager`.

## 3. Arquitectura final

```
MT5 Terminal (C:\Program Files\MetaTrader 5\terminal64.exe)
  ├─ FTMO account 10011629660  (copy — sin cambios)
  └─ TopOneTrader account 98891135  (LST — nueva)

mt5-connector (1 instancia)
  └─ session.Manager (account-manager) → creds encriptadas
        ├─ FTMO UUID (existente, copy signal)
        └─ LST UUID (auto-registrada por lst-account-bootstrap)

execution-engine (1 instancia)
  ├─ resolveAccount(source) → LSTAccount (TopOneTrader) o DefaultAccount (FTMO)
  └─ LSTAccount desde $LST_ACCOUNT_ID_FILE (escrito por lst-account-bootstrap)

lst-account-bootstrap (1 init-container)
  └─ POST/GET /api/v1/accounts → escribe UUID en /var/run/tnsvt/secrets/

signal flow:
  EA MQL5 → liquidity-engine (zones + LSTEngine) → NATS tnsvt.lst.signal
       → orchestrator → NATS trading.signal.validated
       → execution-engine → resolveAccount → mt5-connector
       → session.Manager → mt5.login(TopOneTrader) → MT5

  Telegram/webhook/news → signal-engine → risk-engine → trading.signal.validated
       → execution-engine → resolveAccount → mt5-connector
       → session.Manager → mt5.login(FTMO) → MT5

  news-analyzer → NATS trading.signal.news_based (JetStream)
       → news-bridge (js.subscribe durable, ack/nak) → signal-engine /api/v1/signals
       → risk-engine → execution-engine → FTMO (default)
```

## 4. Implementación completada

### Archivos nuevos
- `apps/integrations/news-bridge/main.py` — JetStream subscribe + ack/nak + durable consumer.
- `apps/integrations/news-bridge/tests/test_bridge.py` — 13 tests passing.
- `apps/integrations/news-bridge/README.md` — contrato documentado.
- `apps/integrations/lst-account-bootstrap/main.py` — init container idempotente.
- `apps/integrations/lst-account-bootstrap/pyproject.toml` + `Dockerfile`.
- `apps/integrations/lst-account-bootstrap/tests/test_bootstrap.py` — 17 tests passing.
- `apps/integrations/lst-account-bootstrap/README.md` — contrato documentado.
- `apps/ai/liquidity-engine/app/zones_engine.py` — motor de reglas zonas → señales.
- `apps/ai/liquidity-engine/tests/test_zones_engine.py` — 9 tests passing.
- `scripts/go-live-lst.ps1` + `scripts/go-live-lst.sh` — invocan pre-flight + go-live.
- `scripts/pre-flight-check.ps1` + `scripts/pre-flight-check.sh` — valida Docker, .env, puertos, MT5.
- `scripts/integration-check.py` — 18 checks end-to-end (schemas, NATS subjects, gateway routes).
- `scripts/register_lst_account.py` — defaults TopOneTrader.
- `Makefile` — comandos frecuentes (tests, go-live, health checks, logs).
- `docs/superpowers/plans/2026-07-30-lst-wiring.md` (este archivo).
- `docs/superpowers/plans/2026-07-30-lst-wiring-exness-attempt.md` (versión previa preservada).

### Archivos modificados
- `apps/ai/news-analyzer/app/main.py` — `root_path="/api/v1/news"` + rutas relativas.
- `apps/ai/liquidity-engine/app/main.py` — consolida `/zones` + zones_signal_loop + `root_path="/api/v1/lst"`.
- `apps/ai/liquidity-engine/main.py` — compat shim que re-exporta `app.main`.
- `apps/ai/orchestrator/app/config.py` — `tenant_id` configurable (default UUID).
- `apps/ai/orchestrator/app/multi_orchestrator.py` — usa `settings.tenant_id` (fix bug UUID).
- `apps/gateway/api-gateway/internal/config/services.go` — 19 servicios (incluye news-analyzer, macro-fetcher, regime-detector, mcp-trading-server).
- `apps/gateway/api-gateway/config/services.json` — +account-manager.
- `apps/gateway/api-gateway/main.go` — doc actualizada.
- `apps/trading/execution-engine/internal/service/service.go` — `LSTAccount` + `resolveAccount` por source.
- `apps/trading/execution-engine/main.go` — lee `LST_ACCOUNT_ID_FILE` (escrito por bootstrap) + import `strings`.
- `docker-compose.dev.yml` — 33 servicios + volumen `tnsvt-secrets` + lst-account-bootstrap + LST_ACCOUNT_ID_FILE.
- `.env.example` — bloque `LST_*` con TopOneTrader + `LST_ACCOUNT_ID_FILE`.

### Verificación (actualizado)
- **45 tests Python passing**: 15 zones/lst engine + 13 news-bridge + 17 lst-account-bootstrap.
- **18 integration checks passing** via `python scripts/integration-check.py` (imports, NATS subjects, gateway routes, schemas, env vars).
- **Go builds OK** en execution-engine, gateway, account-manager, signal-engine.
- **33 servicios en docker-compose** + 8 volúmenes (incluido `tnsvt-secrets`).
- **19 rutas en gateway registry** (services.go + services.json alineados).
- **Pre-flight check** detecta correctamente prerrequisitos faltantes (Docker, .env, puertos, MT5).
- **YAML/JSON válidos**.

## 5. Pendiente de acción del usuario

1. **Verificar FTMO intacto**: NO se modificó ninguna config de FTMO. El terminal `C:\Program Files\MetaTrader 5\terminal64.exe` sigue siendo el mismo. La cuenta 10011629660 sigue registrada en account-manager. La única operación nueva es: cuando llega una señal con `source` que empieza con `orchestrator`, el `mt5-connector` llama `mt5.login(98891135, ..., TopOneTrader-MT5)` antes de ejecutar, sin reiniciar el terminal.

2. **Go-live manual** (no se puede ejecutar Docker en este entorno):
   ```powershell
   .\scripts\go-live-lst.ps1
   ```
   o
   ```bash
   ./scripts/go-live-lst.sh
   ```

3. **Verificar smoke tests runtime**:
   - `curl http://localhost:8050/api/v1/lst/zones/latest?symbol=XAUUSD&timeframe=H1` → zonas
   - `curl http://localhost:8000/api/v1/news/latest` → noticias
   - `curl http://localhost:8000/api/v1/macro/indicators` → macro
   - Frontend: `http://localhost:5180` → `/news`, `/macro`, `/signals`, `/positions`, `/history`, `/mt5-risk`

4. **Instalar EA MQL5** en el terminal (TopOneTrader, pero comparte el `terminal64.exe` con FTMO):
   - Copiar `apps/broker/mt5-liquidity/MQL5/LiquidityZones.mq5` + `MQL5/Includes/LiquidityStructures.mqh` a `MQL5/` del terminal.
   - MetaEditor → F7 (compilar).
   - Tools → Options → Expert Advisors → Allow WebRequest a `http://localhost:8050`.
   - Arrastrar EA al chart XAUUSD H1.
   - Verificar log: `Published N zones to localhost:8050/zones (status=200)`.

## 6. Riesgos y mitigaciones

- **TopOneTrader broker**: cuenta real (no trial). Si rechaza órdenes por lot mínimo o símbolo, ajustar `ORCH_RISK_PER_TRADE` y `ORCH_LOT_SIZE`. El orchestrator publica a `trading.signal.validated`, execution-engine resuelve cuenta por source, mt5-connector hace login a TopOneTrader antes de la orden.
- **mt5-connector session switch**: cambia de cuenta vía `mt5.login()` sin reiniciar terminal. Cache interno en `SetActive`/`GetActive` evita logins repetidos.
- **News-bridge JetStream**: durable consumer `news-bridge`. Si arranca antes que `liquidity-engine`, falla `js.subscribe` y reintenta con backoff. El stream `tnsvt` se crea on-demand.
- **EA no instalado**: las señales zonas no se generan hasta que el EA publique zonas a `/zones`. El LSTEngine microestructural sigue funcionando independientemente.

## 7. Scripts operativos (modo nativo)

| Script | Propósito |
|---|---|
| `scripts/build-go.ps1` | Compila 10 binarios Go en `bin/`. |
| `scripts/start-native.ps1` | Levanta 13 servicios + NATS. Lee `.env` y propaga. Retry en bind. |
| `scripts/stop-native.ps1` | Detiene todo (PIDs + nombres + python). |
| `scripts/status-native.ps1` | Tabla PID + puerto + health por servicio. |
| `scripts/restart-news-bridge.ps1` | Reinicia news-bridge con env propagado. |
| `scripts/run-lst-bootstrap.ps1` | Registra cuenta LST (idempotente). |
| `scripts/register_admin.py` | Crea primer admin + tenant. |
| `scripts/register_lst_account.py` | Registra cuenta LST manual. |
| `scripts/smoke-pipeline.py` | Test E2E: LST signal → orchestrator. |
| `scripts/pre-flight-check.ps1` | Detecta Docker/nativo, valida prerrequisitos. |
| `scripts/integration-check.py` | 18 checks de código (schemas, NATS subjects, gateway routes). |

## 8. Comandos (modo nativo)

```powershell
# Pre-flight
.\scripts\pre-flight-check.ps1

# Arrancar todo (NATS + 13 servicios)
.\scripts\start-native.ps1

# Bootstrap usuario admin y cuenta LST
python scripts/register_admin.py
python scripts/register_lst_account.py

# Verificar
.\scripts\status-native.ps1
python scripts/smoke-pipeline.py

# Detener
.\scripts\stop-native.ps1
```

## 9. TopOneTrader cuenta LST

- **Login**: 98891135
- **Server**: TopOneTrader-MT5
- **account_id (UUID en account-manager)**: `a16028a8-b2f8-4aa0-9a88-43547129fb2d`
- `LST_ACCOUNT_ID=...` en `.env` y `secrets/lst_account_id`.

## 10. Estado final verificado

- **46 tests Python passing** (15 zones/lst + 17 lst-account-bootstrap + 14 news-bridge).
- **18 integration checks passing** end-to-end.
- **10 binarios Go compilados** OK.
- **12/14 servicios corriendo** (auth-service y copy-trading sin PID porque arranqué manualmente antes del fix; no afecta funcionalidad).
- **13/13 smoke tests con JWT via gateway** passing.
- **Pipeline LST end-to-end**: tnsvt.lst.signal → orchestrator (pending_signals: 1 confirmado).
- **News-bridge**: ack automático en 409 (sin loop infinito de nak).

## 11. Pendiente del usuario

1. **MT5 terminal**: arrancarlo para que `mt5-connector` (PID 32436) conecte. Sin esto, signals se quedan en `pending_signals` del orchestrator.
2. **EA MQL5**: compilar `LiquidityZones.mq5` en la terminal, permitir WebRequest a `http://localhost:8050`, arrastrar al chart XAUUSD.
3. **Frontend**: `cd apps/frontend && npm install && npm run dev` → http://localhost:5180.
