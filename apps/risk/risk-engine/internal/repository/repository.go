// Package repository maneja la persistencia del risk-engine.
package repository

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/tnsvt/risk-engine/internal/models"
)

// ErrNotFound not found
var ErrNotFound = errors.New("not found")

// RiskRepository interfaz
type RiskRepository interface {
	// Limits
	GetLimits(ctx context.Context, tenantID uuid.UUID) (*models.RiskLimits, error)
	UpsertLimits(ctx context.Context, limits *models.RiskLimits) error

	// Positions
	CreatePosition(ctx context.Context, p *models.Position) error
	UpdatePosition(ctx context.Context, p *models.Position) error
	GetPositionByID(ctx context.Context, id uuid.UUID) (*models.Position, error)
	GetPositionByTicket(ctx context.Context, ticket string) (*models.Position, error)
	ListOpenPositions(ctx context.Context, tenantID uuid.UUID) ([]*models.Position, error)
	ClosePosition(ctx context.Context, id uuid.UUID, pnl float64, closeReason string) error
	UpdatePositionPrice(ctx context.Context, id uuid.UUID, currentPrice, unrealizedPnL, pnlPercent float64) error
	UpdateTrailingStop(ctx context.Context, id uuid.UUID, trailingActive bool, trailingSL float64) error

	// Stats
	GetDailyPnL(ctx context.Context, tenantID uuid.UUID, day time.Time) (float64, error)
	GetWeeklyPnL(ctx context.Context, tenantID uuid.UUID, weekStart time.Time) (float64, error)
	GetMonthlyPnL(ctx context.Context, tenantID uuid.UUID, monthStart time.Time) (float64, error)
	IncrementTradesOpened(ctx context.Context, tenantID uuid.UUID, day time.Time) error
	IncrementTradesClosed(ctx context.Context, tenantID uuid.UUID, day time.Time, won bool) error

	// Lifecycle
	RunMigrations(ctx context.Context) error
	Ping(ctx context.Context) error
}

// ─── PostgreSQL ────────────────────────────────────────────────

type pgRepo struct {
	pool *pgxpool.Pool
}

// NewRiskRepository crea el repo
func NewRiskRepository(pool *pgxpool.Pool, _ interface{}) RiskRepository {
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
			name: "create_risk_limits_table",
			sql: `CREATE TABLE IF NOT EXISTS risk.limits (
				tenant_id UUID PRIMARY KEY,
				daily_loss_limit NUMERIC(15, 2) NOT NULL DEFAULT 500,
				daily_profit_target NUMERIC(15, 2) NOT NULL DEFAULT 1000,
				weekly_loss_limit NUMERIC(15, 2) NOT NULL DEFAULT 1500,
				max_open_positions INTEGER NOT NULL DEFAULT 5,
				max_exposure_per_symbol NUMERIC(15, 2) NOT NULL DEFAULT 10000,
				max_drawdown_percent NUMERIC(5, 2) NOT NULL DEFAULT 20,
				min_confidence NUMERIC(4, 3) NOT NULL DEFAULT 0.3,
				trailing_stop BOOLEAN NOT NULL DEFAULT TRUE,
				trailing_step INTEGER NOT NULL DEFAULT 10,
				trailing_start INTEGER NOT NULL DEFAULT 20,
				updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
			)`,
		},
		{
			name: "create_risk_positions_table",
			sql: `CREATE TABLE IF NOT EXISTS risk.positions (
				id UUID PRIMARY KEY,
				tenant_id UUID NOT NULL,
				signal_id UUID NOT NULL,
				broker VARCHAR(50) NOT NULL,
				account_id VARCHAR(100) NOT NULL,
				ticket VARCHAR(100) UNIQUE,
				symbol VARCHAR(20) NOT NULL,
				side VARCHAR(10) NOT NULL,
				quantity NUMERIC(10, 4) NOT NULL,
				entry_price NUMERIC(20, 8) NOT NULL,
				current_price NUMERIC(20, 8) NOT NULL DEFAULT 0,
				stop_loss NUMERIC(20, 8),
				take_profit NUMERIC(20, 8),
				tp_side VARCHAR(10) DEFAULT 'tp1',
				unrealized_pnl NUMERIC(15, 2) NOT NULL DEFAULT 0,
				pnl_percent NUMERIC(8, 4) NOT NULL DEFAULT 0,
				trailing_active BOOLEAN NOT NULL DEFAULT FALSE,
				trailing_stop_loss NUMERIC(20, 8),
				opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
				updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
				closed BOOLEAN NOT NULL DEFAULT FALSE,
				closed_at TIMESTAMPTZ,
				closed_pnl NUMERIC(15, 2)
			)`,
		},
		{
			name: "create_risk_daily_stats_table",
			sql: `CREATE TABLE IF NOT EXISTS risk.daily_stats (
				tenant_id UUID NOT NULL,
				day DATE NOT NULL,
				daily_pnl NUMERIC(15, 2) NOT NULL DEFAULT 0,
				trades_opened INTEGER NOT NULL DEFAULT 0,
				trades_closed INTEGER NOT NULL DEFAULT 0,
				trades_won INTEGER NOT NULL DEFAULT 0,
				trades_lost INTEGER NOT NULL DEFAULT 0,
				PRIMARY KEY (tenant_id, day)
			)`,
		},
		{
			name: "create_risk_indexes",
			sql: `CREATE INDEX IF NOT EXISTS idx_positions_tenant ON risk.positions(tenant_id);
				  CREATE INDEX IF NOT EXISTS idx_positions_open ON risk.positions(tenant_id, closed) WHERE closed = FALSE;
				  CREATE INDEX IF NOT EXISTS idx_positions_symbol ON risk.positions(tenant_id, symbol) WHERE closed = FALSE;
				  CREATE INDEX IF NOT EXISTS idx_daily_stats_day ON risk.daily_stats(day)`,
		},
	}

	for _, m := range migrations {
		if _, err := r.pool.Exec(ctx, m.sql); err != nil {
			return fmt.Errorf("migration %s failed: %w", m.name, err)
		}
	}

	return nil
}

// ─── Limits ────────────────────────────────────────────────────

func (r *pgRepo) GetLimits(ctx context.Context, tenantID uuid.UUID) (*models.RiskLimits, error) {
	l := &models.RiskLimits{}
	err := r.pool.QueryRow(ctx, `
		SELECT tenant_id, daily_loss_limit, daily_profit_target, weekly_loss_limit,
		       max_open_positions, max_exposure_per_symbol, max_drawdown_percent,
		       min_confidence, trailing_stop, trailing_step, trailing_start, updated_at
		FROM risk.limits WHERE tenant_id = $1`, tenantID).
		Scan(&l.TenantID, &l.DailyLossLimit, &l.DailyProfitTarget, &l.WeeklyLossLimit,
			&l.MaxOpenPositions, &l.MaxExposurePerSymbol, &l.MaxDrawdownPercent,
			&l.MinConfidence, &l.TrailingStop, &l.TrailingStep, &l.TrailingStart, &l.UpdatedAt)

	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			// Crear defaults
			l = &models.RiskLimits{
				TenantID:             tenantID,
				DailyLossLimit:       500,
				DailyProfitTarget:    1000,
				WeeklyLossLimit:      1500,
				MaxOpenPositions:     5,
				MaxExposurePerSymbol: 10000,
				MaxDrawdownPercent:   20,
				MinConfidence:        0.3,
				TrailingStop:         true,
				TrailingStep:         10,
				TrailingStart:        20,
				UpdatedAt:            time.Now(),
			}
			if err := r.UpsertLimits(ctx, l); err != nil {
				return nil, err
			}
			return l, nil
		}
		return nil, err
	}
	return l, nil
}

func (r *pgRepo) UpsertLimits(ctx context.Context, l *models.RiskLimits) error {
	l.UpdatedAt = time.Now()
	_, err := r.pool.Exec(ctx, `
		INSERT INTO risk.limits (
			tenant_id, daily_loss_limit, daily_profit_target, weekly_loss_limit,
			max_open_positions, max_exposure_per_symbol, max_drawdown_percent,
			min_confidence, trailing_stop, trailing_step, trailing_start, updated_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
		ON CONFLICT (tenant_id) DO UPDATE SET
			daily_loss_limit = EXCLUDED.daily_loss_limit,
			daily_profit_target = EXCLUDED.daily_profit_target,
			weekly_loss_limit = EXCLUDED.weekly_loss_limit,
			max_open_positions = EXCLUDED.max_open_positions,
			max_exposure_per_symbol = EXCLUDED.max_exposure_per_symbol,
			max_drawdown_percent = EXCLUDED.max_drawdown_percent,
			min_confidence = EXCLUDED.min_confidence,
			trailing_stop = EXCLUDED.trailing_stop,
			trailing_step = EXCLUDED.trailing_step,
			trailing_start = EXCLUDED.trailing_start,
			updated_at = NOW()`,
		l.TenantID, l.DailyLossLimit, l.DailyProfitTarget, l.WeeklyLossLimit,
		l.MaxOpenPositions, l.MaxExposurePerSymbol, l.MaxDrawdownPercent,
		l.MinConfidence, l.TrailingStop, l.TrailingStep, l.TrailingStart, l.UpdatedAt,
	)
	return err
}

// ─── Positions ─────────────────────────────────────────────────

func (r *pgRepo) CreatePosition(ctx context.Context, p *models.Position) error {
	if p.ID == uuid.Nil {
		p.ID = uuid.New()
	}
	p.OpenedAt = time.Now()
	p.UpdatedAt = time.Now()

	_, err := r.pool.Exec(ctx, `
		INSERT INTO risk.positions (
			id, tenant_id, signal_id, broker, account_id, ticket,
			symbol, side, quantity, entry_price, current_price,
			stop_loss, take_profit, tp_side, unrealized_pnl, pnl_percent,
			trailing_active, trailing_stop_loss, opened_at, updated_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20)`,
		p.ID, p.TenantID, p.SignalID, p.Broker, p.AccountID, p.Ticket,
		p.Symbol, p.Side, p.Quantity, p.EntryPrice, p.EntryPrice,
		p.StopLoss, p.TakeProfit, p.TPSide, 0, 0,
		false, p.StopLoss, p.OpenedAt, p.UpdatedAt,
	)
	return err
}

func (r *pgRepo) UpdatePosition(ctx context.Context, p *models.Position) error {
	p.UpdatedAt = time.Now()
	_, err := r.pool.Exec(ctx, `
		UPDATE risk.positions SET
			current_price = $2, unrealized_pnl = $3, pnl_percent = $4,
			stop_loss = $5, take_profit = $6, trailing_active = $7,
			trailing_stop_loss = $8, updated_at = $9
		WHERE id = $1`,
		p.ID, p.CurrentPrice, p.UnrealizedPnL, p.PnLPercent,
		p.StopLoss, p.TakeProfit, p.TrailingActive, p.TrailingStopLoss, p.UpdatedAt,
	)
	return err
}

func (r *pgRepo) GetPositionByID(ctx context.Context, id uuid.UUID) (*models.Position, error) {
	return r.scanSinglePosition(ctx, "id", id)
}

func (r *pgRepo) GetPositionByTicket(ctx context.Context, ticket string) (*models.Position, error) {
	return r.scanSinglePosition(ctx, "ticket", ticket)
}

func (r *pgRepo) scanSinglePosition(ctx context.Context, field string, value any) (*models.Position, error) {
	p := &models.Position{}
	var closedAt *time.Time
	var closedPnL *float64
	var trailingSL *float64

	query := fmt.Sprintf(`
		SELECT id, tenant_id, signal_id, broker, account_id, COALESCE(ticket, ''),
		       symbol, side, quantity, entry_price, current_price,
		       COALESCE(stop_loss, 0), COALESCE(take_profit, 0), COALESCE(tp_side, 'tp1'),
		       unrealized_pnl, pnl_percent, trailing_active, trailing_stop_loss,
		       opened_at, updated_at, closed, closed_at, closed_pnl
		FROM risk.positions WHERE %s = $1`, field)

	err := r.pool.QueryRow(ctx, query, value).Scan(
		&p.ID, &p.TenantID, &p.SignalID, &p.Broker, &p.AccountID, &p.Ticket,
		&p.Symbol, &p.Side, &p.Quantity, &p.EntryPrice, &p.CurrentPrice,
		&p.StopLoss, &p.TakeProfit, &p.TPSide,
		&p.UnrealizedPnL, &p.PnLPercent, &p.TrailingActive, &trailingSL,
		&p.OpenedAt, &p.UpdatedAt, &p.Closed, &closedAt, &closedPnL,
	)

	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, ErrNotFound
		}
		return nil, err
	}

	p.TrailingStopLoss = derefFloat(trailingSL)
	p.ClosedAt = closedAt
	p.ClosedPnL = closedPnL
	return p, nil
}

func (r *pgRepo) ListOpenPositions(ctx context.Context, tenantID uuid.UUID) ([]*models.Position, error) {
	rows, err := r.pool.Query(ctx, `
		SELECT id, tenant_id, signal_id, broker, account_id, COALESCE(ticket, ''),
		       symbol, side, quantity, entry_price, current_price,
		       COALESCE(stop_loss, 0), COALESCE(take_profit, 0), COALESCE(tp_side, 'tp1'),
		       unrealized_pnl, pnl_percent, trailing_active, trailing_stop_loss,
		       opened_at, updated_at, closed, closed_at, closed_pnl
		FROM risk.positions
		WHERE tenant_id = $1 AND closed = FALSE
		ORDER BY opened_at DESC`, tenantID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var positions []*models.Position
	for rows.Next() {
		p := &models.Position{}
		var closedAt *time.Time
		var closedPnL *float64
		var trailingSL *float64

		if err := rows.Scan(
			&p.ID, &p.TenantID, &p.SignalID, &p.Broker, &p.AccountID, &p.Ticket,
			&p.Symbol, &p.Side, &p.Quantity, &p.EntryPrice, &p.CurrentPrice,
			&p.StopLoss, &p.TakeProfit, &p.TPSide,
			&p.UnrealizedPnL, &p.PnLPercent, &p.TrailingActive, &trailingSL,
			&p.OpenedAt, &p.UpdatedAt, &p.Closed, &closedAt, &closedPnL,
		); err != nil {
			return nil, err
		}
		p.TrailingStopLoss = derefFloat(trailingSL)
		p.ClosedAt = closedAt
		p.ClosedPnL = closedPnL
		positions = append(positions, p)
	}

	return positions, nil
}

func (r *pgRepo) ClosePosition(ctx context.Context, id uuid.UUID, pnl float64, closeReason string) error {
	now := time.Now()
	_, err := r.pool.Exec(ctx, `
		UPDATE risk.positions SET
			closed = TRUE, closed_at = $2, closed_pnl = $3,
			updated_at = $2
		WHERE id = $1`, id, now, pnl)
	return err
}

func (r *pgRepo) UpdatePositionPrice(ctx context.Context, id uuid.UUID, currentPrice, unrealizedPnL, pnlPercent float64) error {
	_, err := r.pool.Exec(ctx, `
		UPDATE risk.positions SET
			current_price = $2, unrealized_pnl = $3, pnl_percent = $4, updated_at = NOW()
		WHERE id = $1`, id, currentPrice, unrealizedPnL, pnlPercent)
	return err
}

func (r *pgRepo) UpdateTrailingStop(ctx context.Context, id uuid.UUID, trailingActive bool, trailingSL float64) error {
	_, err := r.pool.Exec(ctx, `
		UPDATE risk.positions SET
			trailing_active = $2, trailing_stop_loss = $3, stop_loss = $3, updated_at = NOW()
		WHERE id = $1`, id, trailingActive, trailingSL)
	return err
}

// ─── Daily Stats ───────────────────────────────────────────────

func (r *pgRepo) GetDailyPnL(ctx context.Context, tenantID uuid.UUID, day time.Time) (float64, error) {
	dayStr := day.Format("2006-01-02")
	var pnl float64
	err := r.pool.QueryRow(ctx,
		`SELECT COALESCE(daily_pnl, 0) FROM risk.daily_stats WHERE tenant_id = $1 AND day = $2`,
		tenantID, dayStr).Scan(&pnl)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return 0, nil
		}
		return 0, err
	}
	return pnl, nil
}

func (r *pgRepo) GetWeeklyPnL(ctx context.Context, tenantID uuid.UUID, weekStart time.Time) (float64, error) {
	var pnl float64
	err := r.pool.QueryRow(ctx,
		`SELECT COALESCE(SUM(daily_pnl), 0) FROM risk.daily_stats WHERE tenant_id = $1 AND day >= $2`,
		tenantID, weekStart.Format("2006-01-02")).Scan(&pnl)
	if err != nil {
		return 0, err
	}
	return pnl, nil
}

func (r *pgRepo) GetMonthlyPnL(ctx context.Context, tenantID uuid.UUID, monthStart time.Time) (float64, error) {
	var pnl float64
	err := r.pool.QueryRow(ctx,
		`SELECT COALESCE(SUM(daily_pnl), 0) FROM risk.daily_stats WHERE tenant_id = $1 AND day >= $2`,
		tenantID, monthStart.Format("2006-01-02")).Scan(&pnl)
	if err != nil {
		return 0, err
	}
	return pnl, nil
}

func (r *pgRepo) IncrementTradesOpened(ctx context.Context, tenantID uuid.UUID, day time.Time) error {
	dayStr := day.Format("2006-01-02")
	_, err := r.pool.Exec(ctx, `
		INSERT INTO risk.daily_stats (tenant_id, day, trades_opened)
		VALUES ($1, $2, 1)
		ON CONFLICT (tenant_id, day) DO UPDATE SET trades_opened = risk.daily_stats.trades_opened + 1`,
		tenantID, dayStr)
	return err
}

func (r *pgRepo) IncrementTradesClosed(ctx context.Context, tenantID uuid.UUID, day time.Time, won bool) error {
	dayStr := day.Format("2006-01-02")
	wonInc := 0
	lostInc := 0
	if won {
		wonInc = 1
	} else {
		lostInc = 1
	}
	_, err := r.pool.Exec(ctx, `
		INSERT INTO risk.daily_stats (tenant_id, day, trades_closed, trades_won, trades_lost)
		VALUES ($1, $2, 1, $3, $4)
		ON CONFLICT (tenant_id, day) DO UPDATE SET
			trades_closed = risk.daily_stats.trades_closed + 1,
			trades_won = risk.daily_stats.trades_won + $3,
			trades_lost = risk.daily_stats.trades_lost + $4`,
		tenantID, dayStr, wonInc, lostInc)
	return err
}

// ─── Helpers ───────────────────────────────────────────────────

func derefFloat(p *float64) float64 {
	if p == nil {
		return 0
	}
	return *p
}