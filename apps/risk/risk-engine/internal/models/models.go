// Package models define los modelos del risk-engine.
package models

import (
	"time"

	"github.com/google/uuid"
)

// ─── Risk Level ────────────────────────────────────────────────

// RiskLevel nivel de riesgo de una operación
type RiskLevel string

const (
	RiskLevelLow      RiskLevel = "low"
	RiskLevelMedium   RiskLevel = "medium"
	RiskLevelHigh     RiskLevel = "high"
	RiskLevelCritical RiskLevel = "critical"
)

// ─── Risk Decision ─────────────────────────────────────────────

// Decision decisión sobre una señal
type Decision string

const (
	DecisionApproved Decision = "approved"
	DecisionRejected Decision = "rejected"
)

// ─── Reject Reason ─────────────────────────────────────────────

// RejectReason razón de rechazo del risk check
type RejectReason string

const (
	RejectDailyLossLimit      RejectReason = "daily_loss_limit"
	RejectWeeklyLossLimit     RejectReason = "weekly_loss_limit"
	RejectDailyProfitTarget   RejectReason = "daily_profit_target_reached"
	RejectMaxOpenPositions    RejectReason = "max_open_positions"
	RejectMaxExposurePerSymbol RejectReason = "max_exposure_per_symbol"
	RejectDrawdownLimit       RejectReason = "drawdown_limit"
	RejectLowConfidence       RejectReason = "low_confidence"
	RejectDisabledStrategy    RejectReason = "strategy_disabled"
)

// ─── Risk Limits ───────────────────────────────────────────────

// RiskLimits límites configurables por tenant
type RiskLimits struct {
	TenantID            uuid.UUID `json:"tenant_id"`
	DailyLossLimit      float64   `json:"daily_loss_limit"`
	DailyProfitTarget   float64   `json:"daily_profit_target"`
	WeeklyLossLimit     float64   `json:"weekly_loss_limit"`
	MaxOpenPositions    int       `json:"max_open_positions"`
	MaxExposurePerSymbol float64  `json:"max_exposure_per_symbol"` // En USD
	MaxDrawdownPercent  float64   `json:"max_drawdown_percent"`
	MinConfidence       float64   `json:"min_confidence"`
	TrailingStop        bool      `json:"trailing_stop"`
	TrailingStep        int       `json:"trailing_step"` // pips
	TrailingStart       int       `json:"trailing_start"` // pips (activar trailing después de N pips profit)
	UpdatedAt           time.Time `json:"updated_at"`
}

// ─── Risk Evaluation ───────────────────────────────────────────

// RiskEvaluation resultado de evaluar una señal
type RiskEvaluation struct {
	SignalID          uuid.UUID  `json:"signal_id"`
	TenantID          uuid.UUID  `json:"tenant_id"`
	Decision          Decision   `json:"decision"`
	RiskLevel         RiskLevel  `json:"risk_level"`
	Reason            string     `json:"reason,omitempty"`
	RejectReason      RejectReason `json:"reject_reason,omitempty"`

	// Ajustes sugeridos
	OriginalLotSize   *float64 `json:"original_lot_size,omitempty"`
	RecommendedLotSize *float64 `json:"recommended_lot_size,omitempty"`

	// Estado actual
	CurrentDailyPnL    float64 `json:"current_daily_pnl"`
	CurrentWeeklyPnL   float64 `json:"current_weekly_pnl"`
	CurrentDrawdown    float64 `json:"current_drawdown_percent"`
	OpenPositionsCount int     `json:"open_positions_count"`
	ExposurePerSymbol  map[string]float64 `json:"exposure_per_symbol"`

	Warnings []string `json:"warnings,omitempty"`
	EvaluatedAt time.Time `json:"evaluated_at"`
}

// ─── Position ──────────────────────────────────────────────────

// Position posición abierta
type Position struct {
	ID         uuid.UUID `json:"id"`
	TenantID   uuid.UUID `json:"tenant_id"`
	SignalID   uuid.UUID `json:"signal_id"`
	Broker     string    `json:"broker"`
	AccountID  string    `json:"account_id"`
	Ticket     string    `json:"ticket"`
	Symbol     string    `json:"symbol"`
	Side       string    `json:"side"` // "buy" or "sell"
	Quantity   float64   `json:"quantity"`
	EntryPrice float64   `json:"entry_price"`
	CurrentPrice float64 `json:"current_price"`
	StopLoss   float64   `json:"stop_loss"`
	TakeProfit float64   `json:"take_profit"`
	TPSide     string    `json:"tp_side"` // "tp1", "tp2", etc.

	UnrealizedPnL float64 `json:"unrealized_pnl"`
	PnLPercent    float64 `json:"pnl_percent"`

	// Trailing stop
	TrailingActive   bool    `json:"trailing_active"`
	TrailingStopLoss float64 `json:"trailing_stop_loss"`

	OpenedAt time.Time `json:"opened_at"`
	UpdatedAt time.Time `json:"updated_at"`

	Closed   bool       `json:"closed"`
	ClosedAt *time.Time `json:"closed_at,omitempty"`
	ClosedPnL *float64  `json:"closed_pnl,omitempty"`
}

// ─── Daily Stats ───────────────────────────────────────────────

// DailyStats estadísticas diarias
type DailyStats struct {
	TenantID        uuid.UUID `json:"tenant_id"`
	Date            time.Time `json:"date"`
	DailyPnL        float64   `json:"daily_pnl"`
	WeeklyPnL       float64   `json:"weekly_pnl"`
	TradesOpened    int       `json:"trades_opened"`
	TradesClosed    int       `json:"trades_closed"`
	TradesWon       int       `json:"trades_won"`
	TradesLost      int       `json:"trades_lost"`
	WinRate         float64   `json:"win_rate"`
	OpenPositions   int       `json:"open_positions"`
	CurrentDrawdown float64   `json:"current_drawdown_percent"`
}

// ─── Signal Input (from NATS) ──────────────────────────────────

// SignalInput señal que llega desde NATS
type SignalInput struct {
	ID         uuid.UUID  `json:"id"`
	TenantID   uuid.UUID  `json:"tenant_id"`
	Source     string     `json:"source"`
	Symbol     string     `json:"symbol"`
	Action     string     `json:"action"`
	EntryPrice *float64   `json:"entry_price,omitempty"`
	StopLoss   *float64   `json:"stop_loss,omitempty"`
	TakeProfits []float64 `json:"take_profits,omitempty"`
	LotSize    *float64   `json:"lot_size,omitempty"`
	LotMode    string     `json:"lot_mode,omitempty"`
	RiskPercent *float64  `json:"risk_percent,omitempty"`
	Confidence float64    `json:"confidence"`
	Hash       string     `json:"hash"`
}

// ─── Request DTOs ──────────────────────────────────────────────

// EvaluateRequest DTO
type EvaluateRequest struct {
	Signal SignalInput `json:"signal"`
}

// UpdateLimitsRequest DTO
type UpdateLimitsRequest struct {
	DailyLossLimit      *float64 `json:"daily_loss_limit,omitempty"`
	DailyProfitTarget   *float64 `json:"daily_profit_target,omitempty"`
	WeeklyLossLimit     *float64 `json:"weekly_loss_limit,omitempty"`
	MaxOpenPositions    *int     `json:"max_open_positions,omitempty"`
	MaxExposurePerSymbol *float64 `json:"max_exposure_per_symbol,omitempty"`
	MaxDrawdownPercent  *float64 `json:"max_drawdown_percent,omitempty"`
	MinConfidence       *float64 `json:"min_confidence,omitempty"`
	TrailingStop        *bool    `json:"trailing_stop,omitempty"`
	TrailingStep        *int     `json:"trailing_step,omitempty"`
	TrailingStart       *int     `json:"trailing_start,omitempty"`
}

// TradeOpenedRequest DTO
type TradeOpenedRequest struct {
	SignalID   uuid.UUID `json:"signal_id"`
	Broker     string    `json:"broker"`
	AccountID  string    `json:"account_id"`
	Ticket     string    `json:"ticket"`
	Symbol     string    `json:"symbol"`
	Side       string    `json:"side"`
	Quantity   float64   `json:"quantity"`
	EntryPrice float64   `json:"entry_price"`
	StopLoss   float64   `json:"stop_loss"`
	TakeProfit float64   `json:"take_profit"`
	TPSide     string    `json:"tp_side,omitempty"`
}

// TradeClosedRequest DTO
type TradeClosedRequest struct {
	PositionID uuid.UUID `json:"position_id"`
	Ticket     string    `json:"ticket"`
	ExitPrice  float64   `json:"exit_price"`
	PnL        float64   `json:"pnl"`
	CloseReason string   `json:"close_reason"` // tp, sl, manual, signal
}

// UpdatePriceRequest DTO
type UpdatePriceRequest struct {
	PositionID uuid.UUID `json:"position_id"`
	CurrentPrice float64 `json:"current_price"`
}

// StatsResponse DTO
type StatsResponse struct {
	Daily          DailyStats   `json:"daily"`
	WeeklyPnL      float64      `json:"weekly_pnl"`
	MonthlyPnL     float64      `json:"monthly_pnl"`
	OpenPositions  []Position   `json:"open_positions"`
	Limits         RiskLimits   `json:"limits"`
}