# TNSVT V2 - Signal Engine

Corazón del sistema de trading. Recibe señales de múltiples fuentes, las valida, deduplica y publica a NATS para que otros servicios (risk-engine, execution-engine) las procesen.

## 🎯 Responsabilidad

- **Recibir señales** de: Telegram (vía telegram-bridge), API REST, TNSVT, manual, AI
- **Parsear** mensajes de texto en lenguaje natural (soporta múltiples formatos)
- **Validar** formato: symbol pattern, precios coherentes (BUY: TP > entry > SL)
- **Deduplicar** con SHA-256 hash + TTL 10 min (Redis + PostgreSQL)
- **Publicar** eventos a NATS (`trading.signal.created`, `.rejected`)
- **Stream SSE** para dashboards en tiempo real
- **Estadísticas** de signals recibidos/validados/rechazados

## 📡 Endpoints

| Método | Path | Auth | Descripción |
|--------|------|------|-------------|
| POST | `/api/v1/signals` | JWT | Submit signal manual/API |
| GET | `/api/v1/signals/:id` | JWT | Get signal por ID |
| GET | `/api/v1/signals` | JWT | List paginated |
| POST | `/api/v1/signals/parse` | JWT | Preview parsing de texto |
| GET | `/api/v1/signals/stream` | JWT | SSE stream de signals nuevos |
| GET | `/api/v1/signals/stats` | JWT | Estadísticas |
| POST | `/internal/ingest/telegram` | API Key | Webhook desde telegram-bridge |
| GET | `/health`, `/health/live`, `/health/ready`, `/metrics` | No | Health/Metrics |

## 📝 Formatos de Signal Soportados

El parser acepta múltiples formatos comunes de canales de Telegram:

```
BUY EURUSD @ 1.0850 SL 1.0830 TP 1.0890

SELL XAUUSD
Entry: 2050.50
SL: 2055
TP: 2045, 2040

🔵 BUY GBPUSD
Entry 1.2650
Stop Loss 1.2620
Take Profit 1.2700

📈 BUY EURUSD
🎯 Entry: 1.0850
🛑 SL: 1.0820
✅ TP1: 1.0870
✅ TP2: 1.0890
```

**Acciones soportadas**: BUY, SELL, LONG, SHORT, CLOSE, CLOSE ALL, MODIFY

**Símbolos soportados**: EURUSD, GBPUSD, XAUUSD, XAGUSD, BTCUSD, ETHUSD, US30, NAS100, etc.

## 🔄 Flujo de Procesamiento

```
Telegram msg → telegram-bridge (Python/Telethon)
    ↓ POST /internal/ingest/telegram
signal-engine
    ↓ Parse (regex + normalización)
    ↓ Validate format (symbol, prices coherentes)
    ↓ Deduplicate (SHA-256 hash + Redis TTL 10min)
    ↓ Save to PostgreSQL (trading.signals)
    ↓ Publish to NATS (trading.signal.created)
        ↓
        risk-engine (suscribe)
        ↓ Evalúa riesgo
        ↓ trading.signal.validated (si pasa)
        ↓
        execution-engine (suscribe)
        ↓ Ejecuta orden en MT5
        ↓ trading.signal.executed
```

## 🛡️ Validaciones

- ✅ Symbol pattern: `^[A-Z0-9]+(\.(m|M|r|R|pro|raw|Raw))?$`
- ✅ Entry price > 0
- ✅ SL > 0
- ✅ Al menos 1 TP
- ✅ Coherencia BUY: TP > entry > SL
- ✅ Coherencia SELL: TP < entry < SL
- ✅ Lot size 0.01-100
- ✅ Expiración no vencida
- ✅ Hash único (deduplicación)

## 🗄️ Schema PostgreSQL

Tablas creadas automáticamente:
- `trading.signals` - Todas las señales con su estado
- `trading.channels` - Configuración de canales Telegram

Índices optimizados: tenant_id, status, hash (unique), symbol, received_at, source.

## 🔌 Integraciones

- **PostgreSQL**: persistencia
- **Redis**: dedup fast-path + cache
- **NATS JetStream**: eventos publicados a `trading.signal.*`
- **telegram-bridge** (Python): ingest desde Telegram

## 🧪 Tests

```bash
cd apps/trading/signal-engine
go test ./...

# Tests específicos
go test ./internal/parser/... -v
```

## 🚀 Desarrollo

```bash
# Local (solo engine)
cd apps/trading/signal-engine
go mod tidy
go run .

# Con telegram-bridge
docker compose -f docker-compose.dev.yml up -d signal-engine telegram-bridge

# Ver logs
docker logs -f tnsvt-signal-engine
```

## 📋 Ver También

- [`docs/03-DATA-FLOWS.md`](../../../docs/03-DATA-FLOWS.md) - Flujo completo de datos
- [`docs/04-DATA-MODEL.md`](../../../docs/04-DATA-MODEL.md) - Schema detallado
- [`docs/10-AI-CORE.md`](../../../docs/10-AI-CORE.md) - AI integration