# DOCUMENT 08: OBSERVABILIDAD

## Plataforma de Trading TNSVT V2 — Observabilidad

**Version:** 2.0.0  
**Fecha:** 2026-07-14  
**Estado:** Produccion  
**Autor:** Equipo de Arquitectura TNSVT V2

---

## Tabla de Contenidos

1. [Arquitectura de Observabilidad](#1-arquitectura-de-observabilidad)
2. [OpenTelemetry](#2-opentelemetry)
3. [Metricas RED por Servicio](#3-metricas-red-por-servicio)
4. [Dashboards Grafana](#4-dashboards-grafana)
5. [Loki: Logging Centralizado](#5-loki-logging-centralizado)
6. [Tempo: Distributed Tracing](#6-tempo-distributed-tracing)
7. [Alerting Rules](#7-alerting-rules)
8. [SLOs y SLIs](#8-slos-y-slis)
9. [On-Call Rotation](#9-on-call-rotation)
10. [Dashboard-as-Code](#10-dashboard-as-code)
11. [Politica de Retencion de Logs](#11-politica-de-retencion-de-logs)

---

## 1. Arquitectura de Observabilidad

```
+--------------------------------------------------------------------------+
|                   ARQUITECTURA DE OBSERVABILIDAD TNSVT V2                 |
+--------------------------------------------------------------------------+
|                                                                          |
|  +-------------------+                                                   |
|  | Servicios (Go/Py) |──── OTel SDK ────┐                               |
|  | 12+ microservicios|                   │                               |
|  +-------------------+                   v                               |
|                              +-------------------+                       |
|  +-------------------+      |  OTel Collector   |                       |
|  | NGINX / Traefik   |────►|  (Agent mode)     |                       |
|  +-------------------+      +--------+----------+                       |
|                                       |                                   |
|                          +------------+------------+                     |
|                          v            v            v                     |
|                  +----------+  +----------+  +----------+               |
|                  |Prometheus|  |  Loki    |  |  Tempo   |               |
|                  | Metrics  |  |  Logs    |  |  Traces  |               |
|                  +----+-----+  +----+-----+  +----+-----+               |
|                       |             |             |                      |
|                       v             v             v                      |
|                  +-----------------------------------+                   |
|                  |            Grafana                |                   |
|                  |  6 dashboards de observabilidad   |                   |
|                  +-----------------------------------+                   |
|                                                                          |
+--------------------------------------------------------------------------+
```

### Stack de Observabilidad

| Componente    | Version | Rol                              | Datos                   |
|---------------|---------|----------------------------------|-------------------------|
| OTel SDK      | 1.7+    | Instrumentacion                  | Traces, Metrics, Logs   |
| OTel Collector| 0.105+  | Aggregation + Export             | Routing de telemetria   |
| Prometheus    | 2.53    | Time-series de metricas          | Metricas numericas      |
| Loki          | 3.1     | Logs centralizados               | Logs estructurados      |
| Tempo         | 2.5     | Distributed tracing              | Spans y traces         |
| Grafana       | 11.1    | Visualizacion + Alerting         | Dashboards unificados   |

---

## 2. OpenTelemetry

### 2.1 Configuracion del Collector

```yaml
# otel-collector-config.yml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318
  prometheus:
    config:
      scrape_configs:
        - job_name: "tnsvt-services"
          scrape_interval: 15s
          metrics_path: /metrics
          static_configs:
            - targets:
                - "auth-service:9090"
                - "trading-engine:9090"
                - "risk-engine:9090"
                - "broker-gateway:9090"
                - "ai-engine:9090"
                - "copy-trading:9090"
                - "notification-service:9090"
                - "audit-service:9090"
                - "platform-api:9090"

processors:
  batch:
    timeout: 5s
    send_batch_size: 1000
    send_batch_max_size: 5000

  memory_limiter:
    check_interval: 1s
    limit_mib: 2048
    spike_limit_mib: 256

  attributes:
    actions:
      - key: environment
        action: upsert
        value: production
      - key: region
        action: upsert
        value: us-east-1
      - key: version
        action: upsert
        value: "2.0.0"

  resource:
    attributes:
      - key: service.namespace
        value: "tnsvt-v2"
        action: upsert

exporters:
  prometheus:
    endpoint: "0.0.0.0:8889"
    namespace: "tnsvt"
    const_labels:
      environment: production

  loki:
    endpoint: "http://loki:3100/loki/api/v1/push"
    labels:
      attributes:
        service.name: "service"
        log.level: "level"
        trace_id: "trace_id"

  otlp/tempo:
    endpoint: "tempo:4317"
    tls:
      insecure: true

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, batch, attributes, resource]
      exporters: [otlp/tempo]

    metrics:
      receivers: [otlp, prometheus]
      processors: [memory_limiter, batch, attributes, resource]
      exporters: [prometheus]

    logs:
      receivers: [otlp]
      processors: [memory_limiter, batch, attributes, resource]
      exporters: [loki]
```

### 2.2 Instrumentacion en Go

```go
import (
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
    "go.opentelemetry.io/otel/sdk/trace"
    "go.opentelemetry.io/otel/sdk/resource"
    semconv "go.opentelemetry.io/otel/semconv/v1.7.0"
)

func InitTracer(serviceName string) (*trace.TracerProvider, error) {
    ctx := context.Background()
    
    exporter, err := otlptracegrpc.New(ctx,
        otlptracegrpc.WithEndpoint("otel-collector:4317"),
        otlptracegrpc.WithInsecure(),
    )
    if err != nil {
        return nil, err
    }
    
    res, _ := resource.Merge(
        resource.Default(),
        resource.NewWithAttributes(
            semconv.SchemaURL,
            semconv.ServiceNameKey.String(serviceName),
            semconv.ServiceVersionKey.String("2.0.0"),
            semconv.DeploymentEnvironmentKey.String("production"),
        ),
    )
    
    tp := trace.NewTracerProvider(
        trace.WithBatcher(exporter),
        trace.WithResource(res),
        trace.WithSampler(trace.ParentBased(trace.TraceIDRatioBased(0.1))),
    )
    
    otel.SetTracerProvider(tp)
    return tp, nil
}
```

### 2.3 Instrumentacion en Python

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME

def init_tracer(service_name: str) -> TracerProvider:
    resource = Resource.create({
        SERVICE_NAME: service_name,
        "service.version": "2.0.0",
        "deployment.environment": "production",
    })
    
    exporter = OTLPSpanExporter(
        endpoint="otel-collector:4317",
        insecure=True,
    )
    
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    
    return provider
```

---

## 3. Metricas RED por Servicio

### Metodo RED (Rate, Errors, Duration)

```
+------------------------------------------------------------------+
|                    METODO RED POR SERVICIO                        |
+------------------------------------------------------------------+
|                                                                   |
|  Rate    = tasa de requests por segundo                          |
|  Errors  = tasa de requests con error (4xx + 5xx)               |
|  Duration = distribucion de latencia (p50, p95, p99)            |
|                                                                   |
+------------------------------------------------------------------+
```

### Metricas por Servicio

| Servicio          | Rate Metric                    | Error Metric                  | Duration Metric               |
|-------------------|--------------------------------|-------------------------------|-------------------------------|
| auth-service      | `http_requests_total`          | `http_errors_total`           | `http_request_duration_ms`    |
| trading-engine    | `trading_orders_total`         | `trading_orders_failed`       | `trading_order_latency_ms`    |
| risk-engine       | `risk_checks_total`            | `risk_checks_rejected`        | `risk_check_duration_ms`      |
| broker-gateway    | `broker_submissions_total`     | `broker_submission_errors`    | `broker_submission_latency_ms`|
| ai-engine         | `ai_predictions_total`         | `ai_predictions_failed`       | `ai_prediction_duration_ms`   |
| copy-trading      | `copy_trades_total`            | `copy_trades_failed`          | `copy_trade_latency_ms`       |
| notification-svc  | `notifications_sent_total`     | `notifications_failed`        | `notification_latency_ms`     |
| platform-api      | `platform_requests_total`      | `platform_errors_total`       | `platform_request_duration_ms`|
| audit-service     | `audit_events_total`           | `audit_events_failed`         | `audit_write_duration_ms`     |
| ws-gateway        | `ws_connections_active`        | `ws_connection_errors`        | `ws_message_latency_ms`       |

### Metricas de Infraestructura

| Componente   | Metricas Clave                                               |
|-------------|--------------------------------------------------------------|
| PostgreSQL  | `pg_connections_active`, `pg_queries_duration_ms`, `pg_locks`, `pg_replication_lag_ms` |
| TimescaleDB | `tsdb_compression_ratio`, `tsdb_hypertable_chunks`, `tsdb_retention_dropped` |
| Redis       | `redis_connections_active`, `redis_memory_used_bytes`, `redis_commands_latency_ms` |
| NATS        | `nats_jetstream_msgs_count`, `nats_consumer_pending`, `nats_connection_count` |
| Traefik     | `traefik_service_requests_total`, `traefik_entrypoint_tcp_opened` |

### Metricas de Negocio

| Metrica                              | Descripcion                                  |
|--------------------------------------|----------------------------------------------|
| `business_orders_daily`             | Total de ordenes ejecutadas hoy              |
| `business_volume_usd`               | Volumen total en USD                         |
| `business_active_users`             | Usuarios con al menos 1 sesion activa        |
| `business_positions_open`           | Posiciones abiertas en todos los tenants     |
| `business_pnl_total_usd`            | PnL total del sistema                        |
| `business_copy_trades_active`       | Copy trades activos                          |
| `business_ai_predictions_used`      | Predicciones IA consumidas hoy               |

---

## 4. Dashboards Grafana

### 4.1 Dashboard Overview

```
+------------------------------------------------------------------+
|  DASHBOARD: OVERVIEW (TNSVT V2 - Vista General)                  |
+------------------------------------------------------------------+
|                                                                   |
|  +------------------+  +------------------+  +------------------+|
|  | Total Orders 24h |  | Active Users     |  | System Uptime    ||
|  |   12,456         |  |   1,234          |  |   99.97%         ||
|  +------------------+  +------------------+  +------------------+|
|                                                                   |
|  +------------------+  +------------------+  +------------------+|
|  | Revenue 24h      |  | PnL Total        |  | Alerts Active    ||
|  |   $45,678        |  |   +$12,345       |  |   2 (P3)         ||
|  +------------------+  +------------------+  +------------------+|
|                                                                   |
|  +--------------------------------------------------------------+|
|  |  Request Rate (all services) - Time Series                   ||
|  |  ████░░░░░░░░████░░░░████████░░░░░██████░░░░░░████████      ||
|  +--------------------------------------------------------------+|
|                                                                   |
|  +--------------------------------------------------------------+|
|  |  Error Rate (all services) - Time Series                     ||
|  |  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  ||
|  +--------------------------------------------------------------+|
|                                                                   |
|  +--------------------------------------------------------------+|
|  |  Latency P99 (all services) - Time Series                    ||
|  |  ░░████░░░░████░░░░████░░░░████░░░░████░░░░░░████░░░░░░░░  ||
|  +--------------------------------------------------------------+|
|                                                                   |
+------------------------------------------------------------------+
```

### 4.2 Dashboard Trading

| Panel                      | Tipo        | Query PromQL                                        |
|----------------------------|-------------|-----------------------------------------------------|
| Orders/min by status       | Bar chart   | `sum(rate(trading_orders_total[5m])) by (status)`   |
| Order latency P99          | Gauge       | `histogram_quantile(0.99, ...trading_order_latency)`|
| Active positions           | Stat        | `sum(trading_positions_open)`                        |
| Orders by symbol           | Pie chart   | `sum(trading_orders_total) by (symbol)`              |
| Orders by broker           | Table       | `sum(trading_orders_total) by (broker)`              |
| Filled vs Rejected         | Time series | `sum(rate(...[5m])) by (type)`                       |
| Volume by tenant           | Heatmap     | `sum(trading_volume_usd) by (tenant)`               |
| PnL by strategy            | Time series | `sum(trading_pnl_total) by (strategy)`              |

### 4.3 Dashboard AI

| Panel                      | Tipo        | Query PromQL                                        |
|----------------------------|-------------|-----------------------------------------------------|
| Predictions/min            | Stat        | `sum(rate(ai_predictions_total[5m]))`                |
| Prediction accuracy        | Gauge       | `ai_predictions_correct / ai_predictions_total`     |
| Model latency P99          | Time series | `histogram_quantile(0.99, ...ai_prediction_duration)`|
| Models loaded              | Stat        | `ai_models_loaded_count`                             |
| GPU memory usage           | Gauge       | `nvidia_gpu_memory_used_bytes / total`               |
| Ollama queue depth         | Gauge       | `ollama_queue_size`                                  |
| Sentiment score avg        | Gauge       | `avg(ai_sentiment_score)`                            |
| Anomalies detected         | Time series | `sum(rate(ai_anomaly_detected[5m]))`                 |

### 4.4 Dashboard Risk

| Panel                      | Tipo        | Query PromQL                                        |
|----------------------------|-------------|-----------------------------------------------------|
| Risk checks/min            | Stat        | `sum(rate(risk_checks_total[5m]))`                   |
| Rejection rate             | Gauge       | `risk_checks_rejected / risk_checks_total`          |
| Current drawdown (max)     | Gauge       | `max(risk_drawdown_current)`                         |
| Margin utilization         | Gauge       | `risk_margin_used / risk_margin_available`          |
| Open position exposure     | Bar chart   | `sum(risk_exposure_total) by (symbol)`              |
| Limit breaches             | Time series | `sum(rate(risk_limit_breach_total[5m]))`            |
| VaR (95%)                  | Stat        | `risk_var_95_current`                                |

### 4.5 Dashboard Infrastructure

| Panel                      | Tipo        | Query PromQL                                        |
|----------------------------|-------------|-----------------------------------------------------|
| CPU per pod                | Bar gauge   | `sum(rate(container_cpu_usage[5m])) by (pod)`       |
| Memory per pod             | Bar gauge   | `container_memory_working_set_bytes by (pod)`       |
| Network I/O                | Time series | `rate(container_network_bytes[5m]) by (direction)`  |
| Pod restarts               | Stat        | `sum(kube_pod_container_status_restarts_total)`      |
| PVC usage                  | Gauge       | `kubelet_volume_stats_used_bytes / capacity`        |
| NATS messages/sec          | Time series | `rate(nats_msg_count[5m])`                          |
| PostgreSQL connections     | Gauge       | `pg_stat_activity_count`                             |
| Redis memory               | Gauge       | `redis_memory_used_bytes`                            |

### 4.6 Dashboard Business

| Panel                      | Tipo        | Query PromQL                                        |
|----------------------------|-------------|-----------------------------------------------------|
| Active users (realtime)    | Stat        | `business_active_users`                              |
| Revenue (24h)              | Stat        | `sum(increase(business_revenue_usd[24h]))`          |
| New registrations (7d)     | Time series | `sum(increase(business_registrations[7d]))`         |
| Tenant breakdown           | Pie chart   | `business_revenue_usd by (tenant)`                  |
| Conversion rate            | Gauge       | `business_trial_to_paid_ratio`                      |
| API usage by endpoint      | Table       | `sum(http_requests_total) by (endpoint)`            |

---

## 5. Loki: Logging Centralizado

### 5.1 Estructura de Logs

```json
{
  "timestamp": "2026-07-14T10:30:00.000Z",
  "level": "info",
  "service": "trading-engine",
  "trace_id": "4bf92f3577b34da6a6ce93a30f8e2b0a",
  "span_id": "00f067aa0ba902b7",
  "user_id": "user_xyz789",
  "tenant_id": "tenant_abc123",
  "message": "Orden ejecutada exitosamente",
  "order_id": "ORD-20260714-001",
  "symbol": "EURUSD",
  "side": "BUY",
  "quantity": 1.0,
  "price": 1.0842,
  "broker": "MT5",
  "latency_ms": 45
}
```

### 5.2 Label Schema para Loki

| Label            | Valores Ejemplo                          | Cardinalidad |
|------------------|------------------------------------------|-------------|
| `service`        | trading-engine, risk-engine, etc.        | Baja (12)   |
| `level`          | debug, info, warn, error, fatal          | Baja (5)    |
| `environment`    | development, staging, production         | Baja (3)    |
| `namespace`      | trading, platform, ai, data              | Baja (4)    |
| `event_type`     | order.filled, risk.check, etc.           | Media       |

### 5.3 Queries de Loki

```logql
# Logs de error en trading-engine
{service="trading-engine"} |= "error" | json

# Logs de ordenes fallidas en la ultima hora
{service="trading-engine", level="error"} | json | order_id != ""

# Logs de un usuario especifico
{namespace="trading"} | json | user_id="user_xyz789"

# Conteo de errores por servicio
count_over_time({level="error"}[5m]) | unwrap | sum by (service)

# Top 10 mensajes de error
topk(10, sum by (message) (count_over_time({level="error"}[1h])))
```

---

## 6. Tempo: Distributed Tracing

### 6.1 Configuracion Tempo

```yaml
# tempo-config.yml
server:
  http_listen_port: 3200

distributor:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: 0.0.0.0:4317
        http:
          endpoint: 0.0.0.0:4318

metrics_generator:
  registry:
    external_labels:
      source: tempo
      cluster: production
  storage:
    path: /var/tempo/generator/wal
    remote_write:
      - url: http://prometheus:9090/api/v1/write
        send_exemplars: true
  traces_storage:
    path: /var/tempo/generator/traces
  processor:
    service_graphs:
      dimensions: [service.name, namespace]
    span_metrics:
      dimensions: [service.name, namespace, http.method]

storage:
  trace:
    backend: local
    local:
      path: /var/tempo/traces
    wal:
      path: /var/tempo/wal

overrides:
  defaults:
    metrics_generator:
      processors: [service-graphs, span-metrics]
```

### 6.2 Trace Context Propagation

```
Request Flow con Trace Context:

  User ──► Traefik ──► Trading Engine ──► Risk Engine ──► Broker Gateway
   │          │              │                │               │
   │     trace: abc     trace: abc       trace: abc     trace: abc
   │     span: 001      span: 002        span: 003      span: 004
   │          │              │                │               │
   ▼          ▼              ▼                ▼               ▼
  +----------------------------------------------------------------+
  |                    TEMPO: Trace abc                            |
  |  Traefik[15ms]                                              |
  |    └─ TradingEngine[45ms]                                   |
  |         └─ RiskEngine[8ms]                                  |
  |         └─ BrokerGateway[120ms]                             |
  +----------------------------------------------------------------+
```

---

## 7. Alerting Rules

### 7.1 Reglas de Alerting por Severidad

```yaml
# prometheus/alerts/trading.yml
groups:
  - name: trading-alerts
    rules:
      # === P1: Critico (requiere respuesta inmediata) ===
      - alert: TradingEngineDown
        expr: up{job="trading-engine"} == 0
        for: 1m
        labels:
          severity: P1
          team: trading
        annotations:
          summary: "Trading Engine caido"
          description: "El servicio trading-engine esta inactivo desde hace 1 minuto"
          runbook: "https://docs.tnsvt.com/runbooks/trading-engine-down"

      - alert: RiskEngineDown
        expr: up{job="risk-engine"} == 0
        for: 30s
        labels:
          severity: P1
          team: risk
        annotations:
          summary: "Risk Engine caido - CIRCUITO ABIERTO"
          description: "El risk engine esta caido. Trading detenido automaticamente."
          runbook: "https://docs.tnsvt.com/runbooks/risk-engine-down"

      - alert: OrderFailureRateHigh
        expr: |
          sum(rate(trading_orders_failed[5m])) /
          sum(rate(trading_orders_total[5m])) > 0.05
        for: 2m
        labels:
          severity: P1
          team: trading
        annotations:
          summary: "Tasa de fallo de ordenes > 5%"
          description: "Mas del 5% de las ordenes estan fallando"

      - alert: BrokerGatewayDown
        expr: up{job="broker-gateway"} == 0
        for: 30s
        labels:
          severity: P1
          team: broker
        annotations:
          summary: "Broker Gateway caido"
          description: "No se pueden enviar ordenes a brokers"

      - alert: DatabaseDown
        expr: pg_up == 0
        for: 30s
        labels:
          severity: P1
          team: data
        annotations:
          summary: "PostgreSQL caido"

      - alert: NATSClusterDegraded
        expr: nats_cluster_nodes{state!="online"} > 0
        for: 1m
        labels:
          severity: P1
          team: data
        annotations:
          summary: "Cluster NATS degradado"

      # === P2: Alto (requiere respuesta en 15 min) ===
      - alert: HighErrorRate
        expr: |
          sum(rate(http_errors_total[5m])) by (service) /
          sum(rate(http_requests_total[5m])) by (service) > 0.01
        for: 5m
        labels:
          severity: P2
          team: platform
        annotations:
          summary: "Tasa de error alta en {{ $labels.service }}"

      - alert: HighLatencyP99
        expr: |
          histogram_quantile(0.99,
            sum(rate(http_request_duration_ms_bucket[5m])) by (service, le)
          ) > 2000
        for: 5m
        labels:
          severity: P2
          team: platform
        annotations:
          summary: "Latencia P99 alta en {{ $labels.service }}"

      - alert: RiskLimitBreach
        expr: increase(risk_limit_breach_total[5m]) > 0
        labels:
          severity: P2
          team: risk
        annotations:
          summary: "Limite de riesgo violado"
          description: "Se detecto una violacion de limite de riesgo"

      - alert: DLQMessagesHigh
        expr: nats_dlq_messages_total > 100
        for: 10m
        labels:
          severity: P2
          team: platform
        annotations:
          summary: "DLQ tiene muchos mensajes pendientes"

      - alert: RedisMemoryHigh
        expr: redis_memory_used_bytes / redis_memory_max_bytes > 0.85
        for: 5m
        labels:
          severity: P2
          team: data
        annotations:
          summary: "Redis uso de memoria > 85%"

      - alert: PostgreSQLConnectionsHigh
        expr: pg_stat_activity_count > 180
        for: 5m
        labels:
          severity: P2
          team: data
        annotations:
          summary: "PostgreSQL conexiones altas (>180/200)"

      - alert: PodOOMKilled
        expr: kube_pod_container_status_last_terminated_reason{reason="OOMKilled"} > 0
        labels:
          severity: P2
          team: platform
        annotations:
          summary: "Pod {{ $labels.pod }} terminado por OOM"

      - alert: CertificateExpiringSoon
        expr: cert_manager_certificate_expiration_timestamp_seconds - time() < 7 * 24 * 3600
        for: 1h
        labels:
          severity: P2
          team: platform
        annotations:
          summary: "Certificado TLS expira en menos de 7 dias"

      # === P3: Medio (requiere respuesta en 1 hora) ===
      - alert: HighCPUUsage
        expr: |
          sum(rate(container_cpu_usage_seconds_total[5m])) by (pod)
          / sum(kube_pod_container_resource_limits{resource="cpu"}) by (pod) > 0.8
        for: 15m
        labels:
          severity: P3
          team: platform
        annotations:
          summary: "CPU > 80% en {{ $labels.pod }}"

      - alert: HighMemoryUsage
        expr: |
          container_memory_working_set_bytes /
          kube_pod_container_resource_limits{resource="memory"} > 0.85
        for: 15m
        labels:
          severity: P3
          team: platform
        annotations:
          summary: "Memoria > 85% en {{ $labels.pod }}"

      - alert: PVCUsageHigh
        expr: |
          kubelet_volume_stats_used_bytes /
          kubelet_volume_stats_capacity_bytes > 0.80
        for: 30m
        labels:
          severity: P3
          team: data
        annotations:
          summary: "PVC disco > 80%"

      - alert: PodRestartLoop
        expr: increase(kube_pod_container_status_restarts_total[1h]) > 5
        labels:
          severity: P3
          team: platform
        annotations:
          summary: "Pod {{ $labels.pod }} reiniciandose (>5/hora)"

      - alert: AIModelLatencyHigh
        expr: histogram_quantile(0.99, sum(rate(ai_prediction_duration_ms_bucket[5m])) by (le)) > 5000
        for: 10m
        labels:
          severity: P3
          team: ai
        annotations:
          summary: "Latencia de modelo AI alta"

      - alert: OllamaQueueFull
        expr: ollama_queue_size > 50
        for: 5m
        labels:
          severity: P3
          team: ai
        annotations:
          summary: "Cola de Ollama saturada"

      - alert: ReplicationLagHigh
        expr: pg_replication_lag_seconds > 10
        for: 5m
        labels:
          severity: P3
          team: data
        annotations:
          summary: "Replicacion PostgreSQL lag > 10s"

      # === P4: Bajo (requiere respuesta en 24 horas) ===
      - alert: DiskUsageForecast
        expr: |
          predict_linear(
            kubelet_volume_stats_used_bytes[6h], 7 * 24 * 3600
          ) > kubelet_volume_stats_capacity_bytes
        for: 1h
        labels:
          severity: P4
          team: data
        annotations:
          summary: "Disco se llena en < 7 dias"

      - alert: DeprecatedAPIUsage
        expr: sum(rate(http_requests_total{deprecated="true"}[1h])) > 0
        labels:
          severity: P4
          team: platform
        annotations:
          summary: "API deprecada en uso"

      - alert: HighErrorBudgetBurn
        expr: |
          (
            1 - (sum(rate(http_requests_total{code!~"5.."}[1h])) /
                 sum(rate(http_requests_total[1h])))
          ) / (1 - 0.999) > 1.0
        for: 2h
        labels:
          severity: P4
          team: platform
        annotations:
          summary: "Error budget quemandose a ritmo alto"
```

### 7.2 Resumen de Alertas

| Severidad | Cantidad | Tiempo Respuesta | Canales                   |
|-----------|----------|-------------------|---------------------------|
| P1        | 7        | Inmediato (5min)  | PagerDuty + Slack #crit   |
| P2        | 10       | 15 minutos        | PagerDuty + Slack #high   |
| P3        | 10       | 1 hora            | Slack #medium             |
| P4        | 5        | 24 horas          | Slack #low + email        |
| **Total** | **32**   |                   |                           |

---

## 8. SLOs y SLIs

### 8.1 Service Level Objectives

| Servicio          | SLI                    | SLO Meta   | Error Budget (30d) |
|-------------------|------------------------|------------|---------------------|
| auth-service      | Disponibilidad         | 99.95%     | 21.6 min            |
| trading-engine    | Disponibilidad         | 99.99%     | 4.3 min             |
| trading-engine    | Latencia P99 < 500ms  | 99.9%      | 43.2 min            |
| risk-engine       | Disponibilidad         | 99.99%     | 4.3 min             |
| risk-engine       | Latencia P99 < 100ms  | 99.9%      | 43.2 min            |
| broker-gateway    | Disponibilidad         | 99.95%     | 21.6 min            |
| ai-engine         | Disponibilidad         | 99.9%      | 43.2 min            |
| platform-api      | Disponibilidad         | 99.95%     | 21.6 min            |
| ws-gateway        | Disponibilidad         | 99.9%      | 43.2 min            |
| notification-svc  | Disponibilidad         | 99.5%      | 3.6 horas           |
| audit-service     | Disponibilidad         | 99.99%     | 4.3 min             |

### 8.2 SLIs Definition

```yaml
service_level_indicators:
  trading-engine:
    availability:
      good_events: |
        sum(http_requests_total{service="trading-engine", code!~"5.."})
      total_events: |
        sum(http_requests_total{service="trading-engine"})
    latency:
      good_events: |
        sum(http_request_duration_ms_bucket{service="trading-engine", le="500"})
      total_events: |
        sum(http_request_duration_ms_bucket{service="trading-engine", le="+Inf"})

  risk-engine:
    availability:
      good_events: |
        sum(risk_checks_total{result!="error"})
      total_events: |
        sum(risk_checks_total)
    latency:
      good_events: |
        sum(risk_check_duration_ms_bucket{le="100"})
      total_events: |
        sum(risk_check_duration_ms_bucket{le="+Inf"})
```

---

## 9. On-Call Rotation

### Escalacion

```
P1 Alert
   |
   v
PagerDuty (notificacion inmediata)
   |
   ├── 5 min sin ack ──► Re-escalacion (On-call senior)
   |
   ├── 15 min sin resolve ──► Engineering Manager
   |
   └── 30 min sin resolve ──► VP Engineering
```

### Rotation Schedule

| Semana    | Primary              | Secondary            | Backup               |
|-----------|----------------------|----------------------|----------------------|
| Semana 1  | Dev Team A           | Dev Team B           | Platform Lead        |
| Semana 2  | Dev Team B           | Dev Team C           | Platform Lead        |
| Semana 3  | Dev Team C           | Dev Team A           | Platform Lead        |
| Semana 4  | Platform Lead        | Dev Team A           | CTO                  |

---

## 10. Dashboard-as-Code

### Grafana Provisioning

```yaml
# grafana/provisioning/datasources.yml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false

  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    editable: false

  - name: Tempo
    type: tempo
    access: proxy
    url: http://tempo:3200
    uid: tempo
    editable: false

  - name: Alertmanager
    type: alertmanager
    access: proxy
    url: http://alertmanager:9093
    editable: false

# grafana/provisioning/alerting.yml
apiVersion: 1
groups:
  - orgId: 1
    name: TNST Trading Alerts
    folder: TNSVT V2
    interval: 1m
    rules:
      - uid: trading-engine-down
        title: Trading Engine Down
        condition: C
        data:
          - refId: A
            datasourceUid: prometheus
            model:
              expr: up{job="trading-engine"} == 0
```

---

## 11. Politica de Retencion de Logs

| Capa      | Duracion  | Almacenamiento   | Costo/mes  |
|-----------|-----------|------------------|------------|
| Hot       | 30 dias   | Loki (SSD local) | $200       |
| Warm      | 90 dias   | S3 Standard      | $50        |
| Cold      | 1 ano     | S3 Glacier       | $10        |
| Archive   | 7 anos    | S3 Glacier Deep  | $2         |

```yaml
# loki-config.yml (retention)
limits_config:
  retention_period: 720h  # 30 dias hot
  max_query_series: 100000

compactor:
  compaction_interval: 10m
  retention_enabled: true
  retention_delete_delay: 2h

schema_config:
  configs:
    - from: "2026-01-01"
      store: tsdb
      object_store: s3
      schema: v13
      index:
        prefix: loki_index_
        period: 24h

storage_config:
  s3:
    bucket_name: loki-tnsvt
    endpoint: s3.us-east-1.amazonaws.com
  tsdb_shipper:
    active_index_directory: /loki/index
    cache_location: /loki/cache
```

---

**Fin del documento 08 — Observabilidad**
