# ROADMAP.md — Hoja de Ruta de Desarrollo TNSVT V2

**Proyecto:** TNSVT V2 — Plataforma SaaS de Trading  
**Versión:** 2.0.0  
**Última Actualización:** 2026-07-14  
**Estado:** Documento de Planificación Estratégica  

---

## Tabla de Contenidos

1. [Resumen Ejecutivo](#1-resumen-ejecutivo)
2. [Visión General por Fases](#2-visión-general-por-fases)
3. [Fase 1: MVP (0-3 Meses)](#3-fase-1-mvp-0-3-meses)
4. [Fase 2: Growth (3-9 Meses)](#4-fase-2-growth-3-9-meses)
5. [Fase 3: Scale (9-18 Meses)](#5-fase-3-scale-9-18-meses)
6. [Fase 4: Enterprise (18-36 Meses)](#6-fase-4-enterprise-18-36-meses)
7. [Ruta de Migración Tecnológica](#7-ruta-de-migración-tecnológica)
8. [Hitos de Riesgo y Criterios Go/No-Go](#8-hitos-de-riesgo-y-criterios-gono-go)
9. [Modelo de Costos por Fase](#9-modelo-de-costos-por-fase)
10. [Dependencias Críticas](#10-dependencias-críticas)
11. [Métricas de Éxito por Fase](#11-métricas-de-éxito-por-fase)
12. [Equipo Requerido por Fase](#12-equipo-requerido-por-fase)

---

## 1. Resumen Ejecutivo

TNSVT V2 evoluciona desde un sistema monolítico (Symfony PHP + FastAPI + SQLite)
hacia una plataforma SaaS empresarial distribuida capaz de soportar 100,000+ usuarios
con operaciones multi-broker, multi-tenant e inteligencia artificial avanzada.

### Timeline General

```
Mes:  0     3     6     9     12    15    18    24    30    36
      │     │     │     │     │     │     │     │     │     │
      ├─────┴─────┤     │     │     │     │     │     │     │
      │  FASE 1   │     │     │     │     │     │     │     │
      │  MVP      │     │     │     │     │     │     │     │
      │ 100 users │     │     │     │     │     │     │     │
      │ $0-200/mo │     │     │     │     │     │     │     │
      └───────────┼─────┴─────┤     │     │     │     │     │
                  │  FASE 2   │     │     │     │     │     │
                  │  Growth   │     │     │     │     │     │
                  │ 5K users  │     │     │     │     │     │
                  │ $200-500  │     │     │     │     │     │
                  └───────────┼─────┴─────┴─────┤     │     │
                              │     FASE 3      │     │     │
                              │     Scale       │     │     │
                              │    50K users    │     │     │
                              │   $500-2000     │     │     │
                              └─────────────────┼─────┴─────┴──
                                                │   FASE 4
                                                │   Enterprise
                                                │  100K+ users
                                                │  $2000+
                                                └──────────────
```

### Objetivos Clave por Fase

| Fase | Usuarios | Brokers | Infra Cost/mes | Revenue Target | Arquitectura |
|------|----------|---------|----------------|----------------|--------------|
| MVP | 100 | 2 | $0-200 | $0-500 | Monolito mejorado |
| Growth | 5,000 | 5 | $200-500 | $5,000-15,000 | Microservicios + Docker |
| Scale | 50,000 | 8 | $500-2,000 | $50,000-150,000 | Kubernetes + event-driven |
| Enterprise | 100,000+ | 10+ | $2,000-10,000 | $500,000+ | Multi-region + white-label |

---

## 2. Visión General por Fases

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    EVOLUCIÓN ARQUITECTÓNICA POR FASE                          │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  FASE 1: MVP                                                                │
│  ┌──────────────────────────────────────┐                                   │
│  │  ┌─────────┐  ┌─────────┐  ┌──────┐ │                                   │
│  │  │ Next.js  │  │ Go API  │  │SQLite│ │  ← Docker Compose                │
│  │  │ Frontend │→ │ +Trade  │→ │  DB  │ │  ← 1 servidor                    │
│  │  └─────────┘  └─────────┘  └──────┘ │  ← $0-200/mes                    │
│  └──────────────────────────────────────┘                                   │
│                                                                              │
│  FASE 2: GROWTH                                                             │
│  ┌──────────────────────────────────────────────────────────┐               │
│  │  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │               │
│  │  │ Next.js  │  │ Trading  │  │ AI Core  │  │PostgreSQL│ │               │
│  │  │ Frontend │→ │ Core (Go)│→ │(Python)  │→ │Timescale │ │  ← Docker    │
│  │  └─────────┘  └──────────┘  └──────────┘  └──────────┘ │  ← 2-3 srv   │
│  │  ┌─────────┐  ┌──────────┐  ┌──────────┐               │  ← $200-500  │
│  │  │  NATS   │  │  Redis   │  │ Ollama   │               │               │
│  │  │  (msg)  │  │ (cache)  │  │  (AI)    │               │               │
│  │  └─────────┘  └──────────┘  └──────────┘               │               │
│  └──────────────────────────────────────────────────────────┘               │
│                                                                              │
│  FASE 3: SCALE                                                              │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐       │       │
│  │  │API GW  │ │Trading │ │AI Core │ │Workers │ │Analytics│       │       │
│  │  │(Traefik│ │Core ×3 │ │(GPU)   │ │(Go)    │ │(Python) │       │       │
│  │  └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └───┬─────┘       │       │
│  │      └──────────┼──────────┼──────────┼──────────┘               │       │
│  │           ┌─────▼──────────▼──────────▼─────┐                   │       │
│  │           │     Kubernetes Cluster            │  ← 5-10 nodes   │       │
│  │           └─────────────┬────────────────────┘  ← $500-2000     │       │
│  │           ┌─────────────▼────────────────────┐                   │       │
│  │           │  PostgreSQL (3 replicas)          │                   │       │
│  │           │  Redis Cluster (6 nodes)          │                   │       │
│  │           │  Kafka/NATS (3 brokers)           │                   │       │
│  │           └──────────────────────────────────┘                   │       │
│  └──────────────────────────────────────────────────────────────────┘       │
│                                                                              │
│  FASE 4: ENTERPRISE                                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  ┌──────────────┐  ┌──────────────┐                                 │   │
│  │  │ Region US-East│  │ Region EU-West│  ← Multi-region               │   │
│  │  │ (Primary)     │  │ (Replica)     │                               │   │
│  │  │               │  │               │                                │   │
│  │  │ K8s Cluster   │  │ K8s Cluster   │  ← 20-50 nodes               │   │
│  │  │ PG Primary    │──→ PG Replica   │  ← Global CDN (Cloudflare)    │   │
│  │  │ Redis Primary │──→ Redis Replica│  ← White-label support        │   │
│  │  │ NATS Cluster  │←→ NATS Cluster │  ← $2,000-10,000/mes          │   │
│  │  └──────────────┘  └──────────────┘                                │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Fase 1: MVP (0-3 Meses)

### 3.1 Objetivo

Lanzar una versión funcional de la plataforma con las capacidades mínimas para
 validar el producto con los primeros 100 usuarios beta.

### 3.2 Deliverables

| # | Deliverable | Semana | Estado |
|---|------------|--------|--------|
| 1.1 | Arquitectura base y setup del proyecto | 1-2 | Pendiente |
| 1.2 | Trading Core en Go (órdenes MT5 + cTrader) | 2-6 | Pendiente |
| 1.3 | API REST (Go + Chi/Gin) | 3-5 | Pendiente |
| 1.4 | Next.js Dashboard (Panel Ejecutivo básico) | 3-6 | Pendiente |
| 1.5 | SQLite → PostgreSQL migration script | 4 | Pendiente |
| 1.6 | Autenticación JWT + Refresh tokens | 4-5 | Pendiente |
| 1.7 | Trading Panel (chart + positions + orders) | 5-8 | Pendiente |
| 1.8 | WebSocket market data (MT5 feed) | 6-7 | Pendiente |
| 1.9 | Sistema de estrategias básico (configuración manual) | 6-9 | Pendiente |
| 1.10 | Copy Trading v1 (1 cuenta → N cuentas) | 7-10 | Pendiente |
| 1.11 | Sistema de alertas básico (email + Telegram) | 8-9 | Pendiente |
| 1.12 | Admin Panel básico (usuarios + sistema) | 9-11 | Pendiente |
| 1.13 | Testing (unit + integration, 60% coverage) | 10-12 | Pendiente |
| 1.14 | Deploy en VPS (Docker Compose) | 11-12 | Pendiente |

### 3.3 Stack Tecnológico — Fase 1

| Componente | Tecnología | Justificación |
|------------|-----------|---------------|
| Frontend | Next.js 14 + shadcn/ui | Rápido de desarrollar, SSR |
| API | Go + Chi router | Performance, tipado fuerte |
| Database | PostgreSQL 16 | Base sólida para crecer |
| Cache | Redis 7 | Sessions, cache de datos |
| Mensajería | NATS (standalone) | Simple, suficiente para MVP |
| Brokers | MT5 + cTrader | Los 2 más solicitados |
| Deploy | Docker Compose | Simple, 1 solo servidor |
| Monitoring | Prometheus + Grafana | Básico pero funcional |
| AI | No incluido | Fase 2 |

### 3.4 Infraestructura — Fase 1

```
┌──────────────────────────────────────────────────┐
│         INFRAESTRUCTURA MVP — FASE 1              │
├──────────────────────────────────────────────────┤
│                                                  │
│  1× VPS (Hetzner / DigitalOcean)                 │
│  • CPU: 4 cores                                  │
│  • RAM: 16 GB                                    │
│  • Storage: 200 GB NVMe                          │
│  • Bandwidth: 20 TB                              │
│  • Costo: ~$30-50/mes                           │
│                                                  │
│  Docker Compose services:                        │
│  • nextjs-frontend     (512 MB RAM)              │
│  • go-api              (512 MB RAM)              │
│  • go-trading-core     (512 MB RAM)              │
│  • postgresql          (2 GB RAM)                │
│  • redis               (512 MB RAM)              │
│  • nats                (256 MB RAM)              │
│  • prometheus          (256 MB RAM)              │
│  • grafana             (256 MB RAM)              │
│  • traefik             (128 MB RAM)              │
│                                                  │
│  Total: ~5 GB RAM (de 16 GB disponibles)         │
│  Headroom para crecimiento: 11 GB                │
│                                                  │
│  Dominio: tnsvt.com                              │
│  SSL: Let's Encrypt (automático via Traefik)     │
│  Backup: Daily pg_dump → S3 ($5/mes)            │
│                                                  │
│  Costo total estimado: $40-80/mes               │
│  (VPS + dominio + backup S3)                     │
│                                                  │
└──────────────────────────────────────────────────┘
```

### 3.5 Milestones

| Milestone | Fecha Objetivo | Criterio de Aceptación |
|-----------|---------------|----------------------|
| **M1: Core Funcional** | Semana 4 | Trading Core ejecuta órdenes en MT5 demo |
| **M2: API Ready** | Semana 6 | API completa con auth, CRUD, WebSocket |
| **M3: UI Funcional** | Semana 8 | Dashboard + Trading panel usable |
| **M4: Integration** | Semana 10 | End-to-end: señal → orden → resultado |
| **M5: Beta Launch** | Semana 12 | Deploy en VPS, 10 usuarios beta |

### 3.6 Go/No-Go Criteria para Fase 2

| Criterio | Requisito Mínimo | Ideal |
|----------|-----------------|-------|
| Usuarios activos beta | ≥ 10 | ≥ 50 |
| Trades ejecutados | ≥ 100 | ≥ 1,000 |
| Feedback positivo | ≥ 70% | ≥ 85% |
| Bugs críticos abiertos | 0 | 0 |
| Uptime del sistema | ≥ 99% | ≥ 99.5% |
| Revenue (piloto) | ≥ $0 | ≥ $500/mes |

### 3.7 Presupuesto — Fase 1

| Concepto | Costo Mensual | Costo Total (3 meses) |
|----------|--------------|----------------------|
| VPS (Hetzner AX42) | $45 | $135 |
| Dominio + DNS | $1 | $3 |
| Backup S3 | $5 | $15 |
| Herramientas (GitHub, Vercel) | $0 | $0 |
| Desarrollo (1 full-stack dev) | $3,000 | $9,000 |
| **Total** | **$3,051** | **$9,153** |

---

## 4. Fase 2: Growth (3-9 Meses)

### 4.1 Objetivo

Escalar a 5,000 usuarios con modelo SaaS funcional, AI Core v1, 5 brokers
y sistema de billing automatizado.

### 4.2 Deliverables

| # | Deliverable | Mes | Estado |
|---|------------|-----|--------|
| 2.1 | Multi-tenant architecture (RLS en PostgreSQL) | 3-4 | Pendiente |
| 2.2 | AI Core v1: Regime Detection + Signal Scoring | 3-5 | Pendiente |
| 2.3 | Broker integrations: Binance + Bybit + IBKR | 4-6 | Pendiente |
| 2.4 | Copy Trading v2 (configurable por usuario) | 4-5 | Pendiente |
| 2.5 | Billing system (Stripe integration) | 5-6 | Pendiente |
| 2.6 | Planes: Free, Pro ($49/mes), Enterprise ($199/mes) | 5-6 | Pendiente |
| 2.7 | Overtrading Detection | 5-6 | Pendiente |
| 2.8 | RAG Engine v1 (estrategias docs) | 6-7 | Pendiente |
| 2.9 | LLM Agent v1 (market summaries) | 6-8 | Pendiente |
| 2.10 | Anomaly Detector v1 | 6-7 | Pendiente |
| 2.11 | Admin Panel completo | 6-7 | Pendiente |
| 2.12 | Tauri Desktop App v1 | 7-9 | Pendiente |
| 2.13 | Sistema de notificaciones avanzado | 7-8 | Pendiente |
| 2.14 | Testing (80% coverage, E2E tests) | 8-9 | Pendiente |
| 2.15 | Performance optimization (< 50ms API p99) | 8-9 | Pendiente |
| 2.16 | SOC2 Type 1 preparation | 7-9 | Pendiente |

### 4.3 Stack Tecnológico — Fase 2

| Componente | Cambio vs Fase 1 | Justificación |
|------------|------------------|---------------|
| Database | PostgreSQL + TimescaleDB ext | Time-series para market data |
| Mensajería | NATS JetStream | Persistencia de eventos |
| AI | Python FastAPI + Ollama | AI Core como servicio separado |
| Brokers | + Binance, Bybit, IBKR | Cobertura de mercados |
| Desktop | Tauri v2 | App de escritorio nativa |
| Billing | Stripe | Estándar de la industria |
| Deploy | Docker Compose → ECS/EasyDeploy | Sin K8s todavía |

### 4.4 Infraestructura — Fase 2

```
┌──────────────────────────────────────────────────────────────┐
│         INFRAESTRUCTURA GROWTH — FASE 2                      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Servidor 1: Application Server (Hetzner AX102)             │
│  • CPU: 16 cores (AMD Ryzen)                                │
│  • RAM: 64 GB                                               │
│  • Storage: 1 TB NVMe                                       │
│  • Costo: ~$80/mes                                         │
│                                                              │
│  Servidor 2: Database Server (Hetzner AX102)                │
│  • CPU: 16 cores                                            │
│  • RAM: 64 GB                                               │
│  • Storage: 2 TB NVMe (RAID1)                               │
│  • Costo: ~$80/mes                                         │
│                                                              │
│  Servidor 3: AI Server (GPU) (Hetzner GPU)                  │
│  • CPU: 8 cores                                             │
│  • RAM: 32 GB                                               │
│  • GPU: NVIDIA RTX 4090 (24GB)                              │
│  • Storage: 1 TB NVMe                                       │
│  • Costo: ~$150/mes                                        │
│                                                              │
│  CDN: Cloudflare Free → Pro ($20/mes cuando sea necesario)  │
│  DNS: Cloudflare                                            │
│  Backup: pg_basebackup → S3 ($15/mes)                       │
│  Monitoring: Grafana Cloud Free tier                         │
│                                                              │
│  Docker Compose (srv1+srv2):                                │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Srv1: nginx, nextjs, go-api, trading-core,          │    │
│  │       nats, redis, prometheus, grafana               │    │
│  │ Srv2: postgresql-timescaledb, redis-replica          │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  Docker (srv3):                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Srv3: ollama, ai-core-python, rag-engine            │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  Costo total estimado: $350-500/mes                         │
│  (3 servidores + CDN + backup + dominio)                    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 4.5 Milestones

| Milestone | Fecha Objetivo | Criterio de Aceptación |
|-----------|---------------|----------------------|
| **M1: Multi-Tenant** | Mes 4 | 10 tenants con datos aislados |
| **M2: AI Core v1** | Mes 6 | Regime detection + scoring funcionando |
| **M3: 5 Brokers** | Mes 7 | Trades ejecutables en 5 brokers |
| **M4: Billing Live** | Mes 7 | Primer pago procesado vía Stripe |
| **M5: 1000 Users** | Mes 8 | 1,000 usuarios registrados |
| **M6: Desktop App** | Mes 9 | Tauri app distribuida a beta testers |
| **M7: Growth Gate** | Mes 9 | Métricas de Go/No-Go para Fase 3 |

### 4.6 Go/No-Go Criteria para Fase 3

| Criterio | Requisito Mínimo | Ideal |
|----------|-----------------|-------|
| Usuarios activos | ≥ 1,000 | ≥ 3,00 |
| MRR (Monthly Recurring Revenue) | ≥ $5,000 | ≥ $15,000 |
| Churn rate mensual | < 10% | < 5% |
| Uptime | ≥ 99.5% | ≥ 99.9% |
| AI Core accuracy (AUC) | ≥ 0.70 | ≥ 0.80 |
| NPS score | ≥ 30 | ≥ 50 |
| Bugs críticos | 0 por > 48h | 0 por > 1 semana |

### 4.7 Presupuesto — Fase 2

| Concepto | Costo Mensual | Costo Total (6 meses) |
|----------|--------------|----------------------|
| 3 VPS (Hetzner) | $310 | $1,860 |
| CDN (Cloudflare Pro) | $20 | $120 |
| Backup S3 | $15 | $90 |
| Stripe fees (~2.9%) | Variable | ~$500 |
| Herramientas (GitHub Pro, etc.) | $20 | $120 |
| Desarrollo (2 devs) | $6,000 | $36,000 |
| AI/ML Engineer (part-time) | $2,000 | $12,000 |
| **Total** | **$8,385** | **$50,690** |

---

## 5. Fase 3: Scale (9-18 Meses)

### 5.1 Objetivo

Escalar a 50,000 usuarios con infraestructura Kubernetes, migración a
event-driven architecture completa, AI avanzado, y operaciones multi-región.

### 5.2 Deliverables

| # | Deliverable | Mes | Estado |
|---|------------|-----|--------|
| 3.1 | Kubernetes cluster (EKS/GKE) | 9-10 | Pendiente |
| 3.2 | NATS → Kafka migration (event streaming) | 10-12 | Pendiente |
| 3.3 | Database sharding (by tenant) | 10-12 | Pendiente |
| 3.4 | Read replicas PostgreSQL (streaming replication) | 10-11 | Pendiente |
| 3.5 | AI Core v2: Advanced models, walk-forward | 10-14 | Pendiente |
| 3.6 | Parameter Optimizer (Bayesian) | 11-13 | Pendiente |
| 3.7 | Sentiment Analyzer v2 (multi-source) | 11-13 | Pendiente |
| 3.8 | LLM Agent v2 (autonomous analysis) | 12-15 | Pendiente |
| 3.9 | WebSocket scaling (NATS + sticky sessions) | 12-13 | Pendiente |
| 3.10 | Geographic CDN (multi-region) | 13-14 | Pendiente |
| 3.11 | Advanced Copy Trading (multi-account config) | 13-15 | Pendiente |
| 3.12 | Mobile responsive + PWA | 14-16 | Pendiente |
| 3.13 | SOC2 Type 2 certification | 12-16 | Pendiente |
| 3.14 | Load testing (k6, Locust) → 50K concurrent | 15-16 | Pendiente |
| 3.15 | Disaster recovery procedures | 16-17 | Pendiente |
| 3.16 | Advanced analytics dashboard | 16-18 | Pendiente |
| 3.17 | API v3 (GraphQL + REST) | 17-18 | Pendiente |

### 5.3 Stack Tecnológico — Fase 3

| Componente | Cambio vs Fase 2 | Justificación |
|------------|------------------|---------------|
| Orchestration | Docker Compose → Kubernetes | Auto-scaling, self-healing |
| Messaging | NATS → Apache Kafka | Event streaming a escala |
| Database | Single PG → Sharded PG + replicas | Escala de writes/reads |
| CDN | Cloudflare Pro → Enterprise | Multi-region, WAF avanzado |
| Cache | Redis single → Redis Cluster | High availability |
| Monitoring | Grafana → Grafana + Tempo + Loki | Observability completa |
| AI | Ollama single → Multi-GPU pool | Más inference throughput |
| CI/CD | GitHub Actions → ArgoCD + GitHub Actions | GitOps deployment |

### 5.4 Infraestructura — Fase 3

```
┌──────────────────────────────────────────────────────────────────────────────┐
│         INFRAESTRUCTURA SCALE — FASE 3                                       │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    KUBERNETES CLUSTER (EKS)                           │   │
│  │                                                                        │   │
│  │  Node Pools:                                                          │   │
│  │  ┌──────────────────────────────────────────────────────────────┐    │   │
│  │  │ General Pool:                                                │    │   │
│  │  │   3-8× m5.xlarge (4 vCPU, 16 GB RAM)                       │    │   │
│  │  │   Workloads: API, Trading Core, Workers                      │    │   │
│  │  │   Auto-scale: 3-8 nodes (CPU > 70%)                        │    │   │
│  │  │                                                               │    │   │
│  │  │ Database Pool:                                                │    │   │
│  │  │   2× r5.2xlarge (8 vCPU, 64 GB RAM)                         │    │   │
│  │  │   Workloads: PostgreSQL primary + replica                     │    │   │
│  │  │   No auto-scale (stateful)                                   │    │   │
│  │  │                                                               │    │   │
│  │  │ AI Pool:                                                      │    │   │
│  │  │   1-2× p3.2xlarge (8 vCPU, 61 GB RAM, 1× V100 16GB)         │    │   │
│  │  │   Workloads: Ollama, AI Core, ML Training                    │    │   │
│  │  │   Auto-scale: 1-2 nodes (GPU utilization > 80%)             │    │   │
│  │  └──────────────────────────────────────────────────────────────┘    │   │
│  │                                                                        │   │
│  │  Managed Services:                                                     │   │
│  │  • Amazon MSK (Kafka): 3 brokers, m5.large                          │   │
│  │  • Amazon ElastiCache (Redis): 6 nodes, r5.large                     │   │
│  │  • Amazon RDS PostgreSQL: db.r5.2xlarge, Multi-AZ                    │   │
│  │  • Amazon S3: Backups, assets, model artifacts                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    CDN & EDGE                                          │   │
│  │                                                                        │   │
│  │  Cloudflare:                                                          │   │
│  │  • Edge locations: 200+ cities                                       │   │
│  │  • Static assets: cached at edge                                     │   │
│  │  • API caching: selective (GET endpoints)                            │   │
│  │  • DDoS protection: Layer 3/4/7                                     │   │
│  │  • WAF rules: custom + managed                                       │   │
│  │  • Workers: edge compute for auth, rate limiting                    │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  Costo total estimado: $1,200-2,000/mes                                    │
│  (EKS + RDS + ElastiCache + MSK + S3 + Cloudflare)                         │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 5.5 Milestones

| Milestone | Fecha Objetivo | Criterio de Aceptación |
|-----------|---------------|----------------------|
| **M1: K8s Running** | Mes 10 | Todos los servicios en Kubernetes |
| **M2: Kafka Migrated** | Mes 12 | Event streaming completo en Kafka |
| **M3: Sharded DB** | Mes 12 | Tenant sharding funcionando |
| **M4: AI v2** | Mes 15 | Modelos avanzados en producción |
| **M5: 10K Users** | Mes 14 | 10,000 usuarios activos |
| **M6: Load Test** | Mes 16 | Soporta 50K concurrent connections |
| **M7: SOC2** | Mes 16 | SOC2 Type 2 certificado |
| **M8: Scale Gate** | Mes 18 | Go/No-Go para Enterprise |

### 5.6 Go/No-Go Criteria para Fase 4

| Criterio | Requisito Mínimo | Ideal |
|----------|-----------------|-------|
| Usuarios activos | ≥ 20,000 | ≥ 50,000 |
| MRR | ≥ $50,000 | ≥ $150,000 |
| Churn rate mensual | < 5% | < 3% |
| Uptime | ≥ 99.9% | ≥ 99.95% |
| API p99 latency | < 100ms | < 50ms |
| AI Core accuracy | ≥ 0.75 | ≥ 0.85 |
| SOC2 certified | Sí | Sí |
| White-label interest | ≥ 3 empresas | ≥ 10 empresas |

### 5.7 Presupuesto — Fase 3

| Concepto | Costo Mensual | Costo Total (9 meses) |
|----------|--------------|----------------------|
| EKS Cluster | $150 | $1,350 |
| EC2 Instances (auto-scale) | $400-800 | $5,400 |
| RDS PostgreSQL (Multi-AZ) | $300 | $2,700 |
| ElastiCache Redis | $200 | $1,800 |
| Amazon MSK (Kafka) | $250 | $2,250 |
| S3 + Data Transfer | $50 | $450 |
| Cloudflare Pro | $20 | $180 |
| Herramientas (Datadog, etc.) | $100 | $900 |
| Equipo (3 devs + 1 ML eng) | $12,000 | $108,000 |
| **Total** | **$13,470-13,870** | **$123,030** |

---

## 6. Fase 4: Enterprise (18-36 Meses)

### 6.1 Objetivo

Plataforma enterprise completa con 100K+ usuarios, white-label, mobile app,
multi-region, y compliance financiero completo.

### 6.2 Deliverables

| # | Deliverable | Mes | Estado |
|---|------------|-----|--------|
| 4.1 | White-label platform (customizable por cliente) | 18-22 | Pendiente |
| 4.2 | Mobile app (React Native / Expo) | 18-24 | Pendiente |
| 4.3 | Multi-region deployment (US + EU + Asia) | 20-24 | Pendiente |
| 4.4 | Advanced AI: Custom fine-tuned models per tenant | 20-26 | Pendiente |
| 4.5 | Regulatory compliance (MiFID II, SEC, CFTC) | 22-30 | Pendiente |
| 4.6 | Institutional features (OMS, DMA, FIX protocol) | 24-30 | Pendiente |
| 4.7 | Advanced analytics & reporting | 24-28 | Pendiente |
| 4.8 | Marketplace de estrategias | 26-32 | Pendiente |
| 4.9 | Social trading features | 28-34 | Pendiente |
| 4.10 | ISO 27001 certification | 30-36 | Pendiente |
| 4.11 | Enterprise SSO (SAML, OIDC) | 20-22 | Pendiente |
| 4.12 | Advanced audit trail (blockchain-anchored) | 28-34 | Pendiente |
| 4.13 | Dedicated support infrastructure | 30-36 | Pendiente |
| 4.14 | SLA: 99.99% uptime guarantee | 30-36 | Pendiente |

### 6.3 Stack Tecnológico — Fase 4

| Componente | Cambio vs Fase 3 | Justificación |
|------------|------------------|---------------|
| Deployment | Multi-region K8s | Baja latencia global |
| Database | Global PostgreSQL + Citus | Sharding global |
| CDN | Cloudflare Enterprise | WAF + DDoS + SSL |
| Mobile | React Native (Expo) | Cross-platform |
| Compliance | Custom compliance engine | Multi-regulatory |
| SSO | Keycloak / Auth0 | Enterprise auth |
| Monitoring | Datadog Enterprise | Full observability |

### 6.4 Infraestructura — Fase 4

```
┌──────────────────────────────────────────────────────────────────────────────┐
│         INFRAESTRUCTURA ENTERPRISE — FASE 4                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                      │
│  │  US-EAST-1    │  │  EU-WEST-1   │  │  AP-SOUTH-1  │                      │
│  │  (Virginia)   │  │  (Ireland)   │  │  (Mumbai)    │                      │
│  │               │  │              │  │              │                       │
│  │  K8s Primary  │  │  K8s Replica │  │  K8s Replica │                      │
│  │  PG Primary   │─→│  PG Replica  │─→│  PG Replica  │                      │
│  │  Kafka Primary│←→│  Kafka Mirror│←→│  Kafka Mirror│                      │
│  │  Redis Primary│──→│  Redis Replica│──→│  Redis Replica│                    │
│  │  Ollama Pool  │  │  Ollama Pool │  │  Ollama Pool │                      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                      │
│         │                  │                  │                              │
│         └──────────────────┼──────────────────┘                              │
│                            │                                                 │
│                   ┌────────▼────────┐                                        │
│                   │   Cloudflare    │                                        │
│                   │   Global CDN    │                                        │
│                   │   + WAF + DDoS  │                                        │
│                   └────────┬────────┘                                        │
│                            │                                                 │
│                   ┌────────▼────────┐                                        │
│                   │     Users       │                                        │
│                   │   100K+ concurrent│                                      │
│                   └─────────────────┘                                        │
│                                                                              │
│  Costo total estimado: $5,000-10,000/mes                                    │
│  (3-region K8s + managed services + CDN + compliance)                        │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 6.5 Milestones

| Milestone | Fecha Objetivo | Criterio de Aceptación |
|-----------|---------------|----------------------|
| **M1: White-label** | Mes 22 | Primer cliente white-label onboarded |
| **M2: Mobile App** | Mes 24 | App en App Store + Play Store |
| **M3: Multi-Region** | Mes 24 | Tráfico distribuido en 3 regiones |
| **M4: 50K Users** | Mes 24 | 50,000 usuarios activos |
| **M5: Compliance** | Mes 30 | MiFID II compliance verified |
| **M6: 100K Users** | Mes 30 | 100,000 usuarios activos |
| **M7: ISO 27001** | Mes 36 | Certification achieved |

### 6.6 Presupuesto — Fase 4

| Concepto | Costo Mensual | Costo Total (18 meses) |
|----------|--------------|----------------------|
| Multi-region K8s | $1,500 | $27,000 |
| Managed databases | $1,500 | $27,000 |
| Kafka (3 regions) | $500 | $9,000 |
| Cloudflare Enterprise | $200 | $3,600 |
| Compliance tools | $300 | $5,400 |
| Monitoring (Datadog) | $500 | $9,000 |
| Equipo (5-8 people) | $25,000 | $450,000 |
| Legal & compliance | $2,000 | $36,000 |
| **Total** | **$31,500** | **$567,000** |

---

## 7. Ruta de Migración Tecnológica

### 7.1 Migraciones Programadas

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    TECHNOLOGY MIGRATION TIMELINE                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  MIGRACIÓN 1: SQLite → PostgreSQL                                           │
│  ════════════════════════════════                                            │
│  Trigger: Fase 1, Semana 4                                                  │
│  Razón: SQLite no soporta concurrencia writes                               │
│  Riesgo: BAJO (PostgreSQL ya planeado)                                     │
│  Rollback: Mantener SQLite como fallback read-only                          │
│  Duración: 1 semana                                                        │
│  ┌──────────────────────────────────────────────────────────┐              │
│  │ SQLite ──→ pg_dump/restore ──→ pgloader ──→ PostgreSQL   │              │
│  │                                                         │              │
│  │ Steps:                                                   │              │
│  │ 1. Create PostgreSQL schema (migraciones Go)            │              │
│  │ 2. Export data from SQLite                               │              │
│  │ 3. Transform data types (SQLite → PG)                   │              │
│  │ 4. Import into PostgreSQL                                │              │
│  │ 5. Update connection strings in Go API                  │              │
│  │ 6. Run integration tests                                │              │
│  │ 7. Deploy with feature flag: USE_PG=true               │              │
│  └──────────────────────────────────────────────────────────┘              │
│                                                                              │
│  MIGRACIÓN 2: Docker Compose → Kubernetes                                  │
│  ═════════════════════════════════════════                                  │
│  Trigger: Fase 3, Mes 9-10                                                  │
│  Razón: Auto-scaling, self-healing, rolling updates                         │
│  Riesgo: MEDIO (complejidad operacional aumenta)                           │
│  Rollback: Mantener Docker Compose como hot standby 1 mes                   │
│  Duración: 4-6 semanas                                                     │
│  ┌──────────────────────────────────────────────────────────┐              │
│  │ Phases:                                                  │              │
│  │ 1. Containerizar todos los servicios (ya hecho)         │              │
│  │ 2. Helm charts para cada servicio                       │              │
│  │ 3. Deploy PostgreSQL/ElastiCache/Kafka managed          │              │
│  │ 4. Migrate stateful workloads (DB, Redis)              │              │
│  │ 5. Migrate stateless workloads (API, workers)          │              │
│  │ 6. Configurar HPA (Horizontal Pod Autoscaler)          │              │
│  │ 7. Setup ArgoCD para GitOps                             │              │
│  │ 8. Parallel run 2 semanas                               │              │
│  │ 9. Cut over DNS                                         │              │
│  │ 10. Decommission old infrastructure (después de 1 mes)  │              │
│  └──────────────────────────────────────────────────────────┘              │
│                                                                              │
│  MIGRACIÓN 3: NATS → Kafka                                                │
│  ════════════════════════════                                               │
│  Trigger: Fase 3, Mes 10-12                                                 │
│  Razón: Event streaming, replay, analytics, escala                          │
│  Riesgo: ALTO (múltiples servicios dependen de NATS)                       │
│  Rollback: Dual-write NATS+Kafka por 1 mes, cortar NATS después           │
│  Duración: 6-8 semanas                                                     │
│  ┌──────────────────────────────────────────────────────────┐              │
│  │ Phases:                                                  │              │
│  │ 1. Deploy Kafka cluster (MSK)                           │              │
│  │ 2. Create Kafka topics (mirror NATS subjects)           │              │
│  │ 3. Dual-write: NATS + Kafka simultaneously              │              │
│  │ 4. Migrate consumers one-by-one (feature flags)         │              │
│  │ 5. Validate data consistency (shadow mode)              │              │
│  │ 6. Cut over consumers to Kafka                           │              │
│  │ 7. Stop NATS writes                                     │              │
│  │ 8. Decommission NATS (después de 2 semanas)            │              │
│  │                                                          │              │
│  │ Migration order:                                         │              │
│  │ market.tick.* → signals → alerts → trades → audit       │              │
│  └──────────────────────────────────────────────────────────┘              │
│                                                                              │
│  MIGRACIÓN 4: Single Region → Multi-Region                                 │
│  ═══════════════════════════════════════════                                │
│  Trigger: Fase 4, Mes 20-24                                                 │
│  Razón: Baja latencia global, disaster recovery                            │
│  Riesgo: ALTO (data consistency, conflict resolution)                       │
│  Rollback: Route all traffic to primary region                              │
│  Duración: 8-12 semanas                                                    │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Criterios para Cada Migración

| Criterio | Requisito antes de migrar |
|----------|--------------------------|
| **Tests** | 80%+ coverage en el servicio afectado |
| **Monitoring** | Dashboard de métricas del servicio activo |
| **Runbook** | Documento de migración y rollback escrito |
| **Team** | Al menos 2 personas familiarizadas con la tecnología target |
| **Data Backup** | Backup completo antes de iniciar migración |
| **Feature Flag** | Capacidad de toggle entre old/new sistema |
| **Load Test** | Prueba de carga con 2× el tráfico actual |
| **Window** | Migración programada en horario de bajo tráfico |

---

## 8. Hitos de Riesgo y Criterios Go/No-Go

### 8.1 Tabla de Decisiones por Fase

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    GO / NO-GO DECISION MATRIX                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  FASE 1 → FASE 2 (Mes 3)                                                   │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  GO si:                                                            │     │
│  │  ✅ ≥ 10 usuarios beta activos                                    │     │
│  │  ✅ Sistema estable (uptime ≥ 99%)                                │     │
│  │  ✅ Feedback ≥ 70% positivo                                       │     │
│  │  ✅ 0 bugs críticos abiertos                                      │     │
│  │  ✅ ≥ $0 revenue (piloto)                                         │     │
│  │                                                                    │     │
│  │  NO-GO si:                                                         │     │
│  │  ❌ < 5 usuarios beta                                             │     │
│  │  ❌ Sistema inestable (crashes frecuentes)                        │     │
│  │  ❌ Feedback < 50% positivo                                       │     │
│  │  ❌ > 3 bugs críticos abiertos                                    │     │
│  │                                                                    │     │
│  │  PIVOT si:                                                         │     │
│  │  🔄 Feedback sugiere cambio de direction                          │     │
│  │  🔄 Mercado responde diferente al esperado                        │     │
│  │  🔄 Competidor lanza feature similar                              │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  FASE 2 → FASE 3 (Mes 9)                                                   │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  GO si:                                                            │     │
│  │  ✅ ≥ 1,000 usuarios activos                                      │     │
│  │  ✅ MRR ≥ $5,000                                                  │     │
│  │  ✅ Churn < 10% mensual                                           │     │
│  │  ✅ Uptime ≥ 99.5%                                                │     │
│  │  ✅ AI Core demostrando valor (señales rentables)                 │     │
│  │                                                                    │     │
│  │  NO-GO si:                                                         │     │
│  │  ❌ < 500 usuarios activos                                        │     │
│  │  ❌ MRR < $2,000                                                  │     │
│  │  ❌ Churn > 15% mensual                                           │     │
│  │  ❌ AI Core sin valor demostrado                                  │     │
│  │                                                                    │     │
│  │  ACTION: Stay in Phase 2 + optimize                               │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  FASE 3 → FASE 4 (Mes 18)                                                  │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  GO si:                                                            │     │
│  │  ✅ ≥ 20,000 usuarios activos                                     │     │
│  │  ✅ MRR ≥ $50,000                                                 │     │
│  │  ✅ White-label interest ≥ 3 empresas                             │     │
│  │  ✅ SOC2 Type 2 achieved                                          │     │
│  │  ✅ Load test passed: 50K concurrent                              │     │
│  │                                                                    │     │
│  │  NO-GO si:                                                         │     │
│  │  ❌ < 10,000 usuarios activos                                     │     │
│  │  ❌ MRR < $20,000                                                 │     │
│  │  ❌ No white-label demand                                         │     │
│  │  ❌ Performance issues unresolved                                  │     │
│  │                                                                    │     │
│  │  ACTION: Stay in Phase 3 + focus on retention                     │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Risk Milestones (Señales de Alarma)

| Señal | Fase | Acción Inmediata |
|-------|------|------------------|
| Revenue < 50% del target a los 3 meses | Cualquiera | Revisar pricing, features, marketing |
| Churn > 20% mensual | 2+ | User research intensivo, fix critical issues |
| Uptime < 99% por 1 semana | 2+ | Incident review, infra upgrade |
| Competidor con 10× usuarios | Cualquiera | Diferenciación agresiva, pivot si necesario |
| Costos > 2× presupuesto | Cualquiera | Cost optimization sprint |
| Key developer se va | Cualquiera | Knowledge transfer, hiring urgente |
| Breach de seguridad | Cualquiera | Incident response, pause features, fix |

---

## 9. Modelo de Costos por Fase

### 9.1 Resumen de Costos

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    COST MODEL — ALL PHASES                                     │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Costo Acumulado por Fase:                                                   │
│                                                                              │
│  $600K ┤                                                         ╱          │
│        │                                                       ╱            │
│  $500K ┤                                                     ╱              │
│        │                                                   ╱                │
│  $400K ┤                                                 ╱                  │
│        │                                               ╱                    │
│  $300K ┤                                             ╱                      │
│        │                                           ╱                        │
│  $200K ┤                                     ╱───╱                          │
│        │                                 ╱──╱                               │
│  $100K ┤                           ╱───╱                                    │
│        │                     ╱───╱                                          │
│   $50K ┤               ╱───╱                                                │
│        │         ╱───╱                                                      │
│    $0K ┤───╱                                                                │
│        └──────┬──────┬──────┬──────┬──────┬──────┬──────┬──────           │
│               3      6      9     12     15     18     24     36           │
│                                                                              │
│  Fase 1 (0-3m):     $9,153        ▓░░░░░░░░░░░░░░░░░░░░░░░░               │
│  Fase 2 (3-9m):    $50,690        ▓▓▓▓░░░░░░░░░░░░░░░░░░░░░               │
│  Fase 3 (9-18m):  $123,030        ▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░               │
│  Fase 4 (18-36m): $567,000        ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓               │
│                                                                              │
│  TOTAL 36 meses:   $749,873                                                 │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 9.2 Break-Even Analysis

| Métrica | Valor |
|---------|-------|
| Inversión total (36 meses) | $749,873 |
| Revenue mensual needed (break-even mes 18) | ~$50,000 MRR |
| Usuarios needed (break-even, ARPU $50/mes) | ~1,000 usuarios Pro |
| Payback period | ~24 meses |
| ROI (año 3, proyectado) | 200-400% |

### 9.3 Unit Economics Target

| Métrica | Fase 2 | Fase 3 | Fase 4 |
|---------|--------|--------|--------|
| ARPU (Monthly) | $50 | $60 | $75 |
| CAC (Customer Acquisition Cost) | $100 | $80 | $60 |
| LTV (Lifetime Value) | $600 | $900 | $1,350 |
| LTV/CAC Ratio | 6.0 | 11.3 | 22.5 |
| Gross Margin | 70% | 75% | 80% |
| Payback Period | 2 months | 1.3 months | 0.8 months |

---

## 10. Dependencias Críticas

### 10.1 Mapa de Dependencias

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    DEPENDENCY MAP — CRITICAL PATH                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  FASE 1:                                                                     │
│  ┌───────┐    ┌──────────┐    ┌─────────┐    ┌──────────┐                  │
│  │ Setup │───→│ Trading  │───→│  API    │───→│ Frontend │                  │
│  │ Proj. │    │ Core (Go)│    │  (Go)   │    │ (Next.js)│                  │
│  └───────┘    └──────────┘    └─────────┘    └──────────┘                  │
│                   │                │               │                        │
│                   ▼                ▼               ▼                        │
│              ┌─────────┐    ┌──────────┐    ┌──────────┐                   │
│              │  MT5    │    │ Auth +   │    │ WebSocket│                   │
│              │  cTrader│    │ JWT      │    │ Market   │                   │
│              └─────────┘    └──────────┘    └──────────┘                   │
│                                                                              │
│  FASE 2:                                                                     │
│  ┌───────────┐    ┌───────────┐    ┌──────────────┐                        │
│  │ Multi-    │───→│ AI Core   │───→│  LLM Agent   │                        │
│  │ Tenant    │    │ v1        │    │  (Ollama)    │                        │
│  └───────────┘    └───────────┘    └──────────────┘                        │
│       │                                                         │           │
│       ▼                                                         ▼           │
│  ┌───────────┐                                          ┌──────────────┐   │
│  │ Billing   │                                          │ Desktop App  │   │
│  │ (Stripe)  │                                          │ (Tauri)      │   │
│  └───────────┘                                          └──────────────┘   │
│                                                                              │
│  FASE 3:                                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐             │
│  │   K8s    │───→│  Kafka   │───→│ DB Shard │───→│ Multi-   │             │
│  │ Cluster  │    │ Migration│    │ + Replicas│    │ Region   │             │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘             │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 10.2 Dependencias Externas

| Dependencia | Tipo | Riesgo | Plan Alternativo |
|-------------|------|--------|-----------------|
| Broker MT5 API | API | MEDIO | Mantener cTrader como backup |
| Broker cTrader API | API | BAJO | N/A (primario) |
| Binance API | API | MEDIO | Bybit como alternativa |
| IBKR API | API | ALTO | cTrader como alternativa |
| Stripe | Servicio | BAJO | Paddle como alternativa |
| Vercel | Servicio | BAJO | Self-host Next.js |
| Cloudflare | Servicio | BAJO | AWS CloudFront |
| GitHub | Servicio | BAJO | GitLab self-hosted |
| Ollama | OSS | BAJO | vLLM como alternativa |
| NVIDIA GPUs | Hardware | MEDIO | CPU inference (más lento) |

---

## 11. Métricas de Éxito por Fase

### 11.1 KPIs por Fase

| KPI | Fase 1 | Fase 2 | Fase 3 | Fase 4 |
|-----|--------|--------|--------|--------|
| **Usuarios activos** | 100 | 5,000 | 50,000 | 100,000+ |
| **MRR** | $0-500 | $5K-15K | $50K-150K | $500K+ |
| **Uptime** | 99% | 99.5% | 99.9% | 99.99% |
| **API Latency (p99)** | < 200ms | < 100ms | < 50ms | < 30ms |
| **Churn mensual** | N/A | < 10% | < 5% | < 3% |
| **NPS** | N/A | ≥ 30 | ≥ 50 | ≥ 70 |
| **Brokers soportados** | 2 | 5 | 8 | 10+ |
| **AI Accuracy (AUC)** | N/A | ≥ 0.70 | ≥ 0.75 | ≥ 0.85 |
| **Test Coverage** | 60% | 80% | 85% | 90% |

---

## 12. Equipo Requerido por Fase

### 12.1 Equipo por Fase

| Rol | Fase 1 | Fase 2 | Fase 3 | Fase 4 |
|-----|--------|--------|--------|--------|
| **Full-Stack Developer** | 1 | 1 | 1 | 2 |
| **Backend Developer (Go)** | 0 (covered by FS) | 1 | 1 | 2 |
| **Frontend Developer** | 0 (covered by FS) | 0 (covered by FS) | 1 | 1 |
| **ML/AI Engineer** | 0 | 0.5 (part-time) | 1 | 1 |
| **DevOps/Platform** | 0 (founder) | 0 (founder) | 0.5 | 1 |
| **Product Manager** | 0 (founder) | 0 (founder) | 0.5 | 1 |
| **Designer** | 0 (freelance) | 0 (freelance) | 0.5 | 1 |
| **QA** | 0 | 0 | 0.5 | 1 |
| **Support** | 0 | 0 | 0 | 1 |
| **Total headcount** | 1-2 | 2-3 | 5-6 | 11-13 |
| **Monthly team cost** | $3,000 | $6,000-8,000 | $15,000-20,000 | $30,000-40,000 |

### 12.2 Contrataciones Clave por Fase

| Fase | Contratación Prioritaria | Timing |
|------|-------------------------|--------|
| **Fase 1** | Full-Stack Developer senior | Mes 0 |
| **Fase 2** | Backend Go Developer + ML Engineer (PT) | Mes 3-4 |
| **Fase 3** | Frontend Dev + DevOps + ML Engineer (FT) | Mes 9-10 |
| **Fase 4** | Team expansion: 2 devs + PM + Designer + QA + Support | Mes 18-24 |

---

## Documentos Relacionados

| Documento | Relación |
|-----------|----------|
| [AI-CORE.md](./AI-CORE.md) | Detalles del AI Core por fase |
| [RISKS.md](./RISKS.md) | Riesgos asociados a cada fase |
| [SCALE-100K.md](./SCALE-100K.md) | Estrategia de escalamiento detallada |
| [INFRASTRUCTURE.md](./INFRASTRUCTURE.md) | Infraestructura técnica por fase |
| [UX-DESIGN.md](./UX-DESIGN.md) | Diseño de UI por fase |

---

*Documento generado como parte de la arquitectura de TNSVT V2.*  
*Última revisión: 2026-07-14*
