# TNSVT Bridge API

Servicio FastAPI que conecta tu bot MT5 nativo (`D:\TradingBotMT5`) con el ecosistema TNSVT.

## ¿Qué hace?

- Recibe órdenes ejecutadas en MT5 vía HTTP
- Las persiste en SQLite local (cola persistente)
- Las publica a TNSVT (gateway) con retry automático
- Si TNSVT está caído, las órdenes se reintentan con backoff exponencial (5s → 10s → 20s → ... → máx 5min)

## Endpoints

| Método | Path | Descripción |
|--------|------|-------------|
| `GET` | `/health` | Health + stats de la cola |
| `POST` | `/api/v1/bridge/mt5/order` | Orden ejecutada en MT5 |
| `POST` | `/api/v1/bridge/telegram/signal` | Señal cruda desde Telegram |
| `POST` | `/api/v1/bridge/mt5/mobile` | Webhook desde app MT5 mobile |
| `GET` | `/api/v1/bridge/outbox/stats` | Métricas: PENDING, DELIVERED, etc. |
| `GET` | `/docs` | Swagger UI interactivo |

## Inicio

```cmd
cd apps\bridge\bridge-api
start.bat
```

Levanta en `http://localhost:8522`.

> Nota: el puerto 8502 está ocupado por el `Terminal_Financiera_Pro/api_server.py` heredado, por eso usamos 8522.

## Configuración (`.env`)

```env
BRIDGE_PORT=8502
TNSVT_GATEWAY_URL=http://localhost:8000
BRIDGE_API_KEY=dev-bridge-key-change-me
BRIDGE_DB=bridge_outbox.db
LOG_LEVEL=INFO
```

## Garantía anti-pérdida

```
Bot MT5 ejecuta orden
       │
       ▼
Bridge recibe POST → INSERT en SQLite (PENDING)
       │
       ▼
Bridge responde 202 Accepted al bot (inmediato)
       │
       ▼
Worker en background intenta publicar a TNSVT
       │
       ├── Éxito → marca DELIVERED
       │
       └── Falla → reintenta con backoff (5s, 10s, 20s, ...)
```

**Si el bridge se reinicia**: la cola persiste en `bridge_outbox.db`, se reanuda automáticamente.
**Si TNSVT se reinicia**: la cola espera y se publica cuando vuelva.
**Si la red se cae**: idem.

Ningún evento se pierde.
