# Plan Maestro: TradingView-style Preview + Integración zengtrading

## Visión general (3 niveles drill-down)

```
NIVEL 1 — BACKTESTING (agregado, KPIs, equity, segments)
  Mapeo: nueva sección "Backtest Analytics" en el sidebar
  Datos: tabla backtest_runs en bridge_outbox.db

NIVEL 2 — TRADES TABLE (ledger denso, sortable, filtros)
  Mapeo: extensión de Mt5Positions / nueva "Trade History"
  Filtros: dirección, resultado, sesión, trend
  Click row: expande detalles (timeline + SMC context)

NIVEL 3 — TRADE CHART (preview hover con velas M5)
  Mapeo: hover sobre fila de Mt5Positions / Trade History
  Mini-chart con velas reales + markers (entry/SL/TP/parc)
  Lazy load al primer hover
```

## Decisiones del usuario (confirmadas)

| # | Decisión |
|---|----------|
| 1 | Hover sobre fila del Trade History List (no modal, no inline) |
| 2 | Velas M5 (5 minutos) |
| 3 | Mín 5 velas previas + ventana completa del trade (entry→close) |
| 4 | Usar la sección Mt5Positions (más sentido que History) |
| 5 | Probar endpoint de velas en bridge; si no funciona, fallback a scaffold |
| 6 | Carga lazy (solo cuando hover) — mejora performance |

## FASE 1 — Trade Chart Preview (Hover)

### Backend

#### 1.1 Endpoint bridge: velas MT5
```
GET /api/v1/bridge/mt5/candles?symbol=XAUUSD&tf=M5&from=ISO&to=ISO
```
- Wrapper que llama `MT5Provider.get_candles()` (ya existe)
- Validación: `symbol` ∈ MT5_SYMBOLS, `tf` ∈ TF_MAP
- Cache in-memory con TTL 60s
- Response:
```json
{
  "symbol": "XAUUSD",
  "tf": "M5",
  "candles": [
    {"t": "2026-07-17T01:45:00", "o": 3982.5, "h": 3983.1, "l": 3982.2, "c": 3982.95, "v": 0}
  ]
}
```

#### 1.2 Captura on-trade-open en signal_copier
En `executor.py`, cuando abre un trade:
- Llama `mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 30)` o `copy_rates_range`
- Guarda en `D:\TradingBotMT5\trade_candles\{ticket}_entry.json`
- Contiene: ~5 velas antes del entry + vela del entry + 1-2 después

#### 1.3 Captura on-trade-close en signal_copier
En `mt5_trade_monitor()` cuando detecta cierre:
- Velas desde entry hasta close
- Guarda en `D:\TradingBotMT5\trade_candles\{ticket}_close.json`

#### 1.4 Endpoint combinado
```
GET /api/v1/bridge/trades/{ticket}/candles?tf=M5
```
- Lee los 2 JSON files
- Devuelve array continuo de velas
- Fallback: si no hay snapshots, intenta `get_candles()` en vivo

### Frontend

#### 1.5 Componente `TradePreviewChart.tsx`
- Props: `trade: ClosedTrade`, `onClose: () => void`
- Posición: popover flotante al lado de la fila hovered
- Librería: `lightweight-charts` (open-source, sin auth)
- Markers:
  - `arrowUp`/`arrowDown` en vela del entry
  - `square` en vela del close
  - `circleUp` para TP parciales (Fase 2)
- Líneas horizontales: SL (rojo), Entry (blanco), TP (verde) — todas dashed
- Background band: verde entry→TP, rojo entry→SL

#### 1.6 Componente `TradeHistoryRow.tsx`
- Reemplaza el render actual de filas en `Mt5PositionsPage`
- `onMouseEnter` con debounce 150ms dispara fetch del preview
- Popover posicionado `absolute` al lado derecho de la fila
- `onMouseLeave` con delay 200ms para permitir mover mouse al preview sin cerrar

#### 1.7 Lazy load + cache
- Al montar: NO carga velas
- Primer hover: fetch + render + cache en memoria por ticket
- Si MT5 no devuelve datos → fallback a scaffold (líneas estáticas)

## FASE 2 — Trade History denso

### Backend

#### 2.1 Endpoint existente con filtros server-side
```
GET /api/v1/bridge/analytics/trades?direction=BUY&result=WIN&symbol=XAUUSD&since_days=30&limit=N
```

#### 2.2 Endpoint detail
```
GET /api/v1/bridge/trades/{ticket}/detail
```
Response incluye:
- ticket, symbol, action, entry, sl, tp
- open_time, close_time, duration_candles
- rr, score, session, trend_m15
- timing: to_entry, to_be, to_partial, to_close
- partial_closes: [{time, level, pips, percent, pnl}]
- candles_url

### Frontend

#### 2.3 Página `Mt5PositionsPage.tsx` refactor
- Toggle: `Lista compacta | Tabla densa`
- Tabla densa con 17 columnas (como zengtrading trades_v1)
- Fila click → expande inline con timeline + context cards
- Fila hover → preview chart (Fase 1)

## FASE 3 — Backtest Analytics (opcional, baja prioridad)

### Backend
- Nueva tabla `backtest_runs` en bridge_outbox.db
- POST `/api/v1/bridge/backtest/runs` para ingestar
- GET `/api/v1/bridge/backtest/runs` para listar

### Frontend
- Nueva página `BacktestAnalyticsPage.tsx`
- 8 KPI cards + equity curve + doughnut + bars temporales + segmentaciones

## Mapeo al sidebar del Terminal

```
Dashboard                       (existe)
Positions                  ●    (existente, será extendido)
Signals                        (existe)
Live Ticks                      (existe)
History                        (existente)
MT5 Dashboard                   (existe)
MT5 Positions                  (existente, será extendido)
MT5 Channels                    (existe)
MT5 Settings                    (existe)
MT5 Control                     (existe)
Admin                           (existe)
Settings                        (existe)
---
🆕 Backtest Analytics           (Fase 3)
🆕 Copy Analytics               (alias a Mt5Positions extendido)
```

## Arquitectura de comunicación

```
MT5 broker
    ↓ (mt5.copy_rates_from)
signal_copier (Python) ← MT5Provider ya existe
    ↓ (POST snapshot JSON a disco)
D:\TradingBotMT5\trade_candles\{ticket}_entry.json
D:\TradingBotMT5\trade_candles\{ticket}_close.json
    ↓ (GET via bridge)
bridge-api (FastAPI)
    ↓ (GET /api/v1/bridge/trades/{ticket}/candles)
Frontend React
    ↓ (lightweight-charts)
Popover flotante
```

## Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| MT5 no conectado → velas no disponibles | Fallback a scaffold estático (entry/SL/TP/close lines) |
| Snapshot JSON files faltantes (trades viejos) | Fallback a `get_candles()` en vivo; si falla, scaffold |
| Performance: 100+ trades con hover | Cache por ticket en memoria; debounce 150ms |
| Bridge corriendo en otra máquina que MT5 | Velas deben venir del signal_copier (que tiene MT5), no del bridge |
| Timeframe mismatch | Permitir selector de TF en preview: M1/M5/M15/H1 |
| Trade de segundos → no hay velas suficientes | Mostrar lo que hay, no fallar |

## Estimación de esfuerzo

| Fase | Horas | Bloqueante |
|------|-------|-----------|
| 1.1 Endpoint candles | 1-2h | requiere acceso MT5 |
| 1.2 Captura on-open | 1h | |
| 1.3 Captura on-close | 1h | |
| 1.4 Endpoint combinado | 1h | |
| 1.5 Componente preview chart | 3-4h | |
| 1.6 Hover row + popover | 1-2h | |
| 1.7 Lazy + cache | 0.5h | |
| 2.1 Filtros server-side | 0.5h | |
| 2.2 Endpoint detail | 2h | requiere guardar metadata en signal_copier |
| 2.3 Refactor Mt5Positions | 3-4h | |
| 3.x Backtest Analytics | 8-12h | Fase completa, opcional |
| **Total Fases 1+2** | **14-18h** | |
| **Total con Fase 3** | **22-30h** | |

## Orden de ejecución

1. **Fase 1.1 + 1.4** (endpoints candles en bridge) → 2-3h, base técnica
2. **Fase 1.5** (componente preview chart aislado) → 3-4h, validamos visualmente
3. **Fase 1.6 + 1.7** (hover + lazy) → 1.5-2.5h, integración
4. **Fase 1.2 + 1.3** (captura on-open/on-close) → 2h, completar la pieza
5. **Fase 2.3** (refactor Mt5Positions con tabla densa) → 3-4h
6. **Fase 2.1 + 2.2** (filtros + detail endpoint) → 2.5h
7. **Fase 3** (backtest analytics) → solo si hay demanda

## Decisiones que necesitan confirmación

### A. Lightweight Charts vs Canvas custom
- zengtrading usa lightweight-charts (open-source TradingView)
- Bundle: ~250 KB gzipped
- Alternativa: recharts (ya en el proyecto, pero no soporta candlesticks)
- **Recomendación: lightweight-charts**

### B. Captura on-open vs también on-signal
- Tu mencionaste "al inicio y al cierre" — interpreté on-trade-open y on-trade-close
- ¿Querés también capturar velas desde la señal (cuando llega al Telegram)?

### C. Multi-símbolo desde día 1
- MT5_SYMBOLS: `["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "BTCUSD"]`
- ¿Capturamos velas para todos, o solo XAUUSD?

### D. Backtest analytics es prioritario?
- Es la pieza más grande (8-12h)
- Si no hay backtests reales para ingestar, sería stub

### E. Preview en posiciones live?
- En posiciones abiertas, velas se actualizan en tiempo real
- Chart vivo con last candle refresh cada 5s
- Útil pero +2h

---

*Plan generado el 2026-07-24*
*Estado: pendiente de confirmación*