# SCALE-100K.md — Estrategia de Escalamiento a 100K Usuarios

**Proyecto:** TNSVT V2 — Plataforma SaaS de Trading  
**Versión:** 2.0.0  
**Última Actualización:** 2026-07-14  
**Estado:** Documento de Arquitectura — Fase de Diseño  

---

## Tabla de Contenidos

1. [Resumen Ejecutivo](#1-resumen-ejecutivo)
2. [Arquitectura para 100K Concurrentes](#2-arquitectura-para-100k-concurrentes)
3. [Connection Pooling](#3-connection-pooling)
4. [Estrategia CDN](#4-estrategia-cdn)
5. [Database Sharding](#5-database-sharding)
6. [Read Replicas](#6-read-replicas)
7. [Capas de Caché](#7-capas-de-caché)
8. [Auto-Scaling](#8-auto-scaling)
9. [Load Testing Strategy](#9-load-testing-strategy)
10. [Capacity Planning Model](#10-capacity-planning-model)
11. [Performance Budgets por Endpoint](#11-performance-budgets-por-endpoint)
12. [WebSocket Scaling](#12-websocket-scaling)
13. [Distribución Geográfica](#13-distribución-geográfica)
14. [Costos Estimados a 100K Usuarios](#14-costos-estimados-a-100k-usuarios)
15. [Runbook de Escalamiento](#15-runbook-de-escalamiento)

---

## 1. Resumen Ejecutivo

Este documento detalla la arquitectura, estrategia y costos necesarios para
escalar TNSVT V2 de 5,000 usuarios (Fase 2) a 100,000+ usuarios concurrentes
(Fase 4). El escalamiento se aborda en múltiples capas: compute, almacenamiento,
caché, red, y base de datos.

### Métricas Objetivo a 100K

| Métrica | Target | Medición |
|---------|--------|----------|
| Usuarios concurrentes | 100,000+ | Conexiones simultáneas activas |
| API Latency (p50) | < 20ms | Tiempo de respuesta promedio |
| API Latency (p99) | < 50ms | 99% de requests responden en |
| API Latency (p999) | < 100ms | 99.9% de requests responden en |
| WebSocket Latency | < 10ms | Tick → UI rendering |
| Throughput | 50,000+ req/s | Requests por segundo |
| Uptime | 99.99% | Disponibilidad anual (52 min downtime) |
| RPO | < 5 min | Recovery Point Objective |
| RTO | < 30 min | Recovery Time Objective |
| Error Rate | < 0.01% | Requests con error 5xx |

### Resumen de Arquitectura

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    ARQUITECTURA 100K USERS — VISTA ALTA                       │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                         ┌──────────────────────┐                            │
│                         │   Cloudflare CDN      │                            │
│                         │   (Edge + WAF + DDoS) │                            │
│                         └──────────┬───────────┘                            │
│                                    │                                         │
│                         ┌──────────▼───────────┐                            │
│                         │   Load Balancer       │                            │
│                         │   (AWS ALB / NLB)     │                            │
│                         └──────────┬───────────┘                            │
│                                    │                                         │
│            ┌───────────────────────┼───────────────────────┐                │
│            │                       │                       │                │
│   ┌────────▼────────┐   ┌─────────▼─────────┐   ┌────────▼────────┐       │
│   │  US-EAST-1       │   │  EU-WEST-1        │   │  AP-SOUTH-1     │       │
│   │  (Primary)       │   │  (Replica)        │   │  (Replica)      │       │
│   │                  │   │                   │   │                 │       │
│   │  ┌────────────┐  │   │  ┌────────────┐  │   │  ┌────────────┐ │       │
│   │  │ K8s Cluster │  │   │  │ K8s Cluster │  │   │  │ K8s Cluster │ │       │
│   │  │ 10-20 nodes │  │   │  │ 5-10 nodes  │  │   │  │ 3-5 nodes   │ │       │
│   │  └──────┬─────┘  │   │  └──────┬─────┘  │   │  └──────┬─────┘ │       │
│   │         │        │   │         │        │   │         │        │       │
│   │  ┌──────▼─────┐  │   │  ┌──────▼─────┐  │   │  ┌──────▼─────┐ │       │
│   │  │ PG Primary  │──┼──→│  │ PG Replica  │──┼──→│  │ PG Replica  │ │       │
│   │  │ + Citus     │  │   │  │ (Streaming) │  │   │  │ (Streaming) │ │       │
│   │  └────────────┘  │   │  └────────────┘  │   │  └────────────┘ │       │
│   │  ┌────────────┐  │   │  ┌────────────┐  │   │  ┌────────────┐ │       │
│   │  │ Kafka      │←─┼───┼──│ Kafka      │←─┼───┼──│ Kafka      │ │       │
│   │  │ Cluster    │  │   │  │ MirrorMaker│  │   │  │ MirrorMaker│ │       │
│   │  │ (3 brokers)│  │   │  └────────────┘  │   │  └────────────┘ │       │
│   │  └────────────┘  │   │                   │   │                 │       │
│   │  ┌────────────┐  │   │  ┌────────────┐  │   │  ┌────────────┐ │       │
│   │  │ Redis      │  │   │  │ Redis      │  │   │  │ Redis      │ │       │
│   │  │ Cluster    │  │   │  │ Replica    │  │   │  │ Replica    │ │       │
│   │  │ (6 nodes)  │  │   │  │ (3 nodes)  │  │   │  │ (3 nodes)  │ │       │
│   │  └────────────┘  │   │  └────────────┘  │   │  └────────────┘ │       │
│   │  ┌────────────┐  │   │                   │   │                 │       │
│   │  │ GPU Pool   │  │   │  ┌────────────┐  │   │                 │       │
│   │  │ (AI Core)  │  │   │  │ GPU Pool   │  │   │                 │       │
│   │  │ 2-4× A100  │  │   │  │ 1× A100    │  │   │                 │       │
│   │  └────────────┘  │   │  └────────────┘  │   │                 │       │
│   └──────────────────┘   └───────────────────┘   └─────────────────┘       │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Arquitectura para 100K Concurrentes

### 2.1 Descomposición del Tráfico

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    TRAFFIC BREAKDOWN — 100K CONCURRENT USERS                  │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  100,000 usuarios concurrentes distribuidos:                                 │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                        │ │
│  │  60% en Dashboard (executive + support + admin)                       │ │
│  │  = 60,000 conexiones SSE (polling cada 5-10s)                        │ │
│  │  = 6,000-12,000 requests/s (cada request renueva datos)             │ │
│  │                                                                        │ │
│  │  30% en Trading Panel (trader + developer)                           │ │
│  │  = 30,000 conexiones WebSocket (datos en tiempo real)                │ │
│  │  = 30,000 ticks/s recibidos, 300,000+ mensajes/s emitidos           │ │
│  │                                                                        │ │
│  │  10% en Background (browsing, settings, reports)                     │ │
│  │  = 10,000 usuarios con requests esporádicos                         │ │
│  │  = 500-2,000 requests/s                                              │ │
│  │                                                                        │ │
│  │  TOTAL:                                                                │ │
│  │  • API Requests: ~20,000-50,000 req/s                                │ │
│  │  • WebSocket Messages: ~300,000 msg/s outbound                       │ │
│  │  • SSE Connections: ~60,000 simultaneous                              │ │
│  │  • Database Queries: ~10,000-30,000 queries/s                        │ │
│  │  • Cache Operations: ~50,000-100,000 ops/s                           │ │
│  │  • NATS Messages: ~500,000 msg/s                                     │ │
│  │                                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  Tráfico por Región:                                                        │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                        │ │
│  │  US-East: 45% = 45,000 concurrentes                                   │ │
│  │  EU-West: 35% = 35,000 concurrentes                                   │ │
│  │  AP-South: 20% = 20,000 concurrentes                                  │ │
│  │                                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Stack de Tecnologías a 100K

| Componente | Tecnología | Configuración | Justificación |
|------------|-----------|---------------|---------------|
| **CDN** | Cloudflare Enterprise | 200+ edge locations | DDoS protection, edge caching |
| **Load Balancer** | AWS NLB | Cross-zone, TCP | Low-latency, WebSocket support |
| **API Gateway** | Traefik + Envoy | 50+ pods | Rate limiting, circuit breaking |
| **Compute** | Kubernetes (EKS) | 10-20 general nodes | Auto-scaling, self-healing |
| **Database** | PostgreSQL + Citus | 3 regions, sharded | Horizontal scaling writes |
| **Cache** | Redis Cluster | 6+ nodes per region | High throughput caching |
| **Messaging** | Apache Kafka | 3 brokers, multi-region | Event streaming at scale |
| **AI** | Ollama + GPU Pool | 2-4× NVIDIA A100 | Inference throughput |
| **Object Storage** | AWS S3 | Multi-region | Backups, assets, models |
| **Monitoring** | Datadog / Grafana Cloud | Full stack | Observability a escala |

---

## 3. Connection Pooling

### 3.1 PgBouncer Configuration

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    CONNECTION POOLING ARCHITECTURE                             │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                      DATABASE CONNECTION FLOW                         │   │
│  │                                                                       │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐                │   │
│  │  │ API Pod  │  │ API Pod  │  │ API Pod  │  │ API Pod  │  ... ×50     │   │
│  │  │ (Go)     │  │ (Go)     │  │ (Go)     │  │ (Go)     │              │   │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘              │   │
│  │       │              │              │              │                    │   │
│  │       │   pool_size: 5 per pod     │              │                    │   │
│  │       │              │              │              │                    │   │
│  │       └──────────────┼──────────────┼──────────────┘                   │   │
│  │                      │              │                                   │   │
│  │                      ▼              ▼                                   │   │
│  │              ┌─────────────────────────────────┐                       │   │
│  │              │        PgBouncer (Primary)       │                       │   │
│  │              │                                   │                       │   │
│  │              │  pool_mode: transaction           │                       │   │
│  │              │  max_client_conn: 10,000          │                       │   │
│  │              │  default_pool_size: 200           │                       │   │
│  │              │  min_pool_size: 50                │                       │   │
│  │              │  reserve_pool_size: 50            │                       │   │
│  │              │  reserve_pool_timeout: 3          │                       │   │
│  │              │  server_lifetime: 3600            │                       │   │
│  │              │  server_idle_timeout: 600         │                       │   │
│  │              └──────────────┬────────────────────┘                       │   │
│  │                             │                                           │   │
│  │                             ▼                                           │   │
│  │              ┌─────────────────────────────────┐                       │   │
│  │              │     PostgreSQL Primary            │                       │   │
│  │              │     max_connections: 500          │                       │   │
│  │              └─────────────────────────────────┘                       │   │
│  │                                                                       │   │
│  │  RATIO: 10,000 client connections → 200 server connections            │   │
│  │  REDUCCIÓN: 98% reduction en conexiones directas a PostgreSQL        │   │
│  │                                                                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  PgBouncer Deployment:                                                      │
│  • 2× PgBouncer instances (active-active)                                  │
│  • Health checks cada 5s                                                    │
│  • Auto-failover via Kubernetes service                                     │
│  • Monitoring: connection count, query latency, pool utilization            │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Redis Pool Configuration

```yaml
# Redis connection pool per service
redis_pool:
  trading_core:
    max_connections: 100
    min_idle: 20
    max_idle: 50
    connection_timeout: 5ms
    socket_timeout: 10ms
    retry_on_timeout: true
    health_check: true
    
  api_gateway:
    max_connections: 200
    min_idle: 50
    max_idle: 100
    connection_timeout: 5ms
    socket_timeout: 10ms
    
  ai_core:
    max_connections: 50
    min_idle: 10
    max_idle: 25
    connection_timeout: 5ms
    socket_timeout: 20ms

# Redis Cluster topology
redis_cluster:
  nodes:
    - { host: "redis-1", port: 6379, role: "master" }
    - { host: "redis-2", port: 6379, role: "master" }
    - { host: "redis-3", port: 6379, role: "master" }
    - { host: "redis-4", port: 6379, role: "slave" }   # Replica de redis-1
    - { host: "redis-5", port: 6379, role: "slave" }   # Replica de redis-2
    - { host: "redis-6", port: 6379, role: "slave" }   # Replica de redis-3
  max_memory_per_node: "16gb"
  eviction_policy: "allkeys-lru"
  cluster_timeout: 5000
```

### 3.3 Pool Monitoring

| Métrica | Alerta | Crítico | Acción |
|---------|--------|---------|--------|
| PgBouncer active connections | > 80% of max | > 95% | Scale PgBouncer pods |
| PgBouncer waiting clients | > 0 sustained | > 10 | Increase pool size |
| Redis pool utilization | > 70% | > 90% | Scale Redis cluster |
| Redis connection errors | > 0.01% | > 0.1% | Check network, restart pool |
| Connection latency (avg) | > 5ms | > 20ms | Investigate, optimize queries |

---

## 4. Estrategia CDN

### 4.1 Cloudflare Configuration

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    CDN STRATEGY — CLOUDFLARE ENTERPRISE                       │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    TRAFFIC FLOW                                      │   │
│  │                                                                       │   │
│  │  Usuario → Cloudflare Edge → Origin (AWS)                           │   │
│  │                                                                       │   │
│  │  Cloudflare handles:                                                 │   │
│  │  ✅ DDoS protection (Layer 3/4/7)                                   │   │
│  │  ✅ WAF rules (OWASP Top 10)                                        │   │
│  │  ✅ SSL/TLS termination                                             │   │
│  │  ✅ Static asset caching (CSS, JS, images, fonts)                   │   │
│  │  ✅ API caching (selective GET endpoints)                           │   │
│  │  ✅ Rate limiting (per IP, per user)                                │   │
│  │  ✅ Bot detection and mitigation                                    │   │
│  │  ✅ DNS management                                                  │   │
│  │  ✅ Argo Smart Routing (optimized path to origin)                   │   │
│  │  ✅ Workers (edge compute for auth pre-validation)                  │   │
│  │                                                                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  Caché Rules:                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                                                                       │   │
│  │  Static Assets (Cache-Everything):                                   │   │
│  │  • CSS, JS, images, fonts, favicons                                 │   │
│  │  • TTL: 1 año (fingerprinted filenames)                             │   │
│  │  • Expected hit rate: > 95%                                         │   │
│  │                                                                       │   │
│  │  API Responses (Cache selectively):                                  │   │
│  │  • GET /api/v2/instruments → TTL: 60s                               │   │
│  │  • GET /api/v2/strategies/public → TTL: 300s                        │   │
│  │  • GET /api/v2/market/overview → TTL: 10s                           │   │
│  │  • POST/PUT/DELETE → No cache                                       │   │
│  │  • Expected hit rate: 30-50%                                        │   │
│  │                                                                       │   │
│  │  Never Cache:                                                        │   │
│  │  • /api/v2/portfolio/*                                               │   │
│  │  • /api/v2/positions/*                                               │   │
│  │  • /api/v2/orders/*                                                  │   │
│  │  • /api/v2/sse/*                                                     │   │
│  │  • /ws/*                                                             │   │
│  │                                                                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  Edge Workers (Cloudflare Workers):                                          │
│  • JWT validation before reaching origin                                    │
│  • Rate limiting with sliding window                                        │
│  • Geographic routing based on user region                                  │
│  • A/B testing header injection                                            │
│  • Bot challenge for suspicious traffic                                    │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Cache Hit Rate Targets

| Recurso | Target Hit Rate | Estrategia |
|---------|-----------------|------------|
| Static assets | > 98% | Fingerprinted filenames, 1-year TTL |
| Instrument list | > 90% | 60s TTL, stale-while-revalidate |
| Market overview | > 80% | 10s TTL, edge compute |
| API metadata | > 70% | 5-5 min TTL, varies by endpoint |
| Dynamic data | 0% | No cache (portfolio, positions) |
| **Overall** | **> 85%** | Weighted average |

---

## 5. Database Sharding

### 5.1 Estrategia de Sharding por Tenant

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    DATABASE SHARDING — BY TENANT                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                                                                       │   │
│  │  Shard Key: tenant_id (UUID)                                        │   │
│  │  Shard Method: Hash-based distributed with Citus extension           │   │
│  │                                                                       │   │
│  │  ┌──────────────────────────────────────────────────────────────┐   │   │
│  │  │                                                               │   │   │
│  │  │  hash(tenant_id) % NUM_SHARDS → shard assignment             │   │   │
│  │  │                                                               │   │   │
│  │  │  Shard 0: tenants 0-19,999    (hash 0.00 - 0.25)           │   │   │
│  │  │  Shard 1: tenants 20,000-39,999 (hash 0.25 - 0.50)         │   │   │
│  │  │  Shard 2: tenants 40,000-59,999 (hash 0.50 - 0.75)         │   │   │
│  │  │  Shard 3: tenants 60,000-79,999 (hash 0.75 - 1.00)         │   │   │
│  │  │                                                               │   │   │
│  │  │  Co-location: Todas las tablas de un tenant están en el     │   │   │
│  │  │  mismo shard (referencial integrity preserved)               │   │   │
│  │  │                                                               │   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  │                                                                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  Tablas Shardadas vs No-Shardadas:                                          │
│                                                                              │
│  SHARDadas (por tenant_id):                                                 │
│  ├── users                                                                 │
│  ├── portfolios                                                            │
│  ├── positions                                                             │
│  ├── orders                                                                │
│  ├── trades                                                                │
│  ├── strategies                                                            │
│  ├── ai_decisions                                                          │
│  └── notifications                                                         │
│                                                                              │
│  NO Shardadas (globales):                                                   │
│  ├── broker_configs                                                        │
│  ├── system_settings                                                       │
│  ├── billing_plans                                                         │
│  ├── feature_flags                                                         │
│  └── audit_logs (partitioned by time, not tenant)                         │
│                                                                              │
│  Citus Configuration:                                                       │
│  • Distributed tables: all tenant-scoped tables                            │
│  • Reference tables: small global lookup tables                            │
│  • Co-located tables: related tables on same shard                        │
│  • Distributed queries: transparent cross-shard queries                    │
│  • Rebalancer: online shard rebalancing when adding nodes                  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Shard Sizing

| Métrica | Per Shard | Total (4 shards) |
|---------|-----------|-------------------|
| Tenants | 25,000 | 100,000 |
| Rows (positions) | 50M | 200M |
| Rows (trades) | 200M | 800M |
| Storage | 500 GB | 2 TB |
| QPS (reads) | 5,000 | 20,000 |
| QPS (writes) | 2,000 | 8,000 |
| Connections (via PgBouncer) | 200 | 800 |

### 5.3 Cross-Shard Queries

Para queries que necesitan datos de múltiples shards:

```sql
-- Cross-shard: portfolio summary for admin dashboard
-- Citus handles this automatically with scatter-gather
SELECT 
  tenant_id,
  COUNT(*) as total_positions,
  SUM(pnl) as total_pnl,
  AVG(pnl) as avg_pnl
FROM positions
WHERE status = 'OPEN'
GROUP BY tenant_id
ORDER BY total_pnl DESC
LIMIT 100;

-- Cross-shard with pushdown (Citus optimizes this)
SELECT 
  tenant_id,
  SUM(pnl) as daily_pnl
FROM trades
WHERE trade_date = CURRENT_DATE
GROUP BY tenant_id;
```

---

## 6. Read Replicas

### 6.1 Arquitectura de Réplicas

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    READ REPLICAS — STREAMING REPLICATION                      │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                                                                       │   │
│  │  PRIMARY (US-East-1)                                                 │   │
│  │  ┌──────────────────────────────────────────────────────────┐       │   │
│  │  │ PostgreSQL Primary + Citus                               │       │   │
│  │  │ max_connections: 500                                     │       │   │
│  │  │ Role: READ + WRITE                                       │       │   │
│  │  │ Workload: All writes, cross-shard queries               │       │   │
│  │  │                                                          │       │   │
│  │  │ WAL Sender: streaming to 2 replicas                     │       │   │
│  │  └──────────────────────────┬───────────────────────────────┘       │   │
│  │                             │                                       │   │
│  │              ┌──────────────┼──────────────┐                       │   │
│  │              │              │              │                        │   │
│  │              ▼              ▼              │                        │   │
│  │  REPLICA 1 (EU-West-1)  REPLICA 2         │                        │   │
│  │  ┌──────────────────┐   (same region)     │                        │   │
│  │  │ PG Read Replica  │   ┌──────────────┐  │                        │   │
│  │  │ max_conn: 300    │   │ PG Read      │  │                        │   │
│  │  │ Role: READ ONLY  │   │ Replica      │  │                        │   │
│  │  │ Lag: < 100ms     │   │ max_conn: 200│  │                        │   │
│  │  │ Workload:        │   │ READ ONLY    │  │                        │   │
│  │  │ EU reads, API    │   │ Backup for   │  │                        │   │
│  │  │ queries          │   │ failover     │  │                        │   │
│  │  └──────────────────┘   └──────────────┘  │                        │   │
│  │                                            │                        │   │
│  │  Routing Strategy:                         │                        │   │
│  │  • All writes → Primary                    │                        │   │
│  │  • US reads → Primary                      │                        │   │
│  │  • EU reads → Replica 1                    │                        │   │
│  │  • AP reads → Primary (latency < 200ms)   │                        │   │
│  │  • Background jobs → Replica (any)         │                        │   │
│  │  • Analytics queries → Replica (any)       │                        │   │
│  │                                            │                        │   │
│  └────────────────────────────────────────────┘                        │   │
│                                                                              │
│  Replication Lag Monitoring:                                                │
│  • Alert: lag > 1s (warning)                                               │
│  • Critical: lag > 5s (potential data inconsistency)                        │
│  • Auto-failover: if lag > 30s for 5 minutes                              │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Read/Write Splitting Configuration

```go
// Go application: database routing
type DatabaseRouter struct {
    primary    *sql.DB
    replicas   []*sql.DB
    replicaIdx uint64
}

func (r *DatabaseRouter) Query(query string, args ...interface{}) (*sql.Rows, error) {
    // SELECT queries → round-robin to replicas
    // INSERT/UPDATE/DELETE → primary
    if isReadOnlyQuery(query) {
        replica := r.replicas[atomic.AddUint64(&r.replicaIdx, 1) % uint64(len(r.replicas))]
        return replica.Query(query, args...)
    }
    return r.primary.Query(query, args...)
}

func (r *DatabaseRouter) Exec(query string, args ...interface{}) (sql.Result, error) {
    // All mutations → primary
    return r.primary.Exec(query, args...)
}

// Connection string examples:
// Primary:  "host=pg-primary port=5432 dbname=tnsvt"
// Replica1: "host=pg-replica-eu port=5432 dbname=tnsvt"
// Replica2: "host=pg-replica-backup port=5432 dbname=tnsvt"
```

---

## 7. Capas de Caché

### 7.1 Arquitectura Multi-Nivel

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    MULTI-LEVEL CACHING ARCHITECTURE                           │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                                                                       │   │
│  │  L1: In-Process Cache (por pod)                                     │   │
│  │  ┌──────────────────────────────────────────────────────────┐       │   │
│  │  │  Implementación: sync.Map (Go) / LRUCache               │       │   │
│  │  │  Tamaño: 100 MB por pod                                  │       │   │
│  │  │  TTL: 5-30 segundos (varía por dato)                    │       │   │
│  │  │  Datos: instrument list, user session, feature flags     │       │   │
│  │  │  Hit rate target: 40-60%                                 │       │   │
│  │  │  Invalidation: TTL-based + event-driven                  │       │   │
│  │  │                                                          │       │   │
│  │  │  Ventajas:                                               │       │   │
│  │  │  • Latencia: < 0.001ms (in-memory)                      │       │   │
│  │  │  • Sin network overhead                                 │       │   │
│  │  │                                                          │       │   │
│  │  │  Desventajas:                                            │       │   │
│  │  │  • Per-pod (no compartido)                              │       │   │
│  │  │  • Inconsistencia entre pods (aceptable para stale data)│       │   │
│  │  └──────────────────────────────────────────────────────────┘       │   │
│  │                                                                       │   │
│  │  L2: Redis Cluster (distribuido)                                    │   │
│  │  ┌──────────────────────────────────────────────────────────┐       │   │
│  │  │  Implementación: Redis Cluster (6+ nodos)                │       │   │
│  │  │  Tamaño total: 96 GB (16 GB × 6 nodos)                  │       │   │
│  │  │  TTL: 30 segundos - 1 hora (varía por dato)             │       │   │
│  │  │  Datos: session tokens, cached API responses,            │       │   │
│  │  │         market data, feature store, AI scores            │       │   │
│  │  │  Hit rate target: 85-95%                                 │       │   │
│  │  │  Invalidation: Pub/Sub + TTL                             │       │   │
│  │  │                                                          │       │   │
│  │  │  Ventajas:                                               │       │   │
│  │  │  • Latencia: 0.5-2ms                                    │       │   │
│  │  │  • Compartido entre todos los pods                      │       │   │
│  │  │  • Persistencia (opcional)                               │       │   │
│  │  └──────────────────────────────────────────────────────────┘       │   │
│  │                                                                       │   │
│  │  L3: CDN Edge Cache (global)                                        │   │
│  │  ┌──────────────────────────────────────────────────────────┐       │   │
│  │  │  Implementación: Cloudflare Edge                         │       │   │
│  │  │  Tamaño: Infinito (distributed)                          │       │   │
│  │  │  TTL: 10 segundos - 1 año (varía por recurso)           │       │   │
│  │  │  Datos: static assets, select API responses, DNS        │       │   │
│  │  │  Hit rate target: 85-98% (depende del tipo)             │       │   │
│  │  │  Invalidation: TTL + purge API                           │       │   │
│  │  │                                                          │       │   │
│  │  │  Ventajas:                                               │       │   │
│  │  │  • Latencia: 1-10ms (edge location)                     │       │   │
│  │  │  • Reducción de bandwidth del origin                    │       │   │
│  │  │  • DDoS protection incluida                              │       │   │
│  │  └──────────────────────────────────────────────────────────┘       │   │
│  │                                                                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  Flow de una Request:                                                       │
│                                                                              │
│  Request → Cloudflare (L3)                                                  │
│    │ Hit → Return cached (1-10ms)                                           │
│    │ Miss → Continue                                                        │
│    ▼                                                                        │
│  Load Balancer → API Pod                                                    │
│    │                                                                        │
│    ├── L1 Cache Check (in-process)                                         │
│    │   │ Hit → Return (0.001ms)                                             │
│    │   │ Miss → Continue                                                    │
│    │   ▼                                                                    │
│    ├── L2 Cache Check (Redis)                                              │
│    │   │ Hit → Store in L1, Return (1-2ms)                                 │
│    │   │ Miss → Continue                                                    │
│    │   ▼                                                                    │
│    └── Database Query (PostgreSQL)                                         │
│        │ Store in L2, Store in L1, Return (5-20ms)                         │
│                                                                              │
│  Effective Latency Distribution:                                            │
│  • 50% of requests: < 1ms (L1 hit)                                        │
│  • 85% of requests: < 5ms (L1 or L2 hit)                                  │
│  • 95% of requests: < 15ms (L3 + L1/L2)                                   │
│  • 99% of requests: < 50ms (origin query)                                  │
│  • 99.9% of requests: < 100ms (complex queries)                            │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Cache Key Strategy

| Cache Level | Key Pattern | TTL | Eviction |
|-------------|------------|-----|----------|
| L1 | `l1:{type}:{id}` | 5-30s | TTL + LRU |
| L2 | `l2:{tenant}:{type}:{id}` | 30s-1h | TTL + LRU |
| L3 | `l3:{path}:{hash}` | 10s-1y | TTL |

### 7.3 Cache Invalidation Strategy

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    CACHE INVALIDATION FLOW                                    │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Event: Position updated (trade executed)                                   │
│       │                                                                      │
│       ▼                                                                      │
│  ┌──────────────────────────────────────────────────────────┐               │
│  │ Trading Core publishes NATS event:                       │               │
│  │ topic: "cache.invalidate.portfolio.{tenant_id}"         │               │
│  │ payload: { tenant_id, position_id, timestamp }          │               │
│  └──────────────────────────┬───────────────────────────────┘               │
│                             │                                                │
│                             ▼                                                │
│  ┌──────────────────────────────────────────────────────────┐               │
│  │ Cache Invalidation Service (per pod):                     │               │
│  │                                                           │               │
│  │ 1. Receive NATS event                                     │               │
│  │ 2. Delete L1 cache keys:                                 │               │
│  │    l1:positions:{tenant_id}                               │               │
│  │    l1:portfolio:{tenant_id}                               │               │
│  │ 3. Delete L2 (Redis) keys:                               │               │
│  │    l2:{tenant_id}:positions:* (pattern delete)           │               │
│  │    l2:{tenant_id}:portfolio:summary                       │               │
│  │ 4. Optionally purge L3 (Cloudflare) for public endpoints │               │
│  └──────────────────────────────────────────────────────────┘               │
│                                                                              │
│  Latencia de invalidación: < 50ms end-to-end                               │
│  Ventana de stale data máxima: 30 segundos                                  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Auto-Scaling

### 8.1 HPA (Horizontal Pod Autoscaler) Configuration

```yaml
# Kubernetes HPA for API Gateway
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-gateway-hpa
  namespace: tnsvt
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-gateway
  minReplicas: 10
  maxReplicas: 100
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30
      policies:
        - type: Percent
          value: 100
          periodSeconds: 30
        - type: Pods
          value: 10
          periodSeconds: 30
      selectPolicy: Max
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 10
          periodSeconds: 60
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
    - type: Pods
      pods:
        metric:
          name: http_requests_per_second
        target:
          type: AverageValue
          averageValue: "1000"
```

### 8.2 Scaling Policies por Servicio

| Servicio | Mín Pods | Máx Pods | CPU Target | RAM Target | Custom Metric | Scale-Up | Scale-Down |
|----------|----------|----------|------------|------------|---------------|----------|------------|
| API Gateway | 10 | 100 | 70% | 80% | 1000 req/s/pod | 100%/30s | 10%/60s |
| Trading Core | 5 | 50 | 65% | 75% | 500 orders/s/pod | 100%/30s | 10%/120s |
| AI Core | 3 | 20 | 70% | 85% | GPU 80% | 50%/60s | 10%/300s |
| Workers | 5 | 30 | 75% | 80% | Queue depth > 1000 | 200%/30s | 10%/120s |
| SSE Server | 5 | 40 | 60% | 70% | Connections > 5000/pod | 100%/30s | 10%/60s |

### 8.3 Cluster Autoscaler

```yaml
# AWS EKS Cluster Autoscaler
apiVersion: eks.amazonaws.com/v1
kind: NodeGroup
metadata:
  name: general-workers
spec:
  instanceTypes:
    - m5.2xlarge   # 8 vCPU, 32 GB
    - m5a.2xlarge  # 8 vCPU, 32 GB (AMD, cheaper)
    - m6i.2xlarge  # 8 vCPU, 32 GB (newer Intel)
  minSize: 5
  maxSize: 20
  desiredSize: 10
  labels:
    workload: general
  taints: []
  scalingConfig:
    minSize: 5
    maxSize: 20
    desiredSize: 10

---
# GPU Node Group for AI Core
apiVersion: eks.amazonaws.com/v1
kind: NodeGroup
metadata:
  name: gpu-workers
spec:
  instanceTypes:
    - p3.2xlarge    # 8 vCPU, 61 GB, 1× V100
    - p4d.24xlarge  # 96 vCPU, 1152 GB, 8× A100 (para Fase 4)
  minSize: 1
  maxSize: 4
  desiredSize: 2
  labels:
    workload: gpu
  taints:
    - key: nvidia.com/gpu
      value: "true"
      effect: NoSchedule
```

### 8.4 Scaling Triggers Decision Tree

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    SCALING DECISION TREE                                      │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Metric: CPU > 70% sustained for 30 seconds                                 │
│  │                                                                          │
│  ├─── Pod count < max?                                                      │
│  │    ├─── YES → Scale up pods (HPA)                                       │
│  │    └─── NO → Scale up nodes (Cluster Autoscaler)                        │
│  │                                                                          │
│  Metric: Connections > 5000 per SSE pod                                    │
│  │                                                                          │
│  ├─── Pod count < max?                                                      │
│  │    ├─── YES → Scale up SSE pods                                          │
│  │    └─── NO → Scale up nodes + add SSE pods                              │
│  │                                                                          │
│  Metric: Database connections > 80%                                        │
│  │                                                                          │
│  ├─── PgBouncer pool < max?                                                 │
│  │    ├─── YES → Increase PgBouncer pool size                              │
│  │    └─── NO → Add PgBouncer replica + scale DB                           │
│  │                                                                          │
│  Metric: Redis memory > 80%                                                │
│  │                                                                          │
│  ├─── Can evict stale keys?                                                 │
│  │    ├─── YES → Run eviction, monitor                                      │
│  │    └─── NO → Add Redis node to cluster                                  │
│  │                                                                          │
│  Metric: Kafka lag > 100,000 messages                                      │
│  │                                                                          │
│  ├─── Consumer count < max?                                                 │
│  │    ├─── YES → Scale up consumer pods                                     │
│  │    └─── NO → Add Kafka partitions + scale consumers                     │
│  │                                                                          │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Load Testing Strategy

### 9.1 Herramientas

| Herramienta | Uso | Escenario |
|-------------|-----|-----------|
| **k6** | API load testing | HTTP endpoints, WebSockets |
| **Locust** | Distributed load testing | Multi-user scenarios |
| **Grafana k6 Cloud** | Cloud-based load testing | Large-scale (100K users) |
| **pgbench** | Database stress testing | PostgreSQL performance |
| **redis-benchmark** | Cache stress testing | Redis throughput |
| **vegeta** | HTTP load testing | Static rate load testing |

### 9.2 Test Scenarios

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    LOAD TEST SCENARIOS — 100K USERS                          │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  SCENARIO 1: Normal Load (daily peak)                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Duration: 1 hora                                                    │   │
│  │  Users: 100,000 concurrent (ramp up: 10 min)                        │   │
│  │  Distribution: 60% dashboard, 30% trading, 10% background          │   │
│  │                                                                      │   │
│  │  Expected:                                                           │   │
│  │  • API p99 < 50ms                                                   │   │
│  │  • WebSocket latency < 10ms                                         │   │
│  │  • Error rate < 0.01%                                               │   │
│  │  • No pods restarted                                                │   │
│  │  • DB connections < 80%                                              │   │
│  │  • Redis hit rate > 90%                                             │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  SCENARIO 2: Spike Test (flash crash scenario)                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Duration: 30 minutos                                               │   │
│  │  Users: 10K → 100K in 5 min (spike) → sustain → 10K in 5 min      │   │
│  │                                                                      │   │
│  │  Expected:                                                           │   │
│  │  • Auto-scale triggers within 30s                                   │   │
│  │  • Scale-up completes within 2 min                                  │   │
│  │  • Error rate during spike < 0.1%                                   │   │
│  │  • Scale-down completes within 10 min                               │   │
│  │  • No data loss during scaling                                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  SCENARIO 3: Stress Test (beyond capacity)                                  │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Duration: 1 hora                                                    │   │
│  │  Users: Ramp to 200,000 (2× target)                                │   │
│  │                                                                      │   │
│  │  Expected:                                                           │   │
│  │  • Graceful degradation (429 errors, not 500)                       │   │
│  │  • No cascading failures                                            │   │
│  │  • Recovery to normal within 5 min after load drops                 │   │
│  │  • No data corruption                                               │   │
│  │  • Circuit breakers activate correctly                              │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  SCENARIO 4: Endurance Test (soak test)                                     │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Duration: 8 horas (simula un día de trading completo)              │   │
│  │  Users: 50,000-80,000 (variable, simula patrón real)               │   │
│  │                                                                      │   │
│  │  Expected:                                                           │   │
│  │  • No memory leaks (RAM stable ± 5%)                               │   │
│  │  • No connection pool exhaustion                                    │   │
│  │  • No disk space issues                                             │   │
│  │  • No Kafka lag growth                                              │   │
│  │  • Consistent latency profile                                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  SCENARIO 5: WebSocket Scale Test                                          │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Duration: 30 minutos                                               │   │
│  │  Connections: 50,000 WebSocket connections                          │   │
│  │  Message rate: 500,000 messages/s outbound                         │   │
│  │                                                                      │   │
│  │  Expected:                                                           │   │
│  │  • All connections established < 30s                               │   │
│  │  • Message delivery latency < 10ms (p99)                           │   │
│  │  • No dropped messages                                              │   │
│  │  • Sticky sessions working correctly                                │   │
│  │  • Graceful reconnection on pod restart                            │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 9.3 Ejecución Programada

| Test | Frecuencia | Entorno | Responsable |
|------|------------|---------|-------------|
| API Load Test (k6) | Semanal | Staging | DevOps |
| WebSocket Scale Test | Quincenal | Staging | DevOps |
| Full Scenario Test | Mensual | Pre-prod | Engineering Lead |
| Stress Test | Trimestral | Pre-prod | Engineering Lead |
| Endurance Test | Trimestral | Pre-prod | DevOps |
| Production Validation | Post-deployment | Production | DevOps + On-call |

---

## 10. Capacity Planning Model

### 10.1 Modelo de Dimensionamiento

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    CAPACITY PLANNING MODEL                                    │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Inputs:                                                                     │
│  • Target concurrent users: 100,000                                         │
│  • Average requests per user per minute: 5 (dashboard)                      │
│  • Average WebSocket messages per user per second: 1 (trader)               │
│  • Average DB queries per request: 2                                        │
│  • Average cache hit rate: 90%                                              │
│  • Peak to average ratio: 3×                                               │
│                                                                              │
│  Calculations:                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                                                                       │   │
│  │  API Throughput:                                                      │   │
│  │  = 100,000 users × 5 req/min ÷ 60                                  │   │
│  │  = 8,333 req/s (average)                                            │   │
│  │  × 3 (peak) = 25,000 req/s (peak)                                  │   │
│  │                                                                       │   │
│  │  WebSocket Throughput:                                               │   │
│  │  = 30,000 traders × 1 msg/s = 30,000 msg/s (inbound)              │   │
│  │  = 30,000 traders × 10 msg/s = 300,000 msg/s (outbound broadcast) │   │
│  │                                                                       │   │
│  │  Database QPS:                                                       │   │
│  │  = 25,000 req/s × 2 queries × (1 - 0.90 cache)                    │   │
│  │  = 5,000 queries/s (after cache)                                    │   │
│  │  × 3 (peak) = 15,000 queries/s (peak)                              │   │
│  │                                                                       │   │
│  │  Redis Operations:                                                   │   │
│  │  = 25,000 req/s × 3 ops = 75,000 ops/s (avg)                       │   │
│  │  × 3 (peak) = 225,000 ops/s (peak)                                 │   │
│  │                                                                       │   │
│  │  Memory Required:                                                    │   │
│  │  API Pods: 50 pods × 2 GB = 100 GB                                  │   │
│  │  Trading Core: 20 pods × 2 GB = 40 GB                               │   │
│  │  Redis: 6 nodes × 16 GB = 96 GB                                     │   │
│  │  PostgreSQL: Primary 256 GB + Replicas 128 GB × 2 = 512 GB         │   │
│  │  Total RAM: ~748 GB                                                 │   │
│  │                                                                       │   │
│  │  Storage Required:                                                   │   │
│  │  PostgreSQL: 2 TB (data) + 1 TB (WAL) + 2 TB (backups) = 5 TB     │   │
│  │  Kafka: 1 TB (retention 7 días)                                     │   │
│  │  S3: 10 TB (backups, assets, models)                                │   │
│  │  Total Storage: ~16 TB                                              │   │
│  │                                                                       │   │
│  │  Network Bandwidth:                                                  │   │
│  │  API: 25,000 req/s × 5 KB avg = 125 MB/s                          │   │
│  │  WebSocket: 300,000 msg/s × 200 bytes = 60 MB/s                    │   │
│  │  Total: ~185 MB/s (1.5 Gbps)                                       │   │
│  │                                                                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  Resource Summary:                                                          │
│  ┌──────────────────────┬──────────────┬──────────────┐                    │
│  │ Recurso              │ Cantidad     │ Costo/mes    │                    │
│  ├──────────────────────┼──────────────┼──────────────┤                    │
│  │ K8s Nodes (general)  │ 10-20× m5.2xlarge │ $2,400-4,800 │            │
│  │ K8s Nodes (GPU)      │ 2-4× p3.2xlarge   │ $1,200-2,400 │            │
│  │ RDS PostgreSQL       │ db.r5.4xlarge Multi-AZ │ $1,500    │            │
│  │ ElastiCache Redis    │ 6× r5.xlarge       │ $1,200     │            │
│  │ MSK Kafka            │ 3× kafka.m5.large  │ $750       │            │
│  │ S3 Storage           │ 10 TB              │ $230       │            │
│  │ Cloudflare Enterprise│ Unlimited          │ $200       │            │
│  │ Data Transfer        │ ~5 TB/month        │ $400       │            │
│  │ Monitoring (Datadog) │ Full stack         │ $500       │            │
│  ├──────────────────────┼──────────────┼──────────────┤                    │
│  │ TOTAL                │              │ $8,380-11,980│                    │
│  └──────────────────────┴──────────────┴──────────────┘                    │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 11. Performance Budgets por Endpoint

### 11.1 API Endpoints

| Endpoint | Method | p50 Latency | p99 Latency | p999 Latency | Throughput | Cache TTL |
|----------|--------|-------------|-------------|--------------|------------|-----------|
| `/api/v2/auth/login` | POST | 50ms | 100ms | 200ms | 500 req/s | No cache |
| `/api/v2/auth/refresh` | POST | 20ms | 50ms | 100ms | 2,000 req/s | No cache |
| `/api/v2/portfolio` | GET | 10ms | 30ms | 50ms | 5,000 req/s | L2: 5s |
| `/api/v2/positions` | GET | 8ms | 25ms | 40ms | 10,000 req/s | L2: 2s |
| `/api/v2/orders` | POST | 30ms | 80ms | 150ms | 500 req/s | No cache |
| `/api/v2/orders/history` | GET | 15ms | 40ms | 80ms | 2,000 req/s | L2: 10s |
| `/api/v2/signals` | GET | 5ms | 15ms | 30ms | 10,000 req/s | L2: 3s |
| `/api/v2/ai/insights` | GET | 500ms | 2,000ms | 5,000ms | 100 req/s | L2: 60s |
| `/api/v2/market/instruments` | GET | 3ms | 10ms | 20ms | 20,000 req/s | L3: 60s |
| `/api/v2/strategies` | GET | 10ms | 30ms | 50ms | 3,000 req/s | L2: 30s |

### 11.2 Database Query Budgets

| Query Type | Target Latency | Index Required | Partitioning |
|------------|---------------|----------------|--------------|
| Point lookup (by PK) | < 1ms | PK index | No |
| Range query (trades 7d) | < 5ms | Composite index | TimescaleDB |
| Aggregation (P&L daily) | < 20ms | Materialized view | No |
| Full-text search | < 50ms | GIN index | No |
| Cross-shard aggregation | < 100ms | Citus pushdown | Shard key |
| Reporting query (monthly) | < 500ms | Read replica | No |

### 11.3 Latency Budget Breakdown

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    LATENCY BUDGET — GET /api/v2/positions                    │
│                    Target: p99 < 25ms                                         │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                                                                       │   │
│  │  Cloudflare Edge    │ 2ms   │ ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │   │
│  │  Network (TLS)      │ 3ms   │ ██████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │   │
│  │  Load Balancer      │ 1ms   │ ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │   │
│  │  API Middleware      │ 1ms   │ ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │   │
│  │  Auth Validation     │ 2ms   │ ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │   │
│  │  L1 Cache Check      │ 0ms   │ █░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │   │
│  │  L2 Cache (Redis)    │ 1ms   │ ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │   │
│  │  DB Query (hit)      │ 3ms   │ ██████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │   │
│  │  Response Serialize  │ 1ms   │ ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │   │
│  │  Network (response)  │ 2ms   │ ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │   │
│  │                      │       │                                       │   │
│  │  TOTAL               │ 16ms  │ ██████████████████░░░░░░░░░░░░░░░░░░░│   │
│  │  Budget remaining    │ 9ms   │ (headroom for slow queries)          │   │
│  │                                                                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 12. WebSocket Scaling

### 12.1 Arquitectura WebSocket a Escala

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    WEBSOCKET SCALING — NATS + STICKY SESSIONS                │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                                                                       │   │
│  │  Challenge: WebSocket connections are stateful and long-lived       │   │
│  │  Solución: NATS JetStream como backbone + sticky sessions           │   │
│  │                                                                       │   │
│  │  ┌────────────┐                                                      │   │
│  │  │  Cliente    │◄──── WebSocket Connection ────┐                     │   │
│  │  │  (Browser)  │                               │                     │   │
│  │  └────────────┘                               │                     │   │
│  │                                               │                     │   │
│  │  ┌──────────────────────────────────────────┐ │                     │   │
│  │  │  Load Balancer (Sticky Sessions)         │ │                     │   │
│  │  │  Cookie: TNSESID → routes to same pod    │─┘                     │   │
│  │  └────────────────┬─────────────────────────┘                       │   │
│  │                   │                                                  │   │
│  │         ┌─────────┼─────────┬──────────┐                            │   │
│  │         ▼         ▼         ▼          ▼                            │   │
│  │  ┌──────────┐┌──────────┐┌──────────┐┌──────────┐                  │   │
│  │  │ WS Pod 1 ││ WS Pod 2 ││ WS Pod 3 ││ WS Pod N │                  │   │
│  │  │ 10K conn ││ 10K conn ││ 10K conn ││ 10K conn │                  │   │
│  │  └────┬─────┘└────┬─────┘└────┬─────┘└────┬─────┘                  │   │
│  │       │           │           │            │                        │   │
│  │       └───────────┴─────┬─────┴────────────┘                        │   │
│  │                         │                                           │   │
│  │                         ▼                                           │   │
│  │  ┌──────────────────────────────────────────────────────────┐      │   │
│  │  │                  NATS JETSTREAM                           │      │   │
│  │  │                                                           │      │   │
│  │  │  market.tick.EURUSD ──→ All WS Pods subscribe           │      │   │
│  │  │  market.tick.GBPUSD ──→ All WS Pods subscribe           │      │   │
│  │  │  ... (per instrument subjects)                           │      │   │
│  │  │                                                           │      │   │
│  │  │  Each WS Pod:                                            │      │   │
│  │  │  1. Subscribe to all instrument topics                   │      │   │
│  │  │  2. Filter: only forward to connected clients interested │      │   │
│  │  │  3. Fan-out: broadcast to matching WS connections        │      │   │
│  │  │                                                           │      │   │
│  │  └──────────────────────────────────────────────────────────┘      │   │
│  │                                                                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  Key Metrics:                                                               │
│  • Connections per pod: 10,000 (target)                                    │
│  • Messages per pod: 50,000 msg/s outbound                                │
│  • Memory per connection: ~50 KB                                           │
│  • Total memory per pod: ~500 MB                                           │
│  • Reconnection time: < 2 seconds                                          │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 12.2 WebSocket Server Implementation

```go
// Go WebSocket server with connection management
type WSServer struct {
    hub         *Hub
    natsConn    *nats.Conn
    upgrader    websocket.Upgrader
    connPool    sync.Pool
}

type Hub struct {
    clients    map[*Client]bool
    broadcast  chan *Message
    register   chan *Client
    unregister chan *Client
    mu         sync.RWMutex
}

type Client struct {
    hub          *Hub
    conn         *websocket.Conn
    send         chan []byte
    instruments  map[string]bool  // Subscribed instruments
    tenantID     string
    lastActive   time.Time
}

// Per-pod capacity: 10,000 connections
// Memory per connection: ~50 KB (buffers + state)
// Total per pod: ~500 MB
// Pods needed: 100,000 / 10,000 = 10 pods minimum
// With headroom (2×): 20 pods
```

### 12.3 Reconnection Strategy

```
┌──────────────────────────────────────────────────────────────────────┐
│                    WEBSOCKET RECONNECTION FLOW                        │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. Connection lost detected                                         │
│  │                                                                   │
│  2. Client enters reconnection loop:                                │
│  │   Attempt 1: wait 1s  → reconnect                               │
│  │   Attempt 2: wait 2s  → reconnect                               │
│  │   Attempt 3: wait 4s  → reconnect                               │
│  │   Attempt 4: wait 8s  → reconnect                               │
│  │   Attempt 5: wait 16s → reconnect                               │
│  │   Max:       wait 30s → reconnect (cap at 30s)                  │
│  │                                                                   │
│  3. On successful reconnection:                                     │
│  │   • Re-subscribe to all instruments                             │
│  │   • Request missed events (last event ID)                       │
│  │   • Resume state (positions, orders)                            │
│  │                                                                   │
│  4. Fallback: SSE for dashboard users (no real-time need)          │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 13. Distribución Geográfica

### 13.1 Regiones

| Región | Ubicación | Usuarios | Latencia Objetivo | Servicios |
|--------|-----------|----------|-------------------|-----------|
| US-EAST-1 | Virginia, USA | 45,000 (45%) | < 20ms | Full stack (primary) |
| EU-WEST-1 | Irlanda, EU | 35,000 (35%) | < 30ms | Full stack (replica) |
| AP-SOUTH-1 | Mumbai, India | 20,000 (20%) | < 50ms | Read replica + edge |

### 13.2 Estrategia de Routing

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    GEOGRAPHIC ROUTING STRATEGY                                │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                                                                       │   │
│  │  DNS Routing (Cloudflare Geo Steering):                             │   │
│  │  • US users → US-EAST-1 endpoint                                    │   │
│  │  • EU users → EU-WEST-1 endpoint                                    │   │
│  │  • AP users → AP-SOUTH-1 endpoint (if available) or US-EAST-1      │   │
│  │                                                                       │   │
│  │  API Routing:                                                        │   │
│  │  • Writes → Always primary region (US-EAST-1)                       │   │
│  │  • Reads → Nearest region replica                                   │   │
│  │  • AI queries → Nearest GPU pool                                    │   │
│  │                                                                       │   │
│  │  Data Routing:                                                       │   │
│  │  • User data → Shard in primary region                              │   │
│  │  • Replication → Async to other regions (lag < 100ms)              │   │
│  │  • Backups → Cross-region (S3 cross-region replication)            │   │
│  │                                                                       │   │
│  │  WebSocket Routing:                                                  │   │
│  │  • Connect to nearest edge                                          │   │
│  │  • Edge connects to nearest NATS cluster                            │   │
│  │  • NATS fans out across regions if needed                          │   │
│  │                                                                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  Failover Strategy:                                                        │
│  • If region goes down: route traffic to nearest healthy region            │
│  • DNS failover: automatic if health check fails for 2 min                │
│  • Data consistency: eventual consistency during failover (< 1s)          │
│  • Recovery: automatic re-routing when region recovers                     │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 14. Costos Estimados a 100K Usuarios

### 14.1 Desglose Mensual

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    COST BREAKDOWN — 100K CONCURRENT USERS                     │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │ Computo                                                            │     │
│  │ ├── EKS Control Plane                                $73/mes      │     │
│  │ ├── General Nodes (10× m5.2xlarge)                   $2,400/mes   │     │
│  │ ├── GPU Nodes (2× p3.2xlarge)                        $1,200/mes   │     │
│  │ └── Subtotal computo                                 $3,673/mes   │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │ Base de Datos                                                       │     │
│  │ ├── RDS PostgreSQL (db.r5.4xlarge, Multi-AZ)        $1,500/mes   │     │
│  │ ├── RDS Storage (2 TB gp3)                          $200/mes     │     │
│  │ ├── Read Replica (EU)                               $750/mes     │     │
│  │ └── Subtotal DB                                     $2,450/mes   │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │ Cache                                                               │     │
│  │ ├── ElastiCache Redis (6× r5.xlarge)                $1,200/mes   │     │
│  │ └── Subtotal cache                                  $1,200/mes   │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │ Messaging                                                           │     │
│  │ ├── MSK Kafka (3× kafka.m5.large)                   $750/mes     │     │
│  │ └── Subtotal messaging                              $750/mes      │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │ Red y CDN                                                           │     │
│  │ ├── Cloudflare Enterprise                           $200/mes     │     │
│  │ ├── AWS Data Transfer (5 TB)                        $400/mes     │     │
│  │ ├── AWS NLB                                         $50/mes      │     │
│  │ └── Subtotal red                                    $650/mes     │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │ Almacenamiento                                                       │     │
│  │ ├── S3 Storage (10 TB)                              $230/mes     │     │
│  │ ├── S3 Data Transfer                                $50/mes      │     │
│  │ └── Subtotal storage                                $280/mes     │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │ Observabilidad                                                      │     │
│  │ ├── Datadog (Full Stack)                            $500/mes     │     │
│  │ ├── PagerDuty                                      $50/mes       │     │
│  │ └── Subtotal observabilidad                         $550/mes     │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │ TOTAL INFRAESTRUCTURA                                              │     │
│  │                                                                    │     │
│  │ Computo:           $3,673                                          │     │
│  │ Base de Datos:     $2,450                                          │     │
│  │ Cache:             $1,200                                          │     │
│  │ Messaging:           $750                                          │     │
│  │ Red y CDN:           $650                                          │     │
│  │ Almacenamiento:      $280                                          │     │
│  │ Observabilidad:      $550                                          │     │
│  │ ─────────────────────────                                          │     │
│  │ TOTAL:            $9,553/mes                                       │     │
│  │                                                                    │     │
│  │ + 20% headroom:   $11,464/mes                                     │     │
│  │ + Reserved instances (37% savings): $7,224/mes                    │     │
│  │                                                                    │     │
│  │ COSTO OPTIMIZADO: ~$7,224-9,553/mes                               │     │
│  │                                                                    │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  Revenue Needed to Cover Infra:                                             │
│  • At 70% gross margin: $7,224 / 0.30 = $24,080/mes revenue               │
│  • At ARPU $75/mes: $24,080 / $75 = 321 usuarios de pago                  │
│  • With 100K total users: 0.32% conversion to paid                         │
│  • Industry benchmark: 2-5% conversion → highly profitable                 │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 14.2 Costo por Usuario

| Métrica | Valor |
|---------|-------|
| Costo infra total/mes | $9,553 |
| Usuarios totales | 100,000 |
| Costo por usuario/mes | $0.096 |
| Costo por usuario/día | $0.0032 |
| Costo por usuario/año | $1.15 |
| Revenue por usuario (ARPU $75) | $75.00 |
| Gross margin per user | 99.87% |

---

## 15. Runbook de Escalamiento

### 15.1 Manual de Escalamiento

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    SCALING RUNBOOK — QUICK REFERENCE                          │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  SÍNTOMA: API latency p99 > 100ms                                          │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ 1. Verificar Grafana: CPU de pods API > 70%?                        │   │
│  │    → SI: HPA debería auto-escalar. Verificar maxReplicas.          │   │
│  │    → NO: Verificar database queries (pg_stat_statements)           │   │
│  │                                                                      │   │
│  │ 2. Verificar Redis: hit rate < 80%?                                │   │
│  │    → SI: Revisar cache keys, TTLs, invalidation patterns           │   │
│  │    → NO: Verificar network latency                                 │   │
│  │                                                                      │   │
│  │ 3. Verificar DB: connections > 80%?                                │   │
│  │    → SI: Scale PgBouncer pool, add read replica                    │   │
│  │    → NO: Verificar slow queries (pg_stat_statements)               │   │
│  │                                                                      │   │
│  │ 4. Si nada funciona: Scale pods manualmente:                       │   │
│  │    kubectl scale deployment api-gateway --replicas=50 -n tnsvt    │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  SÍNTOMA: WebSocket connections dropping                                    │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ 1. Verificar WS pod memory: > 80%?                                 │   │
│  │    → SI: Scale WS pods                                              │   │
│  │    → NO: Verificar NATS connectivity                                │   │
│  │                                                                      │   │
│  │ 2. Verificar NATS: message lag > 10K?                              │   │
│  │    → SI: Scale NATS consumers                                       │   │
│  │    → NO: Verificar client-side reconnection logic                   │   │
│  │                                                                      │   │
│  │ 3. Manual scale:                                                   │   │
│  │    kubectl scale deployment ws-server --replicas=20 -n tnsvt      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  SÍNTOMA: Database disk > 80%                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ 1. Verificar growth rate: cuánto crece por día?                    │   │
│  │                                                                      │   │
│  │ 2. Si growth normal: Resize storage (online, no downtime):        │   │
│  │    aws rds modify-db-instance --allocated-storage=4000 ...        │   │
│  │                                                                      │   │
│  │ 3. Si growth inusual: Investigar data leak, runaway logging       │   │
│  │                                                                      │   │
│  │ 4. Cleanup:                                                        │   │
│  │    • Drop old partitions (TimescaleDB)                             │   │
│  │    • Vacuum analyze                                                │   │
│  │    • Archive old data to S3                                        │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  SÍNTOMA: Kafka consumer lag growing                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ 1. Verificar consumer pods: running? CPU正常?                       │   │
│  │                                                                      │   │
│  │ 2. Scale consumers:                                                 │   │
│  │    kubectl scale deployment kafka-consumer --replicas=20 -n tnsvt │   │
│  │                                                                      │   │
│  │ 3. If lag still growing: Check processing logic, add partitions    │   │
│  │                                                                      │   │
│  │ 4. Emergency: Increase retention period to prevent data loss       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ESCALAMIENTO PRE-PLANIFICADO (antes de evento predecible):                │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ • High-impact news event (NFP, Fed decision):                      │   │
│  │   - Scale API pods +50%                                            │   │
│  │   - Scale WS pods +50%                                             │   │
│  │   - Pre-warm Redis cache                                           │   │
│  │   - Notify on-call team                                            │   │
│  │                                                                      │   │
│  │ • Marketing campaign / Product launch:                              │   │
│  │   - Scale all stateless services +100%                             │   │
│  │   - Increase CDN cache TTL                                         │   │
│  │   - Pre-provision database connections                             │   │
│  │   - Enable rate limiting for new users                             │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Documentos Relacionados

| Documento | Relación |
|-----------|----------|
| [AI-CORE.md](./AI-CORE.md) | AI Core scaling con GPU pools |
| [INFRASTRUCTURE.md](./INFRASTRUCTURE.md) | Detalles de infraestructura completa |
| [RISKS.md](./RISKS.md) | Riesgos asociados al escalamiento |
| [ROADMAP.md](./ROADMAP.md) | Cuándo se implementa cada capa |
| [UX-DESIGN.md](./UX-DESIGN.md) | Performance budgets de UI |

---

*Documento generado como parte de la arquitectura de TNSVT V2.*  
*Última revisión: 2026-07-14*
