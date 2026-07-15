# TNSVT V2 — Vista General de la Arquitectura

**Versión:** 2.0  
**Fecha:** 14 de Julio de 2026  
**Clasificación:** Confidencial — Uso Interno  
**Estado:** Aprobado por Arquitectura  

---

## Índice

1. [Arquitectura de Alto Nivel](#1-arquitectura-de-alto-nivel)
2. [Capas Clean Architecture](#2-capas-clean-architecture)
3. [Bounded Contexts (DDD)](#3-bounded-contexts-ddd)
4. [Flujo de Dependencias](#4-flujo-de-dependencias)
5. [Service Mesh con NATS JetStream](#5-service-mesh-con-nats-jetstream)
6. [Flujo de Datos General](#6-flujo-de-datos-general)
7. [Mapeo Tecnológico por Capa](#7-mapeo-tecnológico-por-capa)
8. [Estrategia de Despliegue](#8-estrategia-de-despliegue)
9. [Diagrama de Red](#9-diagrama-de-red)

---

## 1. Arquitectura de Alto Nivel

```
+==============================================================================+
|                         TNSVT V2 - ARQUITECTURA ALTO NIVEL                   |
+==============================================================================+
|                                                                              |
|  +------------------------------------------------------------------------+ |
|  |                        CAPA DE CLIENTES                                | |
|  |                                                                        | |
|  |  +----------------+   +----------------+   +-----------------------+   | |
|  |  | Next.js 15     |   | Tauri 2.0      |   | Mobile App (futuro)   |   | |
|  |  | (SPA + SSR)    |   | (Desktop)      |   | React Native          |   | |
|  |  | Puerto: 3000   |   | Puerto: --     |   | Puerto: --            |   | |
|  |  +-------+--------+   +-------+--------+   +-----------+-----------+   | |
|  |          |                     |                       |               | |
|  +----------+---------------------+-----------------------+---------------+ |
|                           |         |                       |                 |
|                           v         v                       v                 |
|  +------------------------------------------------------------------------+ |
|  |                    CAPA EDGE / INGRESS                                  | |
|  |                                                                        | |
|  |  +--------------------------------------------------------------+     | |
|  |  |                    TRAEFIK 3.0                                |     | |
|  |  |  - TLS termination (Let's Encrypt auto)                      |     | |
|  |  |  - Rate limiting (por tenant, por endpoint)                  |     | |
|  |  |  - WAF rules (OWASP CRS)                                     |     | |
|  |  |  - IP whitelisting/blacklisting                               |     | |
|  |  |  - Request forwarding (service discovery via k8s)            |     | |
|  |  |  - Circuit breaker (per-service)                              |     | |
|  |  |  - gRPC-Web support                                          |     | |
|  |  |  Puerto: 80/443                                               |     | |
|  |  +--------------------------------------------------------------+     | |
|  +------------------------------------------------------------------------+ |
|                           |                                                  |
|              +------------+------------+                                    |
|              v            v            v                                    |
|  +------------------------------------------------------------------------+ |
|  |                    CAPA DE MICROSERVICIOS                               | |
|  |                                                                        | |
|  |  +-------------+  +-------------+  +-------------+  +-------------+   | |
|  |  | TRADING     |  | RISK        |  | BROKER      |  | AI/ML       |   | |
|  |  | CONTEXT     |  | CONTEXT     |  | CONTEXT     |  | CONTEXT     |   | |
|  |  |             |  |             |  |             |  |             |   | |
|  |  | - Engine    |  | - Manager   |  | - Gateway   |  | - Scoring   |   | |
|  |  | - Executor  |  | - Limits    |  | - Abstraction| | - Regime    |   | |
|  |  | - Scheduler |  | - Monitor   |  | - MT5       |  | - RAG       |   | |
|  |  | - State     |  | - Circuit   |  | - cTrader   |  | - Anomaly   |   | |
|  |  +------+------+  +------+------+  | - Binance   |  +------+------+   | |
|  |         |               |           | - Bybit     |         |          | |
|  |         |               |           | - IBKR      |         |          | |
|  |         |               |           +------+------+         |          | |
|  |         |               |                  |                |          | |
|  |  +------+------+  +------+------+  +------+------+  +------+--------+ | |
|  |  | MARKET     |  | PLATFORM   |  | NOTIFICATION|  | AUDIT/BILLING | | |
|  |  | DATA       |  | CONTEXT    |  | CONTEXT     |  | CONTEXT       | | |
|  |  |            |  |            |  |             |  |               | | |
|  |  | - Ingestion|  | - Auth     |  | - Dispatcher|  | - Event Store | | |
|  |  | - Aggregator| | - Tenant   |  | - Template  |  | - Projector   | | |
|  |  | - Historic |  | - Billing  |  | - Channel   |  | - Billing     | | |
|  |  | - Feed     |  | - Admin    |  | - Retry     |  | - Compliance  | | |
|  |  +------+-----+  +------+-----+  +------+------+  +------+--------+ | |
|  +------------------------------------------------------------------------+ |
|                           |                                                  |
|              +------------+------------+                                    |
|              v            v            v                                    |
|  +------------------------------------------------------------------------+ |
|  |                    CAPA DE DATOS Y MENSAJERÍA                          | |
|  |                                                                        | |
|  |  +----------------+  +----------------+  +-------------------------+   | |
|  |  | NATS JetStream |  | Redis 7        |  | PostgreSQL 16           |   | |
|  |  | (3 nodos)      |  | (Cluster 6)    |  | + TimescaleDB 2.x       |   | |
|  |  |                |  |                |  |                         |   | |
|  |  | - Event Bus    |  | - Cache L1     |  | - OLTP (transacciones)  |   | |
|  |  | - Commands     |  | - Session      |  | - Time-series (ticks)   |   | |
|  |  | - Events       |  | - Rate Counter |  | - Event Store           |   | |
|  |  | - Dead Letters |  | - Pub/Sub      |  | - Projections           |   | |
|  |  | Puerto: 4222   |  | Puerto: 6379   |  | Puerto: 5432            |   | |
|  |  +----------------+  +----------------+  +-------------------------+   | |
|  +------------------------------------------------------------------------+ |
|                           |                                                  |
|              +------------+------------+                                    |
|              v            v            v                                    |
|  +------------------------------------------------------------------------+ |
|  |                    CAPA DE INFRAESTRUCTURA                             | |
|  |                                                                        | |
|  |  +----------------+  +----------------+  +-------------------------+   | |
|  |  | Kubernetes     |  | Terraform      |  | OpenTelemetry           |   | |
|  |  | 1.30+          |  | + Helm         |  | + Prometheus + Grafana  |   | |
|  |  |                |  |                |  |                         |   | |
|  |  | - Orquestación |  | - IaC          |  | - Métricas              |   | |
|  |  | - Auto-scaling |  | - State Mgmt   |  | - Tracing               |   | |
|  |  | - Self-healing |  | - Modules      |  | - Logging               |   | |
|  |  | - Rolling Dep  |  | - Workspaces   |  | - Alerting              |   | |
|  |  +----------------+  +----------------+  +-------------------------+   | |
|  +------------------------------------------------------------------------+ |
+==============================================================================+
```

### Principios de Arquitectura Resumidos

| #  | Principio                              | Descripción                                              |
|----|----------------------------------------|----------------------------------------------------------|
| A1 | Event-Driven como patrón primario      | Todos los flujos asincrónicos usan NATS JetStream        |
| A2 | CQRS desde Fase 1                      | Separación write/read en Trading Engine y Audit Engine   |
| A3 | Event Sourcing inmutable               | Cada cambio de estado genera un evento persistido        |
| A4 | Zero Trust                             | mTLS, JWT, RBAC en cada hop                              |
| A5 | Broker Agnostic                        | Trading engine no conoce detalles del broker             |
| A6 | Self-hosted AI                         | Ollama = zero dependencia de APIs externas de LLM        |
| A7 | Multi-tenant desde diseño              | Schema-per-tenant a nivel de base de datos               |

---

## 2. Capas Clean Architecture

### 2.1 Estructura de Directorios por Servicio

```
trading-engine/
├── cmd/
│   └── server/
│       └── main.go                  # Entry point, DI wiring
├── internal/
│   ├── domain/                      # CORE PURO — Sin dependencias externas
│   │   ├── aggregate/
│   │   │   ├── order.go             # OrderAggregate
│   │   │   ├── position.go          # PositionAggregate
│   │   │   └── signal.go            # SignalAggregate
│   │   ├── entity/
│   │   │   ├── account.go           # Account entity
│   │   │   └── broker.go            # Broker entity
│   │   ├── valueobject/
│   │   │   ├── price.go             # Price (Money + Currency)
│   │   │   ├── quantity.go          # Quantity + Lot size
│   │   │   ├── symbol.go            # Symbol (EURUSD, BTCUSDT)
│   │   │   ├── timeframe.go         # M1, M5, H1, D1, etc.
│   │   │   └── direction.go         # BUY / SELL
│   │   ├── event/
│   │   │   ├── order_placed.go      # OrderPlacedEvent
│   │   │   ├── order_filled.go      # OrderFilledEvent
│   │   │   ├── order_rejected.go    # OrderRejectedEvent
│   │   │   └── order_cancelled.go   # OrderCancelledEvent
│   │   ├── repository/
│   │   │   ├── order_repository.go  # Interface (no implementation)
│   │   │   └── event_store.go       # Interface
│   │   ├── service/
│   │   │   ├── price_service.go     # Interface
│   │   │   └── risk_service.go      # Interface
│   │   └── port/
│   │       ├── broker_port.go       # BrokerPort interface (plugin)
│   │       └── market_data_port.go  # MarketDataPort interface
│   ├── application/                 # CASOS DE USO — Orchestration
│   │   ├── command/
│   │   │   ├── place_order.go       # PlaceOrderCommand + Handler
│   │   │   ├── cancel_order.go      # CancelOrderCommand + Handler
│   │   │   └── modify_order.go      # ModifyOrderCommand + Handler
│   │   ├── query/
│   │   │   ├── get_order.go         # GetOrderQuery + Handler
│   │   │   ├── list_orders.go       # ListOrdersQuery + Handler
│   │   │   └── get_positions.go     # GetPositionsQuery + Handler
│   │   ├── dto/
│   │   │   ├── order_dto.go         # Data Transfer Objects
│   │   │   └── signal_dto.go
│   │   └── port/
│   │       ├── event_publisher.go   # Interface para publicar eventos
│   │       └── event_store_port.go  # Interface para event store
│   ├── infrastructure/              # IMPLEMENTACIÓN — Adaptadores
│   │   ├── persistence/
│   │   │   ├── postgres/
│   │   │   │   ├── order_repository.go
│   │   │   │   ├── event_store.go
│   │   │   │   └── migrations/
│   │   │   └── redis/
│   │   │       └── cache.go
│   │   ├── messaging/
│   │   │   ├── nats/
│   │   │   │   ├── publisher.go
│   │   │   │   └── subscriber.go
│   │   │   └── handler.go
│   │   └── broker/
│   │       ├── mt5/
│   │       │   └── adapter.go
│   │       ├── binance/
│   │       │   └── adapter.go
│   │       └── ibkr/
│   │           └── adapter.go
│   └── interface/                   # DELIVERY — HTTP/gRPC handlers
│       ├── http/
│       │   ├── handler/
│       │   │   ├── order_handler.go
│       │   │   └── signal_handler.go
│       │   ├── middleware/
│       │   │   ├── auth.go
│       │   │   ├── tenant.go
│       │   │   └── ratelimit.go
│       │   └── router.go
│       ├── grpc/
│       │   └── trading_service.go
│       └── websocket/
│           └── price_stream.go
├── pkg/                              # Paquetes compartidos (librería pública)
│   ├── money/
│   ├── logging/
│   └── telemetry/
├── configs/
│   └── config.yaml
├── deployments/
│   ├── Dockerfile
│   ├── k8s/
│   └── helm/
├── scripts/
├── Makefile
├── go.mod
└── go.sum
```

### 2.2 Reglas de Dependencia (Clean Architecture)

```
+=====================================================================+
|                    REGLA DE DEPENDENCIA                              |
+=====================================================================+
|                                                                      |
|  INTERFACE (HTTP/gRPC/WS)                                            |
|       |                                                              |
|       v  (puede depender de Application e Infrastructure)            |
|                                                                      |
|  APPLICATION (Casos de Uso)                                          |
|       |                                                              |
|       v  (puede depender de Domain e Infrastructure)                 |
|       |                                                              |
|       +---> Domain  (NUNCA depende de nadie más)                     |
|       |                                                              |
|       v                                                              |
|                                                                      |
|  INFRASTRUCTURE (Implementaciones)                                   |
|       |                                                              |
|       +---> Domain (implementa interfaces de Domain)                 |
|                                                                      |
|  VERIFICACIÓN AUTOMÁTICA:                                           |
|  go vet ./internal/domain/...  # Debe compilar SIN imports externos  |
|  Arquitectura tests en /internal/domain_test/                        |
+=====================================================================+
```

### 2.3 Diagrama de Importaciones

```
domain/
  ├── entity/
  ├── valueobject/
  ├── event/
  ├── repository/     (interfaces)
  └── service/        (interfaces)
       ^
       |  implements
       |
infrastructure/persistence/
  ├── postgres/        ---> domain/repository
  └── redis/           ---> domain/repository

application/
  ├── command/         ---> domain/aggregate
  ├── query/           ---> domain/aggregate
  └── dto/             ---> domain/valueobject

interface/http/
  ├── handler/         ---> application/command, application/query
  └── middleware/      ---> domain (solo value objects para tenant extraction)
```

---

## 3. Bounded Contexts (DDD)

### 3.1 Mapa de Contextos

```
+===========================================================================+
|                     BOUNDED CONTEXTS — MAPA ESTRATÉGICO                    |
+===========================================================================+
|                                                                           |
|   +-------------+    +-------------+    +-------------+                  |
|   |   TRADING   |<-->|    RISK     |<-->|   BROKER    |                  |
|   |   CONTEXT   |    |   CONTEXT   |    |   CONTEXT   |                  |
|   |             |    |             |    |             |                  |
|   | Engine      |    | Manager     |    | Gateway     |                  |
|   | Executor    |    | Limits      |    | Abstraction |                  |
|   | State Mgr   |    | Monitor     |    | 5 adapters  |                  |
|   | Scheduler   |    | Circuit Brk |    | (MT5, cT,   |                  |
|   |             |    |             |    |  BN, BB, IB) |                  |
|   +------+------+    +------+------+    +------+------+                  |
|          |                  |                  |                          |
|          v                  v                  v                          |
|   +-------------+    +-------------+    +-------------+                  |
|   |   MARKET    |    |    AI/ML    |    |    AUDIT    |                  |
|   |   DATA      |    |   CONTEXT   |    |   CONTEXT   |                  |
|   |   CONTEXT   |    |             |    |             |                  |
|   |             |    | Scoring     |    | Event Store |                  |
|   | Ingestion   |    | Regime Det  |    | Projector   |                  |
|   | Aggregator  |    | RAG         |    | Compliance  |                  |
|   | Feed Mgr    |    | Anomaly Det |    | Query       |                  |
|   | Historic    |    | LLM Router  |    |             |                  |
|   +------+------+    +------+------+    +------+------+                  |
|          |                  |                  |                          |
|          v                  v                  v                          |
|   +-------------+    +-------------+    +-------------+                  |
|   |  PLATFORM   |    |NOTIFICATION |    |  BILLING    |                  |
|   |  CONTEXT    |    |  CONTEXT    |    |  CONTEXT    |                  |
|   |             |    |             |    |             |                  |
|   | Auth/ RBAC  |    | Dispatcher  |    | Subscriptions|                 |
|   | Tenant Mgr  |    | Templates   |    | Invoicing   |                  |
|   | User Mgmt   |    | Channels    |    | Metering    |                  |
|   | Admin Panel  |    | (TG, Email, |    | Plans       |                  |
|   |             |    |  WS, SMS)   |    |             |                  |
|   +------+------+    +------+------+    +------+------+                  |
+===========================================================================+
```

### 3.2 Contextos Detallados

| #  | Bounded Context   | Responsabilidad Principal                          | Servicios | Puertos Expuestos     |
|----|-------------------|-----------------------------------------------------|-----------|-----------------------|
| 1  | **Trading**       | Orquestación de órdenes, ejecución, state machines  | 8         | gRPC + NATS           |
| 2  | **Risk**          | Validación pre-ejecución, límites, circuit breakers  | 4         | NATS (interno)        |
| 3  | **Broker**        | Abstracción unificada, adaptadores por broker        | 6         | gRPC + NATS           |
| 4  | **AI/ML**         | Scoring, regime detection, RAG, anomaly detection   | 8         | NATS + WebSocket      |
| 5  | **Market Data**   | Ingestión, normalización, almacenamiento temporal    | 4         | NATS + WebSocket      |
| 6  | **Platform**      | Auth, multi-tenancy, user management, admin           | 8         | HTTP REST + WebSocket |
| 7  | **Notification**  | Despacho multi-canal, templates, retry logic         | 4         | NATS                  |
| 8  | **Audit/Billing** | Event sourcing, proyecciones, facturación, compliance | 6        | HTTP REST + NATS      |

### 3.3 Contratos entre Contextos

```
Trading Context                    Risk Context
===================                =================
     |                                  ^
     |  SignalReceived                  | RiskCheckPassed
     +-----------> Risk Service --------+
     |                                  |
     | OrderValidationRequest           | RiskCheckFailed
     +-----------> Risk Service --------+
     |                                  |
     | <---- RiskCheckResult ---------- +

Trading Context                    Broker Context
===================                =================
     |                                  ^
     | ExecuteOrderCommand              | OrderExecuted
     +-----------> Broker Gateway ------+
     |                                  |
     | CancelOrderCommand               | OrderCancelled
     +-----------> Broker Gateway ------+
     |                                  |
     | <---- ExecutionReport ---------- +

AI/ML Context                      Trading Context
===================                =================
     |                                  ^
     | SignalScored                     | ScoreRequest
     +-----------> Trading Engine ------+
     |                                  |
     | RegimeChanged                    |
     +-----------> Trading Engine ------+
     |                                  |
     | AnomalyDetected                  |
     +-----------> Risk Manager --------+
```

### 3.4 Lenguaje Ubicuo (Glosario por Contexto)

| Contexto   | Término           | Definición                                              |
|------------|-------------------|---------------------------------------------------------|
| Trading    | Order             | Instrucción de compra/venta con precio, cantidad, tipo  |
| Trading    | Position          | Posición abierta resultante de órdenes filladas         |
| Trading    | Signal            | Señal de trading generada por AI o usuario              |
| Trading    | Fill              | Ejecución parcial o total de una orden                  |
| Trading    | Slippage          | Diferencia entre precio esperado y ejecutado            |
| Risk       | Drawdown          | Pérdida máxima desde un pico de equity                  |
| Risk       | Exposure          | Suma de posiciones abiertas en dirección dada           |
| Risk       | Circuit Breaker   | Mecanismo de pausa automática por breach de umbral      |
| Risk       | Risk/Reward Ratio | Relación entre stop loss y take profit                  |
| Broker     | Adapter           | Implementación concreta de la interfaz BrokerPort       |
| Broker     | Bridge            | Componente que conecta con la API del broker            |
| AI/ML      | Regime            | Estado del mercado: trending, ranging, volatile         |
| AI/ML      | Confidence Score  | Nivel de confianza de una señal AI (0-100%)             |
| AI/ML      | RAG               | Retrieval-Augmented Generation para contexto financiero |
| Platform   | Tenant            | Organización o usuario con aislamiento de datos         |
| Platform   | RBAC              | Role-Based Access Control con permisos granulares       |

---

## 4. Flujo de Dependencias

### 4.1 Dependency Injection Container

```go
// cmd/server/main.go - Dependency Wiring

func main() {
    // 1. Infrastructure Layer
    db := postgres.NewConnection(config.Database)
    redis := redis.NewCluster(config.Redis)
    nats := nats.NewConnection(config.NATS)
    eventStore := postgres.NewEventStore(db)

    // 2. Domain Services (Ports)
    brokerGateway := broker.NewGateway(nats)
    riskManager := risk.NewManager(db, redis, nats)
    marketData := marketdata.NewAggregator(nats, redis)

    // 3. Application Layer (Use Cases)
    placeOrder := application.NewPlaceOrderUseCase(
        eventStore,
        brokerGateway,
        riskManager,
        marketData,
    )

    // 4. Interface Layer (Delivery)
    httpHandler := http.NewHandler(placeOrder, ...)
    grpcServer := grpc.NewServer(placeOrder, ...)
    natsHandler := nats.NewHandler(placeOrder, ...)

    // 5. Start
    server.Start(httpHandler, grpcServer, natsHandler)
}
```

### 4.2 Diagrama de Flujo de Dependencias

```
+========================================================================+
|                     FLUJO DE DEPENDENCIAS                              |
+========================================================================+
|                                                                        |
|  [HTTP Request]                                                        |
|       |                                                                |
|       v                                                                |
|  +-----------+      +------------+      +-----------+                  |
|  | Interface |----->| Application|----->| Domain    |                  |
|  | Handler   |      | Use Case   |      | Aggregate |                  |
|  +-----------+      +-----+------+      +-----------+                  |
|       |                    |                                          |
|       v                    v                                          |
|  +-----------+      +------------+                                    |
|  | Infra:    |      | Infra:     |                                    |
|  | HTTP Mw   |      | NATS Pub   |                                    |
|  +-----------+      +-----+------+                                    |
|       |                    |                                          |
|       v                    v                                          |
|  +-----------+      +------------+      +-----------+                  |
|  | Redis     |      | NATS       |      | PostgreSQL|                  |
|  | (Cache)   |      | JetStream  |      | + Events  |                  |
|  +-----------+      +-----+------+      +-----------+                  |
|                            |                                          |
|                            v                                          |
|                    +------------+      +-----------+                   |
|                    | Subscriber  |----->| Another   |                   |
|                    | (Consumer)  |      | Service   |                   |
|                    +------------+      +-----------+                   |
+========================================================================+
```

### 4.3 Regla de Puertos y Adaptadores

```
+--------------------------------------------------------------------+
|                    PUERTOS Y ADAPTADORES                            |
+--------------------------------------------------------------------+
|                                                                     |
|  DOMAIN define INTERFACES (puertos):                               |
|  +-----------------------------------------------------------+     |
|  | type OrderRepository interface {                           |     |
|  |     Save(ctx context.Context, order OrderAggregate) error  |     |
|  |     FindByID(ctx context.Context, id OrderID) (*Order, err)|     |
|  |     FindByAccount(ctx context.Context, id AccountID) []Order|    |
|  | }                                                         |     |
|  +-----------------------------------------------------------+     |
|                                                                     |
|  INFRASTRUCTURE implementa ADAPTADORES:                             |
|  +-----------------------------------------------------------+     |
|  | type PostgresOrderRepository struct {                      |     |
|  |     db *sql.DB                                            |     |
|  | }                                                         |     |
|  |                                                           |     |
|  | func (r *PostgresOrderRepository) Save(ctx, order) error { |     |
|  |     // INSERT INTO orders ...                             |     |
|  | }                                                         |     |
|  +-----------------------------------------------------------+     |
|                                                                     |
|  APPLICATION inyecta el adaptador:                                  |
|  +-----------------------------------------------------------+     |
|  | type PlaceOrderUseCase struct {                            |     |
|  |     repo    domain.OrderRepository     // interface       |     |
|  |     publisher domain.EventPublisher    // interface       |     |
|  | }                                                         |     |
|  +-----------------------------------------------------------+     |
+--------------------------------------------------------------------+
```

---

## 5. Service Mesh con NATS JetStream

### 5.1 Topología NATS

```
+=====================================================================+
|                 NATS JETSTREAM CLUSTER (3 nodos)                     |
+=====================================================================+
|                                                                      |
|  +-------------------+  +-------------------+  +------------------+ |
|  |  NATS Node 1      |  |  NATS Node 2      |  |  NATS Node 3     | |
|  |  (Leader)         |  |  (Follower)       |  |  (Follower)      | |
|  |  Puerto: 4222     |  |  Puerto: 4222     |  |  Puerto: 4222    | |
|  |  Monitor: 8222    |  |  Monitor: 8222    |  |  Monitor: 8222   | |
|  +--------+----------+  +--------+----------+  +--------+---------+ |
|           |                     |                      |             |
|           +----------+----------+----------+----------+             |
|                      |                                             |
|            JetStream Replication (RF=3)                             |
|                      |                                             |
|  +-------------------v--------------------------------------------+|
|  |                    STREAMS                                      ||
|  |                                                                ||
|  |  trading.orders          (replicas: 3, retention: workqueue)   ||
|  |  trading.signals         (replicas: 3, retention: limits)      ||
|  |  trading.executions      (replicas: 3, retention: workqueue)   ||
|  |  risk.events             (replicas: 3, retention: limits)      ||
|  |  broker.executions       (replicas: 3, retention: workqueue)   ||
|  |  marketdata.ticks        (replicas: 1, retention: limits)      ||
|  |  marketdata.ohlc         (replicas: 1, retention: limits)      ||
|  |  ai.signals              (replicas: 3, retention: limits)      ||
|  |  ai.regime               (replicas: 3, retention: limits)      ||
|  |  platform.auth           (replicas: 3, retention: limits)      ||
|  |  notification.outbound   (replicas: 3, retention: workqueue)   ||
|  |  audit.events            (replicas: 3, retention: streams)     ||
|  |                                                                ||
|  +----------------------------------------------------------------+|
+=====================================================================+
```

### 5.2 Subjects NATS por Dominio

| Subject Pattern                        | Publisher           | Consumer(s)                | Retención   |
|----------------------------------------|---------------------|----------------------------|-------------|
| `trading.signal.received`              | Platform            | AI/ML, Trading Engine      | limits      |
| `trading.signal.scored`                | AI/ML               | Trading Engine             | limits      |
| `trading.order.place`                  | Trading Engine      | Risk Manager, Broker       | workqueue   |
| `trading.order.placed`                 | Trading Engine      | Audit, Notification        | workqueue   |
| `trading.order.filled`                 | Broker              | Trading, Risk, Audit       | workqueue   |
| `trading.order.rejected`               | Broker              | Trading, Risk, Audit       | workqueue   |
| `trading.order.cancelled`              | Trading Engine      | Audit, Notification        | workqueue   |
| `risk.check.request`                   | Trading Engine      | Risk Manager               | workqueue   |
| `risk.check.approved`                  | Risk Manager        | Trading Engine, Broker     | workqueue   |
| `risk.check.rejected`                  | Risk Manager        | Trading Engine, Audit      | workqueue   |
| `risk.breach.detected`                 | Risk Manager        | Platform, Notification     | limits      |
| `broker.execute.order`                 | Risk Manager        | Broker Gateway             | workqueue   |
| `broker.execution.report`              | Broker Gateway      | Trading, Risk, Audit       | workqueue   |
| `marketdata.tick.<symbol>`             | Market Data         | Trading, AI/ML, Platform   | limits      |
| `marketdata.ohlc.<symbol>.<tf>`        | Market Data         | AI/ML, Trading             | limits      |
| `ai.regime.changed`                    | AI/ML               | Trading, Risk              | limits      |
| `ai.anomaly.detected`                  | AI/ML               | Risk, Notification         | limits      |
| `platform.user.created`                | Platform            | Billing, Notification      | limits      |
| `platform.tenant.created`              | Platform            | Billing, Audit             | limits      |
| `notification.send`                    | Any Service         | Notification Dispatcher    | workqueue   |
| `audit.event.logged`                   | Audit Engine        | (consumers internos)       | streams     |

### 5.3 Configuración JetStream

```yaml
# NATS JetStream Configuration
jetstream:
  store_dir: /data/nats/jetstream
  max_mem: 2GB
  max_file: 50GB

  streams:
    trading.orders:
      subjects: ["trading.order.>"]
      retention: workqueue
      max_msgs: 1000000
      max_age: 72h
      storage: file
      replicas: 3

    marketdata.tick:
      subjects: ["marketdata.tick.*"]
      retention: limits
      max_msgs: 500000
      max_age: 1h
      storage: memory          # En memoria para baja latencia
      replicas: 1              # No necesita replicación (datos de alta frecuencia)

    audit.events:
      subjects: ["audit.>"]
      retention: streams       # Retención permanente
      max_msgs: -1             # Sin límite
      max_age: -1              # Sin expiración
      storage: file
      replicas: 3
```

### 5.4 Dead Letter Queues

```
+=====================================================================+
|                    DEAD LETTER HANDLING                              |
+=====================================================================+
|                                                                      |
|  Service procesa evento                                              |
|       |                                                              |
|       v                                                              |
|  +-----------+    Falla 3 veces    +----------------+                |
|  | Consumer  |------------------->| DLQ: <subject>.dlq |             |
|  +-----------+                     +-------+--------+                |
|       |                                     |                        |
|       v                                     v                        |
|  [Retry automático]              +------------------+                |
|  con backoff exponencial         | DLQ Monitor      |                |
|  (1s, 2s, 4s, max 30s)          | (cada 5 min)     |                |
|                                  |                  |                |
|                                  | - Reintentar     |                |
|                                  | - Alertar        |                |
|                                  | - Archivar       |                |
|                                  +------------------+                |
+=====================================================================+
```

---

## 6. Flujo de Datos General

### 6.1 Pipeline de Señales (Flujo Principal)

```
+=====================================================================+
|           PIPELINE DE SEÑALES — FLUJO COMPLETO                       |
+=====================================================================+
|                                                                      |
| [External Source]         [Market Data]         [AI/ML]             |
|   (Binance API)    --->   Ingestion     --->    Scoring             |
|   (MT5 Feed)             Aggregator            Regime Det           |
|   (IBKR Feed)           Normalizer            Anomaly Det          |
|        |                      |                    |                 |
|        v                      v                    v                 |
|  +-----------+          +-----------+        +-----------+           |
|  | WebSocket |          | TimescaleDB|       | Ollama    |           |
|  | Stream    |          | (Ticks)    |       | (Local)   |           |
|  +-----------+          +-----------+        +-----------+           |
|                                  |                    |                 |
|                                  v                    v                 |
|                          +-----------------------------+              |
|                          |     NATS JetStream          |              |
|                          |     marketdata.tick.*       |              |
|                          |     ai.signal.scored        |              |
|                          +-------------+---------------+              |
|                                        |                             |
|                              +---------+---------+                   |
|                              v                   v                   |
|                    +----------------+    +----------------+           |
|                    | Trading Engine |    | Risk Manager   |           |
|                    |                |    |                |           |
|                    | 1. Recibe     |    | 2. Valida      |           |
|                    |    signal     |--->|    riesgo      |           |
|                    |                |    |                |           |
|                    | 3. Crea order |    | - Max exposure  |           |
|                    |                |    | - Max drawdown  |           |
|                    |                |    | - Max orders/h  |           |
|                    +-------+--------+    +-------+--------+           |
|                            |                   |                     |
|                            v                   v                     |
|                    +----------------+                              |
|                    | Broker Gateway  |                              |
|                    | (Abstraction)   |                              |
|                    |                 |                              |
|                    | - MT5 Adapter   |---> [MetaTrader 5]           |
|                    | - cTrader Adapt |---> [cTrader]                |
|                    | - Binance Adapt |---> [Binance API]            |
|                    | - Bybit Adapt   |---> [Bybit API]              |
|                    | - IBKR Adapt    |---> [IBKR TWS]               |
|                    +----------------+                              |
+=====================================================================+
```

### 6.2 Pipeline de Copy Trading

```
+=====================================================================+
|           COPY TRADING — FLUJO 1:N CONFIGURABLE                     |
+=====================================================================+
|                                                                      |
| [Master Account]                                                     |
|   Signal Generated                                                   |
|        |                                                             |
|        v                                                             |
|  +----------------+                                                  |
|  | Signal Router  |                                                  |
|  |                |                                                  |
|  | Query:         |                                                  |
|  | COPY_TRADES    |                                                  |
|  | WHERE master = |                                                  |
|  | 'master_001'   |                                                  |
|  +-------+--------+                                                  |
|          |                                                           |
|          +--------------------------------------------------------+ |
|          |               |                   |                     | |
|          v               v                   v                     v |
|  +-----------+   +-----------+       +-----------+      +-----------+ |
|  | Account A |   | Account B |       | Account C |      | Account D | |
|  |           |   |           |       |           |      |           | |
|  | Lot: 0.01 |   | Lot: 0.1  |       | Lot: 0.05 |      | Lot: 1.0  | |
|  | SL: 25pip |   | SL: 50pip |       | SL: 30pip |      | SL: 100pip| |
|  | TP: 50pip |   | TP: 100pip|       | TP: 60pip |      | TP: 200pip| |
|  | Max: $500 |   | Max: $5000|       | Max: $2000|      | Max: $50K | |
|  | Filter:   |   | Filter:   |       | Filter:   |      | Filter:   | |
|  | ALL       |   | FOREX ONLY|       | RISK<30%  |      | ALL       | |
|  +-----------+   +-----------+       +-----------+      +-----------+ |
|        |               |                   |                     |    |
|        v               v                   v                     v    |
|  +-----------+   +-----------+       +-----------+      +-----------+ |
|  | MT5       |   | cTrader   |       | Binance   |      | MT5       | |
|  | Account   |   | Account   |       | Account   |      | Account   | |
|  +-----------+   +-----------+       +-----------+      +-----------+ |
+=====================================================================+
```

### 6.3 Flujo de Autenticación

```
+=====================================================================+
|           FLUJO DE AUTENTICACIÓN — OAUTH2 + JWT + RBAC              |
+=====================================================================+
|                                                                      |
| [User] --> [Traefik] --> [Platform/Auth Service]                     |
|              |                      |                                |
|              v                      v                                |
|     +-------------+        +---------------+                        |
|     | Rate Limit  |        | Auth Service  |                        |
|     | Check       |        |               |                        |
|     +------+------+        | 1. Validate   |                        |
|            |               |    credentials|                        |
|            v               | 2. Check OAuth|                        |
|     +------+------+        |    provider   |                        |
|     | JWT         |        | 3. Generate   |                        |
|     | Validation  |        |    JWT + RT   |                        |
|     | (if token)  |        | 4. Lookup     |                        |
|     +------+------+        |    RBAC roles |                        |
|            |               +-------+-------+                        |
|            v                       |                                |
|     +------+------+                v                                |
|     | Forward to  |        +---------------+                        |
|     | Service     |        | Redis Cache   |                        |
|     +-------------+        | (session TTL  |                        |
|                            |  15min token) |                        |
|                            +---------------+                        |
|                                                                      |
|  JWT Claims:                                                         |
|  {                                                                   |
|    "sub": "user_123",                                               |
|    "tenant": "tenant_abc",                                          |
|    "roles": ["trader", "viewer"],                                   |
|    "permissions": ["order:create", "order:read", "signal:subscribe"]|
|    "exp": 1689427200,                                               |
|    "iat": 1689426300                                                |
|  }                                                                   |
+=====================================================================+
```

---

## 7. Mapeo Tecnológico por Capa

| Capa                    | Componente              | Tecnología                | Puerto     | Namespace K8s     |
|-------------------------|-------------------------|---------------------------|------------|--------------------|
| **Edge**                | API Gateway             | Traefik 3.0               | 80/443     | traefik-system     |
|                         | TLS Certificates        | Let's Encrypt + cert-mgr  | --         | cert-manager       |
| **Trading**             | Trading Engine          | Go 1.22                   | 8080       | trading            |
|                         | Order Executor          | Go 1.22                   | 8081       | trading            |
|                         | Copy Trading Router     | Go 1.22                   | 8082       | trading            |
|                         | Signal Scheduler        | Go 1.22                   | 8083       | trading            |
| **Risk**                | Risk Manager            | Go 1.22                   | 8090       | risk               |
|                         | Risk Monitor            | Go 1.22                   | 8091       | risk               |
|                         | Circuit Breaker         | Go 1.22                   | 8092       | risk               |
| **Broker**              | Broker Gateway          | Go 1.22                   | 8100       | broker             |
|                         | MT5 Adapter             | Go 1.22                   | 8101       | broker             |
|                         | cTrader Adapter         | Go 1.22                   | 8102       | broker             |
|                         | Binance Adapter         | Go 1.22                   | 8103       | broker             |
|                         | Bybit Adapter           | Go 1.22                   | 8104       | broker             |
|                         | IBKR Adapter            | Go 1.22                   | 8105       | broker             |
| **AI/ML**               | Signal Scorer           | Python 3.12               | 8200       | ai                 |
|                         | Regime Detector         | Python 3.12               | 8201       | ai                 |
|                         | Anomaly Detector        | Python 3.12               | 8202       | ai                 |
|                         | RAG Engine              | Python 3.12               | 8203       | ai                 |
|                         | Ollama Gateway          | Ollama                    | 11434      | ai                 |
| **Market Data**         | Data Ingestion          | Go 1.22                   | 8300       | marketdata         |
|                         | Data Aggregator         | Go 1.22                   | 8301       | marketdata         |
|                         | Historical Service      | Go 1.22                   | 8302       | marketdata         |
|                         | Feed Manager            | Go 1.22                   | 8303       | marketdata         |
| **Platform**            | Auth Service            | Go 1.22                   | 8400       | platform           |
|                         | User Service            | Go 1.22                   | 8401       | platform           |
|                         | Tenant Service          | Go 1.22                   | 8402       | platform           |
|                         | Admin Service           | Go 1.22                   | 8403       | platform           |
| **Notification**        | Notification Dispatcher  | Go 1.22                   | 8500       | notification       |
|                         | Template Engine         | Go 1.22                   | 8501       | notification       |
| **Audit/Billing**       | Audit Engine            | Go 1.22                   | 8600       | audit              |
|                         | Event Projector         | Go 1.22                   | 8601       | audit              |
|                         | Billing Service         | Go 1.22                   | 8602       | audit              |
| **Data**                | PostgreSQL + TimescaleDB| PostgreSQL 16              | 5432       | data               |
|                         | Redis Cluster           | Redis 7                   | 6379       | data               |
|                         | NATS JetStream          | NATS 2.10+                | 4222       | data               |
| **Frontend**            | Next.js App             | Node.js 20                | 3000       | frontend           |
| **Desktop**             | Tauri App               | Rust + React              | --         | N/A (local)        |
| **Observability**       | Prometheus              | Prometheus 2.x            | 9090       | monitoring         |
|                         | Grafana                 | Grafana 10.x              | 3001       | monitoring         |
|                         | OpenTelemetry Collector | OTel Collector            | 4317       | monitoring         |
|                         | AlertManager            | AlertManager              | 9093       | monitoring         |

---

## 8. Estrategia de Despliegue

### 8.1 Fases de Despliegue

```
+=====================================================================+
|                    FASES DE DESPLIEGUE                               |
+=====================================================================+
|                                                                      |
|  FASE 1 (Mes 1-3) — MVP INFRASTRUCTURE                             |
|  +------------------------------------------------------------+    |
|  | Docker Compose (1 VPS)                                      |    |
|  | - Trading Engine (Go)                                       |    |
|  | - Risk Manager (Go)                                         |    |
|  | - MT5 Adapter (Go)                                          |    |
|  | - Platform Auth (Go)                                        |    |
|  | - PostgreSQL + Redis + NATS (single node)                   |    |
|  | - Next.js (Frontend)                                        |    |
|  +------------------------------------------------------------+    |
|                                                                      |
|  FASE 2 (Mes 4-6) — K8S + BROKERS                                 |
|  +------------------------------------------------------------+    |
|  | Kubernetes (3-node cluster)                                  |    |
|  | - Todos los servicios Go                                    |    |
|  | - cTrader + Binance adapters                                |    |
|  | - NATS JetStream cluster (3 nodos)                          |    |
|  | - PostgreSQL con replica                                    |    |
|  | - Redis cluster (3 masters + 3 replicas)                    |    |
|  +------------------------------------------------------------+    |
|                                                                      |
|  FASE 3 (Mes 7-12) — AI/ML + MULTI-TENANT                        |
|  +------------------------------------------------------------+    |
|  | Kubernetes (5+ nodes) + GPU node (para Ollama)              |    |
|  | - AI/ML Pipeline completo                                   |    |
|  | - Bybit + IBKR adapters                                     |    |
|  | - Multi-tenant PostgreSQL (schema-per-tenant)               |    |
|  | - TimescaleDB hypertables                                   |    |
|  | - OpenTelemetry completo                                    |    |
|  +------------------------------------------------------------+    |
|                                                                      |
|  FASE 4 (Mes 13-24) — SCALE + COMPLIANCE                         |
|  +------------------------------------------------------------+    |
|  | Multi-region (AWS/GCP)                                      |    |
|  | - Active-active en 2 regiones                               |    |
|  | - CDC para replicación cross-region                         |    |
|  | - SOC2 Type II compliance                                   |    |
|  | - SSO (SAML 2.0) para enterprise                            |    |
|  | - Mobile app (React Native)                                 |    |
|  +------------------------------------------------------------+    |
+=====================================================================+
```

### 8.2 Namespaces Kubernetes

```
+=====================================================================+
|                    KUBERNETES NAMESPACES                             |
+=====================================================================+
|                                                                      |
|  kubecost           — Cost monitoring                               |
|  traefik-system     — API Gateway + Ingress                         |
|  cert-manager       — TLS certificates                              |
|  monitoring         — Prometheus + Grafana + AlertManager            |
|  data               — PostgreSQL + Redis + NATS                      |
|  trading            — Trading Engine + Executor + Copy Trading       |
|  risk               — Risk Manager + Monitor + Circuit Breaker       |
|  broker             — Gateway + Adapters (MT5, cT, BN, BB, IB)     |
|  ai                 — AI/ML services + Ollama                       |
|  marketdata         — Ingestion + Aggregator + Historical           |
|  platform           — Auth + User + Tenant + Admin                   |
|  notification       — Dispatcher + Templates                        |
|  audit              — Audit Engine + Projector + Billing            |
|  frontend           — Next.js                                       |
+=====================================================================+
```

---

## 9. Diagrama de Red

### 9.1 Segmentación de Red

```
+=====================================================================+
|                    SEGMENTACIÓN DE RED (Zero Trust)                  |
+=====================================================================+
|                                                                      |
|  INTERNET                                                           |
|       |                                                              |
|       v                                                              |
|  +------------------+                                               |
|  | DMZ              |  Namespace: traefik-system                    |
|  | Traefik          |  - Puerto 80/443 expuesto                     |
|  | WAF              |  - Rate limiting activo                       |
|  | Rate Limiter     |  - Geo-blocking opcional                      |
|  +--------+---------+                                               |
|           |                                                          |
|           v  (Solo puertos internos de servicios)                   |
|  +------------------+                                               |
|  | App Zone         |  Namespace: trading, risk, broker, ai, etc.   |
|  | Microservicios   |  - Comunicación interna via NATS              |
|  | (pods)           |  - mTLS entre pods (service mesh)             |
|  |                  |  - NetworkPolicies: deny-all + allow explicit  |
|  +--------+---------+                                               |
|           |                                                          |
|           v  (Solo puertos de base de datos)                        |
|  +------------------+                                               |
|  | Data Zone        |  Namespace: data                              |
|  | PostgreSQL       |  - Solo accesible desde App Zone              |
|  | Redis            |  - No acceso directo desde DMZ                |
|  | NATS             |  - Encryption at rest                         |
|  +------------------+                                               |
|                                                                      |
|  NetworkPolicies:                                                    |
|  +------------------------------------------------------------+    |
|  | kind: NetworkPolicy                                        |    |
|  | spec:                                                      |    |
|  |   podSelector: {}                                          |    |
|  |   policyTypes:                                             |    |
|  |     - Ingress                                              |    |
|  |     - Egress                                               |    |
|  |   ingress:                                                 |    |
|  |     - from:                                                |    |
|  |         - namespaceSelector:                               |    |
|  |             matchLabels:                                   |    |
|  |               kubernetes.io/metadata.name: traefik-system |    |
|  |       ports:                                               |    |
|  |         - protocol: TCP                                    |    |
|  |           port: 8080                                       |    |
|  +------------------------------------------------------------+    |
+=====================================================================+
```

### 9.2 Flujo de Red para una Request

```
[Usuario] ----HTTPS/TLS 1.3----> [Traefik:443]
                                       |
                                       | (TLS termination)
                                       v
                                 [Traefik:8080]
                                       |
                                       | (Rate limit check)
                                       | (JWT validation)
                                       | (Routing rules)
                                       v
                              [Trading Engine:8080]  (via ClusterIP)
                                       |
                                       | (NATS publish)
                                       v
                              [NATS JetStream:4222]
                                       |
                                       | (async processing)
                                       v
                              [Risk Manager:8090]  (via ClusterIP)
                                       |
                                       | (NATS publish)
                                       v
                              [Broker Gateway:8100]
                                       |
                                       | (external API call)
                                       v
                              [Binance API] / [MT5 Bridge] / etc.
```

---

## Aprobaciones

| Rol                  | Nombre           | Fecha       | Estado    |
|----------------------|------------------|-------------|-----------|
| CTO                  | ________________ | ____/__/__ | Pendiente |
| Lead Architect       | ________________ | ____/__/__ | Pendiente |
| DevOps Lead          | ________________ | ____/__/__ | Pendiente |

---

*Documento generado como parte del proceso de arquitectura de TNSVT V2.*
*Documento anterior: [00-VISION.md](00-VISION.md)*
*Proximo documento: [02-SERVICES-CATALOG.md](02-SERVICES-CATALOG.md)*
