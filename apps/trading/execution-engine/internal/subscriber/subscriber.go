// Package subscriber consume signals validadas de NATS.
package subscriber

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/nats-io/nats.go"

	"github.com/tnsvt/execution-engine/internal/models"
)

// ExecutionTrigger interfaz mínima
type ExecutionTrigger interface {
	ExecuteSignal(ctx context.Context, signal *models.SignalInput) (*models.Execution, error)
}

// SignalSubscriber escucha trading.signal.validated
type SignalSubscriber struct {
	nats    *nats.Conn
	trigger ExecutionTrigger
	log     interface {
		Info(string, ...any)
		Warn(string, ...any)
		Error(string, error, ...any)
	}
}

// NewSignalSubscriber crea el subscriber
func NewSignalSubscriber(nc *nats.Conn, trigger ExecutionTrigger, log interface {
	Info(string, ...any)
	Warn(string, ...any)
	Error(string, error, ...any)
}) *SignalSubscriber {
	return &SignalSubscriber{
		nats:    nc,
		trigger: trigger,
		log:     log,
	}
}

// Start comienza a escuchar
func (s *SignalSubscriber) Start(ctx context.Context) error {
	sub, err := s.nats.Subscribe("trading.signal.validated", s.handleMessage)
	if err != nil {
		return fmt.Errorf("subscribe to trading.signal.validated: %w", err)
	}
	s.log.Info("NATS subscriber started", "subject", "trading.signal.validated")

	// También escuchar rechazos para no procesarlos
	sub2, err := s.nats.Subscribe("trading.signal.rejected", s.handleRejected)
	if err != nil {
		return fmt.Errorf("subscribe to trading.signal.rejected: %w", err)
	}
	s.log.Info("NATS subscriber started", "subject", "trading.signal.rejected")

	go func() {
		<-ctx.Done()
		sub.Unsubscribe()
		sub2.Unsubscribe()
		s.log.Info("NATS subscribers stopped")
	}()

	return nil
}

func (s *SignalSubscriber) handleMessage(msg *nats.Msg) {
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()

	var signal models.SignalInput
	if err := json.Unmarshal(msg.Data, &signal); err != nil {
		s.log.Error("Failed to unmarshal signal", err)
		return
	}

	if signal.ID == uuid.Nil || signal.TenantID == uuid.Nil {
		s.log.Warn("Signal event missing required fields, skipping")
		return
	}

	s.log.Info("Executing validated signal",
		"signal_id", signal.ID,
		"symbol", signal.Symbol,
		"action", signal.Action,
		"lot_size", derefFloat(signal.LotSize),
		"recommended_lot", derefFloat(signal.RecommendedLotSize))

	exec, err := s.trigger.ExecuteSignal(ctx, &signal)
	if err != nil {
		s.log.Error("Execution failed", err, "signal_id", signal.ID)
		return
	}

	if exec.Status == models.ExecStatusFilled {
		s.log.Info("Execution completed",
			"execution_id", exec.ID,
			"symbol", exec.Symbol,
			"ticket", exec.Ticket,
			"filled_price", derefFloat(exec.FilledPrice))
	}
}

func (s *SignalSubscriber) handleRejected(msg *nats.Msg) {
	// Solo loggear, no hacer nada
	var payload map[string]any
	if err := json.Unmarshal(msg.Data, &payload); err != nil {
		return
	}
	s.log.Info("Signal rejected by risk-engine (audit)",
		"signal_id", payload["signal_id"],
		"reason", payload["reject_reason"])
}

func derefFloat(p *float64) float64 {
	if p == nil {
		return 0
	}
	return *p
}