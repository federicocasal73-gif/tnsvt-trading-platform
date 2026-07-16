# TNSVT V2 — Monorepo

> Plataforma SaaS de trading algorítmico, copy trading y análisis impulsado por IA.

## 📁 Estructura del Monorepo

```
TNSVT-V2-Architecture/
├── apps/                          # Microservicios
│   ├── trading/                   # Signal Engine, Execution Engine, Copy Trading, Telegram Bridge
│   ├── risk/                      # Risk Engine
│   ├── broker/                    # MT5 Connector (broker-abstraction reservado para Fase 2)
│   ├── ai/                        # AI Core (regime-detector reservado para Fase 2)
│   ├── market-data/               # Price Feed
│   ├── platform/                  # auth-service, user-service
│   ├── notification/              # Telegram Bot Service
│   ├── audit/                     # Audit Engine (event-sourcing)
│   └── gateway/                   # API Gateway (Traefik-friendly)
├── apps/frontend/                 # Vite + React 18 + TypeScript (Tauri desktop reservado para Fase 3)
├── shared/                        # Código compartido
│   ├── proto/                     # gRPC contracts
│   ├── schemas/                   # JSON schemas para NATS events
│   └── go-common/                 # Librerías Go compartidas (circuit, logging, metrics, config)
├── infrastructure/                # Docker, observabilidad, DB init
│   ├── observability/             # Prometheus + Grafana provisioning
│   └── postgres/                  # init.sql con schemas DDD
├── scripts/                       # status.sh, test-all.sh, test-service.sh
├── tests/                         # E2E + integration (vacíos en Fase 1)
├── docs/                          # 15 documentos de arquitectura
├── word/                          # Versiones Word de los docs
├── pdf/                           # Versiones PDF de los docs
└── docker-compose.dev.yml         # Stack completo de desarrollo
```

## 🚀 Comandos Rápidos

```bash
make help          # Ver todos los comandos disponibles
make up            # Levantar stack completo (Docker Compose)
make down          # Detener todo
make logs          # Ver logs de todos los servicios
make status        # Estado de cada servicio
make test          # Correr tests (Go + Python)
make build         # Build imágenes Docker
make clean         # Limpiar volúmenes y contenedores
```

## 🏗️ Stack Tecnológico

| Capa | Tecnología | Puerto |
|------|-----------|--------|
| **Backend Core** | Go 1.22+ | varios (8001-8008) |
| **AI/ML** | Python 3.12+ (FastAPI) | 8200 |
| **Market Data** | Go 1.22 (WebSocket + NATS) | 8300 |
| **Frontend** | Vite + React 18 + TypeScript | 5180 |
| **DB Transaccional** | PostgreSQL 16 + TimescaleDB | 5432 |
| **Cache** | Redis 7+ | 6379 |
| **Mensajería** | NATS + JetStream | 4222 |
| **LLM** | Ollama (self-hosted) | 11434 |
| **API Gateway** | Go (Traefik-friendly) | 8000 |
| **Monitoring** | Prometheus + Grafana | 9090, 3001 |

## 📚 Documentación

Ver [`docs/`](docs/) — 15 documentos completos de arquitectura.

**Empezar por**: [`docs/00-VISION.md`](docs/00-VISION.md)

### Índice de documentos:

1. **00-VISION** — Visión ejecutiva
2. **01-ARCHITECTURE-OVERVIEW** — Diagrama de alto nivel
3. **02-SERVICES-CATALOG** — Catálogo de 48 microservicios
4. **03-DATA-FLOWS** — 8 flujos de datos completos
5. **04-DATA-MODEL** — Modelo de datos PostgreSQL
6. **05-COMMUNICATION** — NATS + CloudEvents + sagas
7. **06-SECURITY** — Zero Trust + OAuth2 + RBAC
8. **07-INFRASTRUCTURE** — Docker + Kubernetes + CI/CD
9. **08-OBSERVABILITY** — Prometheus + Grafana + SLOs
10. **09-RESILIENCE** — Circuit breakers + DR plan
11. **10-AI-CORE** — AI Core + Ollama + WebSocket market data
12. **11-UX-DESIGN** — 5 paneles de usuario
13. **12-ROADMAP** — 4 fases de implementación (36 meses)
14. **13-RISKS** — 22 riesgos + mitigaciones
15. **14-SCALE-100K** — Estrategia para 100K usuarios

## 🎯 Servicios Implementados (Fase 1)

10 microservicios backend + 1 frontend en producción:

| # | Servicio | Lenguaje | Puerto | Path | Estado |
|---|----------|----------|--------|------|--------|
| 1 | api-gateway | Go | 8000 | `apps/gateway/api-gateway/` | ✅ |
| 2 | auth-service | Go | 8001 | `apps/platform/auth-service/` | ✅ + tests |
| 3 | user-service | Go | 8401 | `apps/platform/user-service/` | ✅ |
| 4 | signal-engine | Go | 8003 | `apps/trading/signal-engine/` | ✅ + tests |
| 5 | execution-engine | Go | 8004 | `apps/trading/execution-engine/` | ✅ |
| 6 | copy-trading | Go | 8005 | `apps/trading/copy-trading/` | ✅ |
| 7 | risk-engine | Go | 8006 | `apps/risk/risk-engine/` | ✅ + tests |
| 8 | mt5-connector | Go + Python | 8007 | `apps/broker/mt5-connector/` | ✅ (Windows) |
| 9 | audit-engine | Go | 8600 | `apps/audit/audit-engine/` | ✅ |
| 10 | ai-core | Python | 8200 | `apps/ai/ai-core/` | ✅ + tests |
| 11 | price-feed | Go | 8300 | `apps/market-data/price-feed/` | ✅ + tests |
| 12 | telegram-bot-service | Go | 8503 | `apps/notification/telegram-bot-service/` | ✅ |
| 13 | telegram-bridge | Python | (sub-svc) | `apps/trading/signal-engine/telegram-bridge/` | ✅ |
| 14 | frontend | Vite/React/TS | 5180 | `apps/frontend/` | ✅ |

Servicios reservados para Fase 2+ (documentados pero no implementados):
`regime-detector`, `broker-abstraction`.

## 🧪 Tests

```bash
# AI Core (Python)
cd apps/ai/ai-core && pytest tests/ -v

# Go services
for svc in auth-service signal-engine risk-engine price-feed; do
  (cd apps/.../$svc && go test ./... -count=1)
done
```

Servicios con tests unitarios: `ai-core` (7), `auth-service` (13), `signal-engine` (16), `risk-engine` (17), `price-feed` (19).

## 🔗 Proyecto Anterior

Este proyecto NO reemplaza al proyecto actual `Terminal_Financiera_Pro` que sigue corriendo y generando dinero. Es la evolución arquitectónica hacia una plataforma SaaS empresarial.

## 📅 Roadmap

- **Fase 1 (0-3m)**: MVP con 14 servicios, 100 usuarios
- **Fase 2 (3-9m)**: Growth, multi-tenant SaaS, 5K usuarios
- **Fase 3 (9-18m)**: Scale con Kubernetes, 50K usuarios
- **Fase 4 (18-36m)**: Enterprise, 100K+ usuarios

Ver [`docs/12-ROADMAP.md`](docs/12-ROADMAP.md) para detalles completos.

---

**Versión**: 0.1.0 (Fase 1 — MVP)
**Última actualización**: Julio 2026