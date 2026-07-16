# Price Feed Service

Real-time market data ingestion for the TNSVT V2 trading platform.

Connects to one or more upstream price sources (WebSocket or built-in mock),
normalizes the tick format, publishes each tick to NATS (`marketdata.tick.<symbol>`),
and exposes the latest prices via REST + SSE for downstream consumers.

## Endpoints

| Method | Path                              | Description                          |
|--------|-----------------------------------|--------------------------------------|
| GET    | `/health`                         | Liveness + registered sources        |
| GET    | `/health/live`                    | Liveness                             |
| GET    | `/health/ready`                   | Readiness                            |
| GET    | `/metrics`                        | Prometheus                           |
| GET    | `/api/v1/prices`                  | List symbols with at least one tick  |
| GET    | `/api/v1/prices/snapshot`         | Latest tick for every symbol         |
| GET    | `/api/v1/prices/:symbol`          | Latest tick for one symbol           |
| GET    | `/api/v1/prices/stream`           | SSE stream of new ticks (heartbeat 15s) |

## NATS

| Direction | Subject                       | Description                  |
|-----------|-------------------------------|------------------------------|
| Publish   | `marketdata.tick.<symbol>`    | Normalized tick per symbol   |

Stream: `MARKETDATA` (subjects `marketdata.>`)

## Sources

A `Source` represents a single upstream feed. By default the service starts
a **built-in mock** that generates a synthetic random-walk tick stream for
each configured symbol every 500 ms. This is enough for development and
integration testing without external dependencies.

To connect to a real WebSocket source, set `PRICE_FEED_MOCK_URL` (or rename
to `PRICE_FEED_SOURCE_URL`) to your feed's WebSocket endpoint. The expected
payload format is:

```json
{
  "symbol":    "EURUSD",
  "bid":       1.08495,
  "ask":       1.08505,
  "last":      1.08500,
  "volume":    1234,
  "timestamp": 1715812345000
}
```

The service will reconnect with exponential backoff (1s → 30s max) on
disconnection.

## Configuration

Environment variables (with the `PRICE_FEED_` prefix):

- `PRICE_FEED_PORT` (default: `8300`)
- `PRICE_FEED_SYMBOLS` (default: `EURUSD,GBPUSD,USDJPY,XAUUSD,BTCUSD`)
- `PRICE_FEED_MOCK_URL` (default: empty → use builtin mock)
- `PRICE_FEED_LOG_LEVEL` (default: `info`)
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `REDIS_DB`
- `NATS_URL`

## Running locally

```bash
cd apps/market-data/price-feed
go mod download
go run . &
sleep 2

# List active symbols
curl http://localhost:8300/api/v1/prices

# Snapshot of all prices
curl http://localhost:8300/api/v1/prices/snapshot

# Stream ticks in real time (curl --no-buffer)
curl --no-buffer http://localhost:8300/api/v1/prices/stream
```

## Tests

```bash
cd apps/market-data/price-feed
go test ./... -v -count=1
```

Tests cover:
- Tick math (mid, spread, percent spread)
- TickStore (set/get/snapshot, subscribe broadcast)
- Symbol parsing (comma-separated, trimming)
- Built-in mock source (emits ticks, walk bounded)

## Architecture notes

- **Hot path** is in-memory: a `TickStore` keeps the latest tick per symbol
  protected by a RWMutex. Reads from `/api/v1/prices/*` are O(1) map lookups.
- **Redis is optional**: writes are best-effort and failures are logged
  but never block the in-memory store.
- **Broadcast fan-out** uses buffered channels per subscriber; if a
  subscriber is slow, the broadcaster drops rather than blocks (back-pressure
  toward the source, not toward the consumer).
- **Heartbeat** on the SSE stream every 15 s prevents intermediate proxies
  from closing idle connections.
- **Built-in mock** uses `math/rand` seeded with the current Unix time
  and a per-symbol walk bounded to ±0.05% per tick.