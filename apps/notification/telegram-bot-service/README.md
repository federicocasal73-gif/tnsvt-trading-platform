# TNSVT V2 - Telegram Bot Service

Envía notificaciones a Telegram vía Bot API HTTP y responde a comandos slash.

## 🎯 Responsabilidad

- **Enviar** mensajes a chats de Telegram vía Bot HTTP API
- **Responder** comandos: /status, /balance, /positions, /pnl
- Sin estado — solo NATS in → Telegram HTTP out

## 📡 NATS

| Subject | Direction | Descripción |
|---------|-----------|-------------|
| `notification.telegram.send` | ← consumo | Enviar notificación |
| `platform.telegram.command` | ← consumo | Responder a comando |

## ⚙️ Configuración

| Variable | Descripción | Default |
|----------|-------------|---------|
| `TELEGRAM_BOT_PORT` | Puerto HTTP | `8503` |
| `TELEGRAM_BOT_TOKEN` | Token del bot (obligatorio) | — |

## 📡 HTTP API

| Path | Descripción |
|------|-------------|
| `/health` | Health check |
| `/health/live` | Liveness |
| `/health/ready` | Readiness (NATS connected) |
| `/metrics` | Prometheus metrics |

## 🚀 Desarrollo

```bash
export TELEGRAM_BOT_TOKEN="tu_token"
cd apps/notification/telegram-bot-service
go mod tidy
go run .
```

## 🗄️ Dependencias

- **NATS** — consume eventos de notificación
- **Telegram Bot API** — outbound HTTP
- Sin PostgreSQL, sin Redis
