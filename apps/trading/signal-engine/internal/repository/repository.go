// Package repository maneja la persistencia de signals.
package repository

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/tnsvt/signal-engine/internal/models"
)

// ErrNotFound cuando no se encuentra
var ErrNotFound = errors.New("signal not found")

// ErrDuplicate cuando ya existe
var ErrDuplicate = errors.New("signal duplicate")

// SignalRepository interfaz
type SignalRepository interface {
	Create(ctx context.Context, s *models.Signal) error
	GetByID(ctx context.Context, id uuid.UUID) (*models.Signal, error)
	GetByHash(ctx context.Context, hash string) (*models.Signal, error)
	Update(ctx context.Context, s *models.Signal) error
	UpdateStatus(ctx context.Context, id uuid.UUID, status models.Status, reason models.RejectReason, details string) error
	List(ctx context.Context, tenantID *uuid.UUID, limit, offset int) ([]*models.Signal, int64, error)
	Stats(ctx context.Context, tenantID *uuid.UUID, since time.Time) (*models.StatsResponse, error)
	RunMigrations(ctx context.Context) error
	Ping(ctx context.Context) error
}

// ─── PostgreSQL ────────────────────────────────────────────────

type pgRepo struct {
	pool *pgxpool.Pool
}

// NewSignalRepository crea un nuevo repository
func NewSignalRepository(pool *pgxpool.Pool, _ interface{}) SignalRepository {
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
			name: "create_signals_table",
			sql: `CREATE TABLE IF NOT EXISTS trading.signals (
				id UUID PRIMARY KEY,
				tenant_id UUID NOT NULL,
				user_id UUID,
				source VARCHAR(20) NOT NULL,
				source_id VARCHAR(100),
				raw_text TEXT,
				symbol VARCHAR(20) NOT NULL,
				action VARCHAR(20) NOT NULL,
				entry_price NUMERIC(20, 8),
				stop_loss NUMERIC(20, 8),
				take_profits NUMERIC(20, 8)[],
				lot_size NUMERIC(10, 4),
				lot_mode VARCHAR(20) DEFAULT 'fixed',
				risk_percent NUMERIC(5, 2),
				comment TEXT,
				confidence NUMERIC(4, 3) DEFAULT 0,
				status VARCHAR(20) NOT NULL DEFAULT 'received',
				reject_reason VARCHAR(50),
				reject_details TEXT,
				hash VARCHAR(64) NOT NULL,
				channel_id UUID,
				received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
				validated_at TIMESTAMPTZ,
				expires_at TIMESTAMPTZ,
				routed_at TIMESTAMPTZ
			)`,
		},
		{
			name: "create_channels_table",
			sql: `CREATE TABLE IF NOT EXISTS trading.channels (
				id UUID PRIMARY KEY,
				name VARCHAR(100) NOT NULL,
				telegram_id BIGINT UNIQUE NOT NULL,
				telegram_slug VARCHAR(100),
				enabled BOOLEAN NOT NULL DEFAULT TRUE,
				trusted BOOLEAN NOT NULL DEFAULT FALSE,
				min_confidence NUMERIC(4, 3) DEFAULT 0,
				allowed_actions VARCHAR(20)[] DEFAULT ARRAY['BUY','SELL','CLOSE'],
				created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
			)`,
		},
		{
			name: "create_signals_indexes",
			sql: `CREATE INDEX IF NOT EXISTS idx_signals_tenant ON trading.signals(tenant_id);
				  CREATE INDEX IF NOT EXISTS idx_signals_status ON trading.signals(status);
				  CREATE INDEX IF NOT EXISTS idx_signals_hash ON trading.signals(hash);
				  CREATE INDEX IF NOT EXISTS idx_signals_symbol ON trading.signals(symbol);
				  CREATE INDEX IF NOT EXISTS idx_signals_received ON trading.signals(received_at DESC);
				  CREATE INDEX IF NOT EXISTS idx_signals_source ON trading.signals(source)`,
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

func (r *pgRepo) Create(ctx context.Context, s *models.Signal) error {
	if s.ID == uuid.Nil {
		s.ID = uuid.New()
	}

	_, err := r.pool.Exec(ctx, `
		INSERT INTO trading.signals (
			id, tenant_id, user_id, source, source_id, raw_text,
			symbol, action, entry_price, stop_loss, take_profits,
			lot_size, lot_mode, risk_percent, comment, confidence,
			status, reject_reason, reject_details, hash, channel_id,
			received_at, validated_at, expires_at, routed_at
		) VALUES (
			$1, $2, $3, $4, $5, $6,
			$7, $8, $9, $10, $11,
			$12, $13, $14, $15, $16,
			$17, $18, $19, $20, $21,
			$22, $23, $24, $25
		)`,
		s.ID, s.TenantID, s.UserID, s.Source, nullString(s.SourceID), nullString(s.RawText),
		s.Symbol, s.Action, float64Ptr(s.EntryPrice), float64Ptr(s.StopLoss), s.TakeProfits,
		float64Ptr(s.LotSize), nullString(s.LotMode), float64Ptr(s.RiskPercent), nullString(s.Comment), s.Confidence,
		s.Status, nullString(string(s.RejectReason)), nullString(s.RejectDetails), s.Hash, s.ChannelID,
		s.ReceivedAt, s.ValidatedAt, s.ExpiresAt, s.RoutedAt,
	)

	return err
}

func (r *pgRepo) GetByID(ctx context.Context, id uuid.UUID) (*models.Signal, error) {
	s := &models.Signal{}
	var entryPrice, stopLoss, lotSize, riskPercent, confidence *float64
	var validatedAt, expiresAt, routedAt *time.Time

	err := r.pool.QueryRow(ctx, `
		SELECT id, tenant_id, user_id, source, COALESCE(source_id, ''), COALESCE(raw_text, ''),
		       symbol, action, entry_price, stop_loss, take_profits,
		       lot_size, COALESCE(lot_mode, 'fixed'), risk_percent, COALESCE(comment, ''), confidence,
		       status, COALESCE(reject_reason, ''), COALESCE(reject_details, ''), hash, channel_id,
		       received_at, validated_at, expires_at, routed_at
		FROM trading.signals WHERE id = $1`, id).Scan(
		&s.ID, &s.TenantID, &s.UserID, &s.Source, &s.SourceID, &s.RawText,
		&s.Symbol, &s.Action, &entryPrice, &stopLoss, &s.TakeProfits,
		&lotSize, &s.LotMode, &riskPercent, &s.Comment, &confidence,
		&s.Status, &s.RejectReason, &s.RejectDetails, &s.Hash, &s.ChannelID,
		&s.ReceivedAt, &validatedAt, &expiresAt, &routedAt,
	)

	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, ErrNotFound
		}
		return nil, err
	}

	s.EntryPrice = entryPrice
	s.StopLoss = stopLoss
	s.LotSize = lotSize
	s.RiskPercent = riskPercent
	s.Confidence = derefFloat(confidence)
	s.ValidatedAt = validatedAt
	s.ExpiresAt = expiresAt
	s.RoutedAt = routedAt

	return s, nil
}

func (r *pgRepo) GetByHash(ctx context.Context, hash string) (*models.Signal, error) {
	var id uuid.UUID
	err := r.pool.QueryRow(ctx, `SELECT id FROM trading.signals WHERE hash = $1 LIMIT 1`, hash).Scan(&id)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, ErrNotFound
		}
		return nil, err
	}
	return r.GetByID(ctx, id)
}

func (r *pgRepo) Update(ctx context.Context, s *models.Signal) error {
	_, err := r.pool.Exec(ctx, `
		UPDATE trading.signals SET
			status = $2,
			reject_reason = $3,
			reject_details = $4,
			validated_at = $5,
			expires_at = $6,
			routed_at = $7,
			confidence = $8
		WHERE id = $1`,
		s.ID, s.Status, nullString(string(s.RejectReason)), nullString(s.RejectDetails),
		s.ValidatedAt, s.ExpiresAt, s.RoutedAt, s.Confidence,
	)
	return err
}

func (r *pgRepo) UpdateStatus(ctx context.Context, id uuid.UUID, status models.Status, reason models.RejectReason, details string) error {
	_, err := r.pool.Exec(ctx, `
		UPDATE trading.signals SET
			status = $2,
			reject_reason = $3,
			reject_details = $4,
			validated_at = CASE WHEN $2 IN ('validated', 'routed', 'executed') THEN NOW() ELSE validated_at END,
			routed_at = CASE WHEN $2 IN ('routed', 'executed') THEN NOW() ELSE routed_at END
		WHERE id = $1`,
		id, status, nullString(string(reason)), nullString(details),
	)
	return err
}

func (r *pgRepo) List(ctx context.Context, tenantID *uuid.UUID, limit, offset int) ([]*models.Signal, int64, error) {
	if limit <= 0 || limit > 100 {
		limit = 20
	}

	// Count
	var total int64
	countQuery := `SELECT COUNT(*) FROM trading.signals`
	args := []any{}
	if tenantID != nil {
		countQuery += ` WHERE tenant_id = $1`
		args = append(args, *tenantID)
	}
	if err := r.pool.QueryRow(ctx, countQuery, args...).Scan(&total); err != nil {
		return nil, 0, err
	}

	// List
	listQuery := `
		SELECT id, tenant_id, user_id, source, COALESCE(source_id, ''), COALESCE(raw_text, ''),
		       symbol, action, entry_price, stop_loss, take_profits,
		       lot_size, COALESCE(lot_mode, 'fixed'), risk_percent, COALESCE(comment, ''), confidence,
		       status, COALESCE(reject_reason, ''), COALESCE(reject_details, ''), hash, channel_id,
		       received_at, validated_at, expires_at, routed_at
		FROM trading.signals`

	if tenantID != nil {
		listQuery += ` WHERE tenant_id = $1`
	}
	listQuery += ` ORDER BY received_at DESC LIMIT $` + fmt.Sprint(len(args)+1) + ` OFFSET $` + fmt.Sprint(len(args)+2)
	args = append(args, limit, offset)

	rows, err := r.pool.Query(ctx, listQuery, args...)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()

	var signals []*models.Signal
	for rows.Next() {
		s := &models.Signal{}
		var entryPrice, stopLoss, lotSize, riskPercent, confidence *float64
		var validatedAt, expiresAt, routedAt *time.Time

		if err := rows.Scan(
			&s.ID, &s.TenantID, &s.UserID, &s.Source, &s.SourceID, &s.RawText,
			&s.Symbol, &s.Action, &entryPrice, &stopLoss, &s.TakeProfits,
			&lotSize, &s.LotMode, &riskPercent, &s.Comment, &confidence,
			&s.Status, &s.RejectReason, &s.RejectDetails, &s.Hash, &s.ChannelID,
			&s.ReceivedAt, &validatedAt, &expiresAt, &routedAt,
		); err != nil {
			return nil, 0, err
		}

		s.EntryPrice = entryPrice
		s.StopLoss = stopLoss
		s.LotSize = lotSize
		s.RiskPercent = riskPercent
		s.Confidence = derefFloat(confidence)
		s.ValidatedAt = validatedAt
		s.ExpiresAt = expiresAt
		s.RoutedAt = routedAt

		signals = append(signals, s)
	}

	return signals, total, nil
}

func (r *pgRepo) Stats(ctx context.Context, tenantID *uuid.UUID, since time.Time) (*models.StatsResponse, error) {
	stats := &models.StatsResponse{
		RejectionReasons: make(map[string]int64),
		TopSymbols:       make(map[string]int64),
		BySource:         make(map[string]int64),
	}

	whereClause := ""
	args := []any{since}
	if tenantID != nil {
		whereClause = " AND tenant_id = $2"
		args = append(args, *tenantID)
	}

	// Status counts
	rows, err := r.pool.Query(ctx, `
		SELECT status, COUNT(*) FROM trading.signals
		WHERE received_at >= $1`+whereClause+`
		GROUP BY status`, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	for rows.Next() {
		var status string
		var count int64
		if err := rows.Scan(&status, &count); err != nil {
			continue
		}
		switch models.Status(status) {
		case models.StatusReceived:
			stats.TotalReceived += count
		case models.StatusValidated:
			stats.TotalValidated += count
		case models.StatusRejected:
			stats.TotalRejected += count
		case models.StatusRouted:
			stats.TotalRouted += count
		case models.StatusExecuted:
			stats.TotalExecuted += count
		}
	}

	// Rejection reasons
	rows2, err := r.pool.Query(ctx, `
		SELECT COALESCE(reject_reason, 'unknown'), COUNT(*)
		FROM trading.signals
		WHERE status = 'rejected' AND received_at >= $1`+whereClause+`
		GROUP BY reject_reason`, args...)
	if err == nil {
		defer rows2.Close()
		for rows2.Next() {
			var reason string
			var count int64
			if err := rows2.Scan(&reason, &count); err == nil {
				stats.RejectionReasons[reason] = count
			}
		}
	}

	// Top symbols
	rows3, err := r.pool.Query(ctx, `
		SELECT symbol, COUNT(*) as c FROM trading.signals
		WHERE received_at >= $1`+whereClause+`
		GROUP BY symbol ORDER BY c DESC LIMIT 10`, args...)
	if err == nil {
		defer rows3.Close()
		for rows3.Next() {
			var symbol string
			var count int64
			if err := rows3.Scan(&symbol, &count); err == nil {
				stats.TopSymbols[symbol] = count
			}
		}
	}

	// By source
	rows4, err := r.pool.Query(ctx, `
		SELECT source, COUNT(*) FROM trading.signals
		WHERE received_at >= $1`+whereClause+`
		GROUP BY source`, args...)
	if err == nil {
		defer rows4.Close()
		for rows4.Next() {
			var source string
			var count int64
			if err := rows4.Scan(&source, &count); err == nil {
				stats.BySource[source] = count
			}
		}
	}

	stats.Period = "since_" + since.Format("2006-01-02")
	return stats, nil
}

// ─── Helpers ───────────────────────────────────────────────────

func nullString(s string) any {
	if s == "" {
		return nil
	}
	return s
}

func float64Ptr(p *float64) any {
	if p == nil {
		return nil
	}
	return *p
}

func derefFloat(p *float64) float64 {
	if p == nil {
		return 0
	}
	return *p
}