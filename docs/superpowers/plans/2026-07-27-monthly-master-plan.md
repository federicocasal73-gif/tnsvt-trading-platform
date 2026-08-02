# Plan Maestro Mensual: TNSVT V2 — Bot Multi-Activo Unificado

**Fecha:** 2026-07-27
**Estado:** Guardado, pendiente de ejecución
**Modo actual:** No arrancar — solo archivar y consolidar

---

## Contexto y Estado Verificado

### ✅ Funcionando y verificado
- Pipeline NATS → execution-engine → MT5 (ticket 152391032982 BUY 0.01 XAUUSD @ 4077.52)
- liquidity-engine (LST signals) con 9/9 tests pasando
- MT5 connector con endpoints `/rates`, `/orders`, `/health`, `/health/ready`
- NATS JetStream en `nats://localhost:4222`, stream `tnsvt`
- MT5 demo conectado: login `10011629660`, server `metaquotes-demo`

### 🐛 Bugs corregidos durante verificación
1. `mt5_bridge.py` — `TradePosition.commission` AttributeError → removido
2. `mt5_bridge.py` — comment limit del broker (24 chars max) → `sanitize_comment()` con alfanuméricos
3. `execution-engine service.go` — health check upfront abortaba antes del retry loop → removido
4. `mt5-connector handlers.go` — IsConnected check causaba 503 inmediato en retries → removido
5. `mt5-connector client.go` — stderr de Python no capturado → `cmd.Stderr = &stderrBuf`

### 📁 Archivos modificados en verificación
- `apps/trading/execution-engine/internal/service/service.go`
- `apps/broker/mt5-connector/mt5_bridge.py`
- `apps/broker/mt5-connector/internal/handlers/handlers.go`
- `apps/broker/mt5-connector/internal/mt5/client.go`
- `docs/superpowers/plans/2026-07-27-liquidity-engine.md`

---

## Visión Final del Sistema

```
MT5 Terminal
    ↓ /rates
multi-símbolo orchestrator
    ├─ LST Engine (por símbolo)
    ├─ Correlation Engine (Pearson + cointegración)
    ├─ Portfolio Manager (drawdown + position sizing)
    └─ Risk Manager (ATR-based SL/TP + trailing)
    ↓ NATS trading.signal.validated.{symbol}
execution-engine
    ↓ HTTP /api/v1/brokers/orders
mt5-connector
    ↓ Python bridge subprocess
MT5 Terminal
```

**Símbolos objetivo:** XAUUSD, EURUSD, GBPUSD, USDCHF
**Timeframes:** M15, H1, H4
**Estrategia:** Bot de medio-largo plazo, alto winrate, alto retorno, bajo drawdown

---

## Stack Técnico Confirmado

| Componente | Librería/Stack |
|-----------|----------------|
| Backtesting | vectorbt 0.27.x |
| Correlación | scipy.stats.pearsonr |
| Cointegración | statsmodels.tsa.stattools.coint |
| Riesgo/Ratio | numpy, pandas |
| NATS | nats.py (Python) + nats.go |
| MCP | mcp (Python SDK) — opcional, baja prioridad |
| MT5 | MetaTrader5 Python lib vía bridge subprocess |
| Risk metrics | RiskOptima o implementación propia con numpy |

---

## Roadmap Mensual (4 semanas)

### Semana 1: Backtesting & Validación
**Objetivo:** Validar lógica LST + correlación contra datos históricos antes de operar.

| Día | Tarea |
|-----|-------|
| 1 | Setup `apps/ai/backtest-engine/` con vectorbt |
| 2 | Descargar 3 años M15/H1/H4 desde MT5 (XAUUSD, EURUSD, GBPUSD, USDCHF) |
| 3 | Replicar LST en vectorbt, calcular Sharpe/Sortino/DD/winrate por símbolo |
| 4 | Test correlación: confirmar pares esperados (EURUSD↔GBPUSD ≈ 0.7, EURUSD↔USDCHF ≈ -0.9) |
| 5 | Comparar métricas con/sin filtro de correlación |
| 6 | (libre / ajustes) |
| 7 | Reporte final: ¿la estrategia es viable? ¿ajustar parámetros? |

**Output:** Reporte con equity curve, métricas, decisión GO/NO-GO.

**Decisiones pendientes:**
- Fuente de datos: cuenta real vs datos externos (Dukascopy, histdata.com)
- Si datos externos: descargar XAUUSD M15 3 años + EURUSD M15 3 años + GBPUSD + USDCHF

---

### Semana 2: Multi-Symbol Orchestrator + Correlation Engine
**Objetivo:** Construir el orquestador que maneja múltiples símbolos coordinadamente.

| Día | Tarea |
|-----|-------|
| 8 | Crear `apps/ai/orchestrator/orchestrator_multi.py` |
| 9 | Crear `apps/ai/orchestrator/correlation_engine.py` con tests |
| 10 | Integrar con liquidity-engine actual: en vez de 1 símbolo, lista configurable |
| 11 | NATS dual subject: `trading.signal.validated.{symbol}` para routing por símbolo |
| 12 | Docker: imagen multi-símbolo con `SYMBOLS=XAUUSD,EURUSD,GBPUSD,USDCHF` |

**Archivos a crear:**
```
apps/ai/orchestrator/
├── orchestrator_multi.py       # MultiSymbolOrchestrator class
├── correlation_engine.py       # CorrelationEngine class (Pearson + coint)
├── portfolio_manager.py        # (referencia, implementación semana 3)
└── tests/
    └── test_correlation_engine.py
```

**Output:** Orquestador corriendo, publicando señales LST filtradas por correlación.

---

### Semana 3: Portfolio Manager + Risk Dinámico
**Objetivo:** Gestión de cartera multi-activo con riesgo ajustado por volatilidad.

| Día | Tarea |
|-----|-------|
| 15 | `portfolio_manager.py`: position sizing basado en ATR + drawdown + correlación |
| 16 | `risk_manager.py`: SL/TP dinámicos por ATR, partial close en TP1 |
| 17 | Pyramiding: añadir a posición en retrocesos si tendencia fuerte |
| 18 | Trailing stop adaptativo basado en ATR |
| 19 | Tests unitarios + simulación de drawdown scenarios |

**Output:** Sistema de riesgo que limita exposición total a 5% DD y 1% por trade.

**Lógica crítica de position sizing:**
- 1 par: lot risk = 1% del equity
- 2 pares correlacionados (+0.7): lot risk = 0.5% cada uno
- 3 pares correlacionados: lot risk = 0.33% cada uno
- Drawdown > 5%: reducir 30% del lot
- Drawdown > 10%: reducir 50% del lot

---

### Semana 4: MCP Bridge (opcional) + Macro Filter + Producción
**Objetivo:** Control por IA y filtrado macro antes de producción.

| Día | Tarea |
|-----|-------|
| 22 | `apps/integrations/mcp-trading-server/` con tools MCP |
| 23 | `apps/data/macro-fetcher/`: scraper M2Quant (TGA, RRP) + calendar CPI/NFP |
| 24 | Integrar macro filter: pausar BUY durante risk-off |
| 25 | Dashboard básico (FastAPI + HTML) con equity curve y posiciones |
| 26-30 | Run en demo, monitorear 1 semana, ajustar parámetros |

**Output:** Bot operando en demo 24/7 con control IA (si MCP) + observabilidad.

**MCP Tools a implementar (si se prioriza):**
- `get_signal(symbol)` — última señal LST
- `get_bot_status()` — running/paused, posiciones abiertas
- `pause_bot()` / `resume_bot()`
- `send_manual_signal(symbol, action, confidence, lot_size)`
- `get_positions(symbol)`
- `run_backtest(strategy, days)`

---

## Decisiones del Usuario (confirmadas)

1. **Datos:** Cuenta real segura o datos externos (Dukascopy/histdata.com)
2. **No arrancar nada** — solo guardar plan consolidado
3. **MCP server:** Opcional, baja prioridad — dejar para mes 2 si se quiere
4. **Multi-símbolo desde el inicio** confirmado
5. **Phase 3 (SMC engine):** DESCARTADA — no se implementa

---

## Riesgos y Consideraciones

### 1. Datos históricos
- MT5 demo: limitados (~2-3 meses M15)
- Cuenta real: 3+ años pero requiere fondeo
- Externos: Dukascopy (gratis, tick data) o histdata.com (gratis, M1)

### 2. Correlaciones rompibles
- EURUSD/GBPUSD ≈ 0.7 históricamente
- Brexit 2016 demostró que se rompe
- Necesita override manual cuando el usuario lo decida

### 3. Position sizing con correlación
- 3 pares correlacionados = posición efectiva de 3x
- Portfolio manager debe ajustar (no 1% por trade sino 0.33% si los 3 están alineados)

### 4. Riesgo operacional
- Sistema con muchas partes (LST + correlación + portfolio + macro + MCP)
- Necesita logs estructurados, metrics Prometheus, alertas NATS→Slack/Discord, health checks profundos

### 5. Complejidad del orquestador
- Multi-symbol async es complejo (manejo de errores, reconexión NATS, fallos parciales)
- Empezar secuencial (1 símbolo a la vez), paralelo en Fase 2 post-mes

---

## Estructura Final del Monorepo (Proyectada)

```
apps/ai/
├── liquidity-engine/        # YA EXISTE - LST core (1 símbolo)
├── backtest-engine/         # NUEVO - vectorbt + reportes
├── orchestrator/            # NUEVO - multi-symbol
│   ├── orchestrator_multi.py
│   ├── correlation_engine.py
│   ├── portfolio_manager.py
│   ├── risk_manager.py
│   └── tests/
├── macro-fetcher/           # NUEVO - M2Quant + calendar (semana 4)
└── integrations/
    └── mcp-trading-server/  # NUEVO - MCP bridge (opcional, semana 4)
```

```
shared/
└── nats_schemas/
    ├── signal_validated.json
    └── bot_command.json  # NUEVO - pause/resume
```

---

## Plan NO Incluido (descartado por usuario)

### ~~Phase 3: SMC Engine~~ (DESCARTADO)
- ~~BOS (Break of Structure)~~
- ~~FVG (Fair Value Gap)~~
- ~~Liquidity Sweep detection~~
- ~~Combinación LST + SMC para boost de confianza~~

Razón: No la necesitamos — el motor LST + correlación + portfolio ya cubre el caso de uso.

---

## Métricas de Éxito del Mes

| Métrica | Target |
|---------|--------|
| Sharpe Ratio | > 1.5 |
| Max Drawdown | < 8% |
| Win Rate | > 55% |
| Profit Factor | > 1.5 |
| Correlations tracking | Activo en dashboard |
| Latencia signal→order | < 2s |
| Uptime demo | > 95% |

---

## Próximo Paso (cuando el usuario lo indique)

Decirle al usuario:
1. ¿Cuenta real o datos externos (Dukascopy/histdata.com)? Define Semana 1
2. ¿Arrancamos por Semana 1 (backtest) o saltamos directo a Semana 2 (orchestrator)?
3. ¿MCP server es prioridad o queda para mes 2?

Con esas 3 respuestas se arranca.

---

## Notas Adicionales

### Variables de entorno requeridas (ya configuradas)
```bash
# execution-engine
MT5_CONNECTOR_URL=http://localhost:8007
DEFAULT_ACCOUNT_ID=default
DEFAULT_BROKER=mt5
NATS_HOST=localhost
NATS_PORT=4222
EXECUTION_TIMEOUT_SECONDS=30
EXECUTION_RETRY_MAX=3
EXECUTION_RETRY_BACKOFF=2
LOG_LEVEL=info
```

### Comandos útiles
```bash
# Levantar todo
docker-compose -f docker-compose.dev.yml up -d

# Reiniciar mt5-connector tras cambios
cd apps/broker/mt5-connector && go build -o mt5-connector.exe . && Start-Process mt5-connector.exe

# Publicar señal de prueba NATS
cd $env:TEMP\opencode && python verify_e2e.py

# Verificar posiciones MT5
python "C:\Users\HP 240 inch G9\AppData\Local\Temp\check_mt5.py"

# Verificar ejecuciones
Invoke-RestMethod -Uri "http://localhost:8004/api/v1/executions?limit=5"
```

### Tickets de órdenes exitosas (verificación)
- 152387305344 XAUUSD vol=0.16 price=4106.81
- 152389066575 XAUUSD vol=0.01 price=4093.35
- 152389092852 XAUUSD vol=0.01 price=4095.11 (test directo)
- 152390839245 XAUUSD vol=0.01 price=4088.57 (test manual)
- 152390875196 XAUUSD vol=0.01 price=4085.36 (test directo)
- 152390876743 XAUUSD vol=0.01 price=4084.85 (test directo)
- 152391032982 XAUUSD vol=0.01 price=4077.52 ← **PIPELINE COMPLETO NATS→MT5** ✓
- 152391383675 XAUUSD vol=0.20 price=4074.51 ← **VIA ORCHESTRATOR** (lot 0.20, portfolio manager activo) ✓

---

# Anexo: Plan de Integración Frontend Vite (:5180)

**Fecha:** 2026-07-27 (post exploración 3-agent)
**Estado:** En ejecución — Día 1 (gateway + orchestrator endpoint)

## Hallazgos de exploración

### Frontend Vite ya existe y tiene todo
- **Ubicación:** `apps/frontend/` (React 18 + TypeScript + Vite 5, NO Vue/Svelte)
- **Puerto:** 5180 (`strictPort: true`)
- **Páginas existentes:** Dashboard, Positions, Signals, History — **TODAS YA EXISTEN** y tienen implementación
- **API client:** `src/lib/api.ts` con auth, circuit breaker, polling 5-15s
- **State management:** `AppStateProvider` + `BridgeProvider` con polling a `/api/v1/...`
- **NO está dockerizado** — corre nativo via `npm run dev` en Windows host, orquestado por `start_all.ps1`
- **`vite.config.ts` ya tiene dev-proxy:**
  - `/api/v1/bridge` → :8522
  - `/api/v1/auth` → :8001
  - `/api/v1/prices` → :8522
  - `/api` (catch-all) → :8000 (gateway)

### Gateway tiene la mayoría de rutas (excepto orchestrator)
- **`/api/v1/executions/*`** → execution-engine:8004 ✓
- **`/api/v1/brokers/*`** → mt5-connector:8007 ✓
- **`/api/v1/signals/*`** → signal-engine:8003 ✓
- **`/api/v1/lst/*`** → liquidity-engine:8050 ✓
- **`/api/v1/risk/*`** → risk-engine:8006 ✓
- **`/api/v1/bridge/*`** → bridge-api:8522 ✓ (tiene equity curve, Sharpe, drawdown, calendar)
- **Falta:** `/api/v1/orchestrator/*` → orchestrator:8060

### CORS del gateway hardcoded
Whitelist: `localhost:3000`, `localhost:3001`, `localhost:8501`, `app.tnsvt.io`, etc.
**No incluye :5180** — pero el dev-proxy del Vite resuelve antes de salir al navegador, así que probablemente no es problema.

### Equity curve real solo la da bridge-api
- `/api/v1/bridge/analytics/metrics` → Sharpe, Sortino, max DD, win rate, profit factor
- `/api/v1/bridge/analytics/equity-curve` → serie [{date, equity, drawdown}]
- `/api/v1/bridge/analytics/calendar` → heatmap diaria
- `/api/v1/bridge/mt5/accounts` → balance/equity multi-cuenta
- mt5-connector da balance/equity pero no serie histórica
- execution-engine tiene executions pero no agregaciones P&L

## Cambios confirmados a hacer

### Backend (gateway + orchestrator)
1. `apps/gateway/api-gateway/config/services.json` — agregar entrada orchestrator
2. `apps/gateway/api-gateway/internal/config/services.go` — agregar default config orchestrator
3. `apps/gateway/api-gateway/main.go` — actualizar comentario de rutas (líneas 13-26)
4. `apps/ai/orchestrator/app/main.py` — agregar endpoint `GET /signals` que retorna últimas N señales publicadas
5. `apps/ai/orchestrator/app/multi_orchestrator.py` — buffer de señales en `_published_signals: deque(maxlen=200)`

### Frontend (apps/frontend/src/pages/)
6. `Positions.tsx` — usar `GET /api/v1/brokers/accounts/default/positions` (mt5-connector)
7. `Signals.tsx` — usar `GET /api/v1/signals` (signal-engine) + SSE `/api/v1/signals/stream` para live
8. `History.tsx` — usar `GET /api/v1/executions?limit=50&offset=N&symbol=X&status=Y`
9. `Dashboard.tsx` — combinar KPIs de bridge-api + mt5-connector + execution-engine

### Frontend (apps/frontend/src/lib/)
10. `api.ts` — agregar wrappers si hace falta para los endpoints nuevos

## Roadmap 7 días

| Día | Tarea |
|-----|-------|
| 1 | Gateway: agregar orchestrator + nuevo endpoint `/signals` en orchestrator |
| 2 | Frontend Positions.tsx — datos reales de mt5-connector, refresh 5s |
| 3 | Frontend Signals.tsx — historial de signal-engine + live SSE |
| 4 | Frontend History.tsx — ejecuciones paginadas con filtros |
| 5 | Frontend Dashboard.tsx — KPIs combinados + equity curve (recharts) |
| 6 | Polish: loading states, error boundaries, formato numérico |
| 7 | E2E test + build + docs |

## Riesgos identificados

1. **CORS:** si el frontend hace bypass del proxy Vite y pega directo al gateway, va a fallar por whitelist. Verificar primero si el proxy cubre todo.
2. **Auth:** `OptionalAuth` está activo en gateway. Frontend probablemente ya manda bearer token via `api.ts`. Verificar.
3. **Multi-tenant:** execution-engine y signal-engine filtran por `X-Tenant-ID`. Sin header, usan default. Para el dashboard del admin/dev, no es problema.
4. **CORS preflight (OPTIONS):** el gateway ya responde 204 para OPTIONS en su middleware. Verificar que mt5-connector y execution-engine también lo hagan (sino el frontend no podrá hacer POST/PUT).
5. **Performance del dashboard:** si hace 5 llamadas en paralelo cada 5s, el gateway maneja pero conviene agregar endpoint agregado `/api/v1/dashboard/stats` que el gateway orquesta.
6. **Datos históricos del orchestrator:** solo in-memory, no persiste. Si el orchestrator reinicia, se pierden. Para Signal page usar signal-engine que sí persiste.

## Próximo paso inmediato

Día 1: gateway + nuevo endpoint orchestrator `/signals`.