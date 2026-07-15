// Package handlers contiene los HTTP handlers del auth-service.
package handlers

import (
	"context"
	"errors"
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/redis/go-redis/v9"

	"github.com/tnsvt/auth-service/internal/middleware"
	"github.com/tnsvt/auth-service/internal/models"
	"github.com/tnsvt/auth-service/internal/repository"
	"github.com/tnsvt/auth-service/internal/services"
)

// AuthHandler maneja los endpoints de autenticación
type AuthHandler struct {
	service *services.AuthService
	log     interface {
		Info(string, ...any)
		Warn(string, ...any)
		Error(string, error, ...any)
	}
}

// NewAuthHandler crea el handler
func NewAuthHandler(service *services.AuthService, log interface {
	Info(string, ...any)
	Warn(string, ...any)
	Error(string, error, ...any)
}) *AuthHandler {
	return &AuthHandler{service: service, log: log}
}

// Register POST /api/v1/auth/register
func (h *AuthHandler) Register(c *gin.Context) {
	var req models.RegisterRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, models.ErrorResponse{
			Error: "invalid request body",
			Code:  "VALIDATION_ERROR",
			Details: err.Error(),
		})
		return
	}

	resp, err := h.service.Register(c.Request.Context(), &req, c.ClientIP(), c.Request.UserAgent())
	if err != nil {
		switch {
		case errors.Is(err, services.ErrEmailExists):
			c.JSON(http.StatusConflict, models.ErrorResponse{
				Error: "email already registered",
				Code:  "EMAIL_EXISTS",
			})
		case errors.Is(err, services.ErrWeakPassword):
			c.JSON(http.StatusBadRequest, models.ErrorResponse{
				Error: "password too weak (min 12 chars, must include upper, lower, digit)",
				Code:  "WEAK_PASSWORD",
			})
		default:
			h.log.Error("Register failed", err)
			c.JSON(http.StatusInternalServerError, models.ErrorResponse{
				Error: "registration failed",
				Code:  "INTERNAL_ERROR",
			})
		}
		return
	}

	h.log.Info("User registered", "user_id", resp.User.ID, "tenant_id", resp.Tenant.ID, "ip", c.ClientIP())
	c.JSON(http.StatusCreated, resp)
}

// Login POST /api/v1/auth/login
func (h *AuthHandler) Login(c *gin.Context) {
	var req models.LoginRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, models.ErrorResponse{
			Error: "invalid request body",
			Code:  "VALIDATION_ERROR",
			Details: err.Error(),
		})
		return
	}

	resp, err := h.service.Login(c.Request.Context(), &req, c.ClientIP(), c.Request.UserAgent())
	if err != nil {
		switch {
		case errors.Is(err, services.ErrInvalidCredentials):
			c.JSON(http.StatusUnauthorized, models.ErrorResponse{
				Error: "invalid email or password",
				Code:  "INVALID_CREDENTIALS",
			})
		case errors.Is(err, services.ErrUserLocked):
			c.JSON(http.StatusLocked, models.ErrorResponse{
				Error: "account temporarily locked due to too many failed attempts",
				Code:  "ACCOUNT_LOCKED",
			})
		case errors.Is(err, services.ErrUserInactive):
			c.JSON(http.StatusForbidden, models.ErrorResponse{
				Error: "account is inactive or suspended",
				Code:  "ACCOUNT_INACTIVE",
			})
		case errors.Is(err, services.ErrTwoFARequired):
			c.JSON(http.StatusAccepted, gin.H{
				"requires_2fa": true,
				"message":      "2FA code required",
			})
		case errors.Is(err, services.ErrTwoFAInvalid):
			c.JSON(http.StatusUnauthorized, models.ErrorResponse{
				Error: "invalid 2FA code",
				Code:  "INVALID_2FA",
			})
		default:
			h.log.Error("Login failed", err)
			c.JSON(http.StatusInternalServerError, models.ErrorResponse{
				Error: "login failed",
				Code:  "INTERNAL_ERROR",
			})
		}
		return
	}

	h.log.Info("User logged in", "user_id", resp.User.ID, "ip", c.ClientIP())
	c.JSON(http.StatusOK, resp)
}

// Refresh POST /api/v1/auth/refresh
func (h *AuthHandler) Refresh(c *gin.Context) {
	var req models.RefreshRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, models.ErrorResponse{
			Error: "invalid request body",
			Code:  "VALIDATION_ERROR",
		})
		return
	}

	resp, err := h.service.Refresh(c.Request.Context(), req.RefreshToken, c.ClientIP(), c.Request.UserAgent())
	if err != nil {
		if errors.Is(err, services.ErrInvalidRefreshToken) {
			c.JSON(http.StatusUnauthorized, models.ErrorResponse{
				Error: "invalid or expired refresh token",
				Code:  "INVALID_REFRESH",
			})
			return
		}
		h.log.Error("Refresh failed", err)
		c.JSON(http.StatusInternalServerError, models.ErrorResponse{
			Error: "refresh failed",
			Code:  "INTERNAL_ERROR",
		})
		return
	}

	c.JSON(http.StatusOK, resp)
}

// Logout POST /api/v1/auth/logout (requires auth)
func (h *AuthHandler) Logout(c *gin.Context) {
	userID, _ := c.Get(middleware.CtxUserID)
	uid, ok := userID.(interface{ String() string })
	if !ok {
		c.JSON(http.StatusInternalServerError, models.ErrorResponse{Error: "invalid user context"})
		return
	}
	_ = uid // simplificado

	if err := h.service.Logout(c.Request.Context(), mustUUID(c, middleware.CtxUserID), c.PostForm("refresh_token"), c.ClientIP(), c.Request.UserAgent()); err != nil {
		h.log.Warn("Logout error", "error", err.Error())
	}

	c.JSON(http.StatusOK, gin.H{"message": "logged out"})
}

// Me GET /api/v1/auth/me (requires auth)
func (h *AuthHandler) Me(c *gin.Context) {
	uid := mustUUID(c, middleware.CtxUserID)
	tenantID := mustUUID(c, middleware.CtxTenantID)
	email := c.GetString(middleware.CtxEmail)
	role := c.GetString(middleware.CtxRole)

	c.JSON(http.StatusOK, gin.H{
		"user_id":   uid,
		"tenant_id": tenantID,
		"email":     email,
		"role":      role,
		"permissions": models.GetPermissions(role),
	})
}

// ChangePassword POST /api/v1/auth/password/change (requires auth)
func (h *AuthHandler) ChangePassword(c *gin.Context) {
	var req models.ChangePasswordRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, models.ErrorResponse{Error: "invalid request", Details: err.Error()})
		return
	}

	uid := mustUUID(c, middleware.CtxUserID)
	err := h.service.ChangePassword(c.Request.Context(), uid, req.CurrentPassword, req.NewPassword, c.ClientIP(), c.Request.UserAgent())
	if err != nil {
		switch {
		case errors.Is(err, services.ErrInvalidCredentials):
			c.JSON(http.StatusUnauthorized, models.ErrorResponse{Error: "current password is wrong"})
		case errors.Is(err, services.ErrWeakPassword):
			c.JSON(http.StatusBadRequest, models.ErrorResponse{Error: "new password too weak"})
		default:
			h.log.Error("Change password failed", err)
			c.JSON(http.StatusInternalServerError, models.ErrorResponse{Error: "change password failed"})
		}
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "password changed, please log in again"})
}

// Setup2FA POST /api/v1/auth/2fa/setup (requires auth)
func (h *AuthHandler) Setup2FA(c *gin.Context) {
	uid := mustUUID(c, middleware.CtxUserID)
	secret, _ := h.service.Setup2FA(c.Request.Context(), uid)
	c.JSON(http.StatusOK, gin.H{
		"secret":      secret,
		"qr_url":      "otpauth://totp/TNSVT:" + c.GetString(middleware.CtxEmail) + "?secret=" + secret + "&issuer=TNSVT",
		"manual_key":  secret,
	})
}

// Verify2FA POST /api/v1/auth/2fa/verify (requires auth)
func (h *AuthHandler) Verify2FA(c *gin.Context) {
	var req struct {
		Code string `json:"code" binding:"required,len=6"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, models.ErrorResponse{Error: "invalid code"})
		return
	}

	uid := mustUUID(c, middleware.CtxUserID)
	if err := h.service.Verify2FA(c.Request.Context(), uid, req.Code); err != nil {
		c.JSON(http.StatusBadRequest, models.ErrorResponse{Error: "invalid code"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "2FA enabled"})
}

// ListUsers GET /api/v1/auth/users (admin only)
func (h *AuthHandler) ListUsers(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{"message": "admin endpoint"})
}

// ─── Health ─────────────────────────────────────────────────────

// Health GET /health
func Health(repo repository.Repository) gin.HandlerFunc {
	return func(c *gin.Context) {
		ctx, cancel := context.WithTimeout(c.Request.Context(), 2)
		defer cancel()
		_ = ctx

		if err := repo.Ping(c.Request.Context()); err != nil {
			c.JSON(http.StatusServiceUnavailable, gin.H{"status": "degraded", "db": "down"})
			return
		}
		c.JSON(http.StatusOK, gin.H{"status": "ok", "service": "auth-service"})
	}
}

// HealthReady GET /health/ready
func HealthReady(repo repository.Repository, redis *redis.Client) gin.HandlerFunc {
	return func(c *gin.Context) {
		checks := gin.H{}
		ready := true

		if err := repo.Ping(c.Request.Context()); err != nil {
			checks["db"] = "down"
			ready = false
		} else {
			checks["db"] = "up"
		}

		ctx := c.Request.Context()
		if err := redis.Ping(ctx).Err(); err != nil {
			checks["redis"] = "down"
			// Redis es opcional para readiness
		} else {
			checks["redis"] = "up"
		}

		if !ready {
			c.JSON(http.StatusServiceUnavailable, gin.H{
				"status": "not_ready",
				"checks": checks,
			})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"status": "ready",
			"checks": checks,
		})
	}
}

// ─── Helper ─────────────────────────────────────────────────────

func mustUUID(c *gin.Context, key string) (out [16]byte) {
	defer func() { recover() }()
	val, ok := c.Get(key)
	if !ok {
		return
	}
	// Asumimos uuid.UUID que es [16]byte
	if u, ok := val.([16]byte); ok {
		return u
	}
	return
}

// Para evitar warning de unused
var _ = pgxpool.Pool{}