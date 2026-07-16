// Package models define los modelos del copy-trading engine.
package models

import (
	"time"

	"github.com/google/uuid"
)

// ─── Enums ─────────────────────────────────────────────────────

// JobStatus estado de una réplica individual
type JobStatus string

const (
	JobPending   JobStatus = "pending"
	JobRunning   JobStatus = "running"
	JobSuccess   JobStatus = "success"
	JobFailed    JobStatus = "failed"
	JobSkipped   JobStatus = "skipped"
	JobCancelled JobStatus = "cancelled"
)

// LotMode modo de lot size
type LotMode string

const (
	LotModeFixed   LotMode = "fixed"        // usa el lot_size configurado
	LotModeProportional LotMode = "proportional" // escala del original (multiplier)
	LotModeRiskBased    LotMode = "risk_based"  // mismo % riesgo que original
)

// ─── CopyGroup ─────────────────────────────────────────────────

// CopyGroup agrupa cuentas que reciben la misma señal
type CopyGroup struct {
	ID          uuid.UUID `json:"id"`
	TenantID    uuid.UUID `json:"tenant_id"`
	Name        string    `json:"name"`
	Description string    `json:"description,omitempty"`
	Enabled     bool      `json:"enabled"`

	// Filtros opcionales
	Symbols    []string `json:"symbols,omitempty"`    // si vacío = todos
	Actions    []string `json:"actions,omitempty"`    // si vacío = todos
	MinConfidence float64 `json:"min_confidence"`

	// Stats (denormalizados)
	TotalAccounts int       `json:"total_accounts"`
	TotalJobs     int64     `json:"total_jobs"`
	SuccessRate   float64   `json:"success_rate"`
	CreatedAt     time.Time `json:"created_at"`
	UpdatedAt     time.Time `json:"updated_at"`
}

// ─── CopyAccount ───────────────────────────────────────────────

// CopyAccount configuración de una cuenta dentro de un grupo
type CopyAccount struct {
	ID        uuid.UUID `json:"id"`
	GroupID   uuid.UUID `json:"group_id"`
	TenantID  uuid.UUID `json:"tenant_id"`

	// Identificación de cuenta
	Name        string `json:"name"`
	Broker      string `json:"broker"`       // "mt5", "ctrader", etc
	AccountID   string `json:"account_id"`   // ID en el broker

	// Configuración específica
	Enabled        bool     `json:"enabled"`
	LotMode        LotMode  `json:"lot_mode"`
	LotSize        *float64 `json:"lot_size,omitempty"`        // para LotMode=fixed
	LotMultiplier  float64  `json:"lot_multiplier"`             // para LotMode=proportional
	RiskPercent    *float64 `json:"risk_percent,omitempty"`     // para LotMode=risk_based

	// SL/TP override (opcional, sobrescribe los de la señal)
	OverrideSL  bool    `json:"override_sl"`
	SLPips      float64 `json:"sl_pips,omitempty"`  // SL en pips desde entry
	OverrideTP  bool    `json:"override_tp"`
	TPPips      float64 `json:"tp_pips,omitempty"`  // TP en pips desde entry

	// Invertir dirección
	InvertSide bool `json:"invert_side"`

	// Symbol suffix (ej: .m, .pro, .raw)
	SymbolSuffix string `json:"symbol_suffix,omitempty"`

	// Stats
	TotalTrades int64     `json:"total_trades"`
	LastTradeAt  *time.Time `json:"last_trade_at,omitempty"`

	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
}

// ─── CopyJob ───────────────────────────────────────────────────

// CopyJob una réplica individual (signal → account)
type CopyJob struct {
	ID         uuid.UUID `json:"id"`
	TenantID   uuid.UUID `json:"tenant_id"`
	GroupID    uuid.UUID `json:"group_id"`
	AccountID  uuid.UUID `json:"account_id"`
	SignalID   uuid.UUID `json:"signal_id"`

	// Snapshot del signal original
	Symbol    string  `json:"symbol"`
	Action    string  `json:"action"`
	EntryPrice float64 `json:"entry_price"`
	StopLoss  float64 `json:"stop_loss"`
	TakeProfit float64 `json:"take_profit"`
	OriginalLotSize float64 `json:"original_lot_size"`

	// Config aplicada a esta cuenta
	AppliedLotSize  float64 `json:"applied_lot_size"`
	AppliedSL       float64 `json:"applied_sl"`
	AppliedTP       float64 `json:"applied_tp"`
	AppliedSide     string  `json:"applied_side"`
	AppliedSymbol   string  `json:"applied_symbol"` // con suffix

	// Resultado
	Status        JobStatus `json:"status"`
	ExecutionID   *uuid.UUID `json:"execution_id,omitempty"` // del execution-engine
	ErrorMessage  string    `json:"error_message,omitempty"`
	RetryCount    int       `json:"retry_count"`
	StartedAt     *time.Time `json:"started_at,omitempty"`
	CompletedAt   *time.Time `json:"completed_at,omitempty"`
	DurationMs    int64     `json:"duration_ms"`

	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
}

// ─── Signal Input (from NATS) ──────────────────────────────────

// SignalInput señal validada que llega desde NATS
type SignalInput struct {
	ID                uuid.UUID  `json:"id"`
	TenantID          uuid.UUID  `json:"tenant_id"`
	UserID            *uuid.UUID `json:"user_id,omitempty"`
	Source            string     `json:"source"`
	Symbol            string     `json:"symbol"`
	Action            string     `json:"action"`
	EntryPrice        *float64   `json:"entry_price,omitempty"`
	StopLoss          *float64   `json:"stop_loss,omitempty"`
	TakeProfits       []float64  `json:"take_profits,omitempty"`
	LotSize           *float64   `json:"lot_size,omitempty"`
	LotMode           string     `json:"lot_mode,omitempty"`
	RiskPercent       *float64   `json:"risk_percent,omitempty"`
	Confidence        float64    `json:"confidence"`
	Hash              string     `json:"hash"`
	RecommendedLotSize *float64  `json:"recommended_lot_size,omitempty"`
	RiskLevel         string     `json:"risk_level,omitempty"`
}

// ─── Request DTOs ──────────────────────────────────────────────

// CreateGroupRequest DTO
type CreateGroupRequest struct {
	Name           string   `json:"name" binding:"required,min=2,max=100"`
	Description    string   `json:"description"`
	Enabled        *bool    `json:"enabled"`
	Symbols        []string `json:"symbols"`
	Actions        []string `json:"actions"`
	MinConfidence  float64  `json:"min_confidence"`
}

// UpdateGroupRequest DTO
type UpdateGroupRequest struct {
	Name           *string   `json:"name,omitempty"`
	Description    *string   `json:"description,omitempty"`
	Enabled        *bool     `json:"enabled,omitempty"`
	Symbols        *[]string `json:"symbols,omitempty"`
	Actions        *[]string `json:"actions,omitempty"`
	MinConfidence  *float64  `json:"min_confidence,omitempty"`
}

// CreateAccountRequest DTO
type CreateAccountRequest struct {
	Name          string   `json:"name" binding:"required,min=2,max=100"`
	Broker        string   `json:"broker" binding:"required"`
	AccountID     string   `json:"account_id" binding:"required"`
	Enabled       *bool    `json:"enabled"`
	LotMode       LotMode  `json:"lot_mode"`
	LotSize       *float64 `json:"lot_size"`
	LotMultiplier *float64 `json:"lot_multiplier"`
	RiskPercent   *float64 `json:"risk_percent"`
	OverrideSL    *bool    `json:"override_sl"`
	SLPips        *float64 `json:"sl_pips"`
	OverrideTP    *bool    `json:"override_tp"`
	TPPips        *float64 `json:"tp_pips"`
	InvertSide    *bool    `json:"invert_side"`
	SymbolSuffix  string   `json:"symbol_suffix"`
}

// UpdateAccountRequest DTO
type UpdateAccountRequest struct {
	Name          *string  `json:"name,omitempty"`
	Enabled       *bool    `json:"enabled,omitempty"`
	LotMode       *LotMode `json:"lot_mode,omitempty"`
	LotSize       *float64 `json:"lot_size,omitempty"`
	LotMultiplier *float64 `json:"lot_multiplier,omitempty"`
	RiskPercent   *float64 `json:"risk_percent,omitempty"`
	OverrideSL    *bool    `json:"override_sl,omitempty"`
	SLPips        *float64 `json:"sl_pips,omitempty"`
	OverrideTP    *bool    `json:"override_tp,omitempty"`
	TPPips        *float64 `json:"tp_pips,omitempty"`
	InvertSide    *bool    `json:"invert_side,omitempty"`
	SymbolSuffix  *string  `json:"symbol_suffix,omitempty"`
}

// ListGroupsResponse paginada
type ListGroupsResponse struct {
	Groups []*CopyGroup `json:"groups"`
	Total  int64        `json:"total"`
	Limit  int          `json:"limit"`
	Offset int          `json:"offset"`
}

// ListAccountsResponse paginada
type ListAccountsResponse struct {
	Accounts []*CopyAccount `json:"accounts"`
	Total    int64         `json:"total"`
	Limit    int           `json:"limit"`
	Offset   int           `json:"offset"`
}

// ListJobsResponse paginada
type ListJobsResponse struct {
	Jobs   []*CopyJob `json:"jobs"`
	Total  int64      `json:"total"`
	Limit  int        `json:"limit"`
	Offset int        `json:"offset"`
}

// StatsResponse DTO
type StatsResponse struct {
	TotalJobs      int64                  `json:"total_jobs"`
	SuccessfulJobs int64                  `json:"successful_jobs"`
	FailedJobs     int64                  `json:"failed_jobs"`
	SuccessRate    float64                `json:"success_rate"`
	ByGroup        map[string]int64       `json:"by_group"`
	ByAccount      map[string]int64       `json:"by_account"`
	ByStatus       map[string]int64       `json:"by_status"`
	Last24h        int64                  `json:"last_24h"`
}