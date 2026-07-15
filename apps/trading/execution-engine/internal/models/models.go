// Package models define los modelos del execution-engine.
package models

import (
	"time"

	"github.com/google/uuid"
)

// ─── Enums ─────────────────────────────────────────────────────

// ExecutionStatus estado de la ejecución
type ExecutionStatus string

const (
	ExecStatusPending   ExecutionStatus = "pending"
	ExecStatusApproved  ExecutionStatus = "approved"
	ExecStatusRouted    ExecutionStatus = "routed"
	ExecStatusSubmitted ExecutionStatus = "submitted"
	ExecStatusFilled    ExecutionStatus = "filled"
	ExecStatusPartial   ExecutionStatus = "partial"
	ExecStatusRejected  ExecutionStatus = "rejected"
	ExecStatusCancelled ExecutionStatus = "cancelled"
	ExecStatusFailed    ExecutionStatus = "failed"
	ExecStatusExpired   ExecutionStatus = "expired"
)

// BrokerName nombre del broker
type BrokerName string

const (
	BrokerMT5     BrokerName = "mt5"
	BrokerCTrader BrokerName = "ctrader"
	BrokerBinance BrokerName = "binance"
	BrokerBybit   BrokerName = "bybit"
	BrokerIBKR    BrokerName = "ibkr"
)

// OrderSide lado de la orden
type OrderSide string

const (
	SideBuy  OrderSide = "buy"
	SideSell OrderSide = "sell"
)

// OrderType tipo de orden
type OrderType string

const (
	OrderMarket OrderType = "market"
	OrderLimit  OrderType = "limit"
	OrderStop   OrderType = "stop"
)

// ─── Execution ────────────────────────────────────────────────

// Execution representa una ejecución de orden
type Execution struct {
	ID              uuid.UUID      `json:"id"`
	TenantID        uuid.UUID      `json:"tenant_id"`
	SignalID        uuid.UUID      `json:"signal_id"`
	UserID          *uuid.UUID     `json:"user_id,omitempty"`

	// Trade params
	Broker    BrokerName `json:"broker"`
	AccountID string     `json:"account_id"`
	Symbol    string     `json:"symbol"`
	Side      OrderSide  `json:"side"`
	OrderType OrderType  `json:"order_type"`
	Quantity  float64    `json:"quantity"`
	Price     *float64   `json:"price,omitempty"`

	// SL / TP
	StopLoss   *float64 `json:"stop_loss,omitempty"`
	TakeProfit *float64 `json:"take_profit,omitempty"`
	TakeProfits []float64 `json:"take_profits,omitempty"`

	// Execution result
	OrderID      string         `json:"order_id,omitempty"` // broker-side ID
	Ticket       string         `json:"ticket,omitempty"`
	FilledPrice  *float64       `json:"filled_price,omitempty"`
	FilledQty    *float64       `json:"filled_qty,omitempty"`
	Commission   float64        `json:"commission"`
	Status       ExecutionStatus `json:"status"`
	ErrorMessage string         `json:"error_message,omitempty"`

	// Timing
	SubmittedAt *time.Time `json:"submitted_at,omitempty"`
	FilledAt    *time.Time `json:"filled_at,omitempty"`
	CompletedAt *time.Time `json:"completed_at,omitempty"`

	// Risk integration
	PositionID *uuid.UUID `json:"position_id,omitempty"`
	RiskLevel   string     `json:"risk_level,omitempty"`

	// Audit
	RetryCount int       `json:"retry_count"`
	CreatedAt  time.Time `json:"created_at"`
	UpdatedAt  time.Time `json:"updated_at"`
}

// ─── Signal Input (from NATS) ─────────────────────────────────

// SignalInput señal que llega desde NATS
type SignalInput struct {
	ID          uuid.UUID  `json:"id"`
	TenantID    uuid.UUID  `json:"tenant_id"`
	UserID      *uuid.UUID `json:"user_id,omitempty"`
	Source      string     `json:"source"`
	Symbol      string     `json:"symbol"`
	Action      string     `json:"action"` // BUY/SELL/CLOSE
	EntryPrice  *float64   `json:"entry_price,omitempty"`
	StopLoss    *float64   `json:"stop_loss,omitempty"`
	TakeProfits []float64  `json:"take_profits,omitempty"`
	LotSize     *float64   `json:"lot_size,omitempty"`
	LotMode     string     `json:"lot_mode,omitempty"`
	RiskPercent *float64   `json:"risk_percent,omitempty"`
	Confidence  float64    `json:"confidence"`
	Hash        string     `json:"hash"`

	// Risk evaluation (si pasó por risk-engine)
	RecommendedLotSize *float64 `json:"recommended_lot_size,omitempty"`
	RiskLevel          string   `json:"risk_level,omitempty"`
}

// ─── Request DTOs ──────────────────────────────────────────────

// ExecuteRequest DTO
type ExecuteRequest struct {
	Signal SignalInput `json:"signal"`
	Broker string      `json:"broker,omitempty"` // override default broker
	AccountID string   `json:"account_id,omitempty"`
	DryRun   bool     `json:"dry_run,omitempty"` // no ejecutar realmente
}

// CancelRequest DTO
type CancelRequest struct {
	Reason string `json:"reason"`
}

// StatsResponse DTO
type StatsResponse struct {
	Total       int64            `json:"total"`
	ByStatus    map[string]int64 `json:"by_status"`
	ByBroker    map[string]int64 `json:"by_broker"`
	TotalFilled int64            `json:"total_filled"`
	TotalFailed int64            `json:"total_failed"`
	Last24h     int64            `json:"last_24h"`
}

// ListResponse paginada
type ListResponse struct {
	Executions []*Execution `json:"executions"`
	Total      int64        `json:"total"`
	Limit      int          `json:"limit"`
	Offset     int          `json:"offset"`
}