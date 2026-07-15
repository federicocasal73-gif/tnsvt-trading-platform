# DOCUMENT 05: COMUNICACIÓN ENTRE SERVICIOS

## Plataforma de Trading TNSVT V2 — Arquitectura de Comunicación

**Versión:** 2.0.0  
**Fecha:** 2026-07-14  
**Estado:** Producción  
**Autor:** Equipo de Arquitectura TNSVT V2

---

## Tabla de Contenidos

1. [Visión General](#1-visión-general)
2. [Jerarquía de Subjects NATS](#2-jerarquía-de-subjects-nats)
3. [Formato CloudEvents](#3-formato-cloudevents)
4. [Patrones de Comunicación](#4-patrones-de-comunicación)
5. [Saga Pattern](#5-saga-pattern)
6. [Políticas de Reintentos](#6-políticas-de-reintentos)
7. [Dead Letter Queue](#7-dead-letter-queue)
8. [Esquemas de Mensajes](#8-esquemas-de-mensajes)
9. [Configuración JetStream](#9-configuración-jetstream)

---

## 1. Visión General

TNSVT V2 utiliza **NATS** como sistema central de mensajería para la comunicación
entre servicios. Se emplean dos modelos principales:

- **Request/Reply** para llamadas síncronas de baja latencia.
- **Publish/Subscribe** para eventos asíncronos y desacoplamiento entre dominios.

```
┌──────────────────────────────────────────────────────────────────────┐
│                        ARQUITECTURA DE MENSAJERÍA                   │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────┐   Request/Reply    ┌──────────────────────────┐       │
│  │ Service A│◄──────────────────►│   NATS Core (sync calls) │       │
│  └──────────┘                    └──────────────────────────┘       │
│                                                                      │
│  ┌──────────┐   Pub/Sub          ┌──────────────────────────┐       │
│  │ Service A│──── Publish ──────►│ NATS JetStream (events)  │       │
│  └──────────┘                    └──────────┬───────────────┘       │
│                                             │ Subscribe             │
│                          ┌──────────────────┼──────────────┐        │
│                          ▼                  ▼              ▼        │
│                     ┌────────┐        ┌────────┐     ┌────────┐    │
│                     │Svc B   │        │Svc C   │     │Svc D   │    │
│                     └────────┘        └────────┘     └────────┘    │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              CloudEvents v1.0 (todos los eventos)            │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

### Criterios de Decisión: Síncrono vs Asíncrono

| Criterio               | Síncrono (Request/Reply)           | Asíncrono (Pub/Sub)               |
|------------------------|-------------------------------------|-------------------------------------|
| Latencia requerida     | < 50ms                             | Tolerable > 100ms                  |
| Acoplamiento           | Fuerte (conocer receptor)           | Débil (solo subject)               |
| Consistencia           | Fuerte (transacciones distribuidas) | Eventual (eventos)                 |
| Escalabilidad          | Limitada por receptor               | Horizontal libre                   |
| Ejemplo                | Validación de riesgo, cotización    | Notificaciones, audit logs         |

---

## 2. Jerarquía de Subjects NATS

Todos los subjects siguen una convención de tres niveles: `<dominio>.<subdominio>.<acción>`.

```
trading.*                     # Dominio de trading
  trading.order.new           # Nueva orden creada
  trading.order.filled        # Orden ejecutada
  trading.order.rejected      # Orden rechazada
  trading.order.cancelled     # Orden cancelada
  trading.position.opened     # Posición abierta
  trading.position.closed     # Posición cerrada
  trading.position.updated    # Posición actualizada (PnL, etc.)
  trading.signal.received     # Señal de trading recibida
  trading.signal.approved     # Señal aprobada
  trading.signal.rejected     # Señal rechazada

risk.*                        # Dominio de riesgo
  risk.check.request          # Solicitud de verificación
  risk.check.approved         # Verificación aprobada
  risk.check.rejected         # Verificación rechazada
  risk.alert.drawdown         # Alerta de drawdown
  risk.alert.exposure         # Alerta de exposición
  risk.limit.breach           # Límite de riesgo violado
  risk.position.sized         # Tamaño de posición calculado

ai.*                          # Dominio de inteligencia artificial
  ai.model.prediction         # Predicción del modelo
  ai.model.trained            # Modelo entrenado
  ai.model.deployed           # Modelo desplegado
  ai.sentiment.analyzed       # Análisis de sentimiento
  ai.anomaly.detected         # Anomalía detectada
  ai.llm.response             # Respuesta de LLM (Ollama)
  ai.embedding.generated      # Embedding generado

broker.*                      # Dominio de brokers
  broker.connection.status    # Estado de conexión
  broker.order.submitted      # Orden enviada al broker
  broker.order.confirmation   # Confirmación del broker
  broker.position.sync        # Sincronización de posiciones
  broker.market.data          # Datos de mercado en tiempo real
  broker.account.balance      # Balance de cuenta

platform.*                    # Dominio de plataforma
  platform.user.registered    # Usuario registrado
  platform.user.updated       # Usuario actualizado
  platform.tenant.created     # Tenant creado
  platform.tenant.suspended   # Tenant suspendido
  platform.billing.invoice    # Factura generada
  platform.billing.payment    # Pago procesado
  platform.api.key.rotated    # API key rotada

notification.*                # Dominio de notificaciones
  notification.email.send     # Enviar email
  notification.push.send      # Enviar push notification
  notification.telegram.send  # Enviar mensaje Telegram
  notification.webhook.send   # Enviar webhook externo
  notification.alert          # Alerta al usuario
```

### Wildcards

| Wildcard    | Ejemplo                     | Uso                                    |
|-------------|------------------------------|----------------------------------------|
| `>`         | `trading.>`                 | Todos los eventos de trading           |
| `*`         | `*.order.filled`            | Todas las órdenes filling de cualquier dominio |
| `*.*.alert` | `risk.*.alert`              | Todas las alertas de riesgo            |

---

## 3. Formato CloudEvents

Todos los eventos en NATS JetStream utilizan **CloudEvents v1.0** como formato estándar.

### Estructura Base

```json
{
  "specversion": "1.0",
  "id": "evt_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "source": "tnsvt-v2/trading-engine",
  "type": "tnsvt.trading.order.filled",
  "datacontenttype": "application/json",
  "subject": "order-12345",
  "time": "2026-07-14T10:30:00.000Z",
  "traceid": "4bf92f3577b34da6a6ce93a30f8e2b0a",
  "spanid": "00f067aa0ba902b7",
  "tenantid": "tenant_abc123",
  "userid": "user_xyz789",
  "correlationid": "corr-987654321",
  "data": {}
}
```

### Campos Obligatorios

| Campo             | Tipo      | Descripción                                    |
|-------------------|-----------|------------------------------------------------|
| `specversion`     | string    | Siempre `"1.0"`                                |
| `id`              | string    | UUID v4 único del evento                       |
| `source`          | string    | Emisor del evento (`tnsvt-v2/<servicio>`)      |
| `type`            | string    | Tipo jerárquico (`tnsvt.<dominio>.<acción>`)  |
| `datacontenttype` | string    | Siempre `"application/json"`                   |
| `time`            | datetime  | ISO 8601 UTC                                   |
| `data`            | object    | Payload del evento                             |

### Campos Extensiones TNSVT

| Campo             | Tipo   | Requerido | Descripción                     |
|-------------------|--------|-----------|---------------------------------|
| `tenantid`        | string | Sí        | Identificador del tenant        |
| `userid`          | string | No        | Usuario asociado                |
| `traceid`         | string | Sí        | Distributed trace ID            |
| `spanid`          | string | Sí        | Span ID para tracing            |
| `correlationid`   | string | Sí        | ID de correlación transaccional |
| `retried`         | int    | No        | Número de reintentos            |
| `version`         | int    | Sí        | Versión del schema (1, 2, ...)  |

---

## 4. Patrones de Comunicación

### 4.1 Request/Reply (Síncrono)

Utilizado para validaciones en tiempo real y consultas de baja latencia.

```
┌─────────┐                    ┌──────────┐                    ┌─────────┐
│ Service │   Subject:         │   NATS   │   Subject:         │ Service │
│ Cliente │  risk.check.req    │   Core   │  risk.check.req    │  Riesgo │
│         │ ──────────────────►│          │ ──────────────────►│         │
│         │                    │          │                    │         │
│         │   Reply:           │          │   Reply:           │         │
│         │◄───────────────────│          │◄───────────────────│         │
│         │  risk.check.resp   │          │  risk.check.resp   │         │
└─────────┘                    └──────────┘                    └─────────┘
```

**Configuración Go:**

```go
// Servidor (Risk Engine)
nc.Subscribe("risk.check.request", func(msg *nats.Msg) {
    var req RiskCheckRequest
    json.Unmarshal(msg.Data, &req)
    
    result := riskService.Evaluate(req)
    
    resp, _ := json.Marshal(result)
    msg.Respond(resp)
})

// Cliente (Trading Engine)
msg, err := nc.Request("risk.check.request", payload, 100*time.Millisecond)
if err != nil {
    // Timeout o error de conexión
    return ErrRiskCheckTimeout
}
```

**Timeouts por tipo de Request/Reply:**

| Subject                        | Timeout  | Uso                                  |
|--------------------------------|----------|--------------------------------------|
| `risk.check.request`          | 50ms     | Validación pre-trade                 |
| `risk.position.sized`         | 100ms    | Cálculo de tamaño de posición       |
| `broker.market.data`          | 200ms    | Consulta de precio                   |
| `ai.model.prediction`         | 500ms    | Predicción de modelo ML              |
| `platform.user.lookup`        | 30ms     | Lookup rápido de usuario             |

### 4.2 Publish/Subscribe (Asíncrono)

Utilizado para eventos de dominio y desacoplamiento entre servicios.

```
┌──────────┐     Publish          ┌─────────────────────────┐
│ Trading  │───trading.order.────►│     NATS JetStream      │
│ Engine   │     filled           │   (stream: TRADING)     │
└──────────┘                      └───────────┬─────────────┘
                                              │
                              ┌───────────────┼───────────────┐
                              ▼               ▼               ▼
                     ┌────────────┐   ┌────────────┐   ┌────────────┐
                     │ Risk Svc   │   │ Notif Svc  │   │ Audit Svc  │
                     │ .subscribe │   │ .subscribe │   │ .subscribe │
                     │            │   │            │   │            │
                     │ Subject:   │   │ Subject:   │   │ Subject:   │
                     │ trading.*  │   │ trading.*  │   │ trading.*  │
                     └────────────┘   └────────────┘   └────────────┘
```

**Configuración Go:**

```go
// Publisher
func PublishOrderFilled(order OrderFilledEvent) error {
    data, _ := json.Marshal(order)
    return nc.Publish("trading.order.filled", data)
}

// Subscriber con grupo de consumo
sub, _ := nc.QueueSubscribe("trading.order.filled", "risk-engine", func(msg *nats.Msg) {
    var event OrderFilledEvent
    json.Unmarshal(msg.Data, &event)
    riskEngine.ProcessOrderFilled(event)
})
sub.Drain()
```

### 4.3 Request/Reply con Timeouts y Circuit Breaker

```go
type SyncRequester struct {
    nc          *nats.Conn
    timeout     time.Duration
    circuit     *CircuitBreaker
    metrics     *prometheus.CounterVec
}

func (s *SyncRequester) RequestRiskCheck(ctx context.Context, req RiskCheckRequest) (*RiskCheckResponse, error) {
    if !s.circuit.Allow() {
        return nil, ErrCircuitOpen
    }
    
    payload, _ := json.Marshal(req)
    
    msg, err := s.nc.RequestWithContext(ctx, "risk.check.request", payload)
    if err != nil {
        s.circuit.RecordFailure()
        s.metrics.WithLabelValues("risk", "error").Inc()
        return nil, err
    }
    
    s.circuit.RecordSuccess()
    s.metrics.WithLabelValues("risk", "success").Inc()
    
    var resp RiskCheckResponse
    json.Unmarshal(msg.Data, &resp)
    return &resp, nil
}
```

---

## 5. Saga Pattern

Las transacciones distribuidas se orquestan mediante **Saga con Coreografía**
(señal → riesgo → ejecución → notificación).

### Diagrama de Secuencia

```
┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐
│Signal  │  │Risk    │  │Trading │  │Broker │  │Notif  │  │Audit   │
│Service │  │Engine  │  │Engine  │  │Gateway │  │Service │  │Service │
└───┬────┘  └───┬────┘  └───┬────┘  └───┬────┘  └───┬────┘  └───┬────┘
    │           │           │           │           │           │
    │ 1.Signal  │           │           │           │           │
    │ Received  │           │           │           │           │
    │──────────►│           │           │           │           │
    │           │           │           │           │           │
    │ 2.Risk    │           │           │           │           │
    │ Approved  │           │           │           │           │
    │◄──────────│           │           │           │           │
    │           │           │           │           │           │
    │ 3.Signal  │           │           │           │           │
    │ Approved  │           │           │           │           │
    │──────────────────────►│           │           │           │
    │           │           │           │           │           │
    │           │ 4.Order   │           │           │           │
    │           │ Created   │           │           │           │
    │           │──────────►│           │           │           │
    │           │           │           │           │           │
    │           │           │ 5.Submit  │           │           │
    │           │           │ to Broker │           │           │
    │           │           │──────────►│           │           │
    │           │           │           │           │           │
    │           │           │ 6.Filled  │           │           │
    │           │           │◄──────────│           │           │
    │           │           │           │           │           │
    │           │           │ 7.Order   │           │           │
    │           │           │ Filled    │           │           │
    │           │◄──────────────────────│           │           │
    │           │           │           │           │           │
    │           │           │ 8.Position│           │           │
    │           │           │ Opened    │           │           │
    │           │           │           │──────────►│           │
    │           │           │           │           │           │
    │           │           │           │ 9.Notify  │           │
    │           │           │           │ User      │           │
    │           │           │           │──────────────────────►│
    │           │           │           │           │           │
    │           │           │           │           │ 10.Audit  │
    │           │           │           │           │ Log       │
    │           │           │           │           │──────────►│
    │           │           │           │           │           │
```

### Estados de la Saga

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  INITIATED  │────►│   PENDING   │────►│  VALIDATING │
└─────────────┘     │   RISK      │     └──────┬──────┘
                    └─────────────┘            │
                                      ┌───────┴───────┐
                                      ▼               ▼
                              ┌─────────────┐  ┌─────────────┐
                              │  VALIDATED  │  │   REJECTED  │
                              └──────┬──────┘  └─────────────┘
                                     │
                                     ▼
                             ┌─────────────┐
                             │  EXECUTING  │
                             └──────┬──────┘
                                    │
                            ┌───────┴───────┐
                            ▼               ▼
                    ┌─────────────┐  ┌─────────────┐
                    │   FILLED    │  │   FAILED    │
                    └──────┬──────┘  └──────┬──────┘
                           │                │
                           ▼                ▼
                   ┌─────────────┐  ┌─────────────┐
                   │ COMPLETED   │  │ COMPENSATED │
                   └─────────────┘  └─────────────┘
```

### Implementación Go

```go
type SagaStep struct {
    Name    string
    Execute func(ctx context.Context, state *SagaState) error
    Compensate func(ctx context.Context, state *SagaState) error
}

type OrderSaga struct {
    steps    []SagaStep
    state    *SagaState
    pub      *nats.Conn
}

func NewOrderSaga() *OrderSaga {
    return &OrderSaga{
        steps: []SagaStep{
            {Name: "validate_risk",    Execute: executeRiskValidation,    Compensate: compensateRiskValidation},
            {Name: "create_order",     Execute: executeCreateOrder,       Compensate: compensateCreateOrder},
            {Name: "submit_broker",    Execute: executeSubmitToBroker,    Compensate: compensateSubmitToBroker},
            {Name: "confirm_fill",     Execute: executeConfirmFill,       Compensate: compensateConfirmFill},
            {Name: "notify_user",      Execute: executeNotifyUser,        Compensate: nil},
        },
    }
}

func (s *OrderSaga) Execute(ctx context.Context) error {
    completed := []int{}
    
    for i, step := range s.steps {
        log.Info().Str("step", step.Name).Msg("Ejecutando paso de saga")
        
        if err := step.Execute(ctx, s.state); err != nil {
            log.Error().Err(err).Str("step", step.Name).Msg("Fallo en paso de saga")
            
            // Compensar pasos completados en orden inverso
            for j := len(completed) - 1; j >= 0; j-- {
                idx := completed[j]
                if s.steps[idx].Compensate != nil {
                    log.Warn().Str("step", s.steps[idx].Name).Msg("Ejecutando compensación")
                    if cErr := s.steps[idx].Compensate(ctx, s.state); cErr != nil {
                        log.Error().Err(cErr).Str("step", s.steps[idx].Name).Msg("Fallo en compensación")
                    }
                }
            }
            
            return fmt.Errorf("saga failed at step %s: %w", step.Name, err)
        }
        
        completed = append(completed, i)
        
        // Publicar evento de paso completado
        s.publishStepEvent(step.Name, "completed")
    }
    
    return nil
}
```

---

## 6. Políticas de Reintentos

Cada servicio define sus propias políticas de reintento:

### Tabla de Políticas

| Servicio         | Max Retries | Backoff Base | Max Delay  | Jitter | Timeout  |
|------------------|-------------|--------------|------------|--------|----------|
| Trading Engine   | 3           | 100ms        | 2s         | 50ms   | 500ms    |
| Risk Engine      | 2           | 50ms         | 500ms      | 25ms   | 100ms    |
| Broker Gateway   | 5           | 500ms        | 30s        | 100ms  | 5s       |
| AI Service       | 2           | 200ms        | 2s         | 50ms   | 2s       |
| Notification Svc | 5           | 1s           | 60s        | 500ms  | 10s      |
| Platform API     | 3           | 200ms        | 5s         | 100ms  | 2s       |
| Audit Service    | 3           | 100ms        | 5s         | 50ms   | 1s       |
| Copy Trading     | 3           | 200ms        | 5s         | 100ms  | 2s       |

### Implementación

```go
type RetryConfig struct {
    MaxAttempts  int
    BaseDelay    time.Duration
    MaxDelay     time.Duration
    Jitter       time.Duration
    RetryableErrors []string
}

type RetryPolicy struct {
    config   RetryConfig
    metrics  *RetryMetrics
}

func (r *RetryPolicy) Execute(ctx context.Context, fn func() error) error {
    var lastErr error
    
    for attempt := 0; attempt < r.config.MaxAttempts; attempt++ {
        if attempt > 0 {
            delay := r.calculateDelay(attempt)
            log.Info().
                Int("attempt", attempt).
                Dur("delay", delay).
                Msg("Reintentando operación")
            
            select {
            case <-ctx.Done():
                return ctx.Err()
            case <-time.After(delay):
            }
        }
        
        lastErr = fn()
        if lastErr == nil {
            r.metrics.RecordSuccess(attempt)
            return nil
        }
        
        if !r.isRetryable(lastErr) {
            break
        }
        
        r.metrics.RecordRetry(attempt, lastErr)
    }
    
    r.metrics.RecordFailure(r.config.MaxAttempts)
    return fmt.Errorf("máximo de reintentos alcanzado (%d): %w", 
        r.config.MaxAttempts, lastErr)
}

func (r *RetryPolicy) calculateDelay(attempt int) time.Duration {
    delay := r.config.BaseDelay * time.Duration(math.Pow(2, float64(attempt-1)))
    if delay > r.config.MaxDelay {
        delay = r.config.MaxDelay
    }
    
    // Jitter: ± jitter% del delay
    jitterRange := int64(r.config.Jitter) * 2
    jitterOffset := time.Duration(rand.Int63n(jitterRange) - int64(r.config.Jitter))
    
    return delay + jitterOffset
}
```

---

## 7. Dead Letter Queue

Los mensajes que fallan después de todos los reintentos se envían a una DLQ dedicada.

### Configuración por Servicio

```
trading-engine.dlq          # Órdenes fallidas
risk-engine.dlq             # Validaciones fallidas
broker-gateway.dlq          # Envíos a broker fallidos
notification-engine.dlq     # Notificaciones fallidas
ai-engine.dlq               # Predicciones fallidas
audit-engine.dlq            # Audit logs fallidos
```

### Proceso DLQ

```
┌──────────┐    Falla     ┌──────────┐    Falla    ┌─────────┐
│  Pub/Sub │────────────►│  Retry   │────────────►│   DLQ   │
│ Original │             │  Engine  │             │ Stream  │
└──────────┘             └──────────┘             └────┬────┘
                                                       │
                                              ┌────────┴────────┐
                                              ▼                 ▼
                                      ┌──────────────┐  ┌──────────────┐
                                      │ DLQ Monitor  │  │ Manual       │
                                      │ (Alert P2)   │  │ Replay Tool  │
                                      └──────────────┘  └──────────────┘
```

**Configuración DLQ JetStream:**

```yaml
streams:
  TRADING_DLQ:
    subjects: ["trading-engine.dlq.>"]
    retention: limits
    max_msgs: 100000
    max_bytes: 5GB
    max_age: 720h   # 30 días
    storage: file
    replicas: 3
    
  RISK_DLQ:
    subjects: ["risk-engine.dlq.>"]
    retention: limits
    max_msgs: 50000
    max_bytes: 2GB
    max_age: 720h
    storage: file
    replicas: 3
```

**Monitoreo de DLQ:**

```go
func MonitorDLQ(nc *nats.Conn, serviceName string, threshold int) {
    streamName := strings.ToUpper(serviceName) + "_DLQ"
    
    timer := time.NewTicker(30 * time.Second)
    for range timer.C {
        info, _ := nc.StreamInfo(streamName)
        msgCount := info.State.Msgs
        
        if msgCount > int64(threshold) {
            alert := Alert{
                Severity:  "P2",
                Service:   serviceName,
                Message:   fmt.Sprintf("DLQ tiene %d mensajes (umbral: %d)", msgCount, threshold),
                Timestamp: time.Now(),
            }
            publishAlert(nc, alert)
        }
    }
}
```

---

## 8. Esquemas de Mensajes

### 8.1 Evento: Order Filled

```json
{
  "specversion": "1.0",
  "id": "evt_order_filled_001",
  "source": "tnsvt-v2/broker-gateway",
  "type": "tnsvt.trading.order.filled",
  "datacontenttype": "application/json",
  "subject": "order-ORD-20260714-001",
  "time": "2026-07-14T10:30:00.000Z",
  "traceid": "4bf92f3577b34da6a6ce93a30f8e2b0a",
  "spanid": "00f067aa0ba902b7",
  "tenantid": "tenant_abc123",
  "userid": "user_xyz789",
  "correlationid": "corr-12345",
  "data": {
    "orderId": "ORD-20260714-001",
    "symbol": "EURUSD",
    "side": "BUY",
    "type": "LIMIT",
    "quantity": 1.0,
    "fillPrice": 1.0842,
    "broker": "MT5",
    "brokerAccountId": "MT5-123456",
    "commission": 7.0,
    "slippage": 0.00001,
    "positionId": "POS-20260714-001",
    "strategyId": "strat_scalping_01",
    "copyTradeIds": ["ct-001", "ct-002"],
    "filledAt": "2026-07-14T10:30:00.000Z",
    "pnlRealized": 0.0
  }
}
```

### 8.2 Evento: Risk Check Request

```json
{
  "specversion": "1.0",
  "id": "evt_risk_check_001",
  "source": "tnsvt-v2/trading-engine",
  "type": "tnsvt.risk.check.request",
  "datacontenttype": "application/json",
  "subject": "risk-check-RQ-001",
  "time": "2026-07-14T10:29:59.500Z",
  "traceid": "4bf92f3577b34da6a6ce93a30f8e2b0a",
  "spanid": "a1b2c3d4e5f67890",
  "tenantid": "tenant_abc123",
  "correlationid": "corr-12345",
  "data": {
    "requestId": "RQ-001",
    "symbol": "EURUSD",
    "side": "BUY",
    "quantity": 1.0,
    "accountId": "MT5-123456",
    "portfolio": {
      "totalEquity": 50000.0,
      "currentDrawdown": 0.02,
      "openPositions": 3,
      "dailyPnL": 150.0
    },
    "riskLimits": {
      "maxPositionSize": 5.0,
      "maxDailyDrawdown": 0.05,
      "maxOpenPositions": 10,
      "maxDailyTrades": 50
    }
  }
}
```

### 8.3 Evento: AI Prediction

```json
{
  "specversion": "1.0",
  "id": "evt_ai_pred_001",
  "source": "tnsvt-v2/ai-engine",
  "type": "tnsvt.ai.model.prediction",
  "datacontenttype": "application/json",
  "subject": "prediction-EURUSD-1h",
  "time": "2026-07-14T10:29:58.000Z",
  "traceid": "5cf08e3677b34da6a6ce93a30f8e2b0b",
  "spanid": "b2c3d4e5f6789012",
  "tenantid": "tenant_abc123",
  "correlationid": "corr-12345",
  "data": {
    "modelId": "model_lstm_eurusd_v3",
    "modelVersion": "3.2.1",
    "symbol": "EURUSD",
    "timeframe": "1h",
    "prediction": {
      "direction": "BUY",
      "confidence": 0.82,
      "targetPrice": 1.0865,
      "stopLoss": 1.0810,
      "takeProfit": 1.0870,
      "expectedMove": 0.0023,
      "timeHorizon": "4h"
    },
    "features": {
      "rsi14": 42.5,
      "macd": 0.0003,
      "bollingerPosition": 0.3,
      "volumeProfile": "increasing",
      "sentimentScore": 0.65
    },
    "latencyMs": 45
  }
}
```

### 8.4 Evento: Copy Trade Signal

```json
{
  "specversion": "1.0",
  "id": "evt_copy_001",
  "source": "tnsvt-v2/copy-trading",
  "type": "tnsvt.trading.signal.received",
  "datacontenttype": "application/json",
  "subject": "signal-master-001",
  "time": "2026-07-14T10:29:57.000Z",
  "traceid": "6dg09f4788c45eb7b7df04b31g9f3c1b",
  "spanid": "c3d4e5f678901234",
  "tenantid": "tenant_abc123",
  "correlationid": "corr-12345",
  "data": {
    "masterAccountId": "MT5-M-999",
    "masterStrategy": "scalping_pro",
    "signal": {
      "symbol": "EURUSD",
      "side": "BUY",
      "quantity": 2.0,
      "entryPrice": 1.0842,
      "stopLoss": 1.0810,
      "takeProfit": 1.0870
    },
    "followers": [
      {
        "followerId": "user_follower_01",
        "accountId": "MT5-F-101",
        "allocationType": "proportional",
        "allocationPercent": 0.5,
        "riskMultiplier": 1.0
      },
      {
        "followerId": "user_follower_02",
        "accountId": "CT-F-202",
        "allocationType": "fixed",
        "fixedLots": 0.1,
        "riskMultiplier": 0.5
      }
    ],
    "totalFollowers": 2
  }
}
```

---

## 9. Configuración JetStream

### Streams Principales

| Stream Name   | Subjects                   | Retention  | Max Messages | Max Age  | Replicas | Storage |
|---------------|----------------------------|------------|--------------|----------|----------|---------|
| TRADING       | `trading.>`               | WorkQueue  | 1M           | 168h(7d) | 3        | File    |
| RISK          | `risk.>`                  | Limits     | 500K         | 336h(14d)| 3        | File    |
| AI            | `ai.>`                    | Limits     | 200K         | 72h(3d)  | 3        | File    |
| BROKER        | `broker.>`                | WorkQueue  | 1M           | 168h(7d) | 3        | File    |
| PLATFORM      | `platform.>`              | Limits     | 500K         | 720h(30d)| 3        | File    |
| NOTIFICATION  | `notification.>`          | WorkQueue  | 200K         | 168h(7d) | 3        | File    |
| AUDIT         | `tnsvt.audit.>`           | Limits     | ∞            | ∞        | 3        | File    |
| DLQ_GLOBAL    | `*.dlq.>`                 | Limits     | 100K         | 720h(30d)| 3        | File    |

### Configuración Completa de Streams

```yaml
# docker-compose.nats.yml
services:
  nats:
    image: nats:2.10-alpine
    command: >
      --jetstream
      --store_dir /data
      --max_mem 1G
      --max_file 50G
      --cluster_id tns-v2-cluster
      --routes nats://nats-1:6222,nats://nats-2:6222,nats://nats-3:6222
    volumes:
      - nats-data:/data

# Stream: TRADING
# Creado vía API al inicio del trading-engine
```

**Script de Inicialización de Streams (Go):**

```go
func InitializeStreams(nc *nats.Conn) error {
    streams := []nats.StreamConfig{
        {
            Name:      "TRADING",
            Subjects:  []string{"trading.>"},
            Retention: nats.WorkQueuePolicy,
            MaxMsgs:   1_000_000,
            MaxAge:    168 * time.Hour, // 7 días
            Storage:   nats.FileStorage,
            Replicas:  3,
            Discard:   nats.DiscardOld,
            MaxBytes:  50 * 1024 * 1024 * 1024, // 50GB
        },
        {
            Name:      "RISK",
            Subjects:  []string{"risk.>"},
            Retention: nats.LimitsPolicy,
            MaxMsgs:   500_000,
            MaxAge:    336 * time.Hour, // 14 días
            Storage:   nats.FileStorage,
            Replicas:  3,
            Discard:   nats.DiscardOld,
            MaxBytes:  20 * 1024 * 1024 * 1024, // 20GB
        },
        {
            Name:      "AI",
            Subjects:  []string{"ai.>"},
            Retention: nats.LimitsPolicy,
            MaxMsgs:   200_000,
            MaxAge:    72 * time.Hour, // 3 días
            Storage:   nats.FileStorage,
            Replicas:  3,
            Discard:   nats.DiscardOld,
            MaxBytes:  10 * 1024 * 1024 * 1024, // 10GB
        },
        {
            Name:      "BROKER",
            Subjects:  []string{"broker.>"},
            Retention: nats.WorkQueuePolicy,
            MaxMsgs:   1_000_000,
            MaxAge:    168 * time.Hour, // 7 días
            Storage:   nats.FileStorage,
            Replicas:  3,
            Discard:   nats.DiscardOld,
            MaxBytes:  30 * 1024 * 1024 * 1024, // 30GB
        },
        {
            Name:      "PLATFORM",
            Subjects:  []string{"platform.>"},
            Retention: nats.LimitsPolicy,
            MaxMsgs:   500_000,
            MaxAge:    720 * time.Hour, // 30 días
            Storage:   nats.FileStorage,
            Replicas:  3,
            Discard:   nats.DiscardOld,
            MaxBytes:  20 * 1024 * 1024 * 1024, // 20GB
        },
        {
            Name:      "NOTIFICATION",
            Subjects:  []string{"notification.>"},
            Retention: nats.WorkQueuePolicy,
            MaxMsgs:   200_000,
            MaxAge:    168 * time.Hour, // 7 días
            Storage:   nats.FileStorage,
            Replicas:  3,
            Discard:   nats.DiscardOld,
            MaxBytes:  5 * 1024 * 1024 * 1024, // 5GB
        },
        {
            Name:      "AUDIT",
            Subjects:  []string{"tnsvt.audit.>"},
            Retention: nats.LimitsPolicy,
            MaxMsgs:   -1, // Sin límite
            MaxAge:    -1,  // Sin expiración
            Storage:   nats.FileStorage,
            Replicas:  3,
            Discard:   nats.DiscardOld,
            MaxBytes:  -1, // Sin límite
        },
        {
            Name:      "DLQ_GLOBAL",
            Subjects:  []string{"*.dlq.>"},
            Retention: nats.LimitsPolicy,
            MaxMsgs:   100_000,
            MaxAge:    720 * time.Hour, // 30 días
            Storage:   nats.FileStorage,
            Replicas:  3,
            Discard:   nats.DiscardOld,
            MaxBytes:  10 * 1024 * 1024 * 1024, // 10GB
        },
    }
    
    js, err := nc.JetStream()
    if err != nil {
        return err
    }
    
    for _, cfg := range streams {
        _, err := js.AddStream(&cfg)
        if err != nil {
            return fmt.Errorf("error creating stream %s: %w", cfg.Name, err)
        }
    }
    
    return nil
}
```

### Consumer Groups

```yaml
consumers:
  trading-engine:
    stream: TRADING
    durable: trading-engine-main
    filter_subject: trading.order.*
    ack_policy: explicit
    max_deliver: 3
    ack_wait: 30s
    
  risk-engine:
    stream: TRADING
    durable: risk-engine-main
    filter_subject: trading.signal.*
    ack_policy: explicit
    max_deliver: 2
    ack_wait: 10s
    
  notification-service:
    stream: TRADING
    durable: notif-engine-main
    filter_subject: trading.>
    ack_policy: explicit
    max_deliver: 5
    ack_wait: 60s
    
  audit-service:
    stream: TRADING
    durable: audit-engine-main
    filter_subject: trading.>
    ack_policy: none  # Solo lectura
    max_deliver: 1
    
  copy-trading:
    stream: TRADING
    durable: copy-trading-main
    filter_subject: trading.signal.*
    ack_policy: explicit
    max_deliver: 3
    ack_wait: 30s
```

---

## Métricas de Comunicación

Las siguientes métricas se exponen vía Prometheus:

| Métrica                              | Tipo    | Descripción                              |
|--------------------------------------|---------|------------------------------------------|
| `nats_messages_published_total`      | Counter | Total de mensajes publicados             |
| `nats_messages_consumed_total`       | Counter | Total de mensajes consumidos             |
| `nats_message_latency_ms`           | Gauge   | Latencia de publicación/consumo          |
| `nats_stream_msgs_count`            | Gauge   | Mensajes en stream                       |
| `nats_stream_bytes`                 | Gauge   | Bytes en stream                          |
| `nats_consumer_pending_count`       | Gauge   | Mensajes pendientes de consumer          |
| `nats_dlq_messages_total`           | Gauge   | Mensajes en DLQ                          |
| `nats_request_timeout_total`        | Counter | Requests con timeout                     |
| `saga_step_duration_seconds`        | Histogram| Duración de cada paso de saga           |
| `saga_step_failures_total`          | Counter | Fallos por paso de saga                  |
| `saga_compensation_total`           | Counter | Compensaciones ejecutadas                |

---

**Fin del documento 05 — Comunicación entre Servicios**
