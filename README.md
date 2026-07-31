# TNSVT V2 — Monorepo

![Go](https://img.shields.io/badge/Go-1.22+-00ADD8?logo=go)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql)
![NATS](https://img.shields.io/badge/NATS-JetStream-27AAE1?logo=nats)
![Redis](https://img.shields.io/badge/Redis-7-FF4438?logo=redis)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker)
![License](https://img.shields.io/badge/License-Proprietary-red)

> **Plataforma SaaS de trading algorítmico** · 13 microservicios · Event-Driven · AI-Powered · Multi-Broker

| | |
|---|---|
| 📄 **PDF completo** | [`TNSVT-V2-Architecture.pdf`](TNSVT-V2-Architecture.pdf) (3.2 MB) |
| 🔗 **Demo** | `http://localhost:8000` · `admin@tnsvt.local` / `Admin123!Demo` |
| 🏗️ **Arquitectura** | [`ARCHITECTURE.md`](ARCHITECTURE.md) · [`docs/`](docs/) |

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

## 🎯 Servicios (Running)

**13 servicios verificados** operativos en este momento:

| # | Servicio | Puerto | Lenguaje | Ruta Docker |
|---|----------|--------|----------|-------------|
| 1 | `api-gateway` | 8000 | Go | `apps/gateway/api-gateway/` |
| 2 | `auth-service` | 8001 | Go | `apps/platform/auth-service/` |
| 3 | `signal-engine` | 8003 | Go | `apps/trading/signal-engine/` |
| 4 | `execution-engine` | 8004 | Go | `apps/trading/execution-engine/` |
| 5 | `copy-trading` | 8005 | Go | `apps/trading/copy-trading/` |
| 6 | `risk-engine` | 8006 | Go | `apps/risk/risk-engine/` |
| 7 | `mt5-connector` | 8007 | Go | `apps/broker/mt5-connector/` |
| 8 | `signal-generator` | 8011 | Python | `apps/ai/signal-generator/` |
| 9 | `news-analyzer` | 8051 | Python | `apps/ai/news-analyzer/` |
| 10 | `orchestrator` | 8060 | Python | `apps/ai/orchestrator/` |
| 11 | `price-feed` | 8300 | Go | `apps/market-data/price-feed/` |
| 12 | `telegram-bot-service` | 8503 | Go | `apps/notification/telegram-bot-service/` |
| 13 | `bridge-api` | 8522 | Python | `apps/bridge/bridge-api/` |
| 14 | `account-manager` | 8510 | Go | `apps/platform/account-manager/` |

Pipeline E2E: `signal → NATS → signal-engine → copy-trading → execution-engine → mt5-connector` ✅ verificado.

**Servicios planeados Fase 2+**: `regime-detector`, `broker-abstraction`, `frontend (React)`, `user-service`.

## 🧪 Tests

```bash
# Go services
for svc in auth-service signal-engine risk-engine price-feed; do
  (cd apps/trading/$svc && go test ./... -count=1) 2>/dev/null
  (cd apps/risk/$svc && go test ./... -count=1) 2>/dev/null
  (cd apps/platform/$svc && go test ./... -count=1) 2>/dev/null
done

# Python services
for svc in signal-generator news-analyzer orchestrator bridge-api; do
  (cd apps/ai/$svc && python -m pytest tests/ -v) 2>/dev/null
  (cd apps/bridge/$svc && python -m pytest tests/ -v) 2>/dev/null
done
```

Servicios con tests: `auth-service` (13), `signal-engine` (16), `risk-engine` (17), `price-feed` (19).

## 📦 Arquitectura

![System Architecture](docs/diagrams/architecture.png)

Ver [`ARCHITECTURE.md`](ARCHITECTURE.md) para diagrama completo + catálogo de servicios.

## 🚀 Quick Start

```bash
# 1. Levantar todo el stack
docker-compose -f docker-compose.dev.yml up -d

# 2. Verificar estado
& .\scripts\status.bat       # (Windows)
# o
./scripts/status.sh           # (Linux/Mac)

# 3. Abrir dashboard
start http://localhost:8000    # (Windows)
# Login: admin@tnsvt.local / Admin123!Demo

# 4. Verificar E2E Pipeline
curl -s http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $(curl -s http://localhost:8000/api/v1/auth/login \
    -H 'Content-Type: application/json' \
    -d '{\"email\":\"admin@tnsvt.local\",\"password\":\"Admin123!Demo\"}' | \
    python -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>nul)"
```

## 📅 Roadmap

| Fase | Timeline | Objetivo |
|------|----------|----------|
| **1** ✅ Actual | Jul 2026 | 13 servicios, pipeline E2E, bridge MT5, Telegram, AI core |
| **2** | Q3 2026 | Multi-broker (cTrader), WebSocket, Grafana, backtesting |
| **3** | Q4 2026 | Frontend React completo, Tauri desktop, multi-tenancy |
| **4** | Q1 2027 | 100K usuarios, Kubernetes HA, white-label |

Ver [`docs/12-ROADMAP.md`](docs/12-ROADMAP.md) para detalles completos.

---

**Versión**: 2.0 (Fase 1 — Core operativo)
**Última actualización**: Julio 2026