// Package repository maneja la persistencia append-only de eventos de auditoría.
package repository

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/tnsvt/audit-engine/internal/models"
)

// AuditRepository interfaz de almacenamiento
type AuditRepository interface {
	InsertEvent(ctx context.Context, event *models.AuditEvent) error
	RunMigrations(ctx context.Context) error
	Ping(ctx context.Context) error
}

type pgRepo struct {
	pool *pgxpool.Pool
}

// New crea el repositorio PostgreSQL
func New(pool *pgxpool.Pool) AuditRepository {
	return &pgRepo{pool: pool}
}

func (r *pgRepo) Ping(ctx context.Context) error {
	return r.pool.Ping(ctx)
}

func (r *pgRepo) RunMigrations(ctx context.Context) error {
	migrations := []struct {
		name string
		sql  string
	}{
		{
			name: "create_audit_events_table",
			sql: `CREATE TABLE IF NOT EXISTS audit.events (
				id UUID PRIMARY KEY,
				event_type VARCHAR(100) NOT NULL,
				source VARCHAR(100) NOT NULL DEFAULT '',
				subject VARCHAR(255) NOT NULL DEFAULT '',
				data JSONB DEFAULT '{}',
				metadata JSONB DEFAULT '{}',
				tenant_id UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000',
				created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
			)`,
		},
		{
			name: "create_audit_indexes",
			sql: `CREATE INDEX IF NOT EXISTS idx_audit_events_type ON audit.events(event_type);
				  CREATE INDEX IF NOT EXISTS idx_audit_events_tenant ON audit.events(tenant_id);
				  CREATE INDEX IF NOT EXISTS idx_audit_events_created ON audit.events(created_at DESC)`,
		},
	}

	for _, m := range migrations {
		if _, err := r.pool.Exec(ctx, m.sql); err != nil {
			return fmt.Errorf("migration %s failed: %w", m.name, err)
		}
	}
	return nil
}

func (r *pgRepo) InsertEvent(ctx context.Context, event *models.AuditEvent) error {
	data, _ := json.Marshal(event.Data)
	meta, _ := json.Marshal(event.Metadata)

	_, err := r.pool.Exec(ctx, `
		INSERT INTO audit.events (id, event_type, source, subject, data, metadata, tenant_id, created_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
		ON CONFLICT (id) DO NOTHING`,
		event.ID, event.EventType, event.Source, event.Subject,
		data, meta, event.TenantID, event.CreatedAt,
	)
	return err
}
