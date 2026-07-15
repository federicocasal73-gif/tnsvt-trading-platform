# TNSVT V2 — Catálogo de Servicios

**Versión:** 2.0  
**Fecha:** 14 de Julio de 2026  
**Clasificación:** Confidencial — Uso Interno  
**Estado:** Aprobado por Arquitectura  

---

## Índice

1. [Resumen del Catálogo](#1-resumen-del-católogo)
2. [Trading Context (8 servicios)](#2-trading-context)
3. [Risk Context (4 servicios)](#3-risk-context)
4. [Broker Context (6 servicios)](#4-broker-context)
5. [AI/ML Context (8 servicios)](#5-aiml-context)
6. [Market Data Context (4 servicios)](#6-market-data-context)
7. [Platform Context (8 servicios)](#7-platform-context)
8. [Notification Context (4 servicios)](#8-notification-context)
9. [Audit/Billing Context (6 servicios)](#9-auditbilling-context)
10. [Broker Abstraction Layer](#10-broker-abstraction-layer)
11. [Matriz de Dependencias](#11-matriz-de-dependencias)

---

## 1. Resumen del Catálogo

### Conteo por Dominio

| Dominio           | Servicios | Lenguaje Principal | Puerto Rango   |
|-------------------|-----------|---------------------|-----------------|
| Trading           | 8         | Go                  | 8080-8087       |
| Risk              | 4         | Go                  | 8090-8093       |
| Broker            | 6         | Go                  | 8100-8105       |
| AI/ML             | 8         | Python              | 8200-8207       |
| Market Data       | 4         | Go                  | 8300-8303       |
| Platform          | 8         | Go                  | 8400-8407       |
| Notification      | 4         | Go                  | 8500-8503       |
| Audit/Billing     | 6         | Go                  | 8600-8605       |
| **TOTAL**         | **48**    |                     |                 |

### Conteo por Lenguaje

```
Go     ████████████████████████████████████████  40 servicios (83%)
Python ████████████                               8 servicios (17%)

Justificación:
- Go: Baja latencia, concurrency, binarios estáticos, ideal para microservicios de trading
- Python: Ecosistema ML, Ollama SDK, pandas, scikit-learn, ideal para AI/ML pipeline
```

### SLA Targets por Servicio

```
Tier 1 (CRÍTICO — 99.99%):     Trading Engine, Risk Manager, Broker Gateway
Tier 2 (ALTO — 99.95%):        Order Executor, Auth Service, Data Ingestion
Tier 3 (MEDIO — 99.9%):        AI Scoring, Notification, Billing, Admin
Tier 4 (BAJO — 99.5%):         Template Engine, Historical, Report Generator
```

---

## 2. Trading Context

### T-01: Trading Engine

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `trading-engine`                                            |
| **Descripción**      | Orquestador principal de órdenes. Recibe señales, valida    |
|                      | reglas de negocio, coordina con Risk y Broker.              |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8080                                                        |
| **Puerto gRPC**      | 9080                                                        |
| **SLA Target**       | 99.99%                                                      |
| **Latencia Objetivo**| p99 < 50ms para decisiones de routing                       |
| **Dependencias**     | PostgreSQL (events), NATS JetStream, Redis (cache)          |
| **Recursos (k8s)**   | CPU: 2-4 cores, Memoria: 2-4GB, Réplicas: 3+               |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `trading.signal.scored`            | `trading.order.place`                 |
| `risk.check.approved`              | `trading.order.placed`                |
| `risk.check.rejected`              | `trading.order.cancelled`             |
| `broker.execution.report`          | `trading.position.updated`            |
| `marketdata.tick.*`                | `trading.state.changed`               |

**Responsabilidades:**
- Recibir señales scoreadas del AI/ML pipeline
- Coordinar validación de riesgo antes de ejecución
- Enviar órdenes al Broker Gateway
- Mantener state machine de órdenes (Pending→Submitted→Filled/Rejected/Cancelled)
- Gestionar copy trading routing (1 señal → N cuentas)
- Publicar eventos al Event Store (Audit Engine)

---

### T-02: Order Executor

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `order-executor`                                            |
| **Descripción**      | Ejecutor de bajo nivel que maneja la comunicación directa   |
|                      | con el Broker Gateway para fills, partial fills, cancels.   |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8081                                                        |
| **Puerto gRPC**      | 9081                                                        |
| **SLA Target**       | 99.99%                                                      |
| **Latencia Objetivo**| p99 < 30ms para submission                                 |
| **Dependencias**     | NATS JetStream, Redis (connection pool state)              |
| **Recursos (k8s)**   | CPU: 1-2 cores, Memoria: 1-2GB, Réplicas: 3+               |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `trading.order.place`              | `trading.order.submitted`             |
| `broker.execution.report`          | `trading.order.fill`                  |
| `broker.execution.error`           | `trading.order.rejection`             |

**Responsabilidades:**
- Enviar órdenes al broker correcto via Broker Gateway
- Manejar respuestas asincrónicas (fills, partial fills)
- Implementar retry con backoff exponencial para submissions
- Mantener connection pool por broker/account
- Monitorear timeouts de execution (abortar si > 5s sin respuesta)

---

### T-03: Copy Trading Router

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `copy-trading-router`                                       |
| **Descripción**      | Rutea señales del master a múltiples cuentas follower con   |
|                      | configuración individual (lote, SL, TP, filtros).           |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8082                                                        |
| **Puerto gRPC**      | 9082                                                        |
| **SLA Target**       | 99.95%                                                      |
| **Latencia Objetivo**| p99 < 20ms para routing decision                            |
| **Dependencias**     | PostgreSQL (config), NATS JetStream, Redis (cache)          |
| **Recursos (k8s)**   | CPU: 1-2 cores, Memoria: 1-2GB, Réplicas: 2+               |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `trading.order.filled`             | `trading.copy.signal`                 |
| `trading.signal.received`          | `trading.order.place` (×N cuentas)    |

**Responsabilidades:**
- Recibir señal del master account
- Consultar configuración de copy para cada follower account
- Aplicar transformaciones: lot scaling, SL/TP ajustados, filtros
- Generar N órdenes (una por cada follower account que aplique)
- Publicar evento CopyTradeExecuted con resultado aggregate
- Mantener consistencia: si master cancela, cancelar en followers

---

### T-04: Signal Scheduler

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `signal-scheduler`                                          |
| **Descripción**      | Programa y gestiona la ejecución de estrategias periódicas, |
|                      | cron jobs de señales, y time-based triggers.                 |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8083                                                        |
| **SLA Target**       | 99.9%                                                       |
| **Dependencias**     | PostgreSQL (cron definitions), NATS JetStream               |
| **Recursos (k8s)**   | CPU: 0.5 cores, Memoria: 512MB, Réplicas: 2 (leader election) |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `trading.scheduler.trigger`        | `trading.signal.received`             |

**Responsabilidades:**
- Ejecutar estrategias según cron schedule (ej: check cada H1)
- Gestinar time-based triggers (ej: close antes de news)
- Leader election para evitar ejecución duplicada
- Mantener historial de ejecuciones programadas
- Soporte para timezone por tenant

---

### T-05: Position Manager

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `position-manager`                                          |
| **Descripción**      | Gestiona el ciclo de vida de posiciones abiertas: P&L       |
|                      | unrealized, trailing stops, breakeven management.           |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8084                                                        |
| **Puerto gRPC**      | 9084                                                        |
| **SLA Target**       | 99.95%                                                      |
| **Dependencias**     | PostgreSQL, NATS JetStream, Redis (P&L cache)              |
| **Recursos (k8s)**   | CPU: 1-2 cores, Memoria: 1-2GB, Réplicas: 2+               |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `trading.order.filled`             | `trading.position.updated`            |
| `marketdata.tick.*`                | `trading.position.stop_triggered`     |
| `trading.position.modify`          | `trading.position.closed`             |

**Responsabilidades:**
- Calcular P&L unrealized en tiempo real (streaming de precios)
- Implementar trailing stop loss dinámico
- Gestionar move-to-breakeven automático
- Detectar y ejecutar stop loss / take profit
- Mantener equity curve por account

---

### T-06: Strategy Engine

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `strategy-engine`                                           |
| **Descripción**      | Motor de estrategias que permite definir reglas de trading  |
|                      | personalizadas mediante DSL o configuración YAML/JSON.      |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8085                                                        |
| **Puerto gRPC**      | 9085                                                        |
| **SLA Target**       | 99.9%                                                       |
| **Dependencias**     | NATS JetStream, PostgreSQL (strategy definitions)          |
| **Recursos (k8s)**   | CPU: 1-2 cores, Memoria: 1-2GB, Réplicas: 2+               |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `marketdata.ohlc.*`                | `trading.signal.received`             |
| `trading.position.updated`         | `trading.strategy.alert`              |
| `ai.regime.changed`                |                                       |

**Responsabilidades:**
- Evaluar condiciones de entrada/salida según reglas definidas
- Soporte para indicadores técnicos (SMA, EMA, RSI, MACD, BB, ATR)
- Modo backtesting con datos históricos
- Modo paper trading (simulación sin ejecución real)
- Gestión de versiones de estrategias

---

### T-07: Backtesting Service

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `backtesting-service`                                       |
| **Descripción**      | Servicio de backtesting con walk-forward optimization,      |
|                      | Monte Carlo simulation, y métricas de performance.          |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8086                                                        |
| **SLA Target**       | 99.5%                                                       |
| **Dependencias**     | TimescaleDB (histórico), PostgreSQL                         |
| **Recursos (k8s)**   | CPU: 2-8 cores (burst), Memoria: 4-16GB, Réplicas: 1-3     |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `trading.backtest.request`         | `trading.backtest.result`             |

**Responsabilidades:**
- Ejecutar backtesting sobre datos históricos (hasta 10 años)
- Walk-forward optimization (in-sample/out-of-sample)
- Monte Carlo simulation (1000+ runs)
- Métricas: Sharpe, Sortino, Max Drawdown, Win Rate, Profit Factor
- Exportar resultados como HTML report o JSON

---

### T-08: Trade Reconciler

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `trade-reconciler`                                          |
| **Descripción**      | Reconcilia estados entre el sistema interno y el broker.    |
|                      | Detecta discrepancias y ejecuta correcciones automáticas.   |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8087                                                        |
| **SLA Target**       | 99.9%                                                       |
| **Dependencias**     | PostgreSQL, NATS JetStream, Broker Gateway                  |
| **Recursos (k8s)**   | CPU: 0.5 cores, Memoria: 512MB, Réplicas: 1 (cron)         |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `broker.account.snapshot`          | `trading.reconciliation.discrepancy`  |
| `trading.reconciliation.request`   | `trading.reconciliation.completed`    |

**Responsabilidades:**
- Ejecutar reconciliación cada 5 minutos (cron)
- Comparar posiciones internas vs. broker
- Detectar órdenes filladas no registradas internamente
- Generar alertas por discrepancias
- Ejecutar correcciones automáticas (close orphan positions)

---

## 3. Risk Context

### R-01: Risk Manager

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `risk-manager`                                              |
| **Descripción**      | Validador de riesgo pre-ejecución. Evalúa exposure, drawdown,|
|                      | y reglas configurables antes de aprobar/rechazar órdenes.    |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8090                                                        |
| **Puerto gRPC**      | 9090                                                        |
| **SLA Target**       | 99.99%                                                      |
| **Latencia Objetivo**| p99 < 10ms para decisiones de riesgo                        |
| **Dependencias**     | PostgreSQL (limits), Redis (exposure cache), NATS JetStream |
| **Recursos (k8s)**   | CPU: 2-4 cores, Memoria: 2-4GB, Réplicas: 3+               |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `risk.check.request`               | `risk.check.approved`                 |
| `trading.order.filled`             | `risk.check.rejected`                 |
| `trading.position.updated`         | `risk.exposure.updated`               |
| `marketdata.tick.*`                | `risk.breach.detected`                |

**Responsabilidades:**
- Validar cada orden contra reglas de riesgo configurables
- Calcular exposure en tiempo real por account/symbol/direction
- Enforce max drawdown (daily, weekly, monthly)
- Enforce max position size (% del equity)
- Enforce max órdenes por hora/día
- Circuit breaker: pausar trading si umbrales se exceden
- Risk/Reward ratio mínimo requerido

---

### R-02: Risk Monitor

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `risk-monitor`                                              |
| **Descripción**      | Monitoreo continuo de posiciones abiertas para detección    |
|                      | temprana de drawdown excesivo y exposición peligrosa.       |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8091                                                        |
| **SLA Target**       | 99.95%                                                      |
| **Dependencias**     | Redis (positions cache), NATS JetStream, PostgreSQL         |
| **Recursos (k8s)**   | CPU: 1 core, Memoria: 1GB, Réplicas: 2                     |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `marketdata.tick.*`                | `risk.alert.drawdown`                 |
| `trading.position.updated`         | `risk.alert.exposure`                 |
| `risk.exposure.updated`            | `risk.breach.detected`                |

**Responsabilidades:**
- Calcular drawdown en tiempo real por account
- Alertar si drawdown supera umbral (warning: 5%, critical: 10%)
- Calcular exposure neta por dirección (net long/short)
- Detectar correlación excesiva entre posiciones
- Publicar métricas de riesgo para dashboards

---

### R-03: Circuit Breaker

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `circuit-breaker`                                           |
| **Descripción**      | Implementa circuit breakers configurables que pausan el     |
|                      | trading automáticamente ante condiciones adversas.          |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8092                                                        |
| **SLA Target**       | 99.99%                                                      |
| **Dependencias**     | NATS JetStream, Redis (state), PostgreSQL (config)          |
| **Recursos (k8s)**   | CPU: 0.5 cores, Memoria: 512MB, Réplicas: 2                |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `risk.breach.detected`             | `risk.circuit.open`                   |
| `risk.alert.drawdown`              | `risk.circuit.half_open`              |
| `risk.alert.exposure`              | `risk.circuit.closed`                 |
| `trading.order.rejected`           | `risk.circuit.force_stop`             |

**Responsabilidades:**
- Estados: Closed → Open → Half-Open → Closed
- Configuración por account: drawdown threshold, loss streak, time window
- Auto-reset después de cooldown period (configurable)
- Forzar close de todas las posiciones en circuit open (opcional)
- Publicar estado del circuit breaker para UI

---

### R-04: Exposure Calculator

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `exposure-calculator`                                       |
| **Descripción**      | Calcula métricas de exposición agregada: por moneda, sector,|
|                      | dirección, y correlación entre posiciones.                  |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8093                                                        |
| **Puerto gRPC**      | 9093                                                        |
| **SLA Target**       | 99.9%                                                       |
| **Dependencias**     | Redis (real-time positions), PostgreSQL (historical)        |
| **Recursos (k8s)**   | CPU: 1 core, Memoria: 1GB, Réplicas: 1                     |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `trading.position.updated`         | `risk.exposure.updated`               |
| `marketdata.tick.*`                | `risk.exposure.snapshot`              |

**Responsabilidades:**
- Calcular exposure por currency pair
- Calcular net exposure (long - short)
- Calcular notional value exposure
- Detectar concentración excesiva en un activo
- Calcular VaR (Value at Risk) simplified

---

## 4. Broker Context

### B-01: Broker Gateway

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `broker-gateway`                                            |
| **Descripción**      | Gateway unificado que enruta órdenes al adapter correcto.    |
|                      | Expone interfaz BrokerPort y gestiona connection pools.     |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8100                                                        |
| **Puerto gRPC**      | 9100                                                        |
| **SLA Target**       | 99.99%                                                      |
| **Latencia Objetivo**| p99 < 20ms para routing                                    |
| **Dependencias**     | Redis (pool state), NATS JetStream, todos los adapters      |
| **Recursos (k8s)**   | CPU: 2 cores, Memoria: 2GB, Réplicas: 3                    |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `broker.execute.order`             | `broker.order.sent`                   |
| `broker.account.sync`              | `broker.execution.report`             |
| `broker.account.snapshot`          | `broker.execution.error`              |

**Responsabilidades:**
- Routear órdenes al adapter correcto (por account config)
- Mantener connection pool por broker (warm connections)
- Load balancing entre múltiples conexiones al mismo broker
- Circuit breaker por adapter (si adapter falla, failover a backup)
- Rate limiting por broker (respetar API limits)

---

### B-02: MT5 Adapter

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `mt5-adapter`                                               |
| **Descripción**      | Adaptador para MetaTrader 5 via bridge TCP/REST.            |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8101                                                        |
| **Puerto gRPC**      | 9101                                                        |
| **SLA Target**       | 99.95%                                                      |
| **Dependencias**     | MT5 Terminal (bridge), NATS JetStream                       |
| **Recursos (k8s)**   | CPU: 1 core, Memoria: 1GB, Réplicas: 2                     |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `broker.execute.order`             | `broker.mt5.execution.report`         |
| `broker.mt5.account.sync`          | `broker.account.snapshot`             |

**Responsabilidades:**
- Conectar con MT5 Terminal via bridge (TCP socket)
- Enviar órdenes MT5 (market, limit, stop, modify, close)
- Recibir execution reports y traducir a formato interno
- Heartbeat cada 5s con MT5 terminal
- Manejar reconexión automática

---

### B-03: cTrader Adapter

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `ctrader-adapter`                                           |
| **Descripción**      | Adaptador para cTrader via Open API (protobuf/gRPC).        |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8102                                                        |
| **SLA Target**       | 99.95%                                                      |
| **Dependencias**     | cTrader Open API, NATS JetStream                            |
| **Recursos (k8s)**   | CPU: 1 core, Memoria: 1GB, Réplicas: 2                     |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `broker.execute.order`             | `broker.ctrader.execution.report`     |
| `broker.ctrader.account.sync`      | `broker.account.snapshot`             |

**Responsabilidades:**
- Autenticación OAuth2 con cTrader Open API
- Envío de órdenes via protobuf messages
- Streaming de precios en tiempo real
- Manejo de spot metals, energies, indices
- Account management (balance, equity, margin)

---

### B-04: Binance Adapter

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `binance-adapter`                                           |
| **Descripción**      | Adaptador para Binance Spot y Futures via REST + WebSocket. |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8103                                                        |
| **SLA Target**       | 99.95%                                                      |
| **Dependencias**     | Binance API (REST+WS), NATS JetStream                      |
| **Recursos (k8s)**   | CPU: 1 core, Memoria: 1GB, Réplicas: 2                     |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `broker.execute.order`             | `broker.binance.execution.report`     |
| `broker.binance.account.sync`      | `broker.account.snapshot`             |

**Responsabilidades:**
- Firma HMAC-SHA256 para endpoints autenticados
- Rate limiting: 1200 requests/min (trade), 1200 requests/min (market)
- WebSocket para user data stream (execution reports)
- Soporte para Spot y USDT-M Futures
- Manejo de LOT_SIZE, PRICE_FILTER, MIN_NOTIONAL filters

---

### B-05: Bybit Adapter

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `bybit-adapter`                                             |
| **Descripción**      | Adaptador para Bybit via REST API v5 + WebSocket.           |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8104                                                        |
| **SLA Target**       | 99.95%                                                      |
| **Dependencias**     | Bybit API v5 (REST+WS), NATS JetStream                     |
| **Recursos (k8s)**   | CPU: 1 core, Memoria: 1GB, Réplicas: 2                     |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `broker.execute.order`             | `broker.bybit.execution.report`       |
| `broker.bybit.account.sync`        | `broker.account.snapshot`             |

**Responsabilidades:**
- API v5 unificada (Spot, Linear, Inverse, Options)
- HMAC-SHA256 signing
- WebSocket private channel para execution reports
- Manejo de trigger orders (conditional orders)
- Rate limit management por category

---

### B-06: IBKR Adapter

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `ibkr-adapter`                                              |
| **Descripción**      | Adaptador para Interactive Brokers via TWS API (TCP/JSON).  |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8105                                                        |
| **Puerto TWS**       | 7497 (paper) / 7496 (live)                                  |
| **SLA Target**       | 99.95%                                                      |
| **Dependencias**     | TWS/Gateway, NATS JetStream                                 |
| **Recursos (k8s)**   | CPU: 1 core, Memoria: 1GB, Réplicas: 2                     |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `broker.execute.order`             | `broker.ibkr.execution.report`        |
| `broker.ibkr.account.sync`         | `broker.account.snapshot`             |

**Responsabilidades:**
- Conexión TCP directa con TWS API o IB Gateway
- ReqMktData / reqHistoricalData streaming
- OrderStatus / ExecDetails callbacks
- Manejo de smart routing (IBKR auto-route)
- Multi-asset: stocks, options, futures, forex

---

## 5. AI/ML Context

### A-01: Signal Scorer

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `signal-scorer`                                             |
| **Descripción**      | Evalúa señales de trading y asigna score de confianza       |
|                      | (0-100%) usando múltiples indicadores y Ollama LLM.         |
| **Lenguaje**         | Python 3.12+                                                |
| **Puerto HTTP**      | 8200                                                        |
| **SLA Target**       | 99.9%                                                       |
| **Latencia Objetivo**| p99 < 500ms para scoring                                    |
| **Dependencias**     | Ollama Gateway, Redis (model cache), NATS JetStream         |
| **Recursos (k8s)**   | CPU: 2 cores, Memoria: 4GB, Réplicas: 2                     |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `trading.signal.received`          | `trading.signal.scored`               |
| `marketdata.ohlc.*`                | `ai.scoring.model.updated`            |

**Responsabilidades:**
- Recibir señal raw + contexto de mercado
- Extraer features: technical indicators, pattern recognition
- Consultar Ollama LLM para análisis cualitativo
- Combinar scores cuantitativos + cualitativos
- Publicar señal scoreada con nivel de confianza
- Mantener historial de accuracy por modelo

---

### A-02: Regime Detector

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `regime-detector`                                           |
| **Descripción**      | Detecta el régimen actual del mercado: trending, ranging,   |
|                      | volatile, low-vol. Ajusta parámetros de trading dinámicos.  |
| **Lenguaje**         | Python 3.12+                                                |
| **Puerto HTTP**      | 8201                                                        |
| **SLA Target**       | 99.9%                                                       |
| **Dependencias**     | TimescaleDB (histórico), Ollama, NATS JetStream             |
| **Recursos (k8s)**   | CPU: 2 cores, Memoria: 4GB, Réplicas: 2                     |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `marketdata.ohlc.*`                | `ai.regime.changed`                   |
| `trading.position.updated`         | `ai.regime.snapshot`                  |

**Responsabilidades:**
- Clasificar mercado en 4 regimes: Trending, Ranging, Volatile, Low-Vol
- Usar HMM (Hidden Markov Model) + ATR para clasificación
- Actualizar clasificación cada 15 minutos
- Publicar cambios de régimen (event-driven)
- Ajustar parámetros de risk por régimen

---

### A-03: Anomaly Detector

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `anomaly-detector`                                          |
| **Descripción**      | Detecta anomalías en precios, volumes, y spreads que       |
|                      | podrían indicar flash crashes, manipulation, o data errors. |
| **Lenguaje**         | Python 3.12+                                                |
| **Puerto HTTP**      | 8202                                                        |
| **SLA Target**       | 99.9%                                                       |
| **Dependencias**     | Redis (real-time buffer), NATS JetStream, TimescaleDB       |
| **Recursos (k8s)**   | CPU: 2 cores, Memoria: 4GB, Réplicas: 2                     |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `marketdata.tick.*`                | `ai.anomaly.detected`                 |
| `marketdata.ohlc.*`                | `ai.anomaly.resolved`                 |

**Responsabilidades:**
- Detectar spikes de precio (> 3σ en 1 minuto)
- Detectar volumen anómalo (> 10x average)
- Detectar spread widening anómalo
- Clasificar anomalías: Flash Crash, Manipulation, Data Error
- Publicar alertas de anomalía a Risk Manager

---

### A-04: RAG Engine

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `rag-engine`                                                |
| **Descripción**      | Motor Retrieval-Augmented Generation que permite a los LLMs |
|                      | acceder a conocimiento de mercado, fundamentos, y news.     |
| **Lenguaje**         | Python 3.12+                                                |
| **Puerto HTTP**      | 8203                                                        |
| **SLA Target**       | 99.5%                                                       |
| **Dependencias**     | Ollama Gateway, PostgreSQL (vector store), MinIO (docs)     |
| **Recursos (k8s)**   | CPU: 2 cores, Memoria: 4GB, Réplicas: 1                     |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `ai.rag.query`                     | `ai.rag.response`                     |
| `platform.news.ingested`           |                                       |

**Responsabilidades:**
- Indexar documentos financieros (earnings, reports, news)
- Embedding con modelo local (nomic-embed o similar)
- Vector search en PostgreSQL (pgvector)
- Context window management para Ollama
- Cache de embeddings para queries frecuentes

---

### A-05: LLM Gateway

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `llm-gateway`                                               |
| **Descripción**      | Gateway unificado hacia Ollama. Gestiona modelos, rate      |
|                      | limiting, caching, y routing entre modelos.                 |
| **Lenguaje**         | Python 3.12+                                                |
| **Puerto HTTP**      | 8204                                                        |
| **Puerto gRPC**      | 9204                                                        |
| **SLA Target**       | 99.9%                                                       |
| **Dependencias**     | Ollama (local), Redis (cache), NATS JetStream               |
| **Recursos (k8s)**   | CPU: 2 cores, Memoria: 4GB, Réplicas: 2                     |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `ai.llm.request`                   | `ai.llm.response`                     |

**Responsabilidades:**
- Unified API para múltiples modelos Ollama
- Model selection: Llama3 (general), CodeLlama (scripts), Phi3 (fast)
- Response caching (Redis TTL 1h para queries idénticas)
- Streaming responses (SSE) para UI
- Token counting y rate limiting por tenant
- GPU/CPU routing inteligente

---

### A-06: Feature Engineering

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `feature-engineering`                                       |
| **Descripción**      | Extrae y calcula features para los modelos de ML:           |
|                      | technical indicators, statistics, patterns.                  |
| **Lenguaje**         | Python 3.12+                                                |
| **Puerto HTTP**      | 8205                                                        |
| **SLA Target**       | 99.9%                                                       |
| **Dependencias**     | TimescaleDB (OHLC data), Redis (feature cache)              |
| **Recursos (k8s)**   | CPU: 2 cores, Memoria: 4GB, Réplicas: 2                     |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `marketdata.ohlc.*`                | `ai.features.updated`                 |
| `ai.feature.request`               | `ai.feature.response`                 |

**Responsabilidades:**
- Calcular 50+ technical indicators (SMA, EMA, RSI, MACD, BB, ATR, ADX, etc.)
- Estadísticas de rolling windows (mean, std, skew, kurtosis)
- Pattern recognition (candlestick patterns)
- Feature store en Redis para acceso sub-ms
- Normalización y scaling de features

---

### A-07: Model Trainer

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `model-trainer`                                             |
| **Descripción**      | Entrena y valida modelos de ML con datos históricos.        |
|                      | Gestiona experiment tracking y model versioning.            |
| **Lenguaje**         | Python 3.12+                                                |
| **Puerto HTTP**      | 8206                                                        |
| **SLA Target**       | 99.5%                                                       |
| **Dependencias**     | TimescaleDB, MinIO (model artifacts), MLflow               |
| **Recursos (k8s)**   | CPU: 4-8 cores, Memoria: 8-16GB, GPU opcional, Réplicas: 1 |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `ai.training.request`              | `ai.training.completed`               |
| `ai.model.deploy`                  | `ai.model.deployed`                   |

**Responsabilidades:**
- Training pipelines: random forest, XGBoost, LSTM, transformer
- Walk-forward validation
- Hyperparameter tuning (Optuna)
- Model registry (version, metrics, artifacts)
- A/B testing entre modelos versionados

---

### A-08: Backtesting AI

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `backtesting-ai`                                            |
| **Descripción**      | Backtesting específico para estrategias AI/ML. Valida       |
|                      | modelos contra datos out-of-sample.                         |
| **Lenguaje**         | Python 3.12+                                                |
| **Puerto HTTP**      | 8207                                                        |
| **SLA Target**       | 99.5%                                                       |
| **Dependencias**     | TimescaleDB, Model Trainer, MinIO                           |
| **Recursos (k8s)**   | CPU: 4-8 cores, Memoria: 8GB, Réplicas: 1                  |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `ai.backtest.request`              | `ai.backtest.result`                  |

**Responsabilidades:**
- Validar modelos ML contra datos no vistos
- Métricas: accuracy, precision, recall, F1, ROI, Sharpe
- Walk-forward AI-specific (retrain cada N periods)
- Feature importance analysis
- Model drift detection

---

## 6. Market Data Context

### M-01: Data Ingestion

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `data-ingestion`                                            |
| **Descripción**      | Ingesta de datos de mercado en tiempo real desde múltiples  |
|                      | fuentes: exchanges, brokers, proveedores de datos.          |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8300                                                        |
| **Puerto gRPC**      | 9300                                                        |
| **SLA Target**       | 99.95%                                                      |
| **Dependencias**     | NATS JetStream, Redis (connection state)                    |
| **Recursos (k8s)**   | CPU: 2 cores, Memoria: 2GB, Réplicas: 2                     |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `marketdata.source.subscribe`      | `marketdata.tick.raw`                 |
| `marketdata.source.request`        | `marketdata.ohlc.raw`                 |

**Responsabilidades:**
- Conectar con múltiples fuentes de datos simultáneamente
- WebSocket clients para feeds en tiempo real
- Normalización de formato (cada fuente tiene formato propio)
- Heartbeat y reconexión automática
- Buffer en memoria para burst handling

---

### M-02: Data Aggregator

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `data-aggregator`                                           |
| **Descripción**      | Agrega ticks en OHLC candles en múltiples timeframes.       |
|                      | Calcula indicadores derivados en tiempo real.               |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8301                                                        |
| **SLA Target**       | 99.95%                                                      |
| **Dependencias**     | NATS JetStream, TimescaleDB (OHLC storage)                  |
| **Recursos (k8s)**   | CPU: 2 cores, Memoria: 2GB, Réplicas: 2                     |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `marketdata.tick.raw`              | `marketdata.ohlc.<symbol>.<tf>`       |
|                                    | `marketdata.tick.<symbol>`            |

**Responsabilidades:**
- Construir candles: M1, M5, M15, M30, H1, H4, D1, W1, MN
- Manejar candle updates (forming candle)
- Publicar candle completado (event-driven)
- Calcular VWAP intra-candle
- Manages 1000+ symbols × 9 timeframes = 9000 streams

---

### M-03: Historical Service

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `historical-service`                                        |
| **Descripción**      | Sirve datos históricos para backtesting, display en UI,    |
|                      | ytraining de modelos ML.                                    |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8302                                                        |
| **Puerto gRPC**      | 9302                                                        |
| **SLA Target**       | 99.9%                                                       |
| **Dependencias**     | TimescaleDB (OHLC hypertables)                              |
| **Recursos (k8s)**   | CPU: 2 cores, Memoria: 4GB, Réplicas: 2                     |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `marketdata.historical.request`    | `marketdata.historical.response`      |

**Responsabilidades:**
- Serve historical OHLC data (1 min → 1 month candles)
- Pagination eficiente para datasets grandes
- Compression de respuestas (gzip/brotli)
- Cache en Redis para queries frecuentes
- Export: CSV, JSON, Parquet

---

### M-04: Feed Manager

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `feed-manager`                                              |
| **Descripción**      | Gestiona suscripciones a feeds de datos. Decide qué fuentes |
|                      | usar para cada symbol y failover entre fuentes.             |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8303                                                        |
| **SLA Target**       | 99.9%                                                       |
| **Dependencias**     | Data Ingestion, Redis (subscription map)                    |
| **Recursos (k8s)**   | CPU: 0.5 cores, Memoria: 512MB, Réplicas: 1                |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `marketdata.source.status`         | `marketdata.source.subscribe`         |
| `marketdata.symbol.subscribe`      | `marketdata.feed.assigned`            |

**Responsabilidades:**
- Maintener mapa symbol → source(s) con prioridades
- Failover automático si source primaria cae
- Rate limit awareness por source
- Symbol subscription management (on-demand)

---

## 7. Platform Context

### P-01: Auth Service

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `auth-service`                                              |
| **Descripción**      | Servicio de autenticación: OAuth2, JWT, RBAC, session       |
|                      | management, y multi-factor authentication.                  |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8400                                                        |
| **Puerto gRPC**      | 9400                                                        |
| **SLA Target**       | 99.99%                                                      |
| **Dependencias**     | PostgreSQL (users, roles), Redis (sessions, rate limits)    |
| **Recursos (k8s)**   | CPU: 1-2 cores, Memoria: 1-2GB, Réplicas: 3+               |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `platform.auth.login`              | `platform.user.authenticated`         |
| `platform.auth.logout`             | `platform.user.logged_out`            |

**Responsabilidades:**
- OAuth2 providers: Google, GitHub, Discord
- JWT issuance (15min access + 7d refresh tokens)
- RBAC: Admin, Manager, Trader, Viewer, API roles
- MFA via TOTP (Google Authenticator)
- Login rate limiting (5 attempts / 15 min)
- Account lockout después de 10 intentos fallidos

---

### P-02: User Service

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `user-service`                                              |
| **Descripción**      | CRUD de usuarios, profile management, preferences, y        |
|                      | onboarding workflow.                                         |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8401                                                        |
| **Puerto gRPC**      | 9401                                                        |
| **SLA Target**       | 99.95%                                                      |
| **Dependencias**     | PostgreSQL, Redis (cache), NATS JetStream                   |
| **Recursos (k8s)**   | CPU: 1 core, Memoria: 1GB, Réplicas: 2                     |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `platform.user.created`            | `platform.user.updated`               |
| `platform.user.deleted`            | `billing.user.subscription.changed`   |

---

### P-03: Tenant Service

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `tenant-service`                                            |
| **Descripción**      | Gestión de tenants: creación, configuración, aislamiento    |
|                      | de datos, y provisioning de schemas PostgreSQL.             |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8402                                                        |
| **Puerto gRPC**      | 9402                                                        |
| **SLA Target**       | 99.95%                                                      |
| **Dependencias**     | PostgreSQL (admin), NATS JetStream, Redis                   |
| **Recursos (k8s)**   | CPU: 1 core, Memoria: 1GB, Réplicas: 2                     |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `platform.tenant.created`          | `platform.tenant.configured`          |
| `platform.tenant.suspended`        | `platform.tenant.deactivated`         |

**Responsabilidades:**
- Crear/eliminar tenants con schema-per-tenant
- Configuración de brokers habilitados por tenant
- Límites de uso por tenant (orders, signals, users)
- Tenant suspension y reactivation
- Data export por tenant (GDPR compliance)

---

### P-04: Admin Service

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `admin-service`                                             |
| **Descripción**      | Panel de administración: dashboard global, tenant management,|
|                      | system health, y configuration management.                  |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8403                                                        |
| **SLA Target**       | 99.9%                                                       |
| **Dependencias**     | PostgreSQL, Redis, NATS JetStream, Prometheus               |
| **Recursos (k8s)**   | CPU: 1 core, Memoria: 1GB, Réplicas: 1                     |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `platform.admin.command`           | `platform.system.config.changed`      |

---

### P-05: Account Service

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `account-service`                                           |
| **Descripción**      | Gestión de cuentas de trading: vinculación a brokers,       |
|                      | configuración de copy trading, y settings por cuenta.       |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8404                                                        |
| **Puerto gRPC**      | 9404                                                        |
| **SLA Target**       | 99.95%                                                      |
| **Dependencias**     | PostgreSQL, NATS JetStream, Broker Gateway (sync)           |
| **Recursos (k8s)**   | CPU: 1 core, Memoria: 1GB, Réplicas: 2                     |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `broker.account.connected`         | `platform.account.synced`             |
| `platform.account.config.changed`  | `broker.account.sync`                 |

---

### P-06: Settings Service

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `settings-service`                                          |
| **DescripciónFeature | Centraliza configuración del sistema: feature flags,        |
|                      | thresholds, parametrización global.                         |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8405                                                        |
| **SLA Target**       | 99.9%                                                       |
| **Dependencias**     | PostgreSQL, Redis (cache con invalidación)                  |
| **Recursos (k8s)**   | CPU: 0.5 cores, Memoria: 512MB, Réplicas: 1                |

---

### P-07: API Key Service

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `apikey-service`                                            |
| **Descripción**      | Gestión de API keys para acceso programático: creación,     |
|                      | rotación, revocación, y rate limiting por key.              |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8406                                                        |
| **Puerto gRPC**      | 9406                                                        |
| **SLA Target**       | 99.95%                                                      |
| **Dependencias**     | PostgreSQL, Redis (rate limit counters)                     |
| **Recursos (k8s)**   | CPU: 0.5 cores, Memoria: 512MB, Réplicas: 2                |

---

### P-08: WebSocket Hub

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `websocket-hub`                                             |
| **Descripción**      | Hub centralizado de WebSocket connections para streaming    |
|                      | de datos en tiempo real al frontend.                        |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8407 (WebSocket upgrade)                                    |
| **SLA Target**       | 99.95%                                                      |
| **Dependencias**     | NATS JetStream, Redis (session state)                       |
| **Recursos (k8s)**   | CPU: 2 cores, Memoria: 2GB, Réplicas: 3                    |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `marketdata.tick.*`                | (WebSocket → Client)                  |
| `trading.position.updated`         |                                       |
| `trading.order.filled`             |                                       |
| `ai.anomaly.detected`              |                                       |

**Responsabilidades:**
- Manage 10,000+ concurrent WebSocket connections
- Topic-based subscription (por symbol, account, portfolio)
- Connection lifecycle: authenticate, subscribe, unsubscribe, disconnect
- Backpressure handling para slow clients
- Message batching para eficiencia (flush cada 50ms)

---

## 8. Notification Context

### N-01: Notification Dispatcher

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `notification-dispatcher`                                   |
| **Descripción**      | Despacha notificaciones a múltiples canales según           |
|                      | preferencias del usuario: Email, Telegram, WebSocket, Push. |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8500                                                        |
| **SLA Target**       | 99.9%                                                       |
| **Dependencias**     | PostgreSQL (preferences), Redis (rate limits), NATS         |
| **Recursos (k8s)**   | CPU: 1 core, Memoria: 1GB, Réplicas: 2                     |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `notification.send`                | `notification.sent`                   |
| `trading.order.filled`             | `notification.failed`                 |
| `risk.breach.detected`             |                                       |
| `platform.user.created`            |                                       |

**Responsabilidades:**
- Route notifications al canal correcto
- Rate limiting por usuario (evitar spam)
- Retry con dead letter queue
- Priority levels: Critical, High, Normal, Low
- Batch sending para newsletters

---

### N-02: Template Engine

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `template-engine`                                           |
| **Descripción**      | Gestión de templates para notificaciones: Order Filled,     |
|                      | Risk Alert, Daily Summary, Welcome, etc.                    |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8501                                                        |
| **SLA Target**       | 99.9%                                                       |
| **Dependencias**     | PostgreSQL (templates)                                      |
| **Recursos (k8s)**   | CPU: 0.5 cores, Memoria: 512MB, Réplicas: 1                |

**Responsabilidades:**
- Templates en Go html/template + Mustache
- Variables dinámicas por tipo de notificación
- Multi-idioma (i18n): ES, EN, PT, FR
- Preview de templates en admin panel
- Versioning de templates

---

### N-03: Email Service

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `email-service`                                             |
| **Descripción**      | Envío de emails via SMTP o API de proveedor (SendGrid/SES). |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8502                                                        |
| **SLA Target**       | 99.9%                                                       |
| **Dependencias**     | SMTP provider o SendGrid API                                |
| **Recursos (k8s)**   | CPU: 0.5 cores, Memoria: 512MB, Réplicas: 1                |

---

### N-04: Telegram Bot Service

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `telegram-bot-service`                                      |
| **Descripción**      | Bot de Telegram para notificaciones, comandos de trading    |
|                      | básico, y consulta de estado de cuentas.                    |
| **Lenguaje**         | Go 1.22+ (no Telethon)                                     |
| **Puerto HTTP**      | 8503                                                        |
| **SLA Target**       | 99.9%                                                       |
| **Dependencias**     | Telegram Bot API (HTTP, no Telethon), NATS                  |
| **Recursos (k8s)**   | CPU: 0.5 cores, Memoria: 512MB, Réplicas: 1                |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `notification.telegram.send`       | `notification.telegram.sent`          |
| `platform.telegram.command`        | `platform.telegram.response`          |

**Responsabilidades:**
- Send notifications via Telegram Bot API (HTTP REST, no MTProto)
- Slash commands: /status, /balance, /positions, /pnl
- Inline keyboards para confirmaciones de trading
- Webhook mode (no polling) para baja latencia

---

## 9. Audit/Billing Context

### AU-01: Audit Engine

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `audit-engine`                                              |
| **Descripción**      | Motor de auditoría basado en Event Sourcing. Almacena       |
|                      | todos los eventos de forma append-only e inmutable.         |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8600                                                        |
| **Puerto gRPC**      | 9600                                                        |
| **SLA Target**       | 99.99%                                                      |
| **Dependencias**     | PostgreSQL (events table), NATS JetStream                   |
| **Recursos (k8s)**   | CPU: 1 core, Memoria: 1GB, Réplicas: 2                     |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `audit.>`                          | `audit.event.logged`                  |
| (todos los eventos de negocio)     | `audit.projection.updated`            |

**Responsabilidades:**
- Recibir y almacenar todos los eventos de negocio
- Tabla events append-only (nunca UPDATE/DELETE)
- Snapshot management cada 100 eventos por aggregate
- Replay de eventos para reconstruir estado
- Export a parquet para analytics offline

---

### AU-02: Event Projector

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `event-projector`                                           |
| **Descripción**      | Proyecta eventos a read models optimizados para consultas.  |
|                      | Materializa vistas para dashboards y reports.               |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8601                                                        |
| **SLA Target**       | 99.9%                                                       |
| **Dependencias**     | PostgreSQL (read models), NATS JetStream                    |
| **Recursos (k8s)**   | CPU: 1 core, Memoria: 1GB, Réplicas: 1                     |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `audit.event.logged`               | `audit.projection.updated`            |
| `trading.order.filled`             |                                       |
| `trading.position.updated`         |                                       |

**Responsabilidades:**
- Proyectar eventos a tablas de read models
- Equity curve projection (timescaledb)
- P&L daily aggregation
- Trading activity summary por tenant
- Projection rebuild capability (replay)

---

### AU-03: Billing Service

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `billing-service`                                           |
| **Descripción**      | Gestión de suscripciones, planes, facturación, y            |
|                      | metering de uso por tenant.                                 |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8602                                                        |
| **Puerto gRPC**      | 9602                                                        |
| **SLA Target**       | 99.9%                                                       |
| **Dependencias**     | PostgreSQL, Redis, Stripe API, NATS JetStream               |
| **Recursos (k8s)**   | CPU: 1 core, Memoria: 1GB, Réplicas: 2                     |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `billing.subscription.created`     | `billing.invoice.generated`           |
| `billing.metering.tick`            | `platform.tenant.suspended`           |
| `platform.user.created`            | `billing.subscription.activated`      |

**Responsabilidades:**
- Plans: Free, Starter ($29/mo), Pro ($99/mo), Enterprise (custom)
- Metering: órdenes/día, signals/día, API calls/mes
- Stripe integration: subscriptions, invoices, webhooks
- Usage alerts (80% threshold warning)
- Grace period antes de suspension

---

### AU-04: Metering Service

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `metering-service`                                          |
| **Descripción**      | Cuenta y registra uso de recursos por tenant para billing.  |
|                      | Órdenes, señales, API calls, storage.                       |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8603                                                        |
| **SLA Target**       | 99.9%                                                       |
| **Dependencias**     | Redis (counters), TimescaleDB (usage metrics)               |
| **Recursos (k8s)**   | CPU: 0.5 cores, Memoria: 512MB, Réplicas: 1                |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `trading.order.placed`             | `billing.metering.updated`            |
| `trading.signal.scored`            | `billing.metering.tick`               |
| `platform.apikey.used`             |                                       |

---

### AU-05: Compliance Service

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `compliance-service`                                        |
| **Descripción**      | Verifica compliance regulatorio: KYC/AML checks, reporting  |
|                      | de transacciones sospechosas, audit trail para reguladores. |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8604                                                        |
| **SLA Target**       | 99.9%                                                       |
| **Dependencias**     | PostgreSQL, Audit Engine, NATS JetStream                    |
| **Recursos (k8s)**   | CPU: 1 core, Memoria: 1GB, Réplicas: 1                     |

---

### AU-06: Report Generator

| Campo                | Valor                                                       |
|----------------------|-------------------------------------------------------------|
| **Nombre**           | `report-generator`                                          |
| **Descripción**      | Genera reports periódicos: daily P&L, weekly summary,       |
|                      | monthly compliance, y custom reports por tenant.            |
| **Lenguaje**         | Go 1.22+                                                    |
| **Puerto HTTP**      | 8605                                                        |
| **SLA Target**       | 99.5%                                                       |
| **Dependencias**     | PostgreSQL, TimescaleDB, MinIO (PDF storage)                |
| **Recursos (k8s)**   | CPU: 1 core, Memoria: 1GB, Réplicas: 1 (cron)              |

| NATS Subject Consumido             | NATS Subject Publicado               |
|------------------------------------|---------------------------------------|
| `report.generate.request`          | `report.generate.completed`           |
| `report.schedule.trigger`          | `notification.send`                   |

---

## 10. Broker Abstraction Layer

### Concepto

El Broker Abstraction Layer es el patrón central que permite a TNSVT V2
soportar múltiples brokers con una única interfaz unificada.

```go
// broker/port/broker_port.go — Interfaz Unificada

type BrokerPort interface {
    // Conexión
    Connect(ctx context.Context, config BrokerConfig) error
    Disconnect(ctx context.Context) error
    IsConnected() bool

    // Órdenes
    PlaceOrder(ctx context.Context, req PlaceOrderRequest) (*OrderResponse, error)
    ModifyOrder(ctx context.Context, req ModifyOrderRequest) (*OrderResponse, error)
    CancelOrder(ctx context.Context, req CancelOrderRequest) (*OrderResponse, error)
    GetOrderStatus(ctx context.Context, orderID string) (*OrderStatus, error)

    // Cuenta
    GetAccountInfo(ctx context.Context) (*AccountInfo, error)
    GetPositions(ctx context.Context) ([]Position, error)
    GetBalance(ctx context.Context) (*Balance, error)

    // Datos de mercado
    SubscribeTicks(ctx context.Context, symbols []string) error
    UnsubscribeTicks(ctx context.Context, symbols []string) error
    GetHistoricalData(ctx context.Context, req HistoryRequest) ([]OHLC, error)
}
```

### Arquitectura del Adapter

```
+=====================================================================+
|              BROKER ABSTRACTION LAYER                                |
+=====================================================================+
|                                                                      |
|  [Trading Engine]                                                   |
|       |                                                              |
|       v                                                              |
|  +------------------+                                               |
|  | BrokerPort       |  << Interfaz Go (interface{})>>               |
|  | (Interface)      |                                               |
|  +--------+---------+                                               |
|           |                                                          |
|           v                                                          |
|  +------------------+                                               |
|  | Broker Gateway   |  << Router por account>>                     |
|  | (Routing Layer)  |                                               |
|  +--------+---------+                                               |
|           |                                                          |
|  +--------+--------+--------+--------+--------+                    |
|  v        v        v        v        v        v                    |
| +----+ +----+ +--------+ +----+ +----+ +------+                   |
| |MT5 | |cT  | |Binance | |Bybit| |IBKR| |Future|                   |
| |Adpt| |Adpt| |Adapter | |Adpt| |Adpt| |(Fase5)|                   |
| +----+ +----+ +--------+ +----+ +----+ +------+                   |
|                                                                      |
|  Cada Adapter:                                                      |
|  - Implementa BrokerPort                                            |
|  - Traduce al formato del broker específico                         |
|  - Gestiona reconexión y heartbeat                                  |
|  - Publica: broker.<broker>.execution.report                       |
|  - Consume: broker.execute.order                                   |
+=====================================================================+
```

### Tabla de Equivalencias

| Operación           | MT5                    | cTrader            | Binance            | Bybit               | IBKR                |
|---------------------|------------------------|--------------------|--------------------|---------------------|---------------------|
| Place Market Order  | `OrderSend`            | `NewOrder`         | `POST /order`      | `POST /order`       | `reqPlaceOrder`     |
| Place Limit Order   | `OrderSend (LIMIT)`    | `NewOrder (LIMIT)` | `POST /order`      | `POST /order`       | `reqPlaceOrder`     |
| Modify Order        | `OrderModify`          | `ModifyOrder`      | `PUT /order`       | `PUT /order`        | `reqModifyOrder`    |
| Cancel Order        | `OrderClose`           | `CancelOrder`      | `DELETE /order`    | `DELETE /order`     | `reqCancelOrder`    |
| Get Positions       | `PositionsTotal`       | `GetPositionList`  | `GET /position`    | `GET /position`     | `reqPositions`      |
| Get Balance         | `AccountInfoDouble`    | `GetAccountInfo`   | `GET /account`     | `GET /balance`      | `reqAccountSummary` |
| Subscribe Ticks     | `SymbolSubscribe`      | `SubscribeQuotes`  | WebSocket `/stream`| WebSocket           | `reqMktData`        |
| Authentication      | TCP Login              | OAuth2 Token       | HMAC-SHA256        | HMAC-SHA256         | TCP Gateway         |

---

## 11. Matriz de Dependencias

```
+=====================================================================+
|           MATRIZ DE DEPENDENCIAS CRÍTICAS                           |
+=====================================================================+
|                                                                      |
|  Servicio A ---> Servicio B = A depende de B                        |
|                                                                      |
|  Trading Engine ---> Risk Manager                                    |
|  Trading Engine ---> Broker Gateway                                  |
|  Trading Engine ---> Market Data (tick stream)                       |
|  Trading Engine ---> Copy Trading Router                             |
|  Order Executor ---> Broker Gateway                                  |
|  Copy Trading Router ---> Trading Engine (place orders)             |
|  Signal Scheduler ---> Trading Engine                                |
|  Position Manager ---> Market Data (tick stream)                     |
|  Strategy Engine ---> Market Data (OHLC)                             |
|  Backtesting Service ---> TimescaleDB                                |
|                                                                      |
|  Risk Manager ---> Redis (exposure cache)                            |
|  Risk Manager ---> Market Data (tick stream)                         |
|  Risk Monitor ---> Market Data (tick stream)                         |
|  Circuit Breaker ---> Risk Manager                                   |
|  Exposure Calculator ---> Market Data (tick stream)                  |
|                                                                      |
|  Broker Gateway ---> MT5 Adapter                                     |
|  Broker Gateway ---> cTrader Adapter                                 |
|  Broker Gateway ---> Binance Adapter                                 |
|  Broker Gateway ---> Bybit Adapter                                   |
|  Broker Gateway ---> IBKR Adapter                                    |
|                                                                      |
|  Signal Scorer ---> Ollama Gateway                                   |
|  Signal Scorer ---> Feature Engineering                              |
|  Regime Detector ---> Ollama Gateway                                 |
|  Anomaly Detector ---> Market Data (tick stream)                     |
|  RAG Engine ---> Ollama Gateway                                      |
|  RAG Engine ---> PostgreSQL (pgvector)                               |
|                                                                      |
|  Data Ingestion ---> Broker APIs (external)                          |
|  Data Aggregator ---> Data Ingestion                                 |
|  Historical Service ---> TimescaleDB                                 |
|                                                                      |
|  All Services ---> NATS JetStream                                    |
|  All Services ---> PostgreSQL (domain-specific schema)               |
|  All Services ---> Redis (cache where needed)                        |
+=====================================================================+
```

### Health Check Matrix

| Servicio           | Liveness Check          | Readiness Check               | Startup Check            |
|--------------------|-------------------------|-------------------------------|--------------------------|
| Trading Engine     | HTTP /healthz           | NATS connected + DB connected | Event store initialized  |
| Risk Manager       | HTTP /healthz           | Redis connected + DB          | Limits loaded            |
| Broker Gateway     | HTTP /healthz           | ≥1 adapter connected          | Connection pools warm    |
| AI/ML Services     | HTTP /healthz           | Ollama reachable              | Model loaded             |
| Market Data        | HTTP /healthz           | ≥1 feed active                | Symbols subscribed       |
| Platform Auth      | HTTP /healthz           | DB + Redis connected          | JWT keys loaded          |
| PostgreSQL         | TCP 5432                | Accepting connections         | Migrations complete      |
| Redis              | TCP 6379 + PING         | Cluster state OK              | Cluster joined           |
| NATS               | TCP 4222 + PING         | JetStream ready               | Cluster formed           |

---

## Aprobaciones

| Rol                  | Nombre           | Fecha       | Estado    |
|----------------------|------------------|-------------|-----------|
| CTO                  | ________________ | ____/__/__ | Pendiente |
| Lead Architect       | ________________ | ____/__/__ | Pendiente |
| Platform Lead        | ________________ | ____/__/__ | Pendiente |

---

*Documento generado como parte del proceso de arquitectura de TNSVT V2.*
*Documento anterior: [01-ARCHITECTURE-OVERVIEW.md](01-ARCHITECTURE-OVERVIEW.md)*
*Proximo documento: [03-DATA-FLOWS.md](03-DATA-FLOWS.md)*
