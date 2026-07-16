// Package repository maneja la persistencia de perfiles de usuario.
package repository

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/tnsvt/user-service/internal/models"
)

var ErrNotFound = fmt.Errorf("not found")

// UserRepository interfaz
type UserRepository interface {
	GetProfile(ctx context.Context, userID uuid.UUID) (*models.UserProfile, error)
	UpsertProfile(ctx context.Context, p *models.UserProfile) error
	RunMigrations(ctx context.Context) error
	Ping(ctx context.Context) error
}

type pgRepo struct {
	pool *pgxpool.Pool
}

func New(pool *pgxpool.Pool) UserRepository {
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
			name: "create_user_profiles_table",
			sql: `CREATE TABLE IF NOT EXISTS platform.user_profiles (
				user_id UUID PRIMARY KEY REFERENCES platform.users(id) ON DELETE CASCADE,
				tenant_id UUID NOT NULL,
				full_name VARCHAR(200) NOT NULL DEFAULT '',
				avatar_url VARCHAR(500) DEFAULT '',
				timezone VARCHAR(50) NOT NULL DEFAULT 'UTC',
				language VARCHAR(10) NOT NULL DEFAULT 'en',
				phone VARCHAR(30) DEFAULT '',
				preferences JSONB DEFAULT '{}',
				notify_settings JSONB DEFAULT '{}',
				created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
				updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
			)`,
		},
		{
			name: "create_profiles_index",
			sql: `CREATE INDEX IF NOT EXISTS idx_user_profiles_tenant ON platform.user_profiles(tenant_id)`,
		},
	}

	for _, m := range migrations {
		if _, err := r.pool.Exec(ctx, m.sql); err != nil {
			return fmt.Errorf("migration %s: %w", m.name, err)
		}
	}
	return nil
}

func (r *pgRepo) GetProfile(ctx context.Context, userID uuid.UUID) (*models.UserProfile, error) {
	p := &models.UserProfile{}
	var avatar, phone *string
	var prefs, notif []byte

	err := r.pool.QueryRow(ctx, `
		SELECT user_id, tenant_id, full_name, COALESCE(avatar_url, ''), timezone, language,
		       COALESCE(phone, ''), COALESCE(preferences, '{}'), COALESCE(notify_settings, '{}'),
		       created_at, updated_at
		FROM platform.user_profiles WHERE user_id = $1`, userID).Scan(
		&p.UserID, &p.TenantID, &p.FullName, &avatar, &p.Timezone, &p.Language,
		&phone, &prefs, &notif, &p.CreatedAt, &p.UpdatedAt,
	)
	if err != nil {
		if err.Error() == "no rows in result set" {
			return nil, ErrNotFound
		}
		return nil, err
	}

	if avatar != nil {
		p.AvatarURL = *avatar
	}
	if phone != nil {
		p.Phone = *phone
	}
	if len(prefs) > 0 {
		json.Unmarshal(prefs, &p.Preferences)
	}
	if len(notif) > 0 {
		json.Unmarshal(notif, &p.NotifySettings)
	}

	return p, nil
}

func (r *pgRepo) UpsertProfile(ctx context.Context, p *models.UserProfile) error {
	prefs, _ := json.Marshal(p.Preferences)
	notif, _ := json.Marshal(p.NotifySettings)

	_, err := r.pool.Exec(ctx, `
		INSERT INTO platform.user_profiles (user_id, tenant_id, full_name, avatar_url, timezone, language, phone, preferences, notify_settings, created_at, updated_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), NOW())
		ON CONFLICT (user_id) DO UPDATE SET
			full_name = EXCLUDED.full_name,
			avatar_url = EXCLUDED.avatar_url,
			timezone = EXCLUDED.timezone,
			language = EXCLUDED.language,
			phone = EXCLUDED.phone,
			preferences = EXCLUDED.preferences,
			notify_settings = EXCLUDED.notify_settings,
			updated_at = NOW()`,
		p.UserID, p.TenantID, p.FullName, p.AvatarURL, p.Timezone, p.Language, p.Phone,
		prefs, notif,
	)
	return err
}
