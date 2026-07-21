# TNSVT Bot — Telegram + Signal Copier + MT5 Multi-Cuenta

Parte del ecosistema TNSVT V2. Bot de Telegram (`@terminalfinancieraproTNSVT_bot`) + Signal Copier MT5 + scripts de utilidad.

## Estructura

```
tnsvt-bot/
├── bot/                → Telegram bot (comandos inline, watchdog)
├── signal_copier/      → Ejecutor de señales MT5 (multi-cuenta)
├── config/             → Settings
├── scripts/            → Scripts de inicio y utilidades MT5
├── docs/               → Documentación de integración
└── tradingeconomics/   → SDK third-party (legacy)
```

## Requisitos

- Python 3.12+
- MT5 Terminal (MetaTrader 5)
- Telegram Bot Token
- PostgreSQL + NATS + Redis (infra V2)

## Setup

```bash
cd apps/integrations/tnsvt-bot
cp .env.example .env
# Editar .env con credenciales reales
pip install -r requirements.txt
```

## Arranque

| Componente | Comando |
|---|---|
| MT5 Snapshot | `scripts/start-mt5-multi.bat` |
| Signal Copier | `start_copier.bat` |
| Telegram Bot | `start_bot.bat` |
| Bridge API | `start_bridge.bat` |

## Comandos del Bot

| Comando | Descripción |
|---|---|
| `/start` | Menú principal con botones inline |
| `/senales` | Últimas señales de trading |
| `/statshoy` | Estadísticas del día |
| `/historial` | Historial de trades |
| `/canales` | Rendimiento por canal |
| `/cuentas` | Multi-cuenta MT5 |
| `/cerrar SYMBOL` | Cierra posición por símbolo |

## Integración V2

- Bot → Bridge API (`http://localhost:8522`) via `TNSVTClient`
- MT5 snapshots en `D:\TradingBotMT5\account_snapshot_*.json`
- Close commands via `cmd_requests.json` (escrito por bridge-api `/copier/close`)

## Watchdog

El bot publica `SERVICE_DOWN` / `SERVICE_RESTORED` al `BOT_ADMIN_CHAT_ID`
cuando detecta fallos en bridge-api, signal_copier o MT5 snapshot.
