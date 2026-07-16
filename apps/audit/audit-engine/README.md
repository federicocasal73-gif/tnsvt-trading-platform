# TNSVT V2 - Audit Engine

Motor de auditoría que consume eventos de NATS y los persiste de forma append-only e inmutable en PostgreSQL.

## 🎯 Responsabilidad

- **Consumir** eventos de `trading.>`, `audit.>`, `platform.>`, `risk.>` de NATS
- **Almacenar** en `audit.events` (append-only, nunca UPDATE/DELETE)
- Sin lógica de negocio — solo persistencia de eventos

## 📡 NATS Subscriptions

```
trading.>     → eventos de trading (signals, orders, executions)
audit.>       → eventos de auditoría
platform.>    → eventos de plataforma (users, tenants)
risk.>        → eventos de riesgo (validaciones, límites)
```

## 🗄️ Schema PostgreSQL

```sql
CREATE TABLE audit.events (
    id         UUID PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    source     VARCHAR(100) NOT NULL DEFAULT '',
    subject    VARCHAR(255) NOT NULL DEFAULT '',
    data       JSONB DEFAULT '{}',
    metadata   JSONB DEFAULT '{}',
    tenant_id  UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## 🔄 Flujo

```
NATS event → Subscriber → Parse → INSERT INTO audit.events
    (fire & forget, sin retry, ack_policy: none)
```

## ⚙️ Configuración

| Variable | Descripción | Default |
|----------|-------------|---------|
| `AUDIT_ENGINE_PORT` | Puerto HTTP | `8600` |

## 📡 HTTP API

| Método | Path | Descripción |
|--------|------|-------------|
| GET | `/health` | Health check básico |
| GET | `/health/live` | Liveness |
| GET | `/health/ready` | Readiness (PostgreSQL ping) |
| GET | `/metrics` | Prometheus metrics |

## 🚀 Desarrollo

```bash
cd apps/audit/audit-engine
go mod tidy
go run .
```
