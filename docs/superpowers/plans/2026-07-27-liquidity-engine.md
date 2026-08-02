# Plan: Liquidity Engine (LST Signals) — ACTUALIZADO 2026-07-27

## Objetivo
Implementar un servicio `liquidity-engine` en FastAPI que genere señales de liquidez (LST) desde datos MT5, las transforme a formato `SignalInput`, y las publique vía NATS para que execution-engine ejecute trades reales en MT5.

## Arquitectura final
```
MT5 Terminal → mt5-connector (/rates) → liquidity-engine (LST calc + lst_to_signal) 
  → NATS JetStream → execution-engine → mt5-connector (/orders) → MT5 Terminal
```

## Estado de implementación

### ✅ Completado
1. MT5 connector con endpoint `/rates` (OHLCV, Unix timestamps)
2. Liquidity engine completo en `apps/ai/liquidity-engine/` (Python/FastAPI)
3. `lst_engine.py` — cálculo de señales LST (5 métricas, ventana 20 barras)
4. `models.py` — LSTSignal, LSTMetrics, RateOHLCV, SignalInput, lst_to_signal()
5. `nats_client.py` — publicador NATS para `tnsvt.lst.signal` y `trading.signal.validated`
6. `main.py` — FastAPI con signal loop, endpoints /health, /lst/latest, /reset
7. `lst_to_signal()` — transformación LST → SignalInput (filtra señales neutrales)
8. 9/9 tests pasando (incluyendo transformación buy/sell/neutral)
9. Gateway config actualizado con liquidity-engine (puerto 8050)
10. docker-compose.dev.yml actualizado
11. Dockerfile creado
12. **Verificación e2e NATS→execution-engine→MT5 exitosa** (ticket 152391032982 filled @ 4077.52)

### ⚠️ Siguiente paso: Loop automático del liquidity-engine
Una vez verificado el pipeline manual, levantar el signal loop automático que consume MT5 OHLCV y publica señales reales.

## Estructura de archivo (monorepo)
```
apps/ai/liquidity-engine/
  app/
    __init__.py
    main.py          # FastAPI + signal loop + lst_to_signal
    lst_engine.py    # LST calculation
    models.py        # LSTSignal, LSTMetrics, RateOHLCV, SignalInput, lst_to_signal()
    nats_client.py   # NATS publisher (dual subject)
    config.py        # pydantic-settings
  tests/
    test_lst_engine.py  # 9 tests
  pyproject.toml
  Dockerfile
  README.md
```

## SignalInput format (ejecution-engine compatible)
```python
SignalInput(
    id=str(uuid4()),
    tenant_id=str(uuid4()),
    source="liquidity-engine",
    symbol="XAUUSD",
    action="BUY",  # or "SELL"
    entry_price=None,  # market order - execution-engine resolves price
    stop_loss=None,
    take_profits=[],
    lot_size=None,
    lot_mode="fixed",
    confidence=0.9,
    hash="lst:XAUUSD:M1:2026-07-27T...",
)
```

## Lógica de señales LST
- **liquidity_buy**: `liquidity_score > 0.5` + `buy_pressure > 0.15` (aligned volume & flow)
- **liquidity_sell**: `liquidity_score > 0.5` + `sell_pressure > 0.15` (aligned)
- **neutral**: cualquier otra condición (filtrado en `lst_to_signal`)
- **Confianza**: `min(pressure * 2, 1.0) * liquidity_score`

## Métricas LST
- `relative_spread`: (ask - bid) / mid * 10000
- `volume_imbalance`: basado en posición del cierre en el rango barra
- `order_flow_pressure`: directional pressure del cierre
- `microstructure_score`: spread quality + volume consistency
- `liquidity_score`: composite (spread 40% + volume 30% + depth 30%)

## Configuración NATS
- NATS: `nats://localhost:4222`
- Stream: `tnsvt`
- Subject debug: `tnsvt.lst.signal`
- Subject ejecución: `trading.signal.validated` (execution-engine)

## ✅ Verificación e2e completada

### Bugs encontrados y corregidos durante la verificación
1. **mt5_bridge.py — `TradePosition.commission` AttributeError**
   - `p.commission` no existe en el API MT5 Python — removido del `op_positions_get`
   - Bloqueaba queries de posiciones, marcando mt5-connector como desconectado

2. **mt5_bridge.py — comment limit del broker**
   - El broker "metaquotes-demo" rechaza comments de 25+ caracteres con "Invalid comment argument"
   - Agregado `sanitize_comment()` que remueve caracteres no-alfanuméricos y trunca a 24 chars
   - Aplicado en `op_place_order` y `op_close_position`

3. **execution-engine — upstream broker health check abortaba ejecución**
   - `service.go ExecuteSignal()` llamaba `connector.HealthCheck()` antes de `PlaceOrder`
   - Si mt5-connector reportaba 503 (MT5 brevemente desconectado), el execution fallaba sin retry
   - Removido el check upfront — `PlaceOrder` retry loop maneja fallos transitorios

4. **mt5-connector — handler IsConnected check causaba 503 inmediato en retries**
   - Cada handler verificaba `client.IsConnected()` antes de procesar
   - Cuando `callBridge` fallaba una vez, marcaba `connected=false` y todos los retries fallaban con 503
   - Removido el check upfront en handlers — `callBridge` reconecta automáticamente si es necesario

5. **mt5-connector — stderr no capturado**
   - `cmd.Output()` solo capturaba stdout, stderr se perdía
   - Cambiado a `cmd.Stderr = &stderrBuf` para debug del error Python

### Verificación final (ticket 152391032982)
- SignalInput seq=13 publicado en `trading.signal.validated`
- execution-engine (puerto 8004) procesó la señal
- mt5-connector (puerto 8007) ejecutó `place_order` vía Python bridge subprocess
- MT5 Terminal abrió posición ticket 152391032982 BUY 0.01 XAUUSD @ 4077.52
- Execution record en BD: status=**filled**, retry_count=0
- Latencia total: ~600ms

### Variables de entorno requeridas
```
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
