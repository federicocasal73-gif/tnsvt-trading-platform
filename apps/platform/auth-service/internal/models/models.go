// Package models define los modelos de dominio del auth-service.
package models

import (
	"time"

	"github.com/google/uuid"
)

// ─── Roles (RBAC) ──────────────────────────────────────────────
//
// 12 roles totales, ordenados de menor a mayor privilegio:
//   1. tenant_viewer     - Solo lectura
//   2. tenant_trader     - Lectura + ejecutar trades propios
//   3. tenant_admin      - Gestión de su tenant
//   4. bot_service       - Servicios automatizados
//   5. api_user          - Acceso API externo
//   6. viewer            - Viewer global (multi-tenant read)
//   7. trader            - Trader global
//   8. support           - Soporte al cliente
//   9. developer         - Acceso a logs, debug
//   10. billing_admin    - Gestión de facturación
//   11. admin            - Admin del sistema (sin super)
//   12. super_admin      - Acceso total

const (
	RoleSuperAdmin    = "super_admin"
	RoleAdmin         = "admin"
	RoleBillingAdmin  = "billing_admin"
	RoleDeveloper     = "developer"
	RoleSupport       = "support"
	RoleTrader        = "trader"
	RoleViewer        = "viewer"
	RoleAPIUser       = "api_user"
	RoleBotService    = "bot_service"
	RoleTenantAdmin   = "tenant_admin"
	RoleTenantTrader  = "tenant_trader"
	RoleTenantViewer  = "tenant_viewer"
)

// ─── Permissions ───────────────────────────────────────────────
//
// Cada permiso es un string en formato "domain.action"
// Ejemplos: "users.create", "trades.execute", "config.update"

const (
	PermUsersRead          = "users.read"
	PermUsersCreate        = "users.create"
	PermUsersUpdate        = "users.update"
	PermUsersDelete        = "users.delete"
	PermTradesRead         = "trades.read"
	PermTradesExecute      = "trades.execute"
	PermTradesClose        = "trades.close"
	PermConfigRead         = "config.read"
	PermConfigUpdate       = "config.update"
	PermBillingRead        = "billing.read"
	PermBillingUpdate      = "billing.update"
	PermSystemAdmin        = "system.admin"
	PermSystemLogs         = "system.logs"
	PermSystemMetrics      = "system.metrics"
	PermTenantsRead        = "tenants.read"
	PermTenantsCreate      = "tenants.create"
	PermTenantsUpdate      = "tenants.update"
	PermTenantsDelete      = "tenants.delete"
	PermAuditRead          = "audit.read"
	PermAIConfigure        = "ai.configure"
	PermBrokersRead        = "brokers.read"
	PermBrokersUpdate      = "brokers.update"
	PermWebhooksManage     = "webhooks.manage"
	PermNotificationsSend  = "notifications.send"
	PermStrategiesRead     = "strategies.read"
	PermStrategiesExecute  = "strategies.execute"
	PermReportsRead        = "reports.read"
	PermBacktestsExecute   = "backtests.execute"
	PermRiskLimitsUpdate   = "risk.limits.update"
	PermAPIAccess          = "api.access"
	PermServiceAccount     = "service.account"
)

// rolePermissions mapea cada rol a sus permisos
var rolePermissions = map[string][]string{
	RoleSuperAdmin: { // Todos los permisos
		PermUsersRead, PermUsersCreate, PermUsersUpdate, PermUsersDelete,
		PermTradesRead, PermTradesExecute, PermTradesClose,
		PermConfigRead, PermConfigUpdate,
		PermBillingRead, PermBillingUpdate,
		PermSystemAdmin, PermSystemLogs, PermSystemMetrics,
		PermTenantsRead, PermTenantsCreate, PermTenantsUpdate, PermTenantsDelete,
		PermAuditRead, PermAIConfigure,
		PermBrokersRead, PermBrokersUpdate,
		PermWebhooksManage, PermNotificationsSend,
		PermStrategiesRead, PermStrategiesExecute,
		PermReportsRead, PermBacktestsExecute,
		PermRiskLimitsUpdate, PermAPIAccess, PermServiceAccount,
	},
	RoleAdmin: {
		PermUsersRead, PermUsersCreate, PermUsersUpdate,
		PermTradesRead, PermTradesExecute, PermTradesClose,
		PermConfigRead, PermConfigUpdate,
		PermBillingRead, PermSystemLogs, PermSystemMetrics,
		PermTenantsRead, PermAuditRead, PermAIConfigure,
		PermBrokersRead, PermBrokersUpdate,
		PermWebhooksManage, PermNotificationsSend,
		PermStrategiesRead, PermStrategiesExecute,
		PermReportsRead, PermBacktestsExecute,
		PermRiskLimitsUpdate, PermAPIAccess,
	},
	RoleBillingAdmin: {
		PermUsersRead, PermBillingRead, PermBillingUpdate,
		PermTenantsRead, PermReportsRead,
	},
	RoleDeveloper: {
		PermUsersRead, PermTradesRead, PermConfigRead,
		PermSystemLogs, PermSystemMetrics, PermAuditRead,
		PermBrokersRead, PermStrategiesRead, PermReportsRead,
		PermAPIAccess, PermServiceAccount,
	},
	RoleSupport: {
		PermUsersRead, PermTradesRead, PermConfigRead,
		PermTenantsRead, PermReportsRead, PermNotificationsSend,
	},
	RoleTrader: {
		PermUsersRead, PermTradesRead, PermTradesExecute, PermTradesClose,
		PermConfigRead, PermBrokersRead, PermStrategiesRead,
		PermStrategiesExecute, PermReportsRead, PermBacktestsExecute,
		PermAPIAccess,
	},
	RoleViewer: {
		PermUsersRead, PermTradesRead, PermConfigRead,
		PermBrokersRead, PermStrategiesRead, PermReportsRead,
	},
	RoleAPIUser: {
		PermTradesRead, PermTradesExecute, PermStrategiesRead,
		PermAPIAccess,
	},
	RoleBotService: {
		PermTradesRead, PermTradesExecute, PermNotificationsSend,
		PermServiceAccount, PermAPIAccess,
	},
	RoleTenantAdmin: {
		PermUsersRead, PermUsersCreate, PermUsersUpdate,
		PermTradesRead, PermTradesExecute,
		PermConfigRead, PermConfigUpdate,
		PermBrokersRead, PermBrokersUpdate,
		PermStrategiesRead, PermStrategiesExecute,
		PermReportsRead, PermRiskLimitsUpdate,
	},
	RoleTenantTrader: {
		PermTradesRead, PermTradesExecute, PermTradesClose,
		PermConfigRead, PermBrokersRead,
		PermStrategiesRead, PermStrategiesExecute,
		PermReportsRead,
	},
	RoleTenantViewer: {
		PermTradesRead, PermConfigRead, PermReportsRead,
	},
}

// HasPermission verifica si un rol tiene un permiso
func HasPermission(role, permission string) bool {
	perms, ok := rolePermissions[role]
	if !ok {
		return false
	}
	for _, p := range perms {
		if p == permission {
			return true
		}
	}
	return false
}

// GetPermissions retorna los permisos de un rol
func GetPermissions(role string) []string {
	perms, ok := rolePermissions[role]
	if !ok {
		return nil
	}
	out := make([]string, len(perms))
	copy(out, perms)
	return out
}

// ─── Tenant ─────────────────────────────────────────────────────

// Tenant representa una organización (multi-tenant)
type Tenant struct {
	ID          uuid.UUID `json:"id"`
	Name        string    `json:"name"`
	Slug        string    `json:"slug"`
	Schema      string    `json:"schema"`
	Status      string    `json:"status"` // active, suspended, trial
	Plan        string    `json:"plan"`   // free, starter, pro, enterprise
	MaxUsers    int       `json:"max_users"`
	MaxSignals  int       `json:"max_signals_per_day"`
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
}

// ─── User ───────────────────────────────────────────────────────

// User representa un usuario del sistema
type User struct {
	ID                uuid.UUID  `json:"id"`
	TenantID          uuid.UUID  `json:"tenant_id"`
	Email             string     `json:"email"`
	Username          string     `json:"username"`
	PasswordHash      string     `json:"-"` // nunca se serializa
	Role              string     `json:"role"`
	Status            string     `json:"status"` // active, inactive, locked, pending
	EmailVerified     bool       `json:"email_verified"`
	TwoFactorEnabled  bool       `json:"two_factor_enabled"`
	TwoFactorSecret   string     `json:"-"`
	FailedLoginCount  int        `json:"-"`
	LockedUntil       *time.Time `json:"-"`
	LastLoginAt       *time.Time `json:"last_login_at,omitempty"`
	LastLoginIP       string     `json:"-"`
	CreatedAt         time.Time  `json:"created_at"`
	UpdatedAt         time.Time  `json:"updated_at"`
}

// ─── Session / Refresh Token ───────────────────────────────────

// Session representa una sesión activa (refresh token)
type Session struct {
	ID                uuid.UUID `json:"id"`
	UserID            uuid.UUID `json:"user_id"`
	RefreshTokenHash  string    `json:"-"`
	UserAgent         string    `json:"user_agent"`
	IP                string    `json:"ip"`
	ExpiresAt         time.Time `json:"expires_at"`
	RevokedAt         *time.Time `json:"revoked_at,omitempty"`
	RevokedReason     string    `json:"revoked_reason,omitempty"`
	CreatedAt         time.Time `json:"created_at"`
}

// ─── Audit Event ───────────────────────────────────────────────

// AuditEvent representa un evento de auditoría
type AuditEvent struct {
	ID         uuid.UUID              `json:"id"`
	UserID     *uuid.UUID             `json:"user_id,omitempty"`
	TenantID   *uuid.UUID             `json:"tenant_id,omitempty"`
	Action     string                 `json:"action"`     // login, logout, refresh, register, password_change, 2fa_enable, etc.
	IP         string                 `json:"ip"`
	UserAgent  string                 `json:"user_agent"`
	Status     string                 `json:"status"`     // success, failure
	Metadata   map[string]any         `json:"metadata"`
	Timestamp  time.Time              `json:"timestamp"`
}

// ─── DTOs (request/response) ───────────────────────────────────

// RegisterRequest DTO para registro
type RegisterRequest struct {
	TenantName string `json:"tenant_name" binding:"required,min=2,max=100"`
	Email      string `json:"email" binding:"required,email"`
	Username   string `json:"username" binding:"required,min=3,max=50,alphanum"`
	Password   string `json:"password" binding:"required,min=12,max=128"`
}

// LoginRequest DTO para login
type LoginRequest struct {
	Email      string `json:"email" binding:"required,email"`
	Password   string `json:"password" binding:"required,min=1"`
	TwoFACode  string `json:"two_fa_code,omitempty"`
	DeviceName string `json:"device_name,omitempty"`
}

// RefreshRequest DTO para refresh
type RefreshRequest struct {
	RefreshToken string `json:"refresh_token" binding:"required"`
}

// ChangePasswordRequest DTO
type ChangePasswordRequest struct {
	CurrentPassword string `json:"current_password" binding:"required"`
	NewPassword     string `json:"new_password" binding:"required,min=12,max=128"`
}

// AuthResponse respuesta exitosa
type AuthResponse struct {
	AccessToken  string    `json:"access_token"`
	RefreshToken string    `json:"refresh_token"`
	TokenType    string    `json:"token_type"`
	ExpiresIn    int       `json:"expires_in"`
	User         *User     `json:"user"`
	Tenant       *Tenant   `json:"tenant"`
	Requires2FA  bool      `json:"requires_2fa,omitempty"`
}

// ErrorResponse respuesta de error
type ErrorResponse struct {
	Error   string `json:"error"`
	Code    string `json:"code"`
	Details string `json:"details,omitempty"`
}