// Package publisher publica señales a NATS.
//
// Sprint 3.2: signal-generator publica a `trading.signal.created` con
// subject cubierto por TRADING_SIGNALS. La entrega llega a core subscribers
// (copy-trading) y el stream almacena el mensaje automáticamente.
package publisher

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/nats-io/nats.go"
)

// Signal es la estructura que se publica a NATS (compatible con
// models.SignalInput del signal-engine y models.Signal del risk-engine).
type Signal struct {
	ID         string    `json:"id"`
	TenantID   string    `json:"tenant_id"`
	Source     string    `json:"source"`     // "signal-generator"
	Symbol     string    `json:"symbol"`
	Action     string    `json:"action"`     // "BUY" / "SELL"
	EntryPrice *float64  `json:"entry_price,omitempty"`
	StopLoss   *float64  `json:"stop_loss,omitempty"`
	TakeProfits []float64 `json:"take_profits,omitempty"`
	LotSize    *float64  `json:"lot_size,omitempty"`
	LotMode    string    `json:"lot_mode,omitempty"`     // "fixed"
	RiskPercent *float64  `json:"risk_percent,omitempty"`
	Comment    string    `json:"comment,omitempty"`
	Confidence float64   `json:"confidence"`            // 0..1
	GeneratedAt time.Time `json:"generated_at"`
}

// Publisher publica señales a NATS via core NATS.
type Publisher struct {
	nc      *nats.Conn
	subject string
}

// New crea un publisher conectado a un nats.Conn existente.
// Usa core NATS publish; el stream almacena el mensaje automáticamente.
func New(nc *nats.Conn, streamName, subject string) (*Publisher, error) {
	return &Publisher{nc: nc, subject: subject}, nil
}

// Publish publica una señal via core NATS.
// Si no tiene ID, se genera uno nuevo. Devuelve el ID final publicado.
func (p *Publisher) Publish(_ context.Context, s *Signal) (string, error) {
	if s.ID == "" {
		s.ID = uuid.New().String()
	}
	if s.GeneratedAt.IsZero() {
		s.GeneratedAt = time.Now().UTC()
	}
	data, err := json.Marshal(s)
	if err != nil {
		return "", fmt.Errorf("marshal signal: %w", err)
	}
	if err := p.nc.Publish(p.subject, data); err != nil {
		return "", fmt.Errorf("nats publish: %w", err)
	}
	return s.ID, nil
}
