# TNSVT V2 - Execution Engine

Orquesta la ejecución de trades en los brokers. Consume signals validadas de NATS, llama al broker connector, registra posición en risk-engine, y monitorea cierres.

## 🎯 Responsabilidad

- **Consumir** `trading.signal.validated` de NATS
- **Place order** vía broker connector (HTTP al mt5-connector service)
- **Register position** en risk-engine
- **Monitor** trades abiertos (detectar cierres)
- **Retry** con exponential backoff
- **Publish** ejecuciones a NATS (`trading.execution.*`)

## 📡 NATS Subscriptions

```
trading.signal.validated   → ejecutar en broker
trading.signal.rejected    → solo audit (no ejecutar)
```

## 📡 NATS Publishing

```
trading.execution.executed  → order filled successfully
trading.execution.failed    → broker rejected o retries agotados
trading.execution.cancelled → cancelado manualmente
trading.execution.closed    → trade cerrado (SL/TP/manual)
```

## 🔌 Broker Connectors

Patrón abstracto para soportar múltiples brokers:

```
Connector (interface)
  ├── PlaceOrder(req) → OrderResponse
  ├── ClosePosition(account, ticket) → CloseResponse
  ├── GetAccountInfo(account) → AccountInfo
  ├── GetPositions(account) → []Position
  └── HealthCheck() → error
```

**Implementaciones registradas en Fase 1**:
- **HTTPBrokerConnector** — proxy HTTP a mt5-connector service (default)
- (Fase 2) ctrader, binance, bybit, ibkr

Agregar un broker nuevo es tan simple como:
```go
brokerFactory.Register("binance", broker.NewBinanceConnector(...))
```

## 🔄 Flujo de Ejecución

```
1. NATS: trading.signal.validated (signal_id, lot_size, ...)
     ↓
2. Crear Execution (status=pending) en PostgreSQL
     ↓
3. Broker health check
     ↓
4. Order request vía HTTP al broker-connector
     ↓
5a. ✅ Aceptada → Update status=filled, save ticket
     ↓
     5b. POST /api/v1/risk/trade-opened (registrar posición)
     ↓
     5c. Publish NATS: trading.execution.executed

5d. ❌ Rechazada → Retry (max 3, backoff 2s)
     ↓
     5e. Si todos los retries fallan → status=failed
     ↓
     5f. Publish NATS: trading.execution.failed
```

## 🛡️ Trade Monitor (cada 10s)

Detecta trades cerrados automáticamente:

```
Loop cada 10s:
  1. GetFilledExecutions (status=filled)
  2. GetPositions del broker
  3. Si un ticket filled no está en posiciones actuales → trade cerrado
  4. Notify risk-engine: POST /api/v1/risk/trade-closed
  5. Publish NATS: trading.execution.closed
```

## 🔗 Integración risk-engine

**Trade abierto** (POST /api/v1/risk/trade-opened):
```json
{
  "signal_id": "...",
  "broker": "mt5",
  "account_id": "default",
  "ticket": "12345",
  "symbol": "EURUSD",
  "side": "buy",
  "quantity": 0.01,
  "entry_price": 1.0850,
  "stop_loss": 1.0830,
  "take_profit": 1.0890
}
```

**Trade cerrado** (POST /api/v1/risk/trade-closed):
```json
{
  "ticket": "12345",
  "exit_price": 1.0870,
  "pnl": 2.0,
  "close_reason": "tp"
}
```

## 🗄️ Schema PostgreSQL

- **`trading.executions`** — todas las ejecuciones con:
  - broker, account, symbol, side, quantity
  - status (pending → routed → filled / failed / cancelled)
  - order_id, ticket, filled_price, filled_qty, commission
  - retry_count, error_message
  - timestamps (created, submitted, filled, completed)

## ⚙️ Configuración

| Variable | Descripción | Default |
|----------|-------------|---------|
| `EXECUTION_ENGINE_PORT` | Puerto del servicio | `8004` |
| `EXECUTION_TIMEOUT_SECONDS` | Timeout por orden | `30` |
| `EXECUTION_RETRY_MAX` | Reintentos máximos | `3` |
| `EXECUTION_RETRY_BACKOFF` | Backoff entre reintentos (s) | `2` |
| `DEFAULT_BROKER` | Broker default | `mt5` |
| `DEFAULT_ACCOUNT_ID` | Cuenta default | `default` |
| `MT5_CONNECTOR_URL` | URL del mt5-connector | `http://mt5-connector:8007` |
| `RISK_ENGINE_URL` | URL del risk-engine | `http://risk-engine:8006` |

## 📡 HTTP API

| Método | Path | Descripción |
|--------|------|-------------|
| POST | `/api/v1/executions` | Ejecutar signal |
| GET | `/api/v1/executions` | Listar ejecuciones |
| GET | `/api/v1/executions/:id` | Get ejecución |
| POST | `/api/v1/executions/:id/cancel` | Cancelar |
| GET | `/api/v1/executions/stats` | Estadísticas |
| GET | `/health`, `/health/live`, `/health/ready`, `/metrics` | Health |

## 🚀 Desarrollo

```bash
cd apps/trading/execution-engine
go mod tidy
go run .
```

## 📋 Ver También

- [`docs/02-SERVICES-CATALOG.md`](../../../docs/02-SERVICES-CATALOG.md)
- [`docs/03-DATA-FLOWS.md`](../../../docs/03-DATA-FLOWS.md)