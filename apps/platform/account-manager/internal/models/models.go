// Package models define los modelos del account-manager.
package models

import (
	"time"

	"github.com/google/uuid"
)

// ─── Account Status ────────────────────────────────────────────

type AccountStatus string

const (
	AccountStatusActive    AccountStatus = "active"
	AccountStatusPaused    AccountStatus = "paused"
	AccountStatusError     AccountStatus = "error"
	AccountStatusDisabled  AccountStatus = "disabled"
	AccountStatusConnected AccountStatus = "connected" // temporalmente conectado a MT5
	AccountStatusLogging   AccountStatus = "logging_in"
)

// ─── Account ────────────────────────────────────────────────────

// Account es una cuenta MT5 gestionada por el account-manager.
// Las credenciales se almacenan encriptadas con AES-GCM.
type Account struct {
	ID            uuid.UUID     `json:"id"`
	TenantID      uuid.UUID     `json:"tenant_id"`
	Login         int64         `json:"login"`
	Server        string        `json:"server"`
	Broker        string        `json:"broker"` // "mt5", "ctrader", etc
	Alias         *string       `json:"alias,omitempty"`
	Name          *string       `json:"name,omitempty"`
	Status        AccountStatus `json:"status"`
	LastSeen      *time.Time    `json:"last_seen,omitempty"`
	LastError     *string       `json:"last_error,omitempty"`
	CreatedAt     time.Time     `json:"created_at"`
	UpdatedAt     time.Time     `json:"updated_at"`

	// Datos en vivo cacheados (actualizados por snapshot poller)
	LastBalance     *float64   `json:"balance,omitempty"`
	LastEquity      *float64   `json:"equity,omitempty"`
	LastPnL         *float64   `json:"pnl,omitempty"`
	LastOpenPos     int        `json:"open_positions"`
	LastSnapshotAt  *time.Time `json:"snapshot_at,omitempty"`

	// Copy trading: marca esta cuenta como "replicadora" (aparece en Copy Trading UI)
	CopyEnabled bool `json:"copy_enabled"`
}

// CreateAccountRequest DTO para crear cuenta
type CreateAccountRequest struct {
	Login    int64  `json:"login" binding:"required"`
	Password string `json:"password" binding:"required,min=1"`
	Server   string `json:"server" binding:"required"`
	Broker   string `json:"broker"` // default "mt5"
	Alias    string `json:"alias"`
	Name     string `json:"name"`
}

// UpdateAccountRequest DTO para actualizar alias/name/status
type UpdateAccountRequest struct {
	Alias       *string        `json:"alias,omitempty"`
	Name        *string        `json:"name,omitempty"`
	Status      *AccountStatus `json:"status,omitempty"`
	CopyEnabled *bool          `json:"copy_enabled,omitempty"`
}

// ChangePasswordRequest DTO para cambiar la password (re-encripta)
type ChangePasswordRequest struct {
	OldPassword string `json:"old_password"`
	NewPassword string `json:"new_password" binding:"required,min=1"`
}

// AccountSnapshot datos en vivo de una cuenta (leídos del MT5 connector)
type AccountSnapshot struct {
	Login          int64     `json:"login"`
	Server         string    `json:"server"`
	Balance        float64   `json:"balance"`
	Equity         float64   `json:"equity"`
	Margin         float64   `json:"margin"`
	FreeMargin     float64   `json:"free_margin"`
	Profit         float64   `json:"profit"`
	Leverage       int       `json:"leverage"`
	Currency       string    `json:"currency"`
	OpenPositions  int       `json:"open_positions"`
	Connected      bool      `json:"connected"`
	LastUpdate     time.Time `json:"last_update"`
}

// AccountListResponse DTO
type AccountListResponse struct {
	Accounts  []Account          `json:"accounts"`
	Aggregate AggregateSnapshot  `json:"aggregate"`
}

// AggregateSnapshot totales agregados
type AggregateSnapshot struct {
	TotalBalance       float64 `json:"total_balance"`
	TotalEquity        float64 `json:"total_equity"`
	TotalPnL           float64 `json:"total_pnl"`
	TotalOpenPositions int     `json:"total_open_positions"`
	ActiveAccounts     int     `json:"active_accounts"`
}
