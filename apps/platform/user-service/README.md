# TNSVT V2 - User Service

CRUD de perfiles de usuario, preferencias y configuración de notificaciones.

## 🎯 Responsabilidad

- **Perfiles**: nombre, avatar, timezone, language, phone
- **Preferencias**: configuraciones de UI y trading guardadas como JSON
- **Notificaciones**: settings por canal (Telegram, email, push)
- Cache en Redis, eventos publicados en NATS

## 🗄️ Schema PostgreSQL

```sql
CREATE TABLE platform.user_profiles (
    user_id        UUID PRIMARY KEY REFERENCES platform.users(id) ON DELETE CASCADE,
    tenant_id      UUID NOT NULL,
    full_name      VARCHAR(200) NOT NULL DEFAULT '',
    avatar_url     VARCHAR(500) DEFAULT '',
    timezone       VARCHAR(50) NOT NULL DEFAULT 'UTC',
    language       VARCHAR(10) NOT NULL DEFAULT 'en',
    phone          VARCHAR(30) DEFAULT '',
    preferences    JSONB DEFAULT '{}',
    notify_settings JSONB DEFAULT '{}',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## ⚙️ Configuración

| Variable | Descripción | Default |
|----------|-------------|---------|
| `USER_SERVICE_PORT` | Puerto HTTP | `8401` |

## 📡 HTTP API

| Método | Path | Descripción |
|--------|------|-------------|
| GET | `/api/v1/users/:id/profile` | Obtener perfil |
| POST | `/api/v1/users/:id/profile` | Crear perfil |
| PUT | `/api/v1/users/:id/profile` | Actualizar perfil |
| GET | `/health`, `/health/live`, `/health/ready` | Health |
| GET | `/metrics` | Prometheus |

## 🚀 Desarrollo

```bash
cd apps/platform/user-service
go mod tidy
go run .
```
