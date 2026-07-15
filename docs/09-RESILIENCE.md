# DOCUMENT 09: RESILIENCIA

## Plataforma de Trading TNSVT V2 — Patrones de Resiliencia

**Version:** 2.0.0  
**Fecha:** 2026-07-14  
**Estado:** Produccion  
**Autor:** Equipo de Arquitectura TNSVT V2

---

## Tabla de Contenidos

1. [Vision General de Resiliencia](#1-vision-general-de-resiliencia)
2. [Circuit Breaker](#2-circuit-breaker)
3. [Bulkhead Pattern](#3-bulkhead-pattern)
4. [Retry Policies](#4-retry-policies)
5. [Graceful Degradation](#5-graceful-degradation)
6. [Health Checks](#6-health-checks)
7. [Disaster Recovery](#7-disaster-recovery)
8. [Backup Strategy](#8-backup-strategy)
9. [Failover Procedures](#9-failover-procedures)
10. [Chaos Engineering](#10-chaos-engineering)
11. [Load Shedding](#11-load-shedding)
12. [Timeout Budgets](#12-timeout-budgets)
13. [Dead Letter Queue Handling](#13-dead-letter-queue-handling)

---

## 1. Vision General de Resiliencia

```
+-----------------------------------------------------------------------+
|              ARQUITECTURA DE RESILIENCIA TNSVT V2                      |
+-----------------------------------------------------------------------+
|                                                                       |
|  Capa 1: PROTECCION INDIVIDUAL                                       |
|  +---------------------------------------------------------------+   |
|  | Circuit Breaker | Retry | Timeout | Rate Limiter | Bulkhead  |   |
|  +---------------------------------------------------------------+   |
|                                                                       |
|  Capa 2: PROTECCION ENTRE SERVICIOS                                  |
|  +---------------------------------------------------------------+   |
|  | Load Shedding | Health Checks | Graceful Degradation | DLQ   |   |
|  +---------------------------------------------------------------+   |
|                                                                       |
|  Capa 3: PROTECCION GLOBAL                                           |
|  +---------------------------------------------------------------+   |
|  | Failover | Disaster Recovery | Chaos Engineering | Backups  |   |
|  +---------------------------------------------------------------+   |
|                                                                       |
+-----------------------------------------------------------------------+
```

### Metricas de Resiliencia

| Metrica                        | Meta              | Medicion                    |
|--------------------------------|-------------------|-----------------------------|
| Disponibilidad global          | 99.95%            | Uptime 30 dias              |
| Mean Time Between Failures     | > 72 horas        | MTBF mensual                |
| Mean Time To Recovery          | < 15 minutos      | MTR promedio                |
| Recovery Point Objective       | < 5 minutos       | Ultimo backup WAL           |
| Recovery Time Objective        | < 15 minutos      | Tiempo de failover          |

---

## 2. Circuit Breaker

### 2.1 Estados

```
                    CIRCUIT BREAKER STATE MACHINE
+------------------------------------------------------------------+
|                                                                    |
|   CLOSED ──── (failures > threshold) ────► OPEN                   |
|     │                                         │                    |
|     │ (success)                               │ (timeout)         |
|     │                                         │                    |
|     ◄── (half-open success)                   ▼                   |
|     │                                   HALF-OPEN                 |
|     │                                         │                    |
|     │                                   (failure)                 |
|     │                                         │                    |
|     │                                         └───► OPEN          |
|                                                                    |
+------------------------------------------------------------------+
```

### 2.2 Configuracion por Servicio

| Servicio          | Failure Threshold | Success Threshold | Timeout  | Half-Open | Max Requests |
|-------------------|-------------------|-------------------|----------|-----------|--------------|
| risk-engine       | 3 fallos          | 2 exitos          | 5s       | 1 req     | 10           |
| broker-gateway    | 5 fallos          | 3 exitos          | 30s      | 2 req     | 20           |
| ai-engine         | 5 fallos          | 3 exitos          | 10s      | 2 req     | 15           |
| postgresql        | 3 fallos          | 2 exitos          | 5s       | 1 req     | 10           |
| redis             | 3 fallos          | 2 exitos          | 3s       | 1 req     | 10           |
| nats              | 3 fallos          | 2 exitos          | 5s       | 1 req     | 10           |
| notification-svc  | 10 fallos         | 5 exitos          | 60s      | 3 req     | 50           |

### 2.3 Implementacion Go

```go
type CircuitState int

const (
    CircuitClosed CircuitState = iota
    CircuitOpen
    CircuitHalfOpen
)

type CircuitBreaker struct {
    mu               sync.Mutex
    state            CircuitState
    name             string
    failureCount     int
    successCount     int
    failureThreshold int
    successThreshold int
    openTimeout      time.Duration
    lastFailureTime  time.Duration
    halfOpenMax      int
    halfOpenCount    int
    metrics          *CircuitMetrics
}

type CircuitMetrics struct {
    stateChanges    *prometheus.CounterVec
    failures        *prometheus.CounterVec
    successes       *prometheus.CounterVec
    currentState    *prometheus.GaugeVec
}

func NewCircuitBreaker(name string, cfg CircuitConfig) *CircuitBreaker {
    cb := &CircuitBreaker{
        state:            CircuitClosed,
        name:             name,
        failureThreshold: cfg.FailureThreshold,
        successThreshold: cfg.SuccessThreshold,
        openTimeout:      cfg.OpenTimeout,
        halfOpenMax:      cfg.HalfOpenMax,
        metrics:          NewCircuitMetrics(name),
    }
    cb.metrics.currentState.WithLabelValues(name).Set(0)
    return cb
}

func (cb *CircuitBreaker) Allow() bool {
    cb.mu.Lock()
    defer cb.mu.Unlock()
    
    switch cb.state {
    case CircuitClosed:
        return true
    case CircuitOpen:
        if time.Since(cb.lastFailureTime) > cb.openTimeout {
            cb.setState(CircuitHalfOpen)
            cb.halfOpenCount = 0
            return true
        }
        return false
    case CircuitHalfOpen:
        return cb.halfOpenCount < cb.halfOpenMax
    }
    return false
}

func (cb *CircuitBreaker) RecordSuccess() {
    cb.mu.Lock()
    defer cb.mu.Unlock()
    
    cb.metrics.successes.WithLabelValues(cb.name).Inc()
    
    switch cb.state {
    case CircuitClosed:
        cb.failureCount = 0
    case CircuitHalfOpen:
        cb.successCount++
        if cb.successCount >= cb.successThreshold {
            cb.setState(CircuitClosed)
            cb.failureCount = 0
            cb.successCount = 0
        }
    }
}

func (cb *CircuitBreaker) RecordFailure() {
    cb.mu.Lock()
    defer cb.mu.Unlock()
    
    cb.metrics.failures.WithLabelValues(cb.name).Inc()
    cb.lastFailureTime = time.Now()
    
    switch cb.state {
    case CircuitClosed:
        cb.failureCount++
        if cb.failureCount >= cb.failureThreshold {
            cb.setState(CircuitOpen)
        }
    case CircuitHalfOpen:
        cb.setState(CircuitOpen)
    }
}

func (cb *CircuitBreaker) setState(state CircuitState) {
    oldState := cb.state
    cb.state = state
    cb.metrics.stateChanges.WithLabelValues(cb.name, 
        oldState.String(), state.String()).Inc()
    cb.metrics.currentState.WithLabelValues(cb.name).Set(float64(state))
    
    log.Warn().
        Str("circuit", cb.name).
        Str("from", oldState.String()).
        Str("to", state.String()).
        Msg("Circuit breaker state change")
}
```

### 2.4 Dashboard de Circuit Breakers

```
+------------------------------------------------------------------+
|  CIRCUIT BREAKER STATUS                                          |
+------------------------------------------------------------------+
|                                                                   |
|  risk-engine    [CLOSED  ]  Failures: 0/3    Last: OK           |
|  broker-mt5     [CLOSED  ]  Failures: 1/5    Last: OK           |
|  broker-binance [CLOSED  ]  Failures: 0/5    Last: OK           |
|  ai-engine      [HALF-OPN]  Failures: 4/5    Last: timeout      |
|  postgresql     [CLOSED  ]  Failures: 0/3    Last: OK           |
|  redis          [CLOSED  ]  Failures: 0/3    Last: OK           |
|  nats           [CLOSED  ]  Failures: 0/3    Last: OK           |
|  notification   [OPEN    ]  Failures: 8/10   Last: 500 error    |
|                                                                   |
+------------------------------------------------------------------+
```

---

## 3. Bulkhead Pattern

### 3.1 Aislamiento por Dominio

```
+------------------------------------------------------------------+
|                    BULKHEAD PATTERN TNSVT V2                       |
+------------------------------------------------------------------+
|                                                                   |
|  +-----------+  +-----------+  +-----------+  +-----------+     |
|  | TRADING   |  | RISK      |  | BROKER    |  | AI/ML     |     |
|  | POOL      |  | POOL      |  | POOL      |  | POOL      |     |
|  |           |  |           |  |           |  |           |     |
|  | Max: 50   |  | Max: 30   |  | Max: 20   |  | Max: 10   |     |
|  | Queue: 200|  | Queue: 100|  | Queue: 50 |  | Queue: 50 |     |
|  | Timeout:  |  | Timeout:  |  | Timeout:  |  | Timeout:  |     |
|  |   500ms   |  |   100ms   |  |   5000ms  |  |   2000ms  |     |
|  +-----------+  +-----------+  +-----------+  +-----------+     |
|                                                                   |
|  Cada pool tiene:                                                 |
|  - Worker pool independiente                                      |
|  - Cola de requests independiente                                 |
|  - Timeout independiente                                          |
|  - Contadores separados                                           |
|  - Si un pool se llena, NO afecta a los demas                    |
|                                                                   |
+------------------------------------------------------------------+
```

### 3.2 Configuracion de Bulkheads

| Bulkhead       | Max Workers | Queue Size | Timeout  | Overflow Policy |
|----------------|-------------|------------|----------|-----------------|
| trading-core   | 50          | 200        | 500ms    | Reject          |
| risk-check     | 30          | 100        | 100ms    | Reject          |
| broker-exec    | 20          | 50         | 5000ms   | Reject          |
| ai-inference   | 10          | 50         | 2000ms   | Reject          |
| notification   | 20          | 500        | 10000ms  | Drop Oldest     |
| audit-write    | 10          | 200        | 1000ms   | Reject          |

### 3.3 Implementacion

```go
type Bulkhead struct {
    name      string
    sem       chan struct{}
    queue     chan struct{}
    timeout   time.Duration
    metrics   *BulkheadMetrics
}

func NewBulkhead(name string, maxWorkers, queueSize int, timeout time.Duration) *Bulkhead {
    return &Bulkhead{
        name:    name,
        sem:     make(chan struct{}, maxWorkers),
        queue:   make(chan struct{}, queueSize),
        timeout: timeout,
        metrics: NewBulkheadMetrics(name),
    }
}

func (b *Bulkhead) Execute(ctx context.Context, fn func() error) error {
    // Intentar entrar a la cola
    select {
    case b.queue <- struct{}{}:
        defer func() { <-b.queue }()
    default:
        b.metrics.rejected.Inc()
        return fmt.Errorf("bulkhead %s: cola llena, request rechazado", b.name)
    }
    
    // Intentar obtener un worker
    timer := time.NewTimer(b.timeout)
    defer timer.Stop()
    
    select {
    case b.sem <- struct{}{}:
        defer func() { <-b.sem }()
        b.metrics.activeWorkers.Inc()
        defer b.metrics.activeWorkers.Dec()
        return fn()
    case <-timer.C:
        b.metrics.timeout.Inc()
        return fmt.Errorf("bulkhead %s: timeout esperando worker", b.name)
    case <-ctx.Done():
        return ctx.Err()
    }
}
```

---

## 4. Retry Policies

### 4.1 Politicas por Servicio

| Servicio          | Max Retries | Base Delay | Max Delay | Jitter | Backoff     |
|-------------------|-------------|------------|-----------|--------|-------------|
| risk-engine       | 2           | 50ms       | 500ms     | 25ms   | Exponential |
| broker-gateway    | 5           | 500ms      | 30s       | 100ms  | Exponential |
| ai-engine         | 2           | 200ms      | 2s        | 50ms   | Exponential |
| notification-svc  | 5           | 1s         | 60s       | 500ms  | Exponential |
| platform-api      | 3           | 200ms      | 5s        | 100ms  | Exponential |
| audit-service     | 3           | 100ms      | 5s        | 50ms   | Exponential |
| copy-trading      | 3           | 200ms      | 5s        | 100ms  | Exponential |

### 4.2 Implementacion

```go
type RetryConfig struct {
    MaxAttempts     int
    BaseDelay       time.Duration
    MaxDelay        time.Duration
    Jitter          time.Duration
    RetryableErrors []string
}

type RetryPolicy struct {
    config  RetryConfig
    breaker *CircuitBreaker
    metrics *RetryMetrics
}

func (r *RetryPolicy) Execute(ctx context.Context, operation string, fn func() error) error {
    var lastErr error
    
    for attempt := 0; attempt <= r.config.MaxAttempts; attempt++ {
        if attempt > 0 {
            if r.breaker != nil && !r.breaker.Allow() {
                r.metrics.circuitBlocked.Inc()
                return ErrCircuitBreakerOpen
            }
            
            delay := r.calculateDelay(attempt)
            
            log.Debug().
                Str("operation", operation).
                Int("attempt", attempt).
                Dur("delay", delay).
                Msg("Reintentando operacion")
            
            select {
            case <-ctx.Done():
                return ctx.Err()
            case <-time.After(delay):
            }
        }
        
        lastErr = fn()
        
        if lastErr == nil {
            if r.breaker != nil {
                r.breaker.RecordSuccess()
            }
            r.metrics.recordSuccess(operation, attempt)
            return nil
        }
        
        if !r.isRetryable(lastErr) {
            break
        }
        
        if r.breaker != nil {
            r.breaker.RecordFailure()
        }
    }
    
    r.metrics.recordFailure(operation, r.config.MaxAttempts)
    return fmt.Errorf("max reintentos (%d) alcanzado para %s: %w",
        r.config.MaxAttempts, operation, lastErr)
}

func (r *RetryPolicy) calculateDelay(attempt int) time.Duration {
    delay := r.config.BaseDelay * time.Duration(math.Pow(2, float64(attempt-1)))
    if delay > r.config.MaxDelay {
        delay = r.config.MaxDelay
    }
    
    if r.config.Jitter > 0 {
        jitterRange := int64(r.config.Jitter) * 2
        jitterOffset := time.Duration(rand.Int63n(jitterRange) - int64(r.config.Jitter))
        delay += jitterOffset
        if delay < 0 {
            delay = 0
        }
    }
    
    return delay
}
```

---

## 5. Graceful Degradation

### 5.1 Comportamiento por Fallo de Servicio

```
+------------------------------------------------------------------------+
|               GRACEFUL DEGRADATION POR SERVICIO                         |
+------------------------------------------------------------------------+
|                                                                         |
|  SI risk-engine FALLA:                                                  |
|  ┌─────────────────────────────────────────────────────────────────┐   |
|  │ Trading Engine:                                                   │   |
|  │   - Circuit breaker se abre                                      │   |
|  │   - NO nuevas ordenes (rechazar con 503)                        │   |
|  │   - Posiciones abiertas se mantienen                            │   |
|  │   - Alerta P1 inmediata                                          │   |
|  │   - Risk pre-configurado se usa como fallback                    │   |
|  └─────────────────────────────────────────────────────────────────┘   |
|                                                                         |
|  SI broker-gateway FALLA:                                               |
|  ┌─────────────────────────────────────────────────────────────────┐   |
|  │ Trading Engine:                                                   │   |
|  │   - Nuevas ordenes se encolan (max 100)                        │   |
|  │   - Ordenes pendientes reintentadas al reconectar               │   |
|  │   - Posiciones existentes se monitorean via polling             │   |
|  │   - Notificacion a usuarios afectados                           │   |
|  │   - Alerta P1 inmediata                                          │   |
|  └─────────────────────────────────────────────────────────────────┘   |
|                                                                         |
|  SI ai-engine FALLA:                                                    |
|  ┌─────────────────────────────────────────────────────────────────┐   |
|  │ Trading Engine:                                                   │   |
│  │   - Predicciones AI se ignoran temporalmente                     │   |
│  │   - Se usan señales solo de trading basico                      │   |
|  │   - Copy trading funciona normalmente                           │   |
|  │   - Alerta P3 (no critico para trading)                         │   |
|  │   - Notificacion a usuarios con estrategias AI                  │   |
|  └─────────────────────────────────────────────────────────────────┘   |
|                                                                         |
|  SI redis FALLA:                                                        |
|  ┌─────────────────────────────────────────────────────────────────┐   |
|  │ Todos los servicios:                                             │   |
|  │   - Cache miss: datos se leen directo de PostgreSQL             │   |
|  │   - Rate limiting deshabilitado (pasar todo)                    │   |
|  │   - Sesiones se revalidan contra PostgreSQL                     │   |
|  │   - Performance degradada pero funcional                        │   |
|  │   - Alerta P2 inmediata                                          │   |
|  └─────────────────────────────────────────────────────────────────┘   |
|                                                                         |
|  SI notification-service FALLA:                                         |
|  ┌─────────────────────────────────────────────────────────────────┐   |
|  │ Todos los servicios:                                             │   |
|  │   - Notificaciones se encolan en NATS (persistente)            │   |
|  │   - Se procesan al reconectar                                    │   |
|  │   - Trading normalmente funcional                               │   |
|  │   - Alerta P3                                                   │   |
|  └─────────────────────────────────────────────────────────────────┘   |
|                                                                         |
|  SI PostgreSQL FALLA:                                                   |
|  ┌─────────────────────────────────────────────────────────────────┐   |
|  │ Todos los servicios:                                             │   |
|  │   - Circuit breaker se abre                                      │   |
|  │   - Trading se detiene (CRITICO)                                │   |
|  │   - Failover automatico a replica (si HA configurado)           │   |
|  │   - Alerta P1 inmediata                                          │   |
|  │   - DR plan activado                                             │   |
|  └─────────────────────────────────────────────────────────────────┘   |
|                                                                         |
+------------------------------------------------------------------------+
```

---

## 6. Health Checks

### 6.1 Tipos de Health Check

| Tipo        | Endpoint              | Verifica                           | Frecuencia |
|-------------|-----------------------|------------------------------------|------------|
| Liveness    | `/health/live`        | Proceso vivo                       | 10s        |
| Readiness   | `/health/ready`       | Listo para recibir trafico         | 5s         |
| Startup     | `/health/startup`     | Inicio completo                    | 5s (30 max)|

### 6.2 Implementacion

```go
type HealthChecker struct {
    checks map[string]HealthCheck
    mu     sync.RWMutex
}

type HealthCheck struct {
    Name      string
    Check     func(ctx context.Context) error
    Timeout   time.Duration
    Critical  bool  // Si falla, el servicio NO esta ready
}

func (h *HealthChecker) LivenessHandler(w http.ResponseWriter, r *http.Request) {
    // Liveness: solo verifica que el proceso este vivo
    w.WriteHeader(http.StatusOK)
    json.NewEncoder(w).Encode(map[string]string{"status": "alive"})
}

func (h *HealthChecker) ReadinessHandler(w http.ResponseWriter, r *http.Request) {
    ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
    defer cancel()
    
    h.mu.RLock()
    defer h.mu.RUnlock()
    
    status := map[string]string{}
    allHealthy := true
    
    for name, check := range h.checks {
        checkCtx, checkCancel := context.WithTimeout(ctx, check.Timeout)
        defer checkCancel()
        
        if err := check.Check(checkCtx); err != nil {
            status[name] = fmt.Sprintf("unhealthy: %v", err)
            if check.Critical {
                allHealthy = false
            }
        } else {
            status[name] = "healthy"
        }
    }
    
    if allHealthy {
        w.WriteHeader(http.StatusOK)
    } else {
        w.WriteHeader(http.StatusServiceUnavailable)
    }
    
    json.NewEncoder(w).Encode(status)
}

func DefaultChecks(db *sql.DB, redis *redis.Client, nc *nats.Conn) []HealthCheck {
    return []HealthCheck{
        {
            Name:     "postgresql",
            Critical: true,
            Timeout:  3 * time.Second,
            Check: func(ctx context.Context) error {
                return db.PingContext(ctx)
            },
        },
        {
            Name:     "redis",
            Critical: false,
            Timeout:  2 * time.Second,
            Check: func(ctx context.Context) error {
                return redis.Ping(ctx).Err()
            },
        },
        {
            Name:     "nats",
            Critical: true,
            Timeout:  3 * time.Second,
            Check: func(ctx context.Context) error {
                if !nc.IsConnected() {
                    return fmt.Errorf("not connected")
                }
                return nil
            },
        },
        {
            Name:     "disk_space",
            Critical: false,
            Timeout:  1 * time.Second,
            Check: func(ctx context.Context) error {
                var stat unix.Statfs_t
                if err := unix.Statfs("/", &stat); err != nil {
                    return err
                }
                usagePercent := float64(stat.Bfree) / float64(stat.Blocks) * 100
                if usagePercent < 10 {
                    return fmt.Errorf("disk space low: %.1f%% free", usagePercent)
                }
                return nil
            },
        },
    }
}
```

---

## 7. Disaster Recovery

### 7.1 RTO/RPO Targets

| Componente       | RTO          | RPO          | Estrategia                           |
|------------------|--------------|--------------|--------------------------------------|
| PostgreSQL       | 5 min        | 0 (WAL sync) | Streaming replication + automatico   |
| TimescaleDB      | 10 min       | 5 min        | WAL archiving + snapshot diario      |
| Redis            | 2 min        | 1 min        | AOF + replica                        |
| NATS             | 1 min        | 0 (JetStream) | Clustering 3 nodos                 |
| Vault            | 5 min        | 0            | HA con 3 nodos                       |
| Servicios Go     | 2 min        | N/A          | Re-deploy automatico                 |
| Datos de usuario | 15 min       | 5 min        | Backup continuo a S3                 |

### 7.2 DR Runbook

```
+------------------------------------------------------------------+
|              DISASTER RECOVERY PROCEDURE                          |
+------------------------------------------------------------------+
|                                                                   |
|  1. DETECCION                                                    |
|  ┌──────────────────────────────────────────────────────────┐   |
|  │ Monitoreo detecta fallo → Alerta P1 → PagerDuty          │   |
|  │ On-call engineer acknowledge en < 5 min                  │   |
|  └──────────────────────────────────────────────────────────┘   |
|                                                                   |
|  2. ASSESSMENT (5 min)                                          |
|  ┌──────────────────────────────────────────────────────────┐   |
|  │ - Cual servicio fallo?                                    │   |
|  │ - Afecta trading activo?                                  │   |
|  │ - Hay posiciones abiertas en riesgo?                     │   |
|  │ - Auto-failover ya se ejecuto?                           │   |
|  └──────────────────────────────────────────────────────────┘   |
|                                                                   |
|  3. CONTAINMENT (5 min)                                         |
|  ┌──────────────────────────────────────────────────────────┐   |
|  │ Si trading afectado:                                      │   |
|  │   - PAUSAR nuevas ordenes via circuit breaker            │   |
|  │   - NOTIFICAR a usuarios con posiciones abiertas        │   |
|  │   - MONITOREAR posiciones existentes                     │   |
|  └──────────────────────────────────────────────────────────┘   |
|                                                                   |
|  4. RECOVERY (15 min)                                           |
|  ┌──────────────────────────────────────────────────────────┐   |
|  │ PostgreSQL down:                                          │   |
|  │   - Promover replica a primary                            │   |
|  │   - Actualizar connection strings                         │   |
|  │   - Re-deploy servicios con nueva config                  │   |
|  │                                                           │   |
|  │ Servicio Go down:                                         │   |
|  │   - Kubernetes auto-restart (si K8s)                      │   |
|  │   - Si falla persiste: re-deploy con imagen anterior      │   |
|  │   - Si imagen corrupta: rollback a version estable        │   |
|  └──────────────────────────────────────────────────────────┘   |
|                                                                   |
|  5. VERIFICATION (5 min)                                        |
|  ┌──────────────────────────────────────────────────────────┐   |
|  │ - Health checks pasando?                                  │   |
|  │ - Trades ejecutandose normalmente?                       │   |
|  │ - Latencia en rangos aceptables?                         │   |
|  │ - Sin errores en logs recientes?                         │   |
|  └──────────────────────────────────────────────────────────┘   |
|                                                                   |
|  6. POST-MORTEM                                                  |
|  ┌──────────────────────────────────────────────────────────┐   |
|  │ - Documentar timeline completo                            │   |
|  │ - Identificar root cause                                  │   |
|  │ - Crear action items para prevenir recurrencia           │   |
|  │ - Actualizar runbooks si necesario                        │   |
|  └──────────────────────────────────────────────────────────┘   |
+------------------------------------------------------------------+
```

---

## 8. Backup Strategy

### 8.1 Continuous WAL Archiving

```yaml
# backup-cron.yml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgres-backup
  namespace: data
spec:
  schedule: "0 */6 * * *"  # Cada 6 horas
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: backup
              image: registry.tnsvt.com/backup-agent:latest
              command:
                - /bin/sh
                - -c
                - |
                  pg_basebackup \
                    -h postgresql \
                    -U backup \
                    -D /backup/snapshot-$(date +%Y%m%d-%H%M) \
                    -Ft -z -Xs -P
                    
                  # Upload to S3
                  aws s3 sync /backup/ s3://tnsvt-backups/postgres/ \
                    --sse AES256 \
                    --storage-class STANDARD_IA
              env:
                - name: PGPASSWORD
                  valueFrom:
                    secretKeyRef:
                      name: backup-credentials
                      key: password
              volumeMounts:
                - name: backup-storage
                  mountPath: /backup
          volumes:
            - name: backup-storage
              emptyDir:
                sizeLimit: 50Gi
          restartPolicy: OnFailure
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
```

### 8.2 Backup Schedule

| Backup Type       | Frecuencia     | Retencion  | Almacenamiento  |
|-------------------|----------------|------------|-----------------|
| WAL archiving     | Continuo       | 7 dias     | S3 Standard     |
| Base backup       | Cada 6 horas   | 30 dias    | S3 Standard-IA  |
| Snapshot diario   | Diario 2:00 AM | 90 dias    | S3 Standard     |
| Backup semanal    | Domingo 2:00AM | 1 ano      | S3 Glacier      |
| Backup mensual    | 1ro del mes    | 7 anos     | S3 Glacier Deep |

---

## 9. Failover Procedures

### 9.1 PostgreSQL HA Failover

```
+------------------------------------------------------------------+
|           POSTGRESQL FAILOVER AUTOMATICO                           |
+------------------------------------------------------------------+
|                                                                   |
|  Primary ──── streaming ────► Replica 1                          |
|     │                          (sync)                             |
|     └──────── streaming ────► Replica 2                          |
|                                (async)                            |
|                                                                   |
|  Escenario: Primary falla                                         |
|                                                                   |
|  1. Patroni detecta fallo (3 heartbeat miss)                     |
|  2. Patroni electa Replica 1 como nuevo primary                  |
|  3. Replica 1 promueve a primary                                  |
|  4. Connection pooler (PgBouncer) actualiza routing              |
|  5. Servicios reconectan automaticamente                         |
|  6. Replica 2 se reconecta al nuevo primary                      |
|  7. Alerta P1 dispara                                            |
|  8. Nuevo servidor provisionado como replica                     |
|                                                                   |
|  Tiempo total: < 30 segundos                                     |
+------------------------------------------------------------------+
```

### 9.2 Redis Failover

```
+------------------------------------------------------------------+
|              REDIS FAILOVER                                       |
+------------------------------------------------------------------+
|                                                                   |
|  Sentinel Setup:                                                  |
|  - 3 sentinels en nodos separados                                |
|  - Monitorean Redis master cada 1 segundo                       |
|  - 2 sentinels deben confirmar fallo para failover              |
|                                                                   |
|  Master ──── replication ────► Replica                           |
|     │                               │                             |
|  Sentinel 1    Sentinel 2    Sentinel 3                          |
|                                                                   |
|  Failover:                                                       |
|  1. Sentinel detecta master no responde (5s)                    |
|  2. 2+ sentinels confirman fallo                                |
|  3. Sentinel promueve replica a master                           |
|  4. Sentinel actualiza configuracion de clientes                 |
|  5. Clientes Redis reconectan al nuevo master                    |
|  6. Nuevo replica provisionado                                   |
+------------------------------------------------------------------+
```

---

## 10. Chaos Engineering

### 10.1 Experimentos Programados

| Experimento                 | Frecuencia | Impacto        | Blameless |
|-----------------------------|------------|----------------|-----------|
| Matar random pod            | Semanal    | Bajo           | Si        |
| Simular latency en broker   | Quincenal  | Medio          | Si        |
| Llenar disco al 90%         | Mensual    | Medio          | Si        |
| Matar PostgreSQL primary    | Mensual    | Alto           | Si        |
| Simular red partition       | Mensual    | Alto           | Si        |
| Sobrecarga de CPU (50%)     | Bimestral  | Medio          | Si        |
| Matar NATS node             | Bimestral  | Medio          | Si        |

### 10.2 Implementacion con Litmus

```yaml
# chaos-experiments/pod-delete.yml
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: trading-engine-chaos
  namespace: trading
spec:
  appinfo:
    appns: trading
    applabel: app=trading-engine
    appkind: deployment
  chaosServiceAccount: litmus-admin
  experiments:
    - name: pod-delete
      spec:
        components:
          env:
            - name: TOTAL_CHAOS_DURATION
              value: "30"
            - name: CHAOS_INTERVAL
              value: "10"
            - name: FORCE
              value: "false"
        probe:
          - name: trading-engine-health
            type: httpProbe
            httpProbe/inputs:
              url: http://trading-engine:8082/health/ready
              insecureSkipVerify: true
              method:
                get:
                  criteria: ==
                  responseCode: "200"
            mode: Continuous
            runProperties:
              probeTimeout: 5s
              interval: 5s
              retry: 3
```

---

## 11. Load Shedding

### 11.1 Estrategia de Rechazo

```go
type LoadShedder struct {
    mu              sync.RWMutex
    concurrency     int32
    maxConcurrency  int32
    queueDepth      int32
    maxQueueDepth   int32
    metrics         *LoadShedMetrics
}

type RequestPriority int

const (
    PriorityCritical RequestPriority = iota  // Trading execution
    PriorityHigh                             // Risk checks
    PriorityNormal                           // Market data
    PriorityLow                              // Notifications
    PriorityBackground                       // Audit logs
)

func (ls *LoadShedder) ShouldReject(priority RequestPriority) bool {
    current := atomic.LoadInt32(&ls.concurrency)
    queue := atomic.LoadInt32(&ls.queueDepth)
    
    thresholds := map[RequestPriority]struct {
        maxConcurrency int32
        maxQueue       int32
    }{
        PriorityCritical: {ls.maxConcurrency, ls.maxQueueDepth},
        PriorityHigh:     {ls.maxConcurrency * 90 / 100, ls.maxQueueDepth * 80 / 100},
        PriorityNormal:   {ls.maxConcurrency * 70 / 100, ls.maxQueueDepth * 60 / 100},
        PriorityLow:      {ls.maxConcurrency * 50 / 100, ls.maxQueueDepth * 40 / 100},
        PriorityBackground: {ls.maxConcurrency * 30 / 100, ls.maxQueueDepth * 20 / 100},
    }
    
    t, ok := thresholds[priority]
    if !ok {
        return true
    }
    
    if current >= t.maxConcurrency || queue >= t.maxQueue {
        ls.metrics.rejected.WithLabelValues(priority.String()).Inc()
        return true
    }
    
    return false
}
```

### 11.2 Prioridades de Request

| Prioridad  | Tipos de Request                           | Max % del sistema |
|------------|--------------------------------------------|-------------------|
| Critical   | Ejecucion de ordenes, cancelaciones        | 100%              |
| High       | Risk checks, validacion pre-trade          | 90%               |
| Normal     | Market data, posiciones, balances          | 70%               |
| Low        | Notificaciones, webhooks externos          | 50%               |
| Background | Audit logs, metricas, health checks        | 30%               |

---

## 12. Timeout Budgets

### 12.1 Propagacion de Timeouts

```
+------------------------------------------------------------------+
|              TIMEOUT BUDGET PROPAGATION                           |
+------------------------------------------------------------------+
|                                                                   |
|  User Request (Total Budget: 5000ms)                             |
|  |                                                               |
|  ├── Traefik → Trading Engine (Budget: 4800ms)                  |
|  |    |                                                          |
|  |    ├── Trading → Risk Engine (Budget: 200ms)                 |
|  |    |    └── Risk check (Budget: 100ms)                       |
|  |    |                                                          |
|  |    ├── Trading → Broker Gateway (Budget: 4500ms)             |
|  |    |    ├── Broker → MT5 (Budget: 4000ms)                    |
|  |    |    └── Broker → Binance (Budget: 2000ms)                |
|  |    |                                                          |
|  |    ├── Trading → AI Engine (Budget: 500ms)                   |
|  |    |    └── AI → Ollama (Budget: 400ms)                      |
|  |    |                                                          |
|  |    └── Trading → Notification (Budget: 1000ms)               |
|  |         └── Notif → Telegram/Email (Budget: 5000ms)          |
|  |                                                               |
|  Total: 200 + 4500 + 500 + 1000 = 6200ms > 5000ms             |
|  Se usa la ruta critica: 200 + 4500 = 4700ms (< 5000ms)       |
|  Notificaciones van async (no bloquean la respuesta)           |
+------------------------------------------------------------------+
```

### 12.2 Tabla de Timeouts por Camino

| Camino                          | Timeout Total | Timeout por Paso                          |
|---------------------------------|---------------|-------------------------------------------|
| Login completo                  | 3s            | Auth(1s) + 2FA(2s)                       |
| Colocar orden                   | 5s            | Risk(200ms) + Broker(4500ms) + Notify(300ms async) |
| Consultar balance               | 2s            | Auth(100ms) + Broker(1500ms)             |
| Obtener prediccion              | 3s            | AI(2500ms) + Cache(100ms)                |
| Copy trade signal               | 10s           | Risk(500ms) + Broker(8000ms) + Notify(1500ms) |
| Obtener datos de mercado        | 1s            | Market(800ms)                             |

---

## 13. Dead Letter Queue Handling

### 13.1 Proceso de Revision DLQ

```
+------------------------------------------------------------------+
|           DLQ HANDLING PROCEDURE                                 |
+------------------------------------------------------------------+
|                                                                   |
|  1. MONITOREO                                                    |
|  Prometheus detecta count > umbral → Alerta P2                  |
|  Umbral: > 10 mensajes en DLQ por mas de 10 minutos            |
|                                                                   |
|  2. CLASIFICACION                                                |
|  ┌──────────────────────────────────────────────────────────┐   |
|  │ Error Type         │ Auto-replay? │ Accion              │   |
|  │ -------------------│-------------│---------------------│   |
|  │ Timeout            │ Si          │ Replay con backoff  │   |
|  │ Validation error   │ No          │ Alerta + revision   │   |
|  │ Broker rejected    │ Si (1 vez)  │ Replay             │   |
|  │ Rate limited       │ Si (espera) │ Replay despues     │   |
|  │ Circuit open       │ Si (espera) │ Replay al cerrar   │   |
|  │ Unknown error      │ No          │ Alerta P1          │   |
|  └──────────────────────────────────────────────────────────┘   |
|                                                                   |
|  3. REPLAY AUTOMATICO                                            |
|  Servicio DLQ replayea mensajes clasificados como replayable   |
|  Max 3 intentos de replay antes de mover a "failed"             |
|                                                                   |
|  4. REVISION MANUAL                                              |
|  Mensajes no-replayable revisados por on-call工程师             |
|  Options: retry manual, discard, o fix y replay                |
|                                                                   |
|  5. LIMPIEZA                                                     |
|  Mensajes > 30 dias en DLQ se archivan a S3                     |
|  Mensajes > 90 dias se eliminan permanentemente                 |
|                                                                   |
+------------------------------------------------------------------+
```

### 13.2 Implementacion DLQ Processor

```go
type DLQProcessor struct {
    js        nats.JetStreamContext
    services  map[string]ServiceHandler
    maxRetry  int
    metrics   *DLQMetrics
}

type DLQMessage struct {
    OriginalSubject string
    Error           string
    ErrorType       string
    Retries         int
    MaxRetries      int
    Timestamp       time.Time
    LastRetry       time.Time
}

type ErrorClassification int

const (
    ClassRetryable ErrorClassification = iota
    ClassNonRetryable
    ClassNeedsInvestigation
)

func (p *DLQProcessor) ProcessMessages(ctx context.Context) {
    sub, _ := p.js.Subscribe("*.dlq.>", func(msg *nats.Msg) {
        var dlqMsg DLQMessage
        json.Unmarshal(msg.Data, &dlqMsg)
        
        classification := p.classifyError(dlqMsg.ErrorType)
        
        switch classification {
        case ClassRetryable:
            if dlqMsg.Retries < p.maxRetry {
                if err := p.replay(msg); err == nil {
                    msg.Ack()
                    p.metrics.replayed.Inc()
                    return
                }
            }
            p.moveToFailed(msg, dlqMsg)
            
        case ClassNonRetryable:
            p.metrics.nonRetryable.Inc()
            p.alertService.SendAlert(Alert{
                Severity: "P2",
                Message:  fmt.Sprintf("DLQ non-retryable: %s", dlqMsg.Error),
            })
            msg.Ack()
            
        case ClassNeedsInvestigation:
            p.metrics.needsInvestigation.Inc()
            p.alertService.SendAlert(Alert{
                Severity: "P1",
                Message:  fmt.Sprintf("DLQ unknown error: %s", dlqMsg.Error),
            })
            msg.Ack()
        }
    })
    
    <-ctx.Done()
    sub.Drain()
}

func (p *DLQProcessor) classifyError(errorType string) ErrorClassification {
    switch errorType {
    case "timeout", "rate_limited", "circuit_open", "broker_rejected":
        return ClassRetryable
    case "validation_error", "unauthorized", "forbidden":
        return ClassNonRetryable
    default:
        return ClassNeedsInvestigation
    }
}
```

---

## Metricas de Resiliencia

| Metrica                              | Tipo    | Descripcion                             |
|--------------------------------------|---------|-----------------------------------------|
| `circuit_breaker_state`             | Gauge   | Estado actual (0=closed, 1=open, 2=half)|
| `circuit_breaker_state_changes`     | Counter | Cambios de estado totales               |
| `bulkhead_active_workers`           | Gauge   | Workers activos por bulkhead            |
| `bulkhead_rejected_total`           | Counter | Requests rechazados por bulkhead        |
| `retry_attempts_total`              | Counter | Total de reintentos                     |
| `retry_success_after_retry`         | Counter | Exitos despues de reintento             |
| `load_shed_rejected_total`          | Counter | Requests rechazados por load shedding   |
| `dlq_messages_total`                | Gauge   | Mensajes en DLQ                         |
| `dlq_replayed_total`                | Counter | Mensajes re-playeados                   |
| `dlq_failed_total`                  | Counter | Mensajes en DLQ permanently failed      |
| `timeout_budget_exceeded_total`     | Counter | Timeouts que excedieron el budget       |
| `graceful_degradation_events`       | Counter | Veces que el sistema degrado servicio   |
| `backup_last_success_timestamp`     | Gauge   | Timestamp del ultimo backup exitoso     |
| `backup_duration_seconds`           | Histogram| Duracion de backups                    |
| `failover_events_total`             | Counter | Total de failovers ejecutados           |

---

**Fin del documento 09 — Resiliencia**
