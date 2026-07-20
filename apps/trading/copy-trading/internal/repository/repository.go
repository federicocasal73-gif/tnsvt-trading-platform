// Package repository maneja la persistencia del copy-trading.
package repository

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/tnsvt/copy-trading/internal/models"
)

// ErrNotFound not found
var ErrNotFound = errors.New("not found")

// ErrDuplicate duplicado
var ErrDuplicate = errors.New("duplicate")

// CopyTradingRepository interfaz
type CopyTradingRepository interface {
	// Groups
	CreateGroup(ctx context.Context, g *models.CopyGroup) error
	GetGroup(ctx context.Context, id uuid.UUID) (*models.CopyGroup, error)
	UpdateGroup(ctx context.Context, g *models.CopyGroup) error
	DeleteGroup(ctx context.Context, id uuid.UUID) error
	ListGroups(ctx context.Context, tenantID uuid.UUID, limit, offset int) ([]*models.CopyGroup, int64, error)
	ListEnabledGroupsForTenant(ctx context.Context, tenantID uuid.UUID) ([]*models.CopyGroup, error)

	// Accounts
	CreateAccount(ctx context.Context, a *models.CopyAccount) error
	GetAccount(ctx context.Context, id uuid.UUID) (*models.CopyAccount, error)
	UpdateAccount(ctx context.Context, a *models.CopyAccount) error
	DeleteAccount(ctx context.Context, id uuid.UUID) error
	ListAccountsByGroup(ctx context.Context, groupID uuid.UUID, limit, offset int) ([]*models.CopyAccount, int64, error)
	ListEnabledAccountsByGroup(ctx context.Context, groupID uuid.UUID) ([]*models.CopyAccount, error)

	// Jobs
	CreateJob(ctx context.Context, j *models.CopyJob) error
	UpdateJob(ctx context.Context, j *models.CopyJob) error
	GetJob(ctx context.Context, id uuid.UUID) (*models.CopyJob, error)
	ListJobs(ctx context.Context, tenantID *uuid.UUID, groupID, accountID *uuid.UUID, status *models.JobStatus, limit, offset int) ([]*models.CopyJob, int64, error)
	Stats(ctx context.Context, tenantID *uuid.UUID, since time.Time) (*models.StatsResponse, error)

	// Lifecycle
	RunMigrations(ctx context.Context) error
	Ping(ctx context.Context) error
}

// ─── PostgreSQL ────────────────────────────────────────────────

type pgRepo struct {
	pool *pgxpool.Pool
}

// NewCopyTradingRepository crea el repo
func NewCopyTradingRepository(pool *pgxpool.Pool, _ interface{}) CopyTradingRepository {
	return &pgRepo{pool: pool}
}

func (r *pgRepo) Ping(ctx context.Context) error {
	return r.pool.Ping(ctx)
}

// ─── Migrations ────────────────────────────────────────────────

func (r *pgRepo) RunMigrations(ctx context.Context) error {
	migrations := []struct {
		name string
		sql  string
	}{
		{
			name: "create_copy_groups_table",
			sql: `CREATE TABLE IF NOT EXISTS trading.copy_groups (
				id UUID PRIMARY KEY,
				tenant_id UUID NOT NULL,
				name VARCHAR(100) NOT NULL,
				description TEXT,
				enabled BOOLEAN NOT NULL DEFAULT TRUE,
				symbols VARCHAR(20)[] DEFAULT ARRAY[]::VARCHAR[],
				actions VARCHAR(20)[] DEFAULT ARRAY[]::VARCHAR[],
				min_confidence NUMERIC(4, 3) DEFAULT 0,
				total_accounts INTEGER NOT NULL DEFAULT 0,
				total_jobs BIGINT NOT NULL DEFAULT 0,
				success_rate NUMERIC(5, 2) DEFAULT 0,
				created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
				updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
			)`,
		},
		{
			name: "create_copy_accounts_table",
			sql: `CREATE TABLE IF NOT EXISTS trading.copy_accounts (
				id UUID PRIMARY KEY,
				group_id UUID NOT NULL REFERENCES trading.copy_groups(id) ON DELETE CASCADE,
				tenant_id UUID NOT NULL,
				name VARCHAR(100) NOT NULL,
				broker VARCHAR(50) NOT NULL,
				account_id VARCHAR(100) NOT NULL,
				enabled BOOLEAN NOT NULL DEFAULT TRUE,
				lot_mode VARCHAR(20) NOT NULL DEFAULT 'fixed',
				lot_size NUMERIC(10, 4),
				lot_multiplier NUMERIC(5, 2) DEFAULT 1.0,
				risk_percent NUMERIC(5, 2),
				override_sl BOOLEAN NOT NULL DEFAULT FALSE,
				sl_pips NUMERIC(8, 2) DEFAULT 0,
				override_tp BOOLEAN NOT NULL DEFAULT FALSE,
				tp_pips NUMERIC(8, 2) DEFAULT 0,
				invert_side BOOLEAN NOT NULL DEFAULT FALSE,
				symbol_suffix VARCHAR(10) DEFAULT '',
				total_trades BIGINT NOT NULL DEFAULT 0,
				last_trade_at TIMESTAMPTZ,
				created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
				updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
				UNIQUE(group_id, broker, account_id)
			)`,
		},
		{
			name: "create_copy_jobs_table",
			sql: `CREATE TABLE IF NOT EXISTS trading.copy_jobs (
				id UUID PRIMARY KEY,
				tenant_id UUID NOT NULL,
				group_id UUID NOT NULL,
				account_id UUID NOT NULL,
				signal_id UUID NOT NULL,
				symbol VARCHAR(20) NOT NULL,
				action VARCHAR(20) NOT NULL,
				entry_price NUMERIC(20, 8) NOT NULL DEFAULT 0,
				stop_loss NUMERIC(20, 8) DEFAULT 0,
				take_profit NUMERIC(20, 8) DEFAULT 0,
				original_lot_size NUMERIC(10, 4) DEFAULT 0,
				applied_lot_size NUMERIC(10, 4) DEFAULT 0,
				applied_sl NUMERIC(20, 8) DEFAULT 0,
				applied_tp NUMERIC(20, 8) DEFAULT 0,
				applied_side VARCHAR(10) DEFAULT '',
				applied_symbol VARCHAR(30) DEFAULT '',
				status VARCHAR(20) NOT NULL DEFAULT 'pending',
				execution_id UUID,
				error_message TEXT,
				retry_count INTEGER NOT NULL DEFAULT 0,
				started_at TIMESTAMPTZ,
				completed_at TIMESTAMPTZ,
				duration_ms BIGINT NOT NULL DEFAULT 0,
				created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
				updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
			)`,
		},
		{
			name: "create_copy_indexes",
			sql: `CREATE INDEX IF NOT EXISTS idx_copy_groups_tenant ON trading.copy_groups(tenant_id);
				  CREATE INDEX IF NOT EXISTS idx_copy_accounts_group ON trading.copy_accounts(group_id);
				  CREATE INDEX IF NOT EXISTS idx_copy_accounts_tenant ON trading.copy_accounts(tenant_id);
				  CREATE INDEX IF NOT EXISTS idx_copy_jobs_tenant ON trading.copy_jobs(tenant_id);
				  CREATE INDEX IF NOT EXISTS idx_copy_jobs_signal ON trading.copy_jobs(signal_id);
				  CREATE INDEX IF NOT EXISTS idx_copy_jobs_status ON trading.copy_jobs(status);
				  CREATE INDEX IF NOT EXISTS idx_copy_jobs_created ON trading.copy_jobs(created_at DESC)`,
		},
	}

	for _, m := range migrations {
		if _, err := r.pool.Exec(ctx, m.sql); err != nil {
			return fmt.Errorf("migration %s failed: %w", m.name, err)
		}
	}

	return nil
}

// ─── Groups ────────────────────────────────────────────────────

func (r *pgRepo) CreateGroup(ctx context.Context, g *models.CopyGroup) error {
	if g.ID == uuid.Nil {
		g.ID = uuid.New()
	}
	g.CreatedAt = time.Now()
	g.UpdatedAt = time.Now()

	if g.Symbols == nil {
		g.Symbols = []string{}
	}
	if g.Actions == nil {
		g.Actions = []string{}
	}

	_, err := r.pool.Exec(ctx, `
		INSERT INTO trading.copy_groups (id, tenant_id, name, description, enabled, symbols, actions, min_confidence, total_accounts, total_jobs, success_rate, created_at, updated_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)`,
		g.ID, g.TenantID, g.Name, g.Description, g.Enabled, g.Symbols, g.Actions, g.MinConfidence,
		g.TotalAccounts, g.TotalJobs, g.SuccessRate, g.CreatedAt, g.UpdatedAt,
	)
	return err
}

func (r *pgRepo) GetGroup(ctx context.Context, id uuid.UUID) (*models.CopyGroup, error) {
	g := &models.CopyGroup{}
	err := r.pool.QueryRow(ctx, `
		SELECT id, tenant_id, name, COALESCE(description, ''), enabled,
		       COALESCE(symbols, ARRAY[]::VARCHAR[]), COALESCE(actions, ARRAY[]::VARCHAR[]),
		       COALESCE(min_confidence, 0), total_accounts, total_jobs, COALESCE(success_rate, 0),
		       created_at, updated_at
		FROM trading.copy_groups WHERE id = $1`, id).Scan(
		&g.ID, &g.TenantID, &g.Name, &g.Description, &g.Enabled,
		&g.Symbols, &g.Actions, &g.MinConfidence, &g.TotalAccounts, &g.TotalJobs, &g.SuccessRate,
		&g.CreatedAt, &g.UpdatedAt,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, ErrNotFound
		}
		return nil, err
	}
	return g, nil
}

func (r *pgRepo) UpdateGroup(ctx context.Context, g *models.CopyGroup) error {
	g.UpdatedAt = time.Now()
	_, err := r.pool.Exec(ctx, `
		UPDATE trading.copy_groups SET
			name = $2, description = $3, enabled = $4,
			symbols = $5, actions = $6, min_confidence = $7,
			total_accounts = $8, total_jobs = $9, success_rate = $10,
			updated_at = NOW()
		WHERE id = $1`,
		g.ID, g.Name, g.Description, g.Enabled,
		g.Symbols, g.Actions, g.MinConfidence,
		g.TotalAccounts, g.TotalJobs, g.SuccessRate,
	)
	return err
}

func (r *pgRepo) DeleteGroup(ctx context.Context, id uuid.UUID) error {
	_, err := r.pool.Exec(ctx, `DELETE FROM trading.copy_groups WHERE id = $1`, id)
	return err
}

func (r *pgRepo) ListGroups(ctx context.Context, tenantID uuid.UUID, limit, offset int) ([]*models.CopyGroup, int64, error) {
	if limit <= 0 || limit > 100 {
		limit = 20
	}

	var total int64
	if err := r.pool.QueryRow(ctx,
		`SELECT COUNT(*) FROM trading.copy_groups WHERE tenant_id = $1`,
		tenantID).Scan(&total); err != nil {
		return nil, 0, err
	}

	rows, err := r.pool.Query(ctx, `
		SELECT id, tenant_id, name, COALESCE(description, ''), enabled,
		       COALESCE(symbols, ARRAY[]::VARCHAR[]), COALESCE(actions, ARRAY[]::VARCHAR[]),
		       COALESCE(min_confidence, 0), total_accounts, total_jobs, COALESCE(success_rate, 0),
		       created_at, updated_at
		FROM trading.copy_groups
		WHERE tenant_id = $1
		ORDER BY created_at DESC
		LIMIT $2 OFFSET $3`, tenantID, limit, offset)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()

	var groups []*models.CopyGroup
	for rows.Next() {
		g := &models.CopyGroup{}
		if err := rows.Scan(
			&g.ID, &g.TenantID, &g.Name, &g.Description, &g.Enabled,
			&g.Symbols, &g.Actions, &g.MinConfidence, &g.TotalAccounts, &g.TotalJobs, &g.SuccessRate,
			&g.CreatedAt, &g.UpdatedAt,
		); err != nil {
			return nil, 0, err
		}
		groups = append(groups, g)
	}
	return groups, total, nil
}

func (r *pgRepo) ListEnabledGroupsForTenant(ctx context.Context, tenantID uuid.UUID) ([]*models.CopyGroup, error) {
	rows, err := r.pool.Query(ctx, `
		SELECT id, tenant_id, name, COALESCE(description, ''), enabled,
		       COALESCE(symbols, ARRAY[]::VARCHAR[]), COALESCE(actions, ARRAY[]::VARCHAR[]),
		       COALESCE(min_confidence, 0), total_accounts, total_jobs, COALESCE(success_rate, 0),
		       created_at, updated_at
		FROM trading.copy_groups
		WHERE tenant_id = $1 AND enabled = TRUE`, tenantID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var groups []*models.CopyGroup
	for rows.Next() {
		g := &models.CopyGroup{}
		if err := rows.Scan(
			&g.ID, &g.TenantID, &g.Name, &g.Description, &g.Enabled,
			&g.Symbols, &g.Actions, &g.MinConfidence, &g.TotalAccounts, &g.TotalJobs, &g.SuccessRate,
			&g.CreatedAt, &g.UpdatedAt,
		); err != nil {
			continue
		}
		groups = append(groups, g)
	}
	return groups, nil
}

// ─── Accounts ──────────────────────────────────────────────────

func (r *pgRepo) CreateAccount(ctx context.Context, a *models.CopyAccount) error {
	if a.ID == uuid.Nil {
		a.ID = uuid.New()
	}
	a.CreatedAt = time.Now()
	a.UpdatedAt = time.Now()

	if a.LotMode == "" {
		a.LotMode = models.LotModeFixed
	}
	if a.LotMultiplier == 0 {
		a.LotMultiplier = 1.0
	}

	_, err := r.pool.Exec(ctx, `
		INSERT INTO trading.copy_accounts (
			id, group_id, tenant_id, name, broker, account_id,
			enabled, lot_mode, lot_size, lot_multiplier, risk_percent,
			override_sl, sl_pips, override_tp, tp_pips,
			invert_side, symbol_suffix, total_trades, last_trade_at,
			created_at, updated_at
		) VALUES (
			$1, $2, $3, $4, $5, $6,
			$7, $8, $9, $10, $11,
			$12, $13, $14, $15,
			$16, $17, $18, $19,
			$20, $21
		)`,
		a.ID, a.GroupID, a.TenantID, a.Name, a.Broker, a.AccountID,
		a.Enabled, a.LotMode, a.LotSize, a.LotMultiplier, a.RiskPercent,
		a.OverrideSL, a.SLPips, a.OverrideTP, a.TPPips,
		a.InvertSide, a.SymbolSuffix, a.TotalTrades, a.LastTradeAt,
		a.CreatedAt, a.UpdatedAt,
	)

	if err != nil {
		if isUniqueViolation(err) {
			return ErrDuplicate
		}
		return err
	}

	// Update group total_accounts count
	r.pool.Exec(ctx, `
		UPDATE trading.copy_groups SET total_accounts = (
			SELECT COUNT(*) FROM trading.copy_accounts WHERE group_id = $1
		) WHERE id = $1`, a.GroupID)

	return nil
}

func (r *pgRepo) GetAccount(ctx context.Context, id uuid.UUID) (*models.CopyAccount, error) {
	a := &models.CopyAccount{}
	var lotSize, riskPercent *float64
	var lastTradeAt *time.Time

	err := r.pool.QueryRow(ctx, `
		SELECT id, group_id, tenant_id, name, broker, account_id,
		       enabled, lot_mode, lot_size, lot_multiplier, risk_percent,
		       override_sl, sl_pips, override_tp, tp_pips,
		       invert_side, COALESCE(symbol_suffix, ''),
		       total_trades, last_trade_at, created_at, updated_at
		FROM trading.copy_accounts WHERE id = $1`, id).Scan(
		&a.ID, &a.GroupID, &a.TenantID, &a.Name, &a.Broker, &a.AccountID,
		&a.Enabled, &a.LotMode, &lotSize, &a.LotMultiplier, &riskPercent,
		&a.OverrideSL, &a.SLPips, &a.OverrideTP, &a.TPPips,
		&a.InvertSide, &a.SymbolSuffix,
		&a.TotalTrades, &lastTradeAt, &a.CreatedAt, &a.UpdatedAt,
	)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, ErrNotFound
		}
		return nil, err
	}

	a.LotSize = lotSize
	a.RiskPercent = riskPercent
	a.LastTradeAt = lastTradeAt

	return a, nil
}

func (r *pgRepo) UpdateAccount(ctx context.Context, a *models.CopyAccount) error {
	a.UpdatedAt = time.Now()
	_, err := r.pool.Exec(ctx, `
		UPDATE trading.copy_accounts SET
			name = $2, enabled = $3, lot_mode = $4,
			lot_size = $5, lot_multiplier = $6, risk_percent = $7,
			override_sl = $8, sl_pips = $9, override_tp = $10, tp_pips = $11,
			invert_side = $12, symbol_suffix = $13, updated_at = NOW()
		WHERE id = $1`,
		a.ID, a.Name, a.Enabled, a.LotMode,
		a.LotSize, a.LotMultiplier, a.RiskPercent,
		a.OverrideSL, a.SLPips, a.OverrideTP, a.TPPips,
		a.InvertSide, a.SymbolSuffix,
	)
	return err
}

func (r *pgRepo) DeleteAccount(ctx context.Context, id uuid.UUID) error {
	_, err := r.pool.Exec(ctx, `DELETE FROM trading.copy_accounts WHERE id = $1`, id)
	return err
}

func (r *pgRepo) ListAccountsByGroup(ctx context.Context, groupID uuid.UUID, limit, offset int) ([]*models.CopyAccount, int64, error) {
	if limit <= 0 || limit > 100 {
		limit = 20
	}

	var total int64
	r.pool.QueryRow(ctx, `SELECT COUNT(*) FROM trading.copy_accounts WHERE group_id = $1`, groupID).Scan(&total)

	rows, err := r.pool.Query(ctx, `
		SELECT id, group_id, tenant_id, name, broker, account_id,
		       enabled, lot_mode, lot_size, lot_multiplier, risk_percent,
		       override_sl, sl_pips, override_tp, tp_pips,
		       invert_side, COALESCE(symbol_suffix, ''),
		       total_trades, last_trade_at, created_at, updated_at
		FROM trading.copy_accounts
		WHERE group_id = $1
		ORDER BY created_at DESC
		LIMIT $2 OFFSET $3`, groupID, limit, offset)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()

	var accounts []*models.CopyAccount
	for rows.Next() {
		a, err := scanAccountRow(rows)
		if err != nil {
			return nil, 0, err
		}
		accounts = append(accounts, a)
	}
	return accounts, total, nil
}

func (r *pgRepo) ListEnabledAccountsByGroup(ctx context.Context, groupID uuid.UUID) ([]*models.CopyAccount, error) {
	rows, err := r.pool.Query(ctx, `
		SELECT id, group_id, tenant_id, name, broker, account_id,
		       enabled, lot_mode, lot_size, lot_multiplier, risk_percent,
		       override_sl, sl_pips, override_tp, tp_pips,
		       invert_side, COALESCE(symbol_suffix, ''),
		       total_trades, last_trade_at, created_at, updated_at
		FROM trading.copy_accounts
		WHERE group_id = $1 AND enabled = TRUE
		ORDER BY created_at`, groupID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var accounts []*models.CopyAccount
	for rows.Next() {
		a, err := scanAccountRow(rows)
		if err != nil {
			continue
		}
		accounts = append(accounts, a)
	}
	return accounts, nil
}

type scanner interface {
	Scan(dest ...any) error
}

func scanAccountRow(s scanner) (*models.CopyAccount, error) {
	a := &models.CopyAccount{}
	var lotSize, riskPercent *float64
	var lastTradeAt *time.Time
	if err := s.Scan(
		&a.ID, &a.GroupID, &a.TenantID, &a.Name, &a.Broker, &a.AccountID,
		&a.Enabled, &a.LotMode, &lotSize, &a.LotMultiplier, &riskPercent,
		&a.OverrideSL, &a.SLPips, &a.OverrideTP, &a.TPPips,
		&a.InvertSide, &a.SymbolSuffix,
		&a.TotalTrades, &lastTradeAt, &a.CreatedAt, &a.UpdatedAt,
	); err != nil {
		return nil, err
	}
	a.LotSize = lotSize
	a.RiskPercent = riskPercent
	a.LastTradeAt = lastTradeAt
	return a, nil
}

// ─── Jobs ──────────────────────────────────────────────────────

func (r *pgRepo) CreateJob(ctx context.Context, j *models.CopyJob) error {
	if j.ID == uuid.Nil {
		j.ID = uuid.New()
	}
	j.CreatedAt = time.Now()
	j.UpdatedAt = time.Now()

	_, err := r.pool.Exec(ctx, `
		INSERT INTO trading.copy_jobs (
			id, tenant_id, group_id, account_id, signal_id,
			symbol, action, entry_price, stop_loss, take_profit, original_lot_size,
			applied_lot_size, applied_sl, applied_tp, applied_side, applied_symbol,
			status, execution_id, error_message, retry_count,
			started_at, completed_at, duration_ms, created_at, updated_at
		) VALUES (
			$1, $2, $3, $4, $5,
			$6, $7, $8, $9, $10, $11,
			$12, $13, $14, $15, $16,
			$17, $18, $19, $20,
			$21, $22, $23, $24, $25
		)`,
		j.ID, j.TenantID, j.GroupID, j.AccountID, j.SignalID,
		j.Symbol, j.Action, j.EntryPrice, j.StopLoss, j.TakeProfit, j.OriginalLotSize,
		j.AppliedLotSize, j.AppliedSL, j.AppliedTP, j.AppliedSide, j.AppliedSymbol,
		j.Status, j.ExecutionID, nullString(j.ErrorMessage), j.RetryCount,
		j.StartedAt, j.CompletedAt, j.DurationMs, j.CreatedAt, j.UpdatedAt,
	)
	return err
}

func (r *pgRepo) UpdateJob(ctx context.Context, j *models.CopyJob) error {
	j.UpdatedAt = time.Now()
	_, err := r.pool.Exec(ctx, `
		UPDATE trading.copy_jobs SET
			status = $2,
			execution_id = $3,
			error_message = $4,
			retry_count = $5,
			started_at = $6,
			completed_at = $7,
			duration_ms = $8,
			updated_at = NOW()
		WHERE id = $1`,
		j.ID, j.Status, j.ExecutionID, nullString(j.ErrorMessage),
		j.RetryCount, j.StartedAt, j.CompletedAt, j.DurationMs,
	)
	return err
}

func (r *pgRepo) GetJob(ctx context.Context, id uuid.UUID) (*models.CopyJob, error) {
	return r.scanSingleJob(ctx, "id", id)
}

func (r *pgRepo) scanSingleJob(ctx context.Context, field string, value any) (*models.CopyJob, error) {
	j := &models.CopyJob{}
	var executionID *uuid.UUID
	var errorMessage, appliedSide, appliedSymbol *string
	var startedAt, completedAt *time.Time

	query := fmt.Sprintf(`
		SELECT id, tenant_id, group_id, account_id, signal_id,
		       symbol, action, entry_price, stop_loss, take_profit, original_lot_size,
		       applied_lot_size, applied_sl, applied_tp, COALESCE(applied_side, ''), COALESCE(applied_symbol, ''),
		       status, execution_id, COALESCE(error_message, ''),
		       retry_count, started_at, completed_at, duration_ms,
		       created_at, updated_at
		FROM trading.copy_jobs WHERE %s = $1 LIMIT 1`, field)

	err := r.pool.QueryRow(ctx, query, value).Scan(
		&j.ID, &j.TenantID, &j.GroupID, &j.AccountID, &j.SignalID,
		&j.Symbol, &j.Action, &j.EntryPrice, &j.StopLoss, &j.TakeProfit, &j.OriginalLotSize,
		&j.AppliedLotSize, &j.AppliedSL, &j.AppliedTP, &appliedSide, &appliedSymbol,
		&j.Status, &executionID, &errorMessage,
		&j.RetryCount, &startedAt, &completedAt, &j.DurationMs,
		&j.CreatedAt, &j.UpdatedAt,
	)

	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, ErrNotFound
		}
		return nil, err
	}

	j.ExecutionID = executionID
	j.ErrorMessage = derefString(errorMessage)
	j.AppliedSide = derefString(appliedSide)
	j.AppliedSymbol = derefString(appliedSymbol)
	j.StartedAt = startedAt
	j.CompletedAt = completedAt

	return j, nil
}

func (r *pgRepo) ListJobs(ctx context.Context, tenantID *uuid.UUID, groupID, accountID *uuid.UUID, status *models.JobStatus, limit, offset int) ([]*models.CopyJob, int64, error) {
	if limit <= 0 || limit > 100 {
		limit = 20
	}

	args := []any{}
	clauses := []string{}

	if tenantID != nil {
		args = append(args, *tenantID)
		clauses = append(clauses, fmt.Sprintf("tenant_id = $%d", len(args)))
	}
	if groupID != nil {
		args = append(args, *groupID)
		clauses = append(clauses, fmt.Sprintf("group_id = $%d", len(args)))
	}
	if accountID != nil {
		args = append(args, *accountID)
		clauses = append(clauses, fmt.Sprintf("account_id = $%d", len(args)))
	}
	if status != nil {
		args = append(args, *status)
		clauses = append(clauses, fmt.Sprintf("status = $%d", len(args)))
	}

	whereSQL := ""
	if len(clauses) > 0 {
		whereSQL = "WHERE " + joinClauses(clauses, " AND ")
	}

	var total int64
	r.pool.QueryRow(ctx, "SELECT COUNT(*) FROM trading.copy_jobs "+whereSQL, args...).Scan(&total)

	args = append(args, limit, offset)
	listSQL := fmt.Sprintf(`
		SELECT id, tenant_id, group_id, account_id, signal_id,
		       symbol, action, entry_price, stop_loss, take_profit, original_lot_size,
		       applied_lot_size, applied_sl, applied_tp, applied_side, applied_symbol,
		       status, execution_id, error_message,
		       retry_count, started_at, completed_at, duration_ms,
		       created_at, updated_at
		FROM trading.copy_jobs %s
		ORDER BY created_at DESC
		LIMIT $%d OFFSET $%d`, whereSQL, len(args)-1, len(args))

	rows, err := r.pool.Query(ctx, listSQL, args...)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()

	var jobs []*models.CopyJob
	for rows.Next() {
		j, err := scanJobRow(rows)
		if err != nil {
			continue
		}
		jobs = append(jobs, j)
	}
	return jobs, total, nil
}

func scanJobRow(s scanner) (*models.CopyJob, error) {
	j := &models.CopyJob{}
	var executionID *uuid.UUID
	var errorMessage, appliedSide, appliedSymbol *string
	var startedAt, completedAt *time.Time

	if err := s.Scan(
		&j.ID, &j.TenantID, &j.GroupID, &j.AccountID, &j.SignalID,
		&j.Symbol, &j.Action, &j.EntryPrice, &j.StopLoss, &j.TakeProfit, &j.OriginalLotSize,
		&j.AppliedLotSize, &j.AppliedSL, &j.AppliedTP, &appliedSide, &appliedSymbol,
		&j.Status, &executionID, &errorMessage,
		&j.RetryCount, &startedAt, &completedAt, &j.DurationMs,
		&j.CreatedAt, &j.UpdatedAt,
	); err != nil {
		return nil, err
	}
	j.ExecutionID = executionID
	j.ErrorMessage = derefString(errorMessage)
	j.AppliedSide = derefString(appliedSide)
	j.AppliedSymbol = derefString(appliedSymbol)
	j.StartedAt = startedAt
	j.CompletedAt = completedAt
	return j, nil
}

func (r *pgRepo) Stats(ctx context.Context, tenantID *uuid.UUID, since time.Time) (*models.StatsResponse, error) {
	stats := &models.StatsResponse{
		ByGroup:   make(map[string]int64),
		ByAccount: make(map[string]int64),
		ByStatus:  make(map[string]int64),
	}

	whereSQL := "WHERE created_at >= $1"
	args := []any{since}
	if tenantID != nil {
		args = append(args, *tenantID)
		whereSQL += fmt.Sprintf(" AND tenant_id = $%d", len(args))
	}

	// Status counts
	rows, err := r.pool.Query(ctx, "SELECT status, COUNT(*) FROM trading.copy_jobs "+whereSQL+" GROUP BY status", args...)
	if err == nil {
		for rows.Next() {
			var status string
			var count int64
			if err := rows.Scan(&status, &count); err == nil {
				stats.ByStatus[status] = count
				stats.TotalJobs += count
				if models.JobStatus(status) == models.JobSuccess {
					stats.SuccessfulJobs = count
				}
				if models.JobStatus(status) == models.JobFailed {
					stats.FailedJobs = count
				}
			}
		}
		rows.Close()
	}

	// Success rate
	if stats.TotalJobs > 0 {
		stats.SuccessRate = float64(stats.SuccessfulJobs) / float64(stats.TotalJobs) * 100
	}

	// By group
	rows2, err := r.pool.Query(ctx, `
		SELECT g.name, COUNT(j.id)
		FROM trading.copy_jobs j
		JOIN trading.copy_groups g ON j.group_id = g.id
		`+whereSQL+`
		GROUP BY g.name LIMIT 20`, args...)
	if err == nil {
		for rows2.Next() {
			var name string
			var count int64
			if err := rows2.Scan(&name, &count); err == nil {
				stats.ByGroup[name] = count
			}
		}
		rows2.Close()
	}

	// Last 24h
	r.pool.QueryRow(ctx, "SELECT COUNT(*) FROM trading.copy_jobs WHERE created_at >= NOW() - INTERVAL '24 hours'").Scan(&stats.Last24h)

	return stats, nil
}

// ─── Helpers ───────────────────────────────────────────────────

func nullString(s string) any {
	if s == "" {
		return nil
	}
	return s
}

func derefString(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}

func isUniqueViolation(err error) bool {
	if err == nil {
		return false
	}
	s := err.Error()
	return containsAny(s, []string{"duplicate key", "unique constraint", "23505"})
}

func containsAny(s string, subs []string) bool {
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

func joinClauses(clauses []string, sep string) string {
	result := ""
	for i, c := range clauses {
		if i > 0 {
			result += sep
		}
		result += c
	}
	return result
}