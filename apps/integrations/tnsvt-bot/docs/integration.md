# Integración TNSVT Bot → V2

## Arquitectura

```
Telegram ─→ bot/main.py ─→ TNSVTClient ─→ HTTP ─→ Bridge API (:8522) ─→ Go Services
                    ↑                            ↓
               watchdog.py            cmd_requests.json (close)
                    │                            │
                    └── SERVICE_DOWN ────────────┘
                         → BOT_ADMIN_CHAT_ID
```

## Flujo de datos

### MT5 Snapshots → Frontend
1. `mt5_multi_snapshot.py` lee `D:\TradingBotMT5\accounts.json`
2. Escribe `D:\TradingBotMT5\account_snapshot_<login>.json` por cada cuenta
3. Bridge API sirve `/mt5/accounts` y `/mt5/account?login=X`
4. Vite Frontend renderiza KPIs + selector de cuenta

### Cierre de posiciones
1. Frontend → Proxy Vite → `/api/v1/copier/close`
2. Bridge API escribe `D:\TradingBotMT5\cmd_requests.json`
3. `signal_copier/main.py` (cmd_worker task) lo detecta cada 3s
4. Ejecuta `order_close()` en MT5
5. Escribe resultado en `cmd_responses.json`

### Señales de Trading
1. Bridge API publica en NATS: `trading.signal.created`
2. Go signal-engine procesa y publica `trading.signal.validated`
3. Go copy-trading ejecuta en MT5

## Dependencias

| Componente | Puerto | Depende de |
|---|---|---|
| Bridge API | 8522 | NATS, MT5 snapshots |
| Signal Copier | — | Bridge API, MT5 Terminal |
| Telegram Bot | — | Bridge API |
| MT5 Terminal | — | Cuentas en accounts.json |

## Variables de Entorno

Ver `.env.example` para todas las variables.

Claves críticas:
- `BOT_TOKEN` — Token del bot de Telegram
- `BOT_ADMIN_CHAT_ID` — Chat ID para alertas del watchdog
- `TNSVT_BRIDGE_URL` — URL del bridge-api (default `http://localhost:8522`)
