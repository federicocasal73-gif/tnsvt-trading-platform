// Package repository maneja persistencia del execution-engine.
package repository

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/tnsvt/execution-engine/internal/models"
)

// ErrNotFound not found
var ErrNotFound = errors.New("execution not found")

// ExecutionRepository interfaz
type ExecutionRepository interface {
	Create(ctx context.Context, e *models.Execution) error
	GetByID(ctx context.Context, id uuid.UUID) (*models.Execution, error)
	GetBySignalID(ctx context.Context, signalID uuid.UUID) (*models.Execution, error)
	Update(ctx context.Context, e *models.Execution) error
	UpdateStatus(ctx context.Context, id uuid.UUID, status models.ExecutionStatus, errMsg string) error
	List(ctx context.Context, tenantID *uuid.UUID, status *models.ExecutionStatus, broker *models.BrokerName, limit, offset int) ([]*models.Execution, int64, error)
	GetFilledExecutions(ctx context.Context, tenantID uuid.UUID) ([]*models.Execution, error)
	Stats(ctx context.Context, tenantID *uuid.UUID, since time.Time) (*models.StatsResponse, error)
	RunMigrations(ctx context.Context) error
	Ping(ctx context.Context) error
}

// ─── PostgreSQL ────────────────────────────────────────────────

type pgRepo struct {
	pool *pgxpool.Pool
}

// NewExecutionRepository crea el repo
func NewExecutionRepository(pool *pgxpool.Pool, _ interface{}) ExecutionRepository {
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
			name: "create_executions_table",
			sql: `CREATE TABLE IF NOT EXISTS trading.executions (
				id UUID PRIMARY KEY,
				tenant_id UUID NOT NULL,
				signal_id UUID NOT NULL,
				user_id UUID,
				broker VARCHAR(50) NOT NULL,
				account_id VARCHAR(100) NOT NULL,
				symbol VARCHAR(20) NOT NULL,
				side VARCHAR(10) NOT NULL,
				order_type VARCHAR(20) NOT NULL DEFAULT 'market',
				quantity NUMERIC(10, 4) NOT NULL,
				price NUMERIC(20, 8),
				stop_loss NUMERIC(20, 8),
				take_profit NUMERIC(20, 8),
				take_profits NUMERIC(20, 8)[],
				order_id VARCHAR(100),
				ticket VARCHAR(100),
				filled_price NUMERIC(20, 8),
				filled_qty NUMERIC(10, 4),
				commission NUMERIC(10, 4) DEFAULT 0,
				status VARCHAR(20) NOT NULL DEFAULT 'pending',
				error_message TEXT,
				submitted_at TIMESTAMPTZ,
				filled_at TIMESTAMPTZ,
				completed_at TIMESTAMPTZ,
				position_id UUID,
				risk_level VARCHAR(20),
				retry_count INTEGER NOT NULL DEFAULT 0,
				created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
				updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
			)`,
		},
		{
			name: "create_executions_indexes",
			sql: `CREATE INDEX IF NOT EXISTS idx_executions_tenant ON trading.executions(tenant_id);
				  CREATE INDEX IF NOT EXISTS idx_executions_signal ON trading.executions(signal_id);
				  CREATE INDEX IF NOT EXISTS idx_executions_status ON trading.executions(status);
				  CREATE INDEX IF NOT EXISTS idx_executions_broker ON trading.executions(broker);
				  CREATE INDEX IF NOT EXISTS idx_executions_created ON trading.executions(created_at DESC);
				  CREATE INDEX IF NOT EXISTS idx_executions_filled ON trading.executions(tenant_id, status) WHERE status = 'filled'`,
		},
	}

	for _, m := range migrations {
		if _, err := r.pool.Exec(ctx, m.sql); err != nil {
			return fmt.Errorf("migration %s failed: %w", m.name, err)
		}
	}

	return nil
}

// ─── CRUD ──────────────────────────────────────────────────────

func (r *pgRepo) Create(ctx context.Context, e *models.Execution) error {
	if e.ID == uuid.Nil {
		e.ID = uuid.New()
	}
	e.CreatedAt = time.Now()
	e.UpdatedAt = time.Now()

	_, err := r.pool.Exec(ctx, `
		INSERT INTO trading.executions (
			id, tenant_id, signal_id, user_id, broker, account_id,
			symbol, side, order_type, quantity, price, stop_loss, take_profit, take_profits,
			order_id, ticket, filled_price, filled_qty, commission,
			status, error_message, submitted_at, filled_at, completed_at,
			position_id, risk_level, retry_count, created_at, updated_at
		) VALUES (
			$1, $2, $3, $4, $5, $6,
			$7, $8, $9, $10, $11, $12, $13, $14,
			$15, $16, $17, $18, $19,
			$20, $21, $22, $23, $24,
			$25, $26, $27, $28, $29
		)`,
		e.ID, e.TenantID, e.SignalID, e.UserID, e.Broker, e.AccountID,
		e.Symbol, e.Side, e.OrderType, e.Quantity, e.Price, e.StopLoss, e.TakeProfit, e.TakeProfits,
		nullString(e.OrderID), nullString(e.Ticket), e.FilledPrice, e.FilledQty, e.Commission,
		e.Status, nullString(e.ErrorMessage), e.SubmittedAt, e.FilledAt, e.CompletedAt,
		e.PositionID, nullString(e.RiskLevel), e.RetryCount, e.CreatedAt, e.UpdatedAt,
	)
	return err
}

func (r *pgRepo) GetByID(ctx context.Context, id uuid.UUID) (*models.Execution, error) {
	return r.scanSingleExecution(ctx, "id", id)
}

func (r *pgRepo) GetBySignalID(ctx context.Context, signalID uuid.UUID) (*models.Execution, error) {
	return r.scanSingleExecution(ctx, "signal_id", signalID)
}

func (r *pgRepo) scanSingleExecution(ctx context.Context, field string, value any) (*models.Execution, error) {
	e := &models.Execution{}
	var price, stopLoss, takeProfit, filledPrice, filledQty *float64
	var userID, positionID *uuid.UUID
	var orderID, ticket, errorMessage, riskLevel *string
	var submittedAt, filledAt, completedAt *time.Time

	query := fmt.Sprintf(`
		SELECT id, tenant_id, signal_id, user_id, broker, account_id,
		       symbol, side, order_type, quantity, price, stop_loss, take_profit, take_profits,
		       order_id, ticket, filled_price, filled_qty, commission,
		       status, error_message, submitted_at, filled_at, completed_at,
		       position_id, risk_level, retry_count, created_at, updated_at
		FROM trading.executions WHERE %s = $1 LIMIT 1`, field)

	err := r.pool.QueryRow(ctx, query, value).Scan(
		&e.ID, &e.TenantID, &e.SignalID, &userID, &e.Broker, &e.AccountID,
		&e.Symbol, &e.Side, &e.OrderType, &e.Quantity, &price, &stopLoss, &takeProfit, &e.TakeProfits,
		&orderID, &ticket, &filledPrice, &filledQty, &e.Commission,
		&e.Status, &errorMessage, &submittedAt, &filledAt, &completedAt,
		&positionID, &riskLevel, &e.RetryCount, &e.CreatedAt, &e.UpdatedAt,
	)

	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, ErrNotFound
		}
		return nil, err
	}

	e.UserID = userID
	e.PositionID = positionID
	e.Price = price
	e.StopLoss = stopLoss
	e.TakeProfit = takeProfit
	e.FilledPrice = filledPrice
	e.FilledQty = filledQty
	e.OrderID = derefString(orderID)
	e.Ticket = derefString(ticket)
	e.ErrorMessage = derefString(errorMessage)
	e.RiskLevel = derefString(riskLevel)
	e.SubmittedAt = submittedAt
	e.FilledAt = filledAt
	e.CompletedAt = completedAt

	return e, nil
}

func (r *pgRepo) Update(ctx context.Context, e *models.Execution) error {
	e.UpdatedAt = time.Now()
	_, err := r.pool.Exec(ctx, `
		UPDATE trading.executions SET
			status = $2,
			order_id = $3,
			ticket = $4,
			filled_price = $5,
			filled_qty = $6,
			commission = $7,
			error_message = $8,
			submitted_at = $9,
			filled_at = $10,
			completed_at = $11,
			position_id = $12,
			retry_count = $13,
			updated_at = NOW()
		WHERE id = $1`,
		e.ID, e.Status, nullString(e.OrderID), nullString(e.Ticket),
		e.FilledPrice, e.FilledQty, e.Commission, nullString(e.ErrorMessage),
		e.SubmittedAt, e.FilledAt, e.CompletedAt, e.PositionID, e.RetryCount,
	)
	return err
}

func (r *pgRepo) UpdateStatus(ctx context.Context, id uuid.UUID, status models.ExecutionStatus, errMsg string) error {
	_, err := r.pool.Exec(ctx, `
		UPDATE trading.executions SET
			status = $2,
			error_message = $3,
			completed_at = CASE WHEN $2 IN ('filled', 'rejected', 'cancelled', 'failed') THEN NOW() ELSE completed_at END,
			updated_at = NOW()
		WHERE id = $1`,
		id, status, nullString(errMsg),
	)
	return err
}

func (r *pgRepo) List(ctx context.Context, tenantID *uuid.UUID, status *models.ExecutionStatus, broker *models.BrokerName, limit, offset int) ([]*models.Execution, int64, error) {
	if limit <= 0 || limit > 100 {
		limit = 20
	}

	args := []any{}
	whereClauses := []string{}

	if tenantID != nil {
		args = append(args, *tenantID)
		whereClauses = append(whereClauses, fmt.Sprintf("tenant_id = $%d", len(args)))
	}
	if status != nil {
		args = append(args, *status)
		whereClauses = append(whereClauses, fmt.Sprintf("status = $%d", len(args)))
	}
	if broker != nil {
		args = append(args, *broker)
		whereClauses = append(whereClauses, fmt.Sprintf("broker = $%d", len(args)))
	}

	whereSQL := ""
	if len(whereClauses) > 0 {
		whereSQL = "WHERE " + joinClauses(whereClauses, " AND ")
	}

	// Count
	var total int64
	countSQL := "SELECT COUNT(*) FROM trading.executions " + whereSQL
	if err := r.pool.QueryRow(ctx, countSQL, args...).Scan(&total); err != nil {
		return nil, 0, err
	}

	// List
	args = append(args, limit, offset)
	listSQL := fmt.Sprintf(`
		SELECT id, tenant_id, signal_id, user_id, broker, account_id,
		       symbol, side, order_type, quantity, price, stop_loss, take_profit, take_profits,
		       order_id, ticket, filled_price, filled_qty, commission,
		       status, error_message, submitted_at, filled_at, completed_at,
		       position_id, risk_level, retry_count, created_at, updated_at
		FROM trading.executions %s
		ORDER BY created_at DESC
		LIMIT $%d OFFSET $%d`, whereSQL, len(args)-1, len(args))

	rows, err := r.pool.Query(ctx, listSQL, args...)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()

	var executions []*models.Execution
	for rows.Next() {
		e := &models.Execution{}
		var price, stopLoss, takeProfit, filledPrice, filledQty *float64
		var userID, positionID *uuid.UUID
		var orderID, ticket, errorMessage, riskLevel *string
		var submittedAt, filledAt, completedAt *time.Time

		if err := rows.Scan(
			&e.ID, &e.TenantID, &e.SignalID, &userID, &e.Broker, &e.AccountID,
			&e.Symbol, &e.Side, &e.OrderType, &e.Quantity, &price, &stopLoss, &takeProfit, &e.TakeProfits,
			&orderID, &ticket, &filledPrice, &filledQty, &e.Commission,
			&e.Status, &errorMessage, &submittedAt, &filledAt, &completedAt,
			&positionID, &riskLevel, &e.RetryCount, &e.CreatedAt, &e.UpdatedAt,
		); err != nil {
			return nil, 0, err
		}

		e.UserID = userID
		e.PositionID = positionID
		e.Price = price
		e.StopLoss = stopLoss
		e.TakeProfit = takeProfit
		e.FilledPrice = filledPrice
		e.FilledQty = filledQty
		e.OrderID = derefString(orderID)
		e.Ticket = derefString(ticket)
		e.ErrorMessage = derefString(errorMessage)
		e.RiskLevel = derefString(riskLevel)
		e.SubmittedAt = submittedAt
		e.FilledAt = filledAt
		e.CompletedAt = completedAt

		executions = append(executions, e)
	}

	return executions, total, nil
}

func (r *pgRepo) GetFilledExecutions(ctx context.Context, tenantID uuid.UUID) ([]*models.Execution, error) {
	rows, err := r.pool.Query(ctx, `
		SELECT id, tenant_id, signal_id, user_id, broker, account_id,
		       symbol, side, order_type, quantity, price, stop_loss, take_profit, take_profits,
		       order_id, ticket, filled_price, filled_qty, commission,
		       status, error_message, submitted_at, filled_at, completed_at,
		       position_id, risk_level, retry_count, created_at, updated_at
		FROM trading.executions
		WHERE tenant_id = $1 AND status = 'filled'
		ORDER BY filled_at DESC NULLS LAST
		LIMIT 100`, tenantID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var executions []*models.Execution
	for rows.Next() {
		e := &models.Execution{}
		var price, stopLoss, takeProfit, filledPrice, filledQty *float64
		var userID, positionID *uuid.UUID
		var orderID, ticket, errorMessage, riskLevel *string
		var submittedAt, filledAt, completedAt *time.Time

		if err := rows.Scan(
			&e.ID, &e.TenantID, &e.SignalID, &userID, &e.Broker, &e.AccountID,
			&e.Symbol, &e.Side, &e.OrderType, &e.Quantity, &price, &stopLoss, &takeProfit, &e.TakeProfits,
			&orderID, &ticket, &filledPrice, &filledQty, &e.Commission,
			&e.Status, &errorMessage, &submittedAt, &filledAt, &completedAt,
			&positionID, &riskLevel, &e.RetryCount, &e.CreatedAt, &e.UpdatedAt,
		); err != nil {
			continue
		}

		e.UserID = userID
		e.PositionID = positionID
		e.Price = price
		e.StopLoss = stopLoss
		e.TakeProfit = takeProfit
		e.FilledPrice = filledPrice
		e.FilledQty = filledQty
		e.OrderID = derefString(orderID)
		e.Ticket = derefString(ticket)
		e.ErrorMessage = derefString(errorMessage)
		e.RiskLevel = derefString(riskLevel)
		e.SubmittedAt = submittedAt
		e.FilledAt = filledAt
		e.CompletedAt = completedAt

		executions = append(executions, e)
	}

	return executions, nil
}

func (r *pgRepo) Stats(ctx context.Context, tenantID *uuid.UUID, since time.Time) (*models.StatsResponse, error) {
	stats := &models.StatsResponse{
		ByStatus: make(map[string]int64),
		ByBroker: make(map[string]int64),
	}

	whereSQL := "WHERE created_at >= $1"
	args := []any{since}
	if tenantID != nil {
		args = append(args, *tenantID)
		whereSQL += fmt.Sprintf(" AND tenant_id = $%d", len(args))
	}

	// By status
	rows, err := r.pool.Query(ctx, "SELECT status, COUNT(*) FROM trading.executions "+whereSQL+" GROUP BY status", args...)
	if err == nil {
		for rows.Next() {
			var status string
			var count int64
			if err := rows.Scan(&status, &count); err == nil {
				stats.ByStatus[status] = count
				stats.Total += count
				if models.ExecutionStatus(status) == models.ExecStatusFilled {
					stats.TotalFilled = count
				}
				if models.ExecutionStatus(status) == models.ExecStatusFailed {
					stats.TotalFailed = count
				}
			}
		}
		rows.Close()
	}

	// By broker
	rows2, err := r.pool.Query(ctx, "SELECT broker, COUNT(*) FROM trading.executions "+whereSQL+" GROUP BY broker", args...)
	if err == nil {
		for rows2.Next() {
			var broker string
			var count int64
			if err := rows2.Scan(&broker, &count); err == nil {
				stats.ByBroker[broker] = count
			}
		}
		rows2.Close()
	}

	// Last 24h
	var last24h int64
	r.pool.QueryRow(ctx, "SELECT COUNT(*) FROM trading.executions WHERE created_at >= NOW() - INTERVAL '24 hours'", ).Scan(&last24h)
	stats.Last24h = last24h

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