// Package repository maneja la persistencia con PostgreSQL.
package repository

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/tnsvt/auth-service/internal/models"
)

// ErrNotFound cuando un registro no existe
var ErrNotFound = errors.New("not found")

// ErrDuplicate cuando hay conflicto unique
var ErrDuplicate = errors.New("duplicate")

// Repository interfaz
type Repository interface {
	// Tenants
	CreateTenant(ctx context.Context, t *models.Tenant) error
	GetTenantByID(ctx context.Context, id uuid.UUID) (*models.Tenant, error)
	GetTenantBySlug(ctx context.Context, slug string) (*models.Tenant, error)

	// Users
	CreateUser(ctx context.Context, u *models.User) error
	GetUserByEmail(ctx context.Context, email string) (*models.User, error)
	GetUserByID(ctx context.Context, id uuid.UUID) (*models.User, error)
	UpdateUserLastLogin(ctx context.Context, id uuid.UUID, ip string) error
	IncrementFailedLogin(ctx context.Context, id uuid.UUID) (int, error)
	ResetFailedLogin(ctx context.Context, id uuid.UUID) error
	LockUser(ctx context.Context, id uuid.UUID, until time.Time) error
	ListUsers(ctx context.Context, tenantID uuid.UUID, limit, offset int) ([]*models.User, error)

	// Sessions
	CreateSession(ctx context.Context, s *models.Session) error
	GetSessionByTokenHash(ctx context.Context, hash string) (*models.Session, error)
	RevokeSession(ctx context.Context, id uuid.UUID, reason string) error
	RevokeAllUserSessions(ctx context.Context, userID uuid.UUID, reason string) error

	// Audit
	CreateAuditEvent(ctx context.Context, e *models.AuditEvent) error

	// Lifecycle
	Close()
	RunMigrations(ctx context.Context) error
	Ping(ctx context.Context) error
}

// ─── PostgreSQL Implementation ─────────────────────────────────

type postgresRepo struct {
	pool *pgxpool.Pool
}

// NewPostgresRepository crea un nuevo repository PostgreSQL
func NewPostgresRepository(dsn string, log interface{ Error(string, error); Info(string, ...any) }) (Repository, error) {
	cfg, err := pgxpool.ParseConfig(dsn)
	if err != nil {
		return nil, fmt.Errorf("invalid DSN: %w", err)
	}
	cfg.MaxConns = 50
	cfg.MinConns = 2
	cfg.MaxConnLifetime = 30 * time.Minute

	pool, err := pgxpool.NewWithConfig(context.Background(), cfg)
	if err != nil {
		return nil, fmt.Errorf("pool creation failed: %w", err)
	}

	if err := pool.Ping(context.Background()); err != nil {
		return nil, fmt.Errorf("ping failed: %w", err)
	}

	log.Info("Connected to PostgreSQL", "host", cfg.ConnConfig.Host, "max_conns", cfg.MaxConns)

	return &postgresRepo{pool: pool}, nil
}

func (r *postgresRepo) Close() {
	r.pool.Close()
}

func (r *postgresRepo) Ping(ctx context.Context) error {
	return r.pool.Ping(ctx)
}

// ─── Migrations ────────────────────────────────────────────────

func (r *postgresRepo) RunMigrations(ctx context.Context) error {
	migrations := []struct {
		name string
		sql  string
	}{
		{
			name: "create_tenants_table",
			sql: `CREATE TABLE IF NOT EXISTS platform.tenants (
				id UUID PRIMARY KEY,
				name VARCHAR(100) NOT NULL,
				slug VARCHAR(50) UNIQUE NOT NULL,
				schema VARCHAR(50) NOT NULL,
				status VARCHAR(20) NOT NULL DEFAULT 'trial',
				plan VARCHAR(20) NOT NULL DEFAULT 'free',
				max_users INTEGER NOT NULL DEFAULT 1,
				max_signals_per_day INTEGER NOT NULL DEFAULT 100,
				created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
				updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
			)`,
		},
		{
			name: "create_users_table",
			sql: `CREATE TABLE IF NOT EXISTS platform.users (
				id UUID PRIMARY KEY,
				tenant_id UUID NOT NULL REFERENCES platform.tenants(id) ON DELETE CASCADE,
				email VARCHAR(255) UNIQUE NOT NULL,
				username VARCHAR(50) NOT NULL,
				password_hash VARCHAR(255) NOT NULL,
				role VARCHAR(30) NOT NULL DEFAULT 'tenant_viewer',
				status VARCHAR(20) NOT NULL DEFAULT 'active',
				email_verified BOOLEAN NOT NULL DEFAULT FALSE,
				two_factor_enabled BOOLEAN NOT NULL DEFAULT FALSE,
				two_factor_secret VARCHAR(255),
				failed_login_count INTEGER NOT NULL DEFAULT 0,
				locked_until TIMESTAMPTZ,
				last_login_at TIMESTAMPTZ,
				last_login_ip VARCHAR(45),
				created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
				updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
			)`,
		},
		{
			name: "create_sessions_table",
			sql: `CREATE TABLE IF NOT EXISTS platform.sessions (
				id UUID PRIMARY KEY,
				user_id UUID NOT NULL REFERENCES platform.users(id) ON DELETE CASCADE,
				refresh_token_hash VARCHAR(255) UNIQUE NOT NULL,
				user_agent VARCHAR(500),
				ip VARCHAR(45),
				expires_at TIMESTAMPTZ NOT NULL,
				revoked_at TIMESTAMPTZ,
				revoked_reason VARCHAR(100),
				created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
			)`,
		},
		{
			name: "create_audit_events_table",
			sql: `CREATE TABLE IF NOT EXISTS platform.audit_events (
				id UUID PRIMARY KEY,
				user_id UUID,
				tenant_id UUID,
				action VARCHAR(50) NOT NULL,
				ip VARCHAR(45),
				user_agent VARCHAR(500),
				status VARCHAR(20) NOT NULL,
				metadata JSONB DEFAULT '{}'::jsonb,
				timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
			)`,
		},
		{
			name: "create_users_indexes",
			sql: `CREATE INDEX IF NOT EXISTS idx_users_email ON platform.users(email);
				  CREATE INDEX IF NOT EXISTS idx_users_tenant ON platform.users(tenant_id);
				  CREATE INDEX IF NOT EXISTS idx_users_status ON platform.users(status)`,
		},
		{
			name: "create_sessions_indexes",
			sql: `CREATE INDEX IF NOT EXISTS idx_sessions_user ON platform.sessions(user_id);
				  CREATE INDEX IF NOT EXISTS idx_sessions_hash ON platform.sessions(refresh_token_hash);
				  CREATE INDEX IF NOT EXISTS idx_sessions_expires ON platform.sessions(expires_at) WHERE revoked_at IS NULL`,
		},
		{
			name: "create_audit_indexes",
			sql: `CREATE INDEX IF NOT EXISTS idx_audit_user ON platform.audit_events(user_id);
				  CREATE INDEX IF NOT EXISTS idx_audit_action ON platform.audit_events(action);
				  CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON platform.audit_events(timestamp DESC)`,
		},
	}

	for _, m := range migrations {
		if _, err := r.pool.Exec(ctx, m.sql); err != nil {
			return fmt.Errorf("migration %s failed: %w", m.name, err)
		}
	}

	return nil
}

// ─── Tenants ───────────────────────────────────────────────────

func (r *postgresRepo) CreateTenant(ctx context.Context, t *models.Tenant) error {
	if t.ID == uuid.Nil {
		t.ID = uuid.New()
	}
	t.CreatedAt = time.Now()
	t.UpdatedAt = time.Now()

	_, err := r.pool.Exec(ctx,
		`INSERT INTO platform.tenants (id, name, slug, schema, status, plan, max_users, max_signals_per_day, created_at, updated_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)`,
		t.ID, t.Name, t.Slug, t.Schema, t.Status, t.Plan, t.MaxUsers, t.MaxSignals, t.CreatedAt, t.UpdatedAt)
	if err != nil {
		if isUniqueViolation(err) {
			return ErrDuplicate
		}
		return err
	}
	return nil
}

func (r *postgresRepo) GetTenantByID(ctx context.Context, id uuid.UUID) (*models.Tenant, error) {
	t := &models.Tenant{}
	err := r.pool.QueryRow(ctx,
		`SELECT id, name, slug, schema, status, plan, max_users, max_signals_per_day, created_at, updated_at
		 FROM platform.tenants WHERE id = $1`, id).
		Scan(&t.ID, &t.Name, &t.Slug, &t.Schema, &t.Status, &t.Plan, &t.MaxUsers, &t.MaxSignals, &t.CreatedAt, &t.UpdatedAt)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, ErrNotFound
		}
		return nil, err
	}
	return t, nil
}

func (r *postgresRepo) GetTenantBySlug(ctx context.Context, slug string) (*models.Tenant, error) {
	t := &models.Tenant{}
	err := r.pool.QueryRow(ctx,
		`SELECT id, name, slug, schema, status, plan, max_users, max_signals_per_day, created_at, updated_at
		 FROM platform.tenants WHERE slug = $1`, slug).
		Scan(&t.ID, &t.Name, &t.Slug, &t.Schema, &t.Status, &t.Plan, &t.MaxUsers, &t.MaxSignals, &t.CreatedAt, &t.UpdatedAt)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, ErrNotFound
		}
		return nil, err
	}
	return t, nil
}

// ─── Users ─────────────────────────────────────────────────────

func (r *postgresRepo) CreateUser(ctx context.Context, u *models.User) error {
	if u.ID == uuid.Nil {
		u.ID = uuid.New()
	}
	u.CreatedAt = time.Now()
	u.UpdatedAt = time.Now()

	_, err := r.pool.Exec(ctx,
		`INSERT INTO platform.users (id, tenant_id, email, username, password_hash, role, status, email_verified, two_factor_enabled, created_at, updated_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)`,
		u.ID, u.TenantID, u.Email, u.Username, u.PasswordHash, u.Role, u.Status, u.EmailVerified, u.TwoFactorEnabled, u.CreatedAt, u.UpdatedAt)
	if err != nil {
		if isUniqueViolation(err) {
			return ErrDuplicate
		}
		return err
	}
	return nil
}

func (r *postgresRepo) GetUserByEmail(ctx context.Context, email string) (*models.User, error) {
	u := &models.User{}
	var lockedUntil *time.Time
	err := r.pool.QueryRow(ctx,
		`SELECT id, tenant_id, email, username, password_hash, role, status, email_verified,
		        two_factor_enabled, COALESCE(two_factor_secret, ''), failed_login_count,
		        locked_until, last_login_at, COALESCE(last_login_ip, ''), created_at, updated_at
		 FROM platform.users WHERE email = $1`, email).
		Scan(&u.ID, &u.TenantID, &u.Email, &u.Username, &u.PasswordHash, &u.Role, &u.Status,
			&u.EmailVerified, &u.TwoFactorEnabled, &u.TwoFactorSecret, &u.FailedLoginCount,
			&lockedUntil, &u.LastLoginAt, &u.LastLoginIP, &u.CreatedAt, &u.UpdatedAt)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, ErrNotFound
		}
		return nil, err
	}
	u.LockedUntil = lockedUntil
	return u, nil
}

func (r *postgresRepo) GetUserByID(ctx context.Context, id uuid.UUID) (*models.User, error) {
	u := &models.User{}
	var lockedUntil *time.Time
	err := r.pool.QueryRow(ctx,
		`SELECT id, tenant_id, email, username, password_hash, role, status, email_verified,
		        two_factor_enabled, COALESCE(two_factor_secret, ''), failed_login_count,
		        locked_until, last_login_at, COALESCE(last_login_ip, ''), created_at, updated_at
		 FROM platform.users WHERE id = $1`, id).
		Scan(&u.ID, &u.TenantID, &u.Email, &u.Username, &u.PasswordHash, &u.Role, &u.Status,
			&u.EmailVerified, &u.TwoFactorEnabled, &u.TwoFactorSecret, &u.FailedLoginCount,
			&lockedUntil, &u.LastLoginAt, &u.LastLoginIP, &u.CreatedAt, &u.UpdatedAt)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, ErrNotFound
		}
		return nil, err
	}
	u.LockedUntil = lockedUntil
	return u, nil
}

func (r *postgresRepo) UpdateUserLastLogin(ctx context.Context, id uuid.UUID, ip string) error {
	_, err := r.pool.Exec(ctx,
		`UPDATE platform.users SET last_login_at = NOW(), last_login_ip = $2, updated_at = NOW() WHERE id = $1`,
		id, ip)
	return err
}

func (r *postgresRepo) IncrementFailedLogin(ctx context.Context, id uuid.UUID) (int, error) {
	var count int
	err := r.pool.QueryRow(ctx,
		`UPDATE platform.users SET failed_login_count = failed_login_count + 1, updated_at = NOW()
		 WHERE id = $1 RETURNING failed_login_count`, id).Scan(&count)
	return count, err
}

func (r *postgresRepo) ResetFailedLogin(ctx context.Context, id uuid.UUID) error {
	_, err := r.pool.Exec(ctx,
		`UPDATE platform.users SET failed_login_count = 0, locked_until = NULL, updated_at = NOW() WHERE id = $1`,
		id)
	return err
}

func (r *postgresRepo) LockUser(ctx context.Context, id uuid.UUID, until time.Time) error {
	_, err := r.pool.Exec(ctx,
		`UPDATE platform.users SET locked_until = $2, updated_at = NOW() WHERE id = $1`,
		id, until)
	return err
}

func (r *postgresRepo) ListUsers(ctx context.Context, tenantID uuid.UUID, limit, offset int) ([]*models.User, error) {
	if limit > 100 {
		limit = 100
	}
	if limit <= 0 {
		limit = 20
	}
	rows, err := r.pool.Query(ctx,
		`SELECT id, tenant_id, email, username, password_hash, role, status, email_verified,
		        two_factor_enabled, COALESCE(two_factor_secret, ''), failed_login_count,
		        locked_until, last_login_at, COALESCE(last_login_ip, ''), created_at, updated_at
		 FROM platform.users
		 WHERE tenant_id = $1
		 ORDER BY created_at DESC
		 LIMIT $2 OFFSET $3`, tenantID, limit, offset)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var users []*models.User
	for rows.Next() {
		u := &models.User{}
		var lockedUntil *time.Time
		if err := rows.Scan(&u.ID, &u.TenantID, &u.Email, &u.Username, &u.PasswordHash, &u.Role,
			&u.Status, &u.EmailVerified, &u.TwoFactorEnabled, &u.TwoFactorSecret,
			&u.FailedLoginCount, &lockedUntil, &u.LastLoginAt, &u.LastLoginIP,
			&u.CreatedAt, &u.UpdatedAt); err != nil {
			return nil, err
		}
		u.LockedUntil = lockedUntil
		users = append(users, u)
	}
	return users, nil
}

// ─── Sessions ──────────────────────────────────────────────────

func (r *postgresRepo) CreateSession(ctx context.Context, s *models.Session) error {
	if s.ID == uuid.Nil {
		s.ID = uuid.New()
	}
	s.CreatedAt = time.Now()
	_, err := r.pool.Exec(ctx,
		`INSERT INTO platform.sessions (id, user_id, refresh_token_hash, user_agent, ip, expires_at, created_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7)`,
		s.ID, s.UserID, s.RefreshTokenHash, s.UserAgent, s.IP, s.ExpiresAt, s.CreatedAt)
	return err
}

func (r *postgresRepo) GetSessionByTokenHash(ctx context.Context, hash string) (*models.Session, error) {
	s := &models.Session{}
	var revokedAt *time.Time
	var revokedReason *string
	err := r.pool.QueryRow(ctx,
		`SELECT id, user_id, refresh_token_hash, COALESCE(user_agent, ''), COALESCE(ip, ''),
		        expires_at, revoked_at, revoked_reason, created_at
		 FROM platform.sessions WHERE refresh_token_hash = $1`, hash).
		Scan(&s.ID, &s.UserID, &s.RefreshTokenHash, &s.UserAgent, &s.IP,
			&s.ExpiresAt, &revokedAt, &revokedReason, &s.CreatedAt)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, ErrNotFound
		}
		return nil, err
	}
	s.RevokedAt = revokedAt
	if revokedReason != nil {
		s.RevokedReason = *revokedReason
	}
	return s, nil
}

func (r *postgresRepo) RevokeSession(ctx context.Context, id uuid.UUID, reason string) error {
	_, err := r.pool.Exec(ctx,
		`UPDATE platform.sessions SET revoked_at = NOW(), revoked_reason = $2 WHERE id = $1`,
		id, reason)
	return err
}

func (r *postgresRepo) RevokeAllUserSessions(ctx context.Context, userID uuid.UUID, reason string) error {
	_, err := r.pool.Exec(ctx,
		`UPDATE platform.sessions SET revoked_at = NOW(), revoked_reason = $2
		 WHERE user_id = $1 AND revoked_at IS NULL`,
		userID, reason)
	return err
}

// ─── Audit ─────────────────────────────────────────────────────

func (r *postgresRepo) CreateAuditEvent(ctx context.Context, e *models.AuditEvent) error {
	if e.ID == uuid.Nil {
		e.ID = uuid.New()
	}
	if e.Timestamp.IsZero() {
		e.Timestamp = time.Now()
	}
	_, err := r.pool.Exec(ctx,
		`INSERT INTO platform.audit_events (id, user_id, tenant_id, action, ip, user_agent, status, metadata, timestamp)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)`,
		e.ID, e.UserID, e.TenantID, e.Action, e.IP, e.UserAgent, e.Status, e.Metadata, e.Timestamp)
	return err
}

// ─── Helpers ───────────────────────────────────────────────────

func isUniqueViolation(err error) bool {
	return err != nil && (containsAny(err.Error(), "duplicate key", "unique constraint", "23505"))
}

func containsAny(s string, subs ...string) bool {
	for _, sub := range subs {
		if len(sub) == 0 {
			continue
		}
		for i := 0; i+len(sub) <= len(s); i++ {
			if s[i:i+len(sub)] == sub {
				return true
			}
		}
	}
	return false
}