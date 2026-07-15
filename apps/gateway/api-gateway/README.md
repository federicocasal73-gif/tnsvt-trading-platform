# TNSVT V2 - api-gateway

Punto de entrada único para todos los microservicios. Actúa como reverse proxy, validador JWT centralizado, rate limiter, y circuit breaker.

## 🎯 Responsabilidad

- **Reverse proxy** a todos los microservicios
- **Validación JWT centralizada** (opcional por endpoint)
- **Rate limiting** global por IP y por servicio
- **Circuit breaker** por servicio (5 fallos → 30s recovery)
- **Load balancing** round-robin entre instancias
- **Health checks** agregados de todos los servicios
- **CORS** centralizado
- **Publicación de eventos** a NATS para audit/monitoring

## 📡 Routing

```
/api/v1/auth/*          → auth-service:8001
/api/v1/users/*         → user-service:8002
/api/v1/signals/*       → signal-engine:8003
/api/v1/executions/*    → execution-engine:8004
/api/v1/copy/*          → copy-trading:8005
/api/v1/risk/*          → risk-engine:8006
/api/v1/brokers/*       → mt5-connector:8007
/api/v1/audit/*         → audit-engine:8008
/api/v1/ai/*            → ai-core:8010
/api/v1/regime/*        → regime-detector:8011
/api/v1/prices/*        → price-feed:8012
/api/v1/notify/*        → telegram-notifier:8013

Endpoints propios:
GET  /health          → Health check básico
GET  /health/full     → Health check de TODOS los servicios
GET  /health/live     → Liveness probe
GET  /metrics         → Prometheus metrics
GET  /                → Info del gateway
```

## 🔧 Configuración

Editar `config/services.json` para:
- Agregar/quitar servicios
- Cambiar URLs de instancias (load balancing)
- Ajustar timeouts y rate limits

```json
{
  "name": "auth-service",
  "path_prefix": "/api/v1/auth",
  "instances": ["http://auth-service:8001", "http://auth-service-2:8001"],
  "timeout_ms": 5000,
  "rate_limit": 100,
  "health_path": "/health",
  "required": true
}
```

## 🛡️ Características de Seguridad

- **JWT validation**: HS256, valida contra secret en `JWT_SECRET`
- **CORS restrictivo**: solo orígenes whitelisted
- **Rate limiting**: Redis-based, configurable por servicio
- **Circuit breaker**: 5 fallos consecutivos → abre 30s
- **Request ID**: cada request tiene un UUID para tracing
- **Headers forwarded**: X-Request-ID, X-Tenant-ID, X-Real-IP

## 📊 Observabilidad

- Cada request se loggea con: method, path, status, latency_ms, ip, user_id (si está autenticado)
- Publica eventos a NATS en `gateway.request.<service>`
- Expone Prometheus metrics en `/metrics`
- Health check agregado en `/health/full`

## 🚀 Desarrollo

```bash
# Local
cd apps/gateway/api-gateway
go mod tidy
go run .

# Docker
docker build -t tnsvt/api-gateway .
docker run --rm -p 8000:8000 \
  -e REDIS_HOST=host.docker.internal \
  -e NATS_HOST=host.docker.internal \
  -e JWT_SECRET=your_32_char_secret \
  tnsvt/api-gateway
```

## 📝 Variables de Entorno

| Variable | Descripción | Default |
|----------|-------------|---------|
| `API_GATEWAY_PORT` | Puerto del gateway | `8000` |
| `JWT_SECRET` | Secret para validar JWT | `dev_secret_change_me_min_32_chars_abc` |
| `REDIS_HOST` | Redis para rate limiting | `localhost` |
| `REDIS_PORT` | Puerto Redis | `6379` |
| `NATS_HOST` | NATS para eventos | `localhost` |
| `NATS_PORT` | Puerto NATS | `4222` |
| `ENV` | environment | `development` |
| `LOG_LEVEL` | Nivel de logs | `info` |

## 🧪 Tests

```bash
cd apps/gateway/api-gateway
go test ./...
```

Tests pendientes:
- [ ] Unit tests para circuit breaker
- [ ] Tests de routing con mocks
- [ ] Integration tests con servicios reales
- [ ] Load tests con k6

## 🔗 Integraciones

- **Todos los microservicios**: proxy transparente
- **Traefik**: expuesto en puerto 80/443
- **Redis**: rate limiting
- **NATS**: audit events
- **Prometheus**: scraping `/metrics`

## 📋 Ver También

- [`docs/07-INFRASTRUCTURE.md`](../../../docs/07-INFRASTRUCTURE.md) - Infra completa
- [`docs/09-RESILIENCE.md`](../../../docs/09-RESILIENCE.md) - Circuit breakers
- [`docs/06-SECURITY.md`](../../../docs/06-SECURITY.md) - Seguridad Zero Trust