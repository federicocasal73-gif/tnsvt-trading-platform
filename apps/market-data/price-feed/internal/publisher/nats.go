package publisher

import (
	"encoding/json"
	"fmt"
	"sync"

	"github.com/nats-io/nats.go"

	"github.com/tnsvt/price-feed/internal/models"
)

// NatsPublisher publishes normalized ticks to NATS JetStream subjects.
type NatsPublisher struct {
	conn *nats.Conn
	js   nats.JetStreamContext
	mu   sync.Mutex
}

// NewNatsPublisher dials NATS and ensures the marketdata stream exists.
func NewNatsPublisher(url string) (*NatsPublisher, error) {
	conn, err := nats.Connect(url, nats.MaxReconnects(5), nats.ReconnectWait(2))
	if err != nil {
		return nil, err
	}
	js, err := conn.JetStream()
	if err != nil {
		conn.Close()
		return nil, err
	}
	_, err = js.AddStream(&nats.StreamConfig{
		Name:     "MARKETDATA",
		Subjects: []string{"marketdata.>"},
		Storage:  nats.FileStorage,
		MaxAge:   24 * 60 * 60, // 24h
		MaxMsgs:  1_000_000,
	})
	if err != nil && !streamExists(err) {
		conn.Close()
		return nil, err
	}
	return &NatsPublisher{conn: conn, js: js}, nil
}

// Publish serializes the tick and sends it to marketdata.tick.<symbol>.
func (p *NatsPublisher) Publish(t models.Tick) error {
	if p == nil || p.js == nil {
		return nil
	}
	p.mu.Lock()
	defer p.mu.Unlock()

	subject := fmt.Sprintf("marketdata.tick.%s", t.Symbol)
	body, err := json.Marshal(t)
	if err != nil {
		return err
	}
	_, err = p.js.Publish(subject, body)
	return err
}

// Close drains the NATS connection.
func (p *NatsPublisher) Close() error {
	if p == nil || p.conn == nil {
		return nil
	}
	p.conn.Drain()
	return nil
}

func streamExists(err error) bool {
	if err == nil {
		return true
	}
	s := err.Error()
	return contains(s, "already in use") || contains(s, "stream name already")
}

func contains(s, substr string) bool {
	for i := 0; i+len(substr) <= len(s); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}