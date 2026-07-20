// Package subscriber consume signals validadas de NATS y dispara replicación.
package subscriber

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/nats-io/nats.go"

	"github.com/tnsvt/copy-trading/internal/models"
)

// ReplicationTrigger interfaz mínima
type ReplicationTrigger interface {
	ReplicateSignal(ctx context.Context, signal *models.SignalInput) error
}

// SignalSubscriber escucha trading.signal.validated
type SignalSubscriber struct {
	nats    *nats.Conn
	trigger ReplicationTrigger
	log     interface {
		Info(string, ...any)
		Warn(string, ...any)
		Error(string, error, ...any)
	}
}

// NewSignalSubscriber crea el subscriber
func NewSignalSubscriber(nc *nats.Conn, trigger ReplicationTrigger, log interface {
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
	subCreated, err := s.nats.Subscribe("trading.signal.created", s.handleMessage)
	if err != nil {
		return fmt.Errorf("subscribe to trading.signal.created: %w", err)
	}
	subValidated, err := s.nats.Subscribe("trading.signal.validated", s.handleMessage)
	if err != nil {
		return fmt.Errorf("subscribe to trading.signal.validated: %w", err)
	}
	s.log.Info("NATS subscriber started", "subjects", []string{"trading.signal.created", "trading.signal.validated"})

	go func() {
		<-ctx.Done()
		subCreated.Unsubscribe()
		subValidated.Unsubscribe()
		s.log.Info("NATS subscriber stopped")
	}()

	return nil
}

func (s *SignalSubscriber) handleMessage(msg *nats.Msg) {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

	var signal models.SignalInput
	if err := json.Unmarshal(msg.Data, &signal); err != nil {
		s.log.Error("Failed to unmarshal signal", err)
		return
	}

	if signal.ID == uuid.Nil || signal.TenantID == uuid.Nil {
		s.log.Warn("Signal event missing required fields")
		return
	}

	s.log.Info("Replicating signal",
		"signal_id", signal.ID,
		"symbol", signal.Symbol,
		"action", signal.Action)

	if err := s.trigger.ReplicateSignal(ctx, &signal); err != nil {
		s.log.Error("Replication failed", err, "signal_id", signal.ID)
	}
}