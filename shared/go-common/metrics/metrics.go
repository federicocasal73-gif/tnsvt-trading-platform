// Package metrics implementa métricas Prometheus con la metodología RED.
// Portado de signal_copier/metrics.py a Go.
package metrics

import (
	"net/http"
	"sync"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

// Server expone métricas Prometheus via HTTP
type Server struct {
	port   string
	mu     sync.RWMutex
	server *http.Server

	registry *prometheus.Registry

	// RED metrics por servicio
	requests *prometheus.CounterVec
	duration *prometheus.HistogramVec
	errors   *prometheus.CounterVec

	// Métricas específicas del dominio
	custom *prometheus.GaugeVec
}

// NewServer crea un nuevo servidor de métricas
func NewServer(serviceName, port string) *Server {
	reg := prometheus.NewRegistry()

	s := &Server{
		port:     port,
		registry: reg,
		requests: prometheus.NewCounterVec(
			prometheus.CounterOpts{
				Namespace: "tnsvt",
				Subsystem: serviceName,
				Name:      "requests_total",
				Help:      "Total number of requests",
			},
			[]string{"method", "endpoint", "status"},
		),
		duration: prometheus.NewHistogramVec(
			prometheus.HistogramOpts{
				Namespace: "tnsvt",
				Subsystem: serviceName,
				Name:      "request_duration_seconds",
				Help:      "Duration of requests in seconds",
				Buckets:   []float64{0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10},
			},
			[]string{"method", "endpoint"},
		),
		errors: prometheus.NewCounterVec(
			prometheus.CounterOpts{
				Namespace: "tnsvt",
				Subsystem: serviceName,
				Name:      "errors_total",
				Help:      "Total number of errors",
			},
			[]string{"method", "endpoint", "error_type"},
		),
		custom: prometheus.NewGaugeVec(
			prometheus.GaugeOpts{
				Namespace: "tnsvt",
				Subsystem: serviceName,
				Name:      "custom",
				Help:      "Custom metric gauge",
			},
			[]string{"name", "labels"},
		),
	}

	reg.MustRegister(s.requests, s.duration, s.errors, s.custom)

	mux := http.NewServeMux()
	mux.Handle("/metrics", promhttp.HandlerFor(reg, promhttp.HandlerOpts{Registry: reg}))
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"ok"}`))
	})
	mux.HandleFunc("/health/live", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})
	mux.HandleFunc("/health/ready", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})

	s.server = &http.Server{
		Addr:    ":" + port,
		Handler: mux,
	}

	return s
}

// Start inicia el servidor de métricas
func (s *Server) Start() error {
	return s.server.ListenAndServe()
}

// Stop detiene el servidor
func (s *Server) Stop() error {
	return s.server.Close()
}

// RecordRequest registra una request
func (s *Server) RecordRequest(method, endpoint string, status int, duration time.Duration) {
	s.requests.WithLabelValues(method, endpoint, statusCode(status)).Inc()
	s.duration.WithLabelValues(method, endpoint).Observe(duration.Seconds())
}

// RecordError registra un error
func (s *Server) RecordError(method, endpoint, errorType string) {
	s.errors.WithLabelValues(method, endpoint, errorType).Inc()
}

// SetGauge setea un valor de gauge
func (s *Server) SetGauge(name string, labels map[string]string, value float64) {
	labelValues := make([]string, 0, 2)
	lv, _ := labels["name"]
	ll, _ := labels["labels"]
	labelValues = append(labelValues, lv, ll)
	s.custom.WithLabelValues(name, labelValues[1]).Set(value)
}

func statusCode(code int) string {
	switch {
	case code < 200:
		return "1xx"
	case code < 300:
		return "2xx"
	case code < 400:
		return "3xx"
	case code < 500:
		return "4xx"
	default:
		return "5xx"
	}
}

// ─── Métricas específicas del dominio trading ───

// TradeOpenedCounter cuenta trades abiertos
type TradeOpenedCounter struct {
	counter prometheus.Counter
}

// NewTradeOpenedCounter crea contador de trades abiertos
func (s *Server) NewTradeOpenedCounter() *TradeOpenedCounter {
	c := prometheus.NewCounter(prometheus.CounterOpts{
		Namespace: "tnsvt",
		Subsystem: "trading",
		Name:      "trades_opened_total",
		Help:      "Total number of trades opened",
	})
	s.registry.MustRegister(c)
	return &TradeOpenedCounter{counter: c}
}

// Inc incrementa el contador
func (t *TradeOpenedCounter) Inc() {
	t.counter.Inc()
}