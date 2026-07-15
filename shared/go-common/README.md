# Shared Go Common Libraries

Librerías compartidas entre todos los servicios Go de TNSVT V2.

## Paquetes

### `circuit/` — Circuit Breaker

Protege servicios contra fallos en cascada. Portado de `signal_copier/circuit_breaker.py`.

```go
import "github.com/tnsvt/shared-go/circuit"

cb := circuit.New(circuit.Config{
    Name:             "tnsvt-client",
    FailureThreshold: 5,
    RecoveryTimeout:  30 * time.Second,
})

err := cb.Execute(func() error {
    return client.DoRequest()
})
if errors.Is(err, circuit.ErrCircuitOpen) {
    // El breaker está abierto, rechaza request
}
```

### `logging/` — Structured Logging con Secret Masking

Logger JSON estructurado que enmascara automáticamente passwords, tokens, API keys. Portado de `signal_copier/log_security.py`.

```go
import "github.com/tnsvt/shared-go/logging"

log := logging.New("signal-engine", "info")
log.Info("signal received", "symbol", "EURUSD", "token", "abc123")
// Output: {"service":"signal-engine","msg":"signal received","symbol":"EURUSD","token":"***MASKED***"}
```

### `metrics/` — Prometheus Metrics (RED Method)

Servidor HTTP que expone métricas Prometheus. Portado de `signal_copier/metrics.py`.

```go
import "github.com/tnsvt/shared-go/metrics"

m := metrics.NewServer("signal-engine", "8003")
go m.Start() // /metrics, /health, /health/live, /health/ready

m.RecordRequest("POST", "/signals", 200, 50*time.Millisecond)
m.RecordError("POST", "/signals", "validation_error")
```

### `config/` — Configuration Loader

Carga configuración desde variables de entorno con defaults. Portado de `config/settings.py`.

```go
import "github.com/tnsvt/shared-go/config"

cfg := config.Load("signal-engine")

dsn := cfg.Postgres.DSN()     // host=... port=... dbname=...
url := cfg.NATS.URL()         // nats://localhost:4222
timeout := cfg.GetInt("SIGNAL_TIMEOUT_MS", 5000)
```

## Instalación

En cualquier servicio Go:

```bash
go get github.com/tnsvt/shared-go
```

O agregar como replace local en `go.mod`:

```
replace github.com/tnsvt/shared-go => ../../shared/go-common
```

## Versionado

Estos paquetes son el **contrato compartido** entre todos los servicios Go. Cualquier cambio breaking debe coordinarse con todos los equipos consumidores.