module github.com/tnsvt/shared-go

go 1.22

require (
	github.com/prometheus/client_golang v1.19.0
)

// Paquetes:
//   circuit  - Circuit breaker pattern
//   logging  - Structured logging con secret masking
//   metrics  - Prometheus metrics (RED method)
//   config   - Carga de configuración desde env vars