// Package models define la estructura de eventos de auditoría.
package models

import (
	"time"

	"github.com/google/uuid"
)

// AuditEvent representa un evento de negocio inmutable.
type AuditEvent struct {
	ID        uuid.UUID              `json:"id"`
	EventType string                 `json:"event_type"`
	Source    string                 `json:"source"`
	Subject   string                 `json:"subject"`
	Data      map[string]interface{} `json:"data,omitempty"`
	Metadata  map[string]interface{} `json:"metadata,omitempty"`
	TenantID  uuid.UUID              `json:"tenant_id"`
	CreatedAt time.Time              `json:"created_at"`
}
