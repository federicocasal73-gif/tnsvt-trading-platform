// Package repository encapsula la persistencia de cuentas en PostgreSQL.
package repository

import (
	"context"
	"errors"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/tnsvt/account-manager/internal/models"
)

// Repository define las operaciones de persistencia.
type Repository interface {
	RunMigrations(ctx context.Context) error
	Create(ctx context.Context, a *models.Account, passwordEncrypted string) error
	GetByID(ctx context.Context, id uuid.UUID) (*models.Account, string, error)
	GetByLogin(ctx context.Context, tenantID uuid.UUID, login int64, server string) (*models.Account, error)
	ListByTenant(ctx context.Context, tenantID uuid.UUID) ([]*models.Account, error)
	ListReplicatorsByTenant(ctx context.Context, tenantID uuid.UUID) ([]*models.Account, error)
	ListAll(ctx context.Context) ([]*models.Account, error)
	Update(ctx context.Context, a *models.Account) error
	UpdatePassword(ctx context.Context, id uuid.UUID, passwordEncrypted string) error
	UpdateStatus(ctx context.Context, id uuid.UUID, status models.AccountStatus, lastError string) error
	UpdateSnapshot(ctx context.Context, id uuid.UUID, snap *models.AccountSnapshot) error
	Delete(ctx context.Context, id uuid.UUID) error
}

type pgRepo struct {
	pool *pgxpool.Pool
}

// NewPostgresRepository crea un repository sobre el pool.
func NewPostgresRepository(pool *pgxpool.Pool) Repository {
	return &pgRepo{pool: pool}
}

const ddl = `
CREATE TABLE IF NOT EXISTS accounts (
    id              UUID PRIMARY KEY,
    tenant_id       UUID NOT NULL,
    login           BIGINT NOT NULL,
    password_enc    TEXT NOT NULL,
    server          TEXT NOT NULL,
    broker          TEXT NOT NULL DEFAULT 'mt5',
    alias           TEXT,
    name            TEXT,
    status          TEXT NOT NULL DEFAULT 'active',
    last_seen       TIMESTAMPTZ,
    last_error      TEXT,
    last_balance    DOUBLE PRECISION,
    last_equity     DOUBLE PRECISION,
    last_pnl        DOUBLE PRECISION,
    last_open_pos   INTEGER DEFAULT 0,
    last_snapshot_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, login, server)
);
CREATE INDEX IF NOT EXISTS idx_accounts_tenant ON accounts(tenant_id);
CREATE INDEX IF NOT EXISTS idx_accounts_status ON accounts(status);
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS copy_enabled BOOLEAN NOT NULL DEFAULT false;
CREATE INDEX IF NOT EXISTS idx_accounts_replicators ON accounts(tenant_id, copy_enabled) WHERE copy_enabled = true;
`

// RunMigrations corre el DDL idempotente.
func (r *pgRepo) RunMigrations(ctx context.Context) error {
	_, err := r.pool.Exec(ctx, ddl)
	return err
}

func (r *pgRepo) Create(ctx context.Context, a *models.Account, passwordEncrypted string) error {
	_, err := r.pool.Exec(ctx, `
		INSERT INTO accounts (id, tenant_id, login, password_enc, server, broker, alias, name, status, copy_enabled, created_at, updated_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW(), NOW())
	`, a.ID, a.TenantID, a.Login, passwordEncrypted, a.Server, a.Broker, a.Alias, a.Name, string(a.Status), a.CopyEnabled)
	return err
}

func (r *pgRepo) GetByID(ctx context.Context, id uuid.UUID) (*models.Account, string, error) {
	row := r.pool.QueryRow(ctx, `
		SELECT id, tenant_id, login, password_enc, server, broker, alias, name, status,
		       copy_enabled, last_seen, last_error, last_balance, last_equity, last_pnl, last_open_pos, last_snapshot_at,
		       created_at, updated_at
		FROM accounts WHERE id = $1
	`, id)
	a, enc, err := scanAccount(row)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, "", nil
		}
		return nil, "", err
	}
	return a, enc, nil
}

func (r *pgRepo) GetByLogin(ctx context.Context, tenantID uuid.UUID, login int64, server string) (*models.Account, error) {
	row := r.pool.QueryRow(ctx, `
		SELECT id, tenant_id, login, password_enc, server, broker, alias, name, status,
		       copy_enabled, last_seen, last_error, last_balance, last_equity, last_pnl, last_open_pos, last_snapshot_at,
		       created_at, updated_at
		FROM accounts WHERE tenant_id = $1 AND login = $2 AND server = $3
	`, tenantID, login, server)
	a, _, err := scanAccount(row)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return a, nil
}

func (r *pgRepo) ListByTenant(ctx context.Context, tenantID uuid.UUID) ([]*models.Account, error) {
	rows, err := r.pool.Query(ctx, `
		SELECT id, tenant_id, login, password_enc, server, broker, alias, name, status,
		       copy_enabled, last_seen, last_error, last_balance, last_equity, last_pnl, last_open_pos, last_snapshot_at,
		       created_at, updated_at
		FROM accounts WHERE tenant_id = $1
		ORDER BY created_at DESC
	`, tenantID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return scanAccounts(rows)
}

func (r *pgRepo) ListReplicatorsByTenant(ctx context.Context, tenantID uuid.UUID) ([]*models.Account, error) {
	rows, err := r.pool.Query(ctx, `
		SELECT id, tenant_id, login, password_enc, server, broker, alias, name, status,
		       copy_enabled, last_seen, last_error, last_balance, last_equity, last_pnl, last_open_pos, last_snapshot_at,
		       created_at, updated_at
		FROM accounts WHERE tenant_id = $1 AND copy_enabled = true
		ORDER BY created_at DESC
	`, tenantID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return scanAccounts(rows)
}

func (r *pgRepo) ListAll(ctx context.Context) ([]*models.Account, error) {
	rows, err := r.pool.Query(ctx, `
		SELECT id, tenant_id, login, password_enc, server, broker, alias, name, status,
		       copy_enabled, last_seen, last_error, last_balance, last_equity, last_pnl, last_open_pos, last_snapshot_at,
		       created_at, updated_at
		FROM accounts
		ORDER BY tenant_id, login
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return scanAccounts(rows)
}

func (r *pgRepo) Update(ctx context.Context, a *models.Account) error {
	_, err := r.pool.Exec(ctx, `
		UPDATE accounts SET
		    alias = $2, name = $3, status = $4, copy_enabled = $5, last_error = $6, updated_at = NOW()
		WHERE id = $1
	`, a.ID, a.Alias, a.Name, string(a.Status), a.CopyEnabled, a.LastError)
	return err
}

func (r *pgRepo) UpdatePassword(ctx context.Context, id uuid.UUID, passwordEncrypted string) error {
	_, err := r.pool.Exec(ctx, `
		UPDATE accounts SET password_enc = $2, updated_at = NOW() WHERE id = $1
	`, id, passwordEncrypted)
	return err
}

func (r *pgRepo) UpdateStatus(ctx context.Context, id uuid.UUID, status models.AccountStatus, lastError string) error {
	_, err := r.pool.Exec(ctx, `
		UPDATE accounts SET status = $2, last_error = $3, updated_at = NOW() WHERE id = $1
	`, id, string(status), lastError)
	return err
}

func (r *pgRepo) UpdateSnapshot(ctx context.Context, id uuid.UUID, snap *models.AccountSnapshot) error {
	_, err := r.pool.Exec(ctx, `
		UPDATE accounts SET
		    last_balance = $2, last_equity = $3, last_pnl = $4, last_open_pos = $5,
		    last_snapshot_at = NOW(), updated_at = NOW()
		WHERE id = $1
	`, id, snap.Balance, snap.Equity, snap.Profit, snap.OpenPositions)
	return err
}

func (r *pgRepo) Delete(ctx context.Context, id uuid.UUID) error {
	_, err := r.pool.Exec(ctx, `DELETE FROM accounts WHERE id = $1`, id)
	return err
}

// ─── helpers ────────────────────────────────────────────────────

type rowScanner interface {
	Scan(dest ...any) error
}

func scanAccount(row rowScanner) (*models.Account, string, error) {
	var a models.Account
	var status string
	var enc string
	err := row.Scan(
		&a.ID, &a.TenantID, &a.Login, &enc, &a.Server, &a.Broker, &a.Alias, &a.Name, &status,
		&a.CopyEnabled, &a.LastSeen, &a.LastError, &a.LastBalance, &a.LastEquity, &a.LastPnL, &a.LastOpenPos, &a.LastSnapshotAt,
		&a.CreatedAt, &a.UpdatedAt,
	)
	if err != nil {
		return nil, "", err
	}
	a.Status = models.AccountStatus(status)
	return &a, enc, nil
}

func scanAccounts(rows pgx.Rows) ([]*models.Account, error) {
	out := make([]*models.Account, 0)
	for rows.Next() {
		var a models.Account
		var status string
		var enc string
		if err := rows.Scan(
			&a.ID, &a.TenantID, &a.Login, &enc, &a.Server, &a.Broker, &a.Alias, &a.Name, &status,
			&a.CopyEnabled, &a.LastSeen, &a.LastError, &a.LastBalance, &a.LastEquity, &a.LastPnL, &a.LastOpenPos, &a.LastSnapshotAt,
			&a.CreatedAt, &a.UpdatedAt,
		); err != nil {
			return nil, err
		}
		a.Status = models.AccountStatus(status)
		out = append(out, &a)
	}
	return out, rows.Err()
}
