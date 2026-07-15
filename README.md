# TNSVT V2 — Monorepo

> Plataforma SaaS de trading algorítmico, copy trading y análisis impulsado por IA.

## 📁 Estructura del Monorepo

```
TNSVT-V2-Architecture/
├── apps/                    # 17 microservicios (Go + Python)
│   ├── trading/             # Signal Engine, Execution Engine, Copy Trading
│   ├── risk/                # Risk Engine
│   ├── broker/              # MT5 Connector, Broker Abstraction
│   ├── ai/                  # AI Core, Regime Detector
│   ├── market-data/         # Price Feed
│   ├── platform/            # Auth, User Service
│   ├── notification/        # Telegram Notifier
│   ├── infrastructure/      # Audit Engine (Event Sourcing)
│   └── gateway/             # API Gateway (Traefik)
├── frontend/                # Next.js 14+ (web) + Tauri (desktop, opcional)
├── shared/                  # Código compartido
│   ├── proto/               # gRPC contracts
│   ├── schemas/             # JSON schemas para NATS events
│   └── go-common/           # Librerías Go compartidas (circuit, logging, metrics, config)
├── infrastructure/          # Docker, K8s, monitoring
│   ├── observability/       # Prometheus + Grafana
│   └── dockerfiles/         # Dockerfile multi-stage
├── scripts/                 # start.sh, stop.sh, status.sh, test-all.sh
├── tests/                   # E2E + integration tests
├── docs/                    # 15 documentos de arquitectura
├── word/                    # Versiones Word de los docs
└── pdf/                     # Versiones PDF de los docs
```

## 🚀 Comandos Rápidos

```bash
make help        # Ver todos los comandos disponibles
make up          # Levantar stack completo (Docker Compose)
make down        # Detener todo
make logs        # Ver logs de todos los servicios
make status      # Estado de cada servicio
make test        # Correr tests
make build       # Build imágenes Docker
make clean       # Limpiar volúmenes y contenedores
```

## 🏗️ Stack Tecnológico

| Capa | Tecnología | Puerto |
|------|-----------|--------|
| **Backend Core** | Go 1.22+ | varios |
| **AI/ML** | Python 3.12+ (FastAPI) | 8000-8005 |
| **Frontend** | Next.js 14+ (TypeScript) | 3000 |
| **DB Transaccional** | PostgreSQL 16 + TimescaleDB | 5432 |
| **Cache** | Redis 7+ | 6379 |
| **Mensajería** | NATS + JetStream | 4222 |
| **LLM** | Ollama (self-hosted) | 11434 |
| **API Gateway** | Traefik | 80, 443, 8080 |
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

## 🎯 Servicios de Fase 1 (MVP)

Los 17 servicios implementados en esta fase:

| # | Servicio | Lenguaje | Puerto | Estado |
|---|----------|----------|--------|--------|
| 1 | api-gateway | Go | 8000 | 🚧 |
| 2 | auth-service | Go | 8001 | 🚧 |
| 3 | user-service | Go | 8002 | 🚧 |
| 4 | signal-engine | Go | 8003 | 🚧 |
| 5 | execution-engine | Go | 8004 | 🚧 |
| 6 | copy-trading | Go | 8005 | 🚧 |
| 7 | risk-engine | Go | 8006 | 🚧 |
| 8 | mt5-connector | Go | 8007 | 🚧 |
| 9 | audit-engine | Go | 8008 | 🚧 |
| 10 | ai-core | Python | 8010 | 🚧 |
| 11 | regime-detector | Python | 8011 | 🚧 |
| 12 | price-feed | Python | 8012 | 🚧 |
| 13 | telegram-notifier | Python | 8013 | 🚧 |

## 🔗 Proyecto Anterior

Este proyecto NO reemplaza al proyecto actual `Terminal_Financiera_Pro` que sigue corriendo y generando dinero. Es la evolución arquitectónica hacia una plataforma SaaS empresarial.

## 📅 Roadmap

- **Fase 1 (0-3m)**: MVP con 17 servicios, 100 usuarios
- **Fase 2 (3-9m)**: Growth, multi-tenant SaaS, 5K usuarios
- **Fase 3 (9-18m)**: Scale con Kubernetes, 50K usuarios
- **Fase 4 (18-36m)**: Enterprise, 100K+ usuarios

Ver [`docs/12-ROADMAP.md`](docs/12-ROADMAP.md) para detalles completos.

---

**Versión**: 0.1.0 (Fase 0 — Setup Base)
**Última actualización**: Julio 2026