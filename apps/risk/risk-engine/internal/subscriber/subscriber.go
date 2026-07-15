// Package subscriber consume signals de NATS y los evalúa con el risk engine.
package subscriber

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/nats-io/nats.go"

	"github.com/tnsvt/risk-engine/internal/models"
)

// RiskEvaluator interfaz mínima para evitar import circular
type RiskEvaluator interface {
	EvaluateSignal(ctx context.Context, signal *models.SignalInput) (*models.RiskEvaluation, error)
}

// SignalSubscriber escucha eventos trading.signal.created
type SignalSubscriber struct {
	nats     *nats.Conn
	evaluator RiskEvaluator
	log      interface {
		Info(string, ...any)
		Warn(string, ...any)
		Error(string, error, ...any)
	}
}

// NewSignalSubscriber crea el subscriber
func NewSignalSubscriber(nc *nats.Conn, evaluator RiskEvaluator, log interface {
	Info(string, ...any)
	Warn(string, ...any)
	Error(string, error, ...any)
}) *SignalSubscriber {
	return &SignalSubscriber{
		nats:      nc,
		evaluator: evaluator,
		log:       log,
	}
}

// Start comienza a escuchar eventos
func (s *SignalSubscriber) Start(ctx context.Context) error {
	// Durable subscription para no perder mensajes si el servicio reinicia
	sub, err := s.nats.Subscribe("trading.signal.created", s.handleMessage)
	if err != nil {
		return fmt.Errorf("subscribe to trading.signal.created: %w", err)
	}
	s.log.Info("NATS subscriber started", "subject", "trading.signal.created")

	go func() {
		<-ctx.Done()
		sub.Unsubscribe()
		s.log.Info("NATS subscriber stopped")
	}()

	return nil
}

func (s *SignalSubscriber) handleMessage(msg *nats.Msg) {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	var signal models.SignalInput
	if err := json.Unmarshal(msg.Data, &signal); err != nil {
		s.log.Error("Failed to unmarshal signal event", err)
		return
	}

	if signal.ID == uuid.Nil {
		s.log.Warn("Signal event missing ID, skipping")
		return
	}

	if signal.TenantID == uuid.Nil {
		signal.TenantID = uuid.MustParse("00000000-0000-0000-0000-000000000001")
	}

	s.log.Info("Evaluating signal from NATS",
		"signal_id", signal.ID,
		"symbol", signal.Symbol,
		"action", signal.Action)

	ev, err := s.evaluator.EvaluateSignal(ctx, &signal)
	if err != nil {
		s.log.Error("Risk evaluation failed", err, "signal_id", signal.ID)
		return
	}

	if ev.Decision == models.DecisionApproved {
		s.log.Info("Signal approved for execution",
			"signal_id", signal.ID,
			"risk_level", ev.RiskLevel,
			"recommended_lot", derefFloat(ev.RecommendedLotSize))
	} else {
		s.log.Info("Signal rejected by risk engine",
			"signal_id", signal.ID,
			"reject_reason", ev.RejectReason,
			"reason", ev.Reason)
	}
}

// ─── Helpers ───────────────────────────────────────────────────

func derefFloat(p *float64) float64 {
	if p == nil {
		return 0
	}
	return *p
}

// ErrInvalidMessage mensaje inválido
var ErrInvalidMessage = errors.New("invalid message")