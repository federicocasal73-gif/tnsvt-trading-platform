package service

import "github.com/prometheus/client_golang/prometheus"

var (
	ordersPlaced = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Namespace: "tnsvt",
			Subsystem: "execution_engine",
			Name:      "orders_placed_total",
			Help:      "Total orders placed by result",
		},
		[]string{"status"},
	)
	ordersLatency = prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Namespace: "tnsvt",
			Subsystem: "execution_engine",
			Name:      "order_latency_seconds",
			Help:      "Order execution latency in seconds",
			Buckets:   []float64{0.01, 0.05, 0.1, 0.5, 1, 2.5, 5, 10},
		},
		[]string{"status"},
	)
	openPositions = prometheus.NewGauge(
		prometheus.GaugeOpts{
			Namespace: "tnsvt",
			Subsystem: "execution_engine",
			Name:      "open_positions",
			Help:      "Current number of open positions tracked",
		},
	)
	riskNotifications = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Namespace: "tnsvt",
			Subsystem: "execution_engine",
			Name:      "risk_notifications_total",
			Help:      "Total risk-engine notifications by type",
		},
		[]string{"type"},
	)
	signalsReceived = prometheus.NewCounter(
		prometheus.CounterOpts{
			Namespace: "tnsvt",
			Subsystem: "execution_engine",
			Name:      "signals_received_total",
			Help:      "Total validated signals received from NATS",
		},
	)
)

func init() {
	prometheus.MustRegister(ordersPlaced, ordersLatency, openPositions, riskNotifications, signalsReceived)
}
