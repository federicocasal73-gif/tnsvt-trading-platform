# Multi-Symbol Orchestrator

Orquestador multi-activo que consume señales crudas del `liquidity-engine` (NATS `tnsvt.lst.signal`), aplica filtro de correlación + cointegración, calcula SL/TP dinámicos por ATR, ajusta lot size por drawdown/correlación y publica `SignalInput` final en `trading.signal.validated` para el `execution-engine`.

## Arquitectura

```
tnsvt.lst.signal (del liquidity-engine)
        ↓
[NATS subscribe]
        ↓
MultiSymbolOrchestrator
  ├─ CorrelationEngine (Pearson + Engle-Granger cointegration)
  ├─ PortfolioManager (drawdown-aware position sizing)
  ├─ RiskManager (ATR-based SL/TP)
        ↓
[NATS publish]
        ↓
trading.signal.validated → execution-engine → MT5
```

## Archivos clave

- `app/correlation_engine.py` — correlación Pearson móvil + cointegración Engle-Granger + filtrado de señales opuestas en pares correlacionados + refuerzo de señales alineadas
- `app/portfolio_manager.py` — position sizing ajustado por drawdown, número de posiciones abiertas, y correlación con posiciones activas
- `app/risk_manager.py` — cálculo de ATR(14), SL = ATR × 1.5, TP = ATR × 2.5
- `app/multi_orchestrator.py` — orquestador principal (acumula señales en ventana, evalúa correlación, publica final)
- `app/nats_client.py` — cliente NATS dual (subscribe + publish con JetStream)
- `app/price_feed.py` — cliente HTTP al mt5-connector para `/rates`

## Configuración (env vars con prefix `ORCH_`)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `ORCH_NATS_URL` | `nats://localhost:4222` | URL NATS |
| `ORCH_NATS_SUBJECT_IN` | `tnsvt.lst.signal` | subject de señales crudas |
| `ORCH_NATS_SUBJECT_OUT` | `trading.signal.validated` | subject de señales finales |
| `ORCH_MT5_CONNECTOR_URL` | `http://localhost:8007` | URL mt5-connector |
| `ORCH_SYMBOLS` | `["XAUUSD","EURUSD","GBPUSD","USDCHF"]` | símbolos a operar |
| `ORCH_TIMEFRAMES` | `["M15","H1","H4"]` | timeframes |
| `ORCH_POLL_INTERVAL_SECONDS` | `30` | intervalo de evaluación |
| `ORCH_HISTORY_WINDOW` | `100` | velas para correlación |
| `ORCH_CORRELATION_THRESHOLD` | `0.7` | umbral para considerar correlación fuerte |
| `ORCH_ACCOUNT_BALANCE` | `10000.0` | equity inicial |
| `ORCH_RISK_PER_TRADE` | `0.01` | 1% del equity por trade |
| `ORCH_MAX_DRAWDOWN` | `0.15` | DD máximo antes de parar |
| `ORCH_MAX_POSITIONS` | `3` | máximo de posiciones simultáneas |
| `ORCH_ATR_PERIOD` | `14` | período ATR |
| `ORCH_SL_ATR_MULTIPLIER` | `1.5` | SL = ATR × esto |
| `ORCH_TP_ATR_MULTIPLIER` | `2.5` | TP = ATR × esto |
| `ORCH_COINT_ENABLED` | `true` | habilitar cointegración (Engle-Granger) |

## Lógica de filtrado por correlación

Para cada par de símbolos correlacionados (|ρ| > 0.7):
- **Señales opuestas** (uno BUY, otro SELL) → ambas se descartan (filtradas)
- **Señales alineadas** (ambos BUY o ambos SELL) → lot_multiplier × 1.2, confidence × 1.2
- **Correlación negativa** con misma dirección → lot_multiplier × 0.8

## Lógica de position sizing

```
base_risk = equity * 0.01
dd_factor = 1.0 (DD < 5%) | 0.7 (5-10%) | 0.5 (>10%)
pos_factor = 1.0 (<2 pos) | 0.8 (2-3) | 0.5 (>3)
corr_factor = 1.0 (0 correlated) | 0.75 (1) | 0.5 (2+)
final_risk = base_risk × dd_factor × pos_factor × corr_factor × lot_multiplier
lot_size = final_risk / (SL_distance × pip_value)
```

## Tests

```bash
cd apps/ai/orchestrator
pip install -e ".[dev]"
pytest tests/ -v
```

## Run local

```bash
cd apps/ai/orchestrator
ORCH_NATS_URL=nats://localhost:4222 \
ORCH_MT5_CONNECTOR_URL=http://localhost:8007 \
uvicorn app.main:app --host 0.0.0.0 --port 8060
```

## Docker

```bash
docker-compose -f docker-compose.dev.yml up -d orchestrator
```