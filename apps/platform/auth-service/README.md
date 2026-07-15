# TNSVT V2 - auth-service

Servicio de autenticación OAuth2 + JWT + RBAC con multi-tenant.

## 🎯 Responsabilidad

- Registro y autenticación de usuarios
- Multi-tenant (cada usuario pertenece a un tenant)
- OAuth2 password grant con access + refresh tokens (JWT HS256)
- bcrypt para passwords (rounds=12)
- RBAC: 12 roles, 30+ permisos
- 2FA (TOTP) opcional
- Rate limiting con Redis
- Audit log de cada evento

## 📡 Endpoints

| Método | Path | Auth | Descripción |
|--------|------|------|-------------|
| POST | `/api/v1/auth/register` | No | Crear tenant + usuario admin |
| POST | `/api/v1/auth/login` | No | Login (retorna tokens) |
| POST | `/api/v1/auth/refresh` | No | Renovar tokens |
| POST | `/api/v1/auth/logout` | JWT | Logout (revoca sesión) |
| GET | `/api/v1/auth/me` | JWT | Info del usuario actual |
| POST | `/api/v1/auth/password/change` | JWT | Cambiar contraseña |
| POST | `/api/v1/auth/2fa/setup` | JWT | Generar secret 2FA |
| POST | `/api/v1/auth/2fa/verify` | JWT | Activar 2FA con código |
| GET | `/api/v1/auth/users` | Admin | Listar usuarios del tenant |
| GET | `/health` | No | Health check |
| GET | `/health/live` | No | Liveness probe |
| GET | `/health/ready` | No | Readiness probe |
| GET | `/metrics` | No | Prometheus metrics |

## 🔐 Roles (RBAC)

12 roles con permisos jerárquicos:

```
super_admin      → Todos los permisos
admin            → Casi todos (sin delete tenant)
billing_admin    → Solo billing
developer        → Logs, metrics, API
support          → Lectura + notificaciones
trader           → Ejecutar trades
viewer           → Solo lectura
api_user         → API externa
bot_service      → Servicios automatizados
tenant_admin     → Admin de su tenant
tenant_trader    → Trader de su tenant
tenant_viewer    → Viewer de su tenant
```

## 🗄️ Schema PostgreSQL

Crea automáticamente las tablas:

- `platform.tenants` - Organizaciones (multi-tenant)
- `platform.users` - Usuarios con bcrypt + 2FA
- `platform.sessions` - Refresh tokens hasheados
- `platform.audit_events` - Log de auditoría

## 🚀 Desarrollo

```bash
# Local (requiere Go 1.22+)
cd apps/platform/auth-service
go mod tidy
go run .

# Con Docker
docker build -t tnsvt/auth-service .
docker run --rm -p 8001:8001 \
  -e POSTGRES_HOST=host.docker.internal \
  -e JWT_SECRET=your_32_char_secret_here \
  tnsvt/auth-service
```

## 📝 Variables de Entorno

Ver [`/shared/.env.example`](../../../.env.example) sección `AUTH_SERVICE`.

Críticas:
- `JWT_SECRET` (mínimo 32 caracteres)
- `POSTGRES_*` (conexión DB)
- `REDIS_*` (rate limiting)
- `BCRYPT_ROUNDS` (default 12)

## 🧪 Tests

```bash
cd apps/platform/auth-service
go test ./...
```

Tests pendientes para Fase 1:
- [ ] Unit tests por service
- [ ] Integration tests con testcontainers
- [ ] E2E tests
- [ ] Benchmarks

## 🔗 Integraciones

- **PostgreSQL 16**: usuarios, tenants, sesiones, audit
- **Redis 7**: rate limiting, sesiones activas
- **Otros servicios**: emite JWT que validan los demás

## 📋 Ver También

- [`docs/06-SECURITY.md`](../../../docs/06-SECURITY.md) - Estrategia completa de seguridad
- [`docs/02-SERVICES-CATALOG.md`](../../../docs/02-SERVICES-CATALOG.md) - Catálogo de servicios
- [`shared/go-common/`](../../../shared/go-common/) - Librerías compartidas