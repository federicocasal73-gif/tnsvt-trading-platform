// Package models define los modelos del signal-engine.
package models

import (
	"time"

	"github.com/google/uuid"
)

// ─── Enums ─────────────────────────────────────────────────────

// Action tipo de acción de la señal
type Action string

const (
	ActionBuy    Action = "BUY"
	ActionSell   Action = "SELL"
	ActionClose  Action = "CLOSE"
	ActionModify Action = "MODIFY"
)

// Source origen de la señal
type Source string

const (
	SourceTelegram Source = "telegram"
	SourceTNSVT    Source = "tnsvt"
	SourceAPI      Source = "api"
	SourceManual   Source = "manual"
	SourceAI       Source = "ai"
)

// Status estado de procesamiento
type Status string

const (
	StatusReceived   Status = "received"
	StatusValidating Status = "validating"
	StatusValidated  Status = "validated"
	StatusRejected   Status = "rejected"
	StatusRouted     Status = "routed"
	StatusExecuted   Status = "executed"
	StatusExpired    Status = "expired"
)

// RejectReason razón de rechazo
type RejectReason string

const (
	RejectInvalidFormat    RejectReason = "invalid_format"
	RejectInvalidSymbol    RejectReason = "invalid_symbol"
	RejectInvalidPrice     RejectReason = "invalid_price"
	RejectDuplicate        RejectReason = "duplicate"
	RejectRiskLimit        RejectReason = "risk_limit"
	RejectNewsFilter       RejectReason = "news_filter"
	RejectSymbolNotAllowed RejectReason = "symbol_not_allowed"
)

// ─── Channel (Telegram channel configuration) ──────────────────

// Channel configuración de un canal de Telegram que envía señales
type Channel struct {
	ID            uuid.UUID `json:"id"`
	Name          string    `json:"name"`
	TelegramID    int64     `json:"telegram_id"`
	TelegramSlug  string    `json:"telegram_slug"`
	Enabled       bool      `json:"enabled"`
	Trusted       bool      `json:"trusted"` // Si es true, las señales se ejecutan sin confirmación
	MinConfidence float64   `json:"min_confidence"`
	AllowedActions []Action  `json:"allowed_actions"`
	CreatedAt     time.Time `json:"created_at"`
}

// ─── Signal ────────────────────────────────────────────────────

// Signal representa una señal de trading completa
type Signal struct {
	ID          uuid.UUID `json:"id"`
	TenantID    uuid.UUID `json:"tenant_id"`
	UserID      *uuid.UUID `json:"user_id,omitempty"`

	// Source
	Source   Source `json:"source"`
	SourceID string `json:"source_id,omitempty"` // ID en el origen (ej: message_id de Telegram)
	RawText  string `json:"raw_text,omitempty"`

	// Trade params
	Symbol       string   `json:"symbol" binding:"required"`
	Action       Action   `json:"action" binding:"required"`
	EntryPrice   *float64 `json:"entry_price,omitempty"`
	StopLoss     *float64 `json:"stop_loss,omitempty"`
	TakeProfits  []float64 `json:"take_profits,omitempty"`
	LotSize      *float64 `json:"lot_size,omitempty"`
	LotMode      string   `json:"lot_mode,omitempty"`
	RiskPercent  *float64 `json:"risk_percent,omitempty"`
	Comment      string   `json:"comment,omitempty"`

	// Metadata
	Confidence  float64 `json:"confidence,omitempty"`  // AI score 0-1
	Status      Status  `json:"status"`
	RejectReason RejectReason `json:"reject_reason,omitempty"`
	RejectDetails string `json:"reject_details,omitempty"`

	// Hash para deduplicación
	Hash string `json:"hash"`

	// Lifecycle
	ReceivedAt  time.Time  `json:"received_at"`
	ValidatedAt *time.Time `json:"validated_at,omitempty"`
	ExpiresAt   *time.Time `json:"expires_at,omitempty"`
	RoutedAt    *time.Time `json:"routed_at,omitempty"`

	// Channel info
	ChannelID *uuid.UUID `json:"channel_id,omitempty"`
}

// ─── Raw signal (from telegram, pre-validation) ────────────────

// RawSignal señal cruda recibida de Telegram
type RawSignal struct {
	ChannelID   int64     `json:"channel_id"`
	ChannelName string    `json:"channel_name"`
	MessageID   int64     `json:"message_id"`
	SenderID    int64     `json:"sender_id"`
	Text        string    `json:"text"`
	Timestamp   time.Time `json:"timestamp"`
	ReplyToMsgID *int64   `json:"reply_to_msg_id,omitempty"`
}

// ─── Request DTOs ─────────────────────────────────────────────

// SubmitSignalRequest DTO para submit manual/API
type SubmitSignalRequest struct {
	Symbol      string    `json:"symbol" binding:"required"`
	Action      Action    `json:"action" binding:"required"`
	EntryPrice  *float64  `json:"entry_price"`
	StopLoss    *float64  `json:"stop_loss"`
	TakeProfits []float64 `json:"take_profits"`
	LotSize     *float64  `json:"lot_size"`
	LotMode     string    `json:"lot_mode"`
	RiskPercent *float64  `json:"risk_percent"`
	Comment     string    `json:"comment"`
	TenantID    uuid.UUID `json:"tenant_id"`
	UserID      *uuid.UUID `json:"user_id,omitempty"`
	ExpiresIn   int       `json:"expires_in_seconds,omitempty"`
}

// ParseRequest DTO para preview de parsing
type ParseRequest struct {
	Text string `json:"text" binding:"required"`
}

// StatsResponse estadísticas de señales
type StatsResponse struct {
	TotalReceived    int64            `json:"total_received"`
	TotalValidated   int64            `json:"total_validated"`
	TotalRejected    int64            `json:"total_rejected"`
	TotalRouted      int64            `json:"total_routed"`
	TotalExecuted    int64            `json:"total_executed"`
	RejectionReasons map[string]int64 `json:"rejection_reasons"`
	TopSymbols       map[string]int64 `json:"top_symbols"`
	BySource         map[string]int64 `json:"by_source"`
	Period           string           `json:"period"` // last_24h, last_7d, all_time
}

// ListResponse paginada
type ListResponse struct {
	Signals []*Signal `json:"signals"`
	Total   int64     `json:"total"`
	Limit   int       `json:"limit"`
	Offset  int       `json:"offset"`
}