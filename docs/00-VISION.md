# TNSVT V2 — Documento de Visión Estratégica

**Versión:** 2.0  
**Fecha:** 14 de Julio de 2026  
**Clasificación:** Confidencial — Uso Interno  
**Estado:** Aprobado por Arquitectura  

---

## Índice

1. [Resumen Ejecutivo](#1-resumen-ejecutivo)
2. [Problemas Actuales](#2-problemas-actuales)
3. [Propuesta de Valor](#3-propuesta-de-valor)
4. [Pilares Arquitectónicos](#4-pilares-arquitectónicos)
5. [Stack Tecnológico](#5-stack-tecnológico)
6. [Principios de Diseño](#6-principios-de-diseño)
7. [Diferenciadores Competitivos](#7-diferenciadores-competitivos)
8. [Métricas de Éxito](#8-métricas-de-éxito)
9. [Restricciones y Supuestos](#9-restricciones-y-supuestos)

---

## 1. Resumen Ejecutivo

TNSVT V2 (Trading Network Signals & Vault Technology, versión 2) es una
**plataforma SaaS de trading algorítmico** de nivel empresarial diseñada para
servir desde traders individuales hasta operaciones white-label de alta
frecuencia. La plataforma integra un motor de señales multi-broker, un sistema
de copy trading configurable por cuenta, inteligencia artificial autoalojada
(Ollama), y un framework de riesgo en tiempo real — todo sobre una arquitectura
orientada a eventos con Event Sourcing desde la Fase 1.

### Contexto Actual vs. Visión

```
+-----------------------------+          +----------------------------------+
|   SISTEMA ACTUAL (V1)       |          |   PLATAFORMA OBJETIVO (V2)       |
+-----------------------------+          +----------------------------------+
| Symfony PHP monolítico      |    --->  | Go microservices (trading core)  |
| FastAPI punto suelto        |          | Python AI/ML pipeline            |
| MT5 como único broker       |          | Multi-broker (5+ exchanges)      |
| Telethon + Telegram Bot     |          | Next.js + Tauri desktop          |
| Streamlit dashboards        |          | WebSocket real-time streams      |
| SQLite (sin escalabilidad)  |          | PostgreSQL + TimescaleDB          |
| Sin mensajería centralizada |          | NATS JetStream event bus         |
| Sin observabilidad          |          | OpenTelemetry + Prometheus       |
| Copy trading rígido         |          | Copy trading configurable/account |
| Sin AI/ML productivo        |          | Ollama self-hosted + RAG + scoring|
| Sin multi-tenancy           |          | Schema-per-tenant PostgreSQL     |
+-----------------------------+          +----------------------------------+
```

### Alcance del Proyecto

| Dimensión              | Actual (V1)         | Objetivo (V2)            |
|------------------------|---------------------|--------------------------|
| Usuarios concurrentes  | ~50                 | 100,000+                 |
| Brokers soportados     | 1 (MT5)             | 5+ (MT5, cTrader, Binance, Bybit, IBKR) |
| Latencia de ejecución  | 2-5 segundos        | < 100ms (p99)            |
| Disponibilidad          | Sin SLA formal      | 99.95% uptime            |
| Datos de mercado        | Polling cada 5s     | WebSocket tick-by-tick   |
| AI/ML                   | Prototipos          | Producción con RAG       |
| Copy Trading            | 1:1 rígido          | 1:N configurable por cuenta |
| Event Sourcing          | No                  | Sí, desde Fase 1         |

---

## 2. Problemas Actuales

| #  | Problema                                    | Impacto                                    | Severidad | Frecuencia        |
|----|---------------------------------------------|--------------------------------------------|-----------|-------------------|
| P1 | Monolito Symfony con acoplamiento excesivo  | Imposible escalar componentes independiente | Crítica   | Continua          |
| P2 | SQLite como única base de datos              | Corrupción bajo carga, sin concurrencia     | Crítica   | Diaria            |
| P3 | Latencia elevada en ejecución (2-5s)        | Pérdida de oportunidades de trading        | Alta      | Multiples/día     |
| P4 | Solo soporta MetaTrader 5                    | Limita mercado objetivo y revenue          | Alta      | Permanente        |
| P5 | Copy trading rígido (1:1)                    | No permite configuración por cuenta        | Media     | Permanente        |
| P6 | Sin sistema de riesgo centralizado           | Exposición a drawdowns catastroficos       | Crítica   | Eventual          |
| P7 | Sin observabilidad ni métricas               | Imposible diagnosticar problemas en prod   | Alta      | Continua          |
| P8 | Telegram Bot como canal primario             | Dependencia de terceros, rate limits        | Media     | Continua          |
| P9 | Sin framework de autenticación robusto       | Riesgo de seguridad, sin RBAC              | Crítica   | Permanente        |
| P10| Sin integración AI productiva                | Competitividad reducida                    | Media     | Permanente        |
| P11| Sin testing automatizado significativo       | Regresiones frecuentes, despliegues riesgosos | Alta   | Continua          |
| P12| Stack heterogéneo sin contratos              | Integración frágil entre componentes       | Alta      | Continua          |
| P13| Sin estrategia de disaster recovery          | Pérdida total de datos ante fallos         | Crítica   | Eventual          |
| P14| Ausencia de multi-tenancy                    | Imposible ofrecer modelo SaaS              | Alta      | Permanente        |
| P15| Acoplamiento a Telegram/Telethon             | Bloquea canales alternativos               | Media     | Permanente        |

### Clasificación por Severidad

```
Crítica (P1, P2, P6, P9, P13)  ████████████████████████  5 problemas
Alta    (P3, P4, P7, P11, P12, P14) ████████████████████  6 problemas
Media   (P5, P8, P10, P15)  ████████████████              4 problemas

Prioridad de Resolución:
  Fase 1: P2, P9, P13 → Infraestructura base + seguridad
  Fase 2: P1, P6, P3  → Microservicios + riesgo + performance
  Fase 3: P4, P5, P10  → Multi-broker + AI + copy trading avanzado
  Fase 4: P7, P11-P15  → Observabilidad + calidad + multi-tenancy
```

---

## 3. Propuesta de Valor

### 3.1 Para el Trader Individual

```
+=====================================================================+
|                    TRADER INDIVIDUAL                                 |
+=====================================================================+
|                                                                      |
|  [Señales Multi-Broker]     [Copy Trading Config]    [AI Scoring]   |
|       |                           |                       |          |
|       v                           v                       v          |
|  +----------+            +---------------+         +------------+   |
|  | Broker   |            | Cuenta A:     |         | Confianza  |   |
|  | Selector |            |   Lote: 0.01  |         |   87%      |   |
|  |----------|            |   SL: 25 pips |         | Risk: Bajo |   |
|  | MT5      |            |   TP: 50 pips |         | Regime:    |   |
|  | cTrader  |            |---------------|         | Bullish    |   |
|  | Binance  |            | Cuenta B:     |         +------------+   |
|  | Bybit    |            |   Lote: 0.1   |                          |
|  | IBKR     |            |   SL: 50 pips |                          |
|  +----------+            |   TP: 100 pips|                          |
|                          +---------------+                          |
+=====================================================================+
```

**Beneficios clave:**
- Ejecución sub-100ms en lugar de 2-5 segundos
- Copy trading con configuración personalizada por cuenta
- Señales puntuadas por IA con explicabilidad
- Desktop app nativa (Tauri) sin dependencia del navegador
- Backtesting con walk-forward optimization integrado

### 3.2 Para Operadores SaaS (B2B)

| Característica             | Descripción                                          |
|----------------------------|------------------------------------------------------|
| Multi-tenant aislado       | Schema PostgreSQL por tenant con datos completamente separados |
| White-label configurable   | Branding, dominio propio, flujos de onboarding custom |
| API REST + WebSocket       | Integración con sistemas propios del cliente         |
| Billing por uso            | Modelos: por señal, por cuenta, por volumen, flat    |
| SLA garantizado            | 99.95% uptime con penalidades contractuales          |
| Auditoría inmutable        | Event Sourcing con trails completos para compliance  |

### 3.3 Para White-Label Partners

| Capacidad                   | Detalle                                                |
|-----------------------------|--------------------------------------------------------|
| Tenant isolation completa   | Cada partner opera como tenant independiente           |
| Configuración de brokers    | Cada partner define sus brokers habilitados            |
| Pipeline de señales custom  | Configurar reglas de filtrado y scoring propias        |
| Dashboard rebrandeable      | Next.js con theming por tenant                         |
| Facturación white-label     | Invoicing con logo y datos del partner                 |
| Soporte L1/L2 configurado   | Alertas y escalamiento por tenant                      |

---

## 4. Pilares Arquitectónicos

```
                    +===================================+
                    |     TNSVT V2 - PILARES            |
                    +===================================+
                    |                                   |
    +---------------+---------------+---------------+---+----------+
    |               |               |               |              |
    v               v               v               v              v
+-------+     +----------+    +----------+    +-----------+  +----------+
|MODULA-|     |ESCALABI- |    |SEGURIDAD |    |OBSERVA-   |  |RESILIENCIA|
|RIDAD  |     |LIDAD     |    |          |    |BILIDAD    |  |          |
+-------+     +----------+    +----------+    +-----------+  +----------+
|       |     |          |    |          |    |           |  |          |
|DDD    |     |K8s/Hori- |    |Zero Trust|    |OpenTele-  |  |Event     |
|Bounded|     |zontal    |    |mTLS      |    |metry      |  |Sourcing  |
|Context|     |Auto-     |    |RBAC      |    |Prometheus |  |CQRS      |
|Clean  |     |scaling   |    |Audit     |    |Grafana    |  |Circuit   |
|Arch   |     |NATS      |    |Logging   |    |Distributed|  |Breakers  |
|       |     |Federación|    |Encrypt   |    |Tracing    |  |Retry     |
+-------+     +----------+    +----------+    +-----------+  +----------+
```

### 4.1 Modularidad

**Objetivo:** Cada bounded context es un dominio independiente con su propio
ciclo de vida, despliegue y escalabilidad.

| Principio                | Implementación                                    |
|--------------------------|---------------------------------------------------|
| Bounded Contexts DDD     | 8 contextos con contratos explícitos              |
| Clean Architecture       | Domain → Application → Infrastructure (regla de dependencia) |
| Event-Driven             | NATS JetStream como backbone asincrónico          |
| Plugin Architecture      | Brokers como plugins con interfaz unificada        |
| API Gateway              | Traefik como punto único de entrada                |

### 4.2 Escalabilidad

| Estrategia               | Implementación                                    |
|--------------------------|---------------------------------------------------|
| Horizontal               | Kubernetes HPA por métricas custom                |
| Data Partitioning        | TimescaleDB por tenant + partición temporal        |
| Caching                  | Redis cluster con invalidación por evento          |
| Message Broker           | NATS JetStream con clustering y replicación       |
| Read/Write Separation    | CQRS con read replicas para consultas              |

### 4.3 Seguridad (Zero Trust)

```
+------------------------------------------------------------------+
|                    ZERO TRUST MODEL                               |
+------------------------------------------------------------------+
|                                                                   |
|  [Usuario]  --->  [Traefik]  --->  [Service Mesh]  --->  [Servicio]
|      |               |                  |                    |    |
|      v               v                  v                    v    |
|  +--------+    +-----------+      +-----------+        +--------+ |
|  | JWT +  |    | Rate      |      | mTLS      |        | AuthZ  | |
|  | OAuth2 |    | Limiting  |      | Between   |        | Check  | |
|  | + RBAC |    | WAF       |      | Services  |        | Per    | |
|  +--------+    | IP Filter |      +-----------+        | Request| |
|                +-----------+                           +--------+ |
+------------------------------------------------------------------+

Cada request es autenticado Y autorizado. No existe confianza implícita.
```

### 4.4 Observabilidad

| Pilar              | Herramienta          | Uso                                       |
|--------------------|----------------------|-------------------------------------------|
| Métricas           | Prometheus           | Latencia, throughput, errores, business KPIs |
| Logging            | Structured JSON      | Logs correlacionados por trace ID         |
| Tracing            | OpenTelemetry        | Distributed tracing end-to-end            |
| Dashboards         | Grafana              | Operaciones, negocio, tenant              |
| Alertas            | AlertManager         | PagerDuty/Slack por severidad             |
| Health Checks      | Custom + k8s probes  | Liveness, readiness, startup              |

---

## 5. Stack Tecnológico

| Capa                  | Tecnología              | Justificación                                              |
|-----------------------|-------------------------|------------------------------------------------------------|
| **Trading Core**      | Go 1.22+                | Baja latencia, concurrency nativa, binarios estáticos     |
| **AI/ML Pipeline**    | Python 3.12+            | Ecosistema ML, Ollama SDK, pandas, scikit-learn           |
| **Frontend Web**      | Next.js 15 (App Router) | SSR/SSG, React Server Components, streaming               |
| **Desktop App**       | Tauri 2.0               | Nativo, bajo consumo, sharing de lógica con Next.js        |
| **API Gateway**       | Traefik 3.0             | Auto-discovery con k8s, TLS automático, rate limiting      |
| **Message Broker**    | NATS JetStream          | Ultra-baja latencia, exactly-once, clustering nativo      |
| **Database OLTP**     | PostgreSQL 16           | ACID, JSON support, extensions ricas, madurez              |
| **Time-Series**       | TimescaleDB 2.x         | Hypertables, compression, continuous aggregates            |
| **Cache**             | Redis 7 (Cluster)       | Pub/Sub, Streams, TTL, Lua scripting                       |
| **LLM Self-hosted**   | Ollama                  | Sin dependencia externa, datos nunca salen del servidor    |
| **Container Orchest.**| Kubernetes 1.30+        | Orquestación estándar, auto-scaling, self-healing          |
| **IaC**               | Terraform + Helm        | Infraestructura como código, despliegues reproducibles     |
| **CI/CD**             | GitHub Actions          | Integración nativa, matrices de build, OIDC               |
| **Monitoring**        | Prometheus + Grafana    | Estándar de industria, coste cero, ecosistema enorme       |
| **Tracing**           | OpenTelemetry           | Vendor-neutral, standards W3C, integración nativa         |

### Arquitectura de Capas

```
+=========================================================================+
|                         CAPA DE PRESENTACIÓN                            |
|  +------------------+  +------------------+  +-----------------------+   |
|  | Next.js (Web)    |  | Tauri (Desktop)  |  | Mobile (futuro)       |   |
|  +------------------+  +------------------+  +-----------------------+   |
+=========================================================================+
                                    |
                                    v
+=========================================================================+
|                         CAPA DE API GATEWAY                              |
|  +--------------------------------------------------------------+       |
|  |                    Traefik 3.0                                |       |
|  |  [Rate Limit] [WAF] [TLS] [Auth] [Load Balancing] [mTLS]    |       |
|  +--------------------------------------------------------------+       |
+=========================================================================+
                                    |
                    +---------------+---------------+
                    v               v               v
+=========================================================================+
|                     CAPA DE MICROSERVICIOS                               |
|                                                                         |
|  +----------+  +----------+  +----------+  +----------+  +----------+  |
|  | Trading  |  | Risk     |  | Broker   |  | AI/ML    |  | Market   |  |
|  | Engine   |  | Manager  |  | Gateway  |  | Pipeline |  | Data     |  |
|  +----------+  +----------+  +----------+  +----------+  +----------+  |
|                                                                         |
|  +----------+  +----------+  +----------+  +----------+                |
|  | Platform |  | Notifi-  |  | Audit    |  | Billing  |                |
|  | Service  |  | cation   |  | Engine   |  | Service  |                |
|  +----------+  +----------+  +----------+  +----------+                |
+=========================================================================+
                                    |
                    +---------------+---------------+
                    v               v               v
+=========================================================================+
|                     CAPA DE DATOS Y MENSAJERÍA                          |
|                                                                         |
|  +----------------+  +----------------+  +---------------------------+  |
|  | NATS JetStream |  | Redis Cluster  |  | PostgreSQL + TimescaleDB  |  |
|  | (Event Bus)    |  | (Cache/PubSub) |  | (Persistencia)            |  |
|  +----------------+  +----------------+  +---------------------------+  |
+=========================================================================+
                                    |
                                    v
+=========================================================================+
|                     CAPA DE INFRAESTRUCTURA                             |
|                                                                         |
|  +----------------+  +----------------+  +---------------------------+  |
|  | Kubernetes     |  | Terraform/Helm |  | OpenTelemetry             |  |
|  | (Orquestación) |  | (IaC)          |  | (Observabilidad)          |  |
|  +----------------+  +----------------+  +---------------------------+  |
+=========================================================================+
```

---

## 6. Principios de Diseño

### 6.1 SOLID

| Principio                  | Aplicación en TNSVT V2                                  |
|----------------------------|----------------------------------------------------------|
| **S**ingle Responsibility | Cada microservicio tiene una y solo una razón para existir |
| **O**pen/Closed           | Brokers se agregan sin modificar el core (plugin pattern) |
| **L**iskov Substitution    | Todos los brokers implementan `BrokerPort` intercambiable |
| **I**nterface Segregation  | APIs internas finas: cada servicio expone solo lo necesario |
| **D**ependency Inversion   | Domain depende de abstractions, no de infraestructura    |

### 6.2 Clean Architecture

```
+----------------------------------------------------------+
|                  CLEAN ARCHITECTURE                       |
|                                                          |
|   +------------------+                                   |
|   |    DOMAIN        |  << Entidades, Value Objects,     |
|   |  (Core Puro)     |    Aggregates, Domain Events,     |
|   |  Go packages     |    Repository Interfaces          |
|   +------------------+                                   |
|          ^                                               |
|          |                                               |
|   +------------------+                                   |
|   |  APPLICATION     |  << Use Cases, Orchestration,     |
|   |  (Casos Uso)     |    DTOs, Command/Query Handlers   |
|   |  Go packages     |                                   |
|   +------------------+                                   |
|          ^                                               |
|          |                                               |
|   +------------------+                                   |
|   |  INFRASTRUCTURE  |  << DB, Cache, APIs Externas,     |
|   |  (Implementación)|    NATS, gRPC, HTTP Clients       |
|   |  Go + Python     |                                   |
|   +------------------+                                   |
|          ^                                               |
|          |                                               |
|   +------------------+                                   |
|   |  INTERFACE       |  << HTTP Handlers, gRPC Server,   |
|   |  (Delivery)      |    CLI, WebSocket Handlers        |
|   +------------------+                                   |
+----------------------------------------------------------+

REGLA: Las dependencias SIEMPRE apuntan hacia adentro (hacia Domain).
       Domain NUNCA depende de Infrastructure.
```

### 6.3 Domain-Driven Design

| Concepto DDD            | Implementación                                         |
|-------------------------|--------------------------------------------------------|
| Bounded Contexts        | 8 contextos claramente delimitados                     |
| Ubiquitous Language     | Glosario compartido por contexto documentado en CODEBASE |
| Aggregates              | OrderAggregate, AccountAggregate, SignalAggregate      |
| Value Objects           | Price, Quantity, Symbol, Money, TimeRange              |
| Domain Events           | OrderPlaced, RiskBreached, SignalScored                |
| Domain Services         | PriceCalculationService, RiskScoringService            |
| Repositories            | Interfaces en Domain, implementaciones en Infrastructure |

### 6.4 CQRS + Event Sourcing

```
                    COMANDO (Write Side)
                    ====================
   [API Request] ---> [Command Handler] ---> [Aggregate] ---> [Event Store]
                                                     |              |
                                                     v              v
                                              [Domain Logic]  [NATS Event]
                                                                    |
                                                                    v
                    QUERY (Read Side)
                    =================
   [API Request] ---> [Query Handler] ---> [Projection/View] <--- [Event Projector]
                           |
                           v
                    [Read Database (PostgreSQL)]
```

| Aspecto                 | Decisión                                                         |
|-------------------------|------------------------------------------------------------------|
| Event Store primario    | PostgreSQL con tabla `events` append-only                        |
| Snapshots               | Cada 100 eventos por aggregate                                    |
| Projections             | Async via NATS consumers, eventual consistency                   |
| Read models             | Materialized views optimizadas por query pattern                 |
| Replay                  | Soporte completo de rebuild desde eventos                         |

### 6.5 Zero Trust Security

| Capa                    | Mecanismo                                                        |
|-------------------------|------------------------------------------------------------------|
| Perímetro               | Traefik WAF + Rate Limiting + IP Filtering                       |
| Transporte              | mTLS entre todos los servicios (service mesh)                    |
| Identidad               | JWT (短期 15min) + Refresh tokens (7 días)                        |
| Autorización            | RBAC con roles: Admin, Manager, Trader, Viewer, API              |
| Datos                   | Encryption at rest (AES-256) + in transit (TLS 1.3)              |
| Auditoría               | Event Sourcing inmutable + audit log por cada acción             |
| Secretos                | HashiCorp Vault / Kubernetes Secrets con rotation automático     |
| Network                 | NetworkPolicies de Kubernetes, segmentación por namespace        |

---

## 7. Diferenciadores Competitivos

| Feature                | TradingView      | MetaTrader 5     | 3Commas           | **TNSVT V2**                |
|------------------------|------------------|-------------------|--------------------|-----------------------------|
| Multi-broker nativo    | Solo charting    | Solo MT5          | Limitado           | **5+ brokers con abstracción unificada** |
| Copy trading config    | No               | Limitado          | Básico             | **1:N configurable por cuenta (lote, SL, TP)** |
| AI Self-hosted         | No               | No                | No                 | **Ollama + RAG + scoring en tiempo real** |
| Event Sourcing         | No               | No                | No                 | **Auditoría inmutable desde Fase 1** |
| Latencia ejecución     | N/A              | 1-3s              | 0.5-2s             | **< 100ms (p99)**           |
| Open source core       | No               | Parcial           | No                 | **Core abierto, SaaS closed** |
| Desktop nativo         | Web only         | Windows only      | Web/mobile         | **Tauri (Win/Mac/Linux)**   |
| Backtesting avanzado   | Básico           | MQL5 Strategy     | Limitado           | **Walk-forward + optimización integrada** |
| White-label            | No               | Limitado          | No                 | **Multi-tenant completo**   |
| Self-hosted option     | No               | On-premise        | No                 | **Ollama + deployment on-premise** |
| Precios                | $12-60/mes       | Gratis (broker)   | $29-99/mes         | **Freemium + tiers escalables** |

### Ventaja Competitiva Clave

```
+=================================================================+
|                    VENTAJA COMPETITIVA                           |
+=================================================================+
|                                                                  |
|  1. OPEN AI LAYER: Ollama self-hosted = sin costo por token     |
|     + datos del usuario NUNCA salen del servidor                 |
|                                                                  |
|  2. COPY TRADING CONFIGURABLE: Un signal → N cuentas            |
|     con lotes, SL, TP, y filtros INDIVIDUALES por cuenta        |
|                                                                  |
|  3. MULTI-BROKER ABSTRACTION: Mismo código, mismas señales,     |
|     diferentes brokers. Swap sin cambiar nada.                   |
|                                                                  |
|  4. EVENT SOURCING: Auditoría completa, replay, compliance      |
|     desde el primer día de operación                             |
|                                                                  |
|  5. SUB-100ms EXECUTION: Go core + NATS + connection pooling    |
|     = ventanas de ejecución que la competencia no puede matchear |
+=================================================================+
```

---

## 8. Métricas de Éxito

### 8.1 Métricas Técnicas

| Métrica                           | 12 Meses       | 24 Meses       | 36 Meses       |
|-----------------------------------|----------------|----------------|----------------|
| Latencia p50 ejecución            | < 50ms         | < 30ms         | < 20ms         |
| Latencia p99 ejecución            | < 100ms        | < 75ms         | < 50ms         |
| Throughput (órdenes/segundo)      | 1,000          | 10,000         | 50,000         |
| Disponibilidad                    | 99.9%          | 99.95%         | 99.99%         |
| Tiempo de recuperación (RTO)      | < 30min        | < 15min        | < 5min         |
| Pérdida de datos (RPO)            | < 5min         | < 1min         | < 30s (CDC)    |
| Cobertura de tests                | 70%            | 85%            | 90%            |
| Lead time (cambio a producción)   | < 1 semana     | < 2 días       | < 1 día        |
| Deploy frequency                  | Semanal        | Diaria         | Múltiples/día  |
| MTBF (Mean Time Between Failures) | 7 días         | 30 días        | 90 días        |

### 8.2 Métricas de Negocio

| Métrica                           | 12 Meses       | 24 Meses       | 36 Meses       |
|-----------------------------------|----------------|----------------|----------------|
| Usuarios registrados              | 5,000          | 25,000         | 100,000        |
| Usuarios activos mensuales (MAU)  | 1,000          | 8,000          | 40,000         |
| Usuarios paying                   | 200            | 2,000          | 15,000         |
| MRR (Monthly Recurring Revenue)   | $10K           | $100K          | $500K          |
| ARR (Annual Recurring Revenue)    | $120K          | $1.2M          | $6M            |
| Churn rate mensual                | < 8%           | < 5%           | < 3%           |
| NPS (Net Promoter Score)          | > 30           | > 50           | > 70           |
| Brokers activos integrados        | 3              | 5              | 7+             |
| Señales ejecutadas/día            | 500            | 5,000          | 50,000         |
| Volumen mensual (USD)             | $5M            | $50M           | $500M          |

### 8.3 Métricas Operacionales

| Métrica                           | 12 Meses       | 24 Meses       | 36 Meses       |
|-----------------------------------|----------------|----------------|----------------|
| Cobertura de observabilidad       | 80%            | 95%            | 99%            |
| Alertas falsas positivas          | < 20%          | < 10%          | < 5%           |
| Mean Time to Detection (MTTD)     | < 10min        | < 5min         | < 2min         |
| Mean Time to Resolution (MTTR)    | < 2h           | < 30min        | < 15min        |
| Infraestructura como código       | 80%            | 95%            | 100%           |
| Secretos rotados automáticamente  | 50%            | 90%            | 100%           |
| Compliance audit readiness        | Básico         | SOC2 Type I    | SOC2 Type II   |

---

## 9. Restricciones y Supuestos

### 9.1 Restricciones

| #  | Restricción                                    | Impacto                                            |
|----|------------------------------------------------|----------------------------------------------------|
| R1 | Equipo actual: 2-4 desarrolladores             | Fases incrementales obligatorias, MVP primero      |
| R2 | Presupuesto infra limitado en Fase 1            | Empezar con VPS, migrar a K8s cloud en Fase 2      |
| R3 | Compliance regulatorio por jurisdicción         | KYC/AML diferido a Fase 4, focus en no-EEUU inicial|
| R4 | Latencia de red entre regiones                  | Deploy multi-region diferido a Fase 3              |
| R5 | Licenciamiento de brokers                        | Algunos brokers requieren acuerdos de partners      |
| R6 | GPU para Ollama                                 | Ollama funciona sin GPU (CPU inference) en Fase 1  |
| R7 | Base de usuarios actual migra de V1              | Script de migración obligatorio antes de Fase 2    |

### 9.2 Supuestos

| #  | Supuesto                                        | Validación Requerida                              |
|----|-------------------------------------------------|---------------------------------------------------|
| S1 | Los usuarios aceptarán modelo SaaS sobre V1     | Validar con encuesta a base actual (50 usuarios)  |
| S2 | NATS JetStream soporta el throughput requerido  | Benchmark: 1M msgs/sec en hardware provisionado   |
| S3 | Ollama produce suficiente calidad para scoring   | Backtest con datos históricos reales               |
| S4 | MT5 bridge se puede estabilizar para < 100ms    | PoC con bridge custom en Go (no Python)            |
| S5 | TimescaleDB maneja 10B+ rows de tick data       | Benchmark con datos de 5 años de EURUSD 1min       |
| S6 | El mercado acepta pricing por signals            | Análisis competitivo de pricing                   |
| S7 | K8s es overkill para Fase 1                     | Confirmar: Docker Compose para MVP, K8s en Fase 2 |

### 9.3 Supuestos de Negocio

| Supuesto                           | Validación                                  | Riesgo si falla        |
|------------------------------------|---------------------------------------------|------------------------|
| Mercado crece 15% anual            | Informe Mordor Intelligence 2025            | Mercado saturado       |
| Users愿意 pagar por AI signals   | Benchmark 3Commas, Cryptohopper             | Pricing inviable       |
| Brokers permiten API trading       | Documentación pública + acuerdos            | Sin ejecución = sin producto |
| Copy trading es demanda real       | Reddit, Telegram groups, encuestas          | Feature sin uso        |
| Latencia < 100ms es diferenciador  | Análisis de competidores                    | Feature irrelevante    |

---

## Aprobaciones

| Rol                  | Nombre           | Fecha       | Estado    |
|----------------------|------------------|-------------|-----------|
| CTO                  | ________________ | ____/__/__ | Pendiente |
| Lead Architect       | ________________ | ____/__/__ | Pendiente |
| Product Owner        | ________________ | ____/__/__ | Pendiente |
| Security Lead        | ________________ | ____/__/__ | Pendiente |

---

*Documento generado como parte del proceso de arquitectura de TNSVT V2.*
*Proximo documento: [01-ARCHITECTURE-OVERVIEW.md](01-ARCHITECTURE-OVERVIEW.md)*
