// Package subscriber consume eventos de NATS y los persiste en audit.events.
package subscriber

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/nats-io/nats.go"

	"github.com/tnsvt/audit-engine/internal/models"
	"github.com/tnsvt/audit-engine/internal/repository"
)

const defaultTenant = "00000000-0000-0000-0000-000000000001"

// AuditSubscriber escucha subjects de negocio y los almacena.
type AuditSubscriber struct {
	nats *nats.Conn
	repo repository.AuditRepository
	log  interface {
		Info(string, ...any)
		Warn(string, ...any)
		Error(string, error, ...any)
	}
}

// New crea el subscriber
func New(nc *nats.Conn, repo repository.AuditRepository, log interface {
	Info(string, ...any)
	Warn(string, ...any)
	Error(string, error, ...any)
}) *AuditSubscriber {
	return &AuditSubscriber{
		nats: nc,
		repo: repo,
		log:  log,
	}
}

// Start suscribe a subjects de negocio.
// Escucha trading.> y audit.> para registrar todos los eventos del sistema.
func (s *AuditSubscriber) Start(ctx context.Context) error {
	subjects := []string{"trading.>", "audit.>", "platform.>", "risk.>"}
	for _, subj := range subjects {
		sub, err := s.nats.Subscribe(subj, func(msg *nats.Msg) {
			s.handleEvent(msg)
		})
		if err != nil {
			return fmt.Errorf("subscribe to %s: %w", subj, err)
		}
		go func() {
			<-ctx.Done()
			sub.Unsubscribe()
		}()
		s.log.Info("Subscribed", "subject", subj)
	}
	return nil
}

func (s *AuditSubscriber) handleEvent(msg *nats.Msg) {
	event := &models.AuditEvent{
		ID:        uuid.New(),
		Subject:   msg.Subject,
		EventType: msg.Subject,
		Source:    extractSource(msg.Subject),
		CreatedAt: time.Now(),
		TenantID:  uuid.MustParse(defaultTenant),
		Data:      make(map[string]interface{}),
		Metadata:  make(map[string]interface{}),
	}

	var raw map[string]interface{}
	if err := json.Unmarshal(msg.Data, &raw); err == nil {
		if id, ok := raw["id"].(string); ok {
			if uid, err := uuid.Parse(id); err == nil {
				event.ID = uid
			}
		}
		if et, ok := raw["event_type"].(string); ok && et != "" {
			event.EventType = et
		}
		if src, ok := raw["source"].(string); ok {
			event.Source = src
		}
		if tid, ok := raw["tenant_id"].(string); ok {
			if uid, err := uuid.Parse(tid); err == nil {
				event.TenantID = uid
			}
		}
		if data, ok := raw["data"].(map[string]interface{}); ok {
			event.Data = data
		}
		if meta, ok := raw["metadata"].(map[string]interface{}); ok {
			event.Metadata = meta
		}
		if ts, ok := raw["time"].(string); ok {
			if t, err := time.Parse(time.RFC3339, ts); err == nil {
				event.CreatedAt = t
			}
		}
		if ts, ok := raw["created_at"].(string); ok {
			if t, err := time.Parse(time.RFC3339, ts); err == nil {
				event.CreatedAt = t
			}
		}
	} else {
		event.Data = map[string]interface{}{
			"raw": string(msg.Data),
		}
	}

	if err := s.repo.InsertEvent(context.Background(), event); err != nil {
		s.log.Error("InsertEvent failed", err, "subject", msg.Subject)
	}
}

func extractSource(subject string) string {
	for i := 0; i < len(subject); i++ {
		if subject[i] == '.' {
			return subject[:i]
		}
	}
	return subject
}
