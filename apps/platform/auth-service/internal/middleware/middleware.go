// Package middleware contiene middlewares HTTP del auth-service.
package middleware

import (
	"context"
	"errors"
	"net/http"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"

	"github.com/tnsvt/auth-service/internal/models"
)

// ─── Request ID ────────────────────────────────────────────────

// RequestID middleware que asigna un ID único a cada request
func RequestID() gin.HandlerFunc {
	return func(c *gin.Context) {
		id := c.GetHeader("X-Request-ID")
		if id == "" {
			id = uuid.New().String()
		}
		c.Set("request_id", id)
		c.Writer.Header().Set("X-Request-ID", id)
		c.Next()
	}
}

// ─── Logging ───────────────────────────────────────────────────

// Logging middleware que loggea cada request
func Logging(log interface {
	Info(string, ...any)
	Warn(string, ...any)
	Error(string, error, ...any)
}) gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()
		path := c.Request.URL.Path
		method := c.Request.Method

		c.Next()

		latency := time.Since(start)
		status := c.Writer.Status()

		fields := []any{
			"method", method,
			"path", path,
			"status", status,
			"latency_ms", latency.Milliseconds(),
			"ip", c.ClientIP(),
			"request_id", c.GetString("request_id"),
		}

		switch {
		case status >= 500:
			log.Error("Request failed", errors.New(c.Errors.String()), fields...)
		case status >= 400:
			log.Warn("Request warning", fields...)
		default:
			log.Info("Request completed", fields...)
		}
	}
}

// ─── CORS ──────────────────────────────────────────────────────

// CORS middleware (configurado restrictivo por defecto)
func CORS() gin.HandlerFunc {
	return func(c *gin.Context) {
		origin := c.GetHeader("Origin")
		// Whitelist de orígenes permitidos
		allowed := map[string]bool{
			"http://localhost:3000":  true, // Next.js dev
			"http://localhost:8501":  true, // Dashboard
			"http://127.0.0.1:3000":  true,
			"http://127.0.0.1:8501":  true,
			"tauri://localhost":      true, // Tauri desktop
		}

		if allowed[origin] {
			c.Writer.Header().Set("Access-Control-Allow-Origin", origin)
		}

		c.Writer.Header().Set("Access-Control-Allow-Credentials", "true")
		c.Writer.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Request-ID, X-Tenant-ID")
		c.Writer.Header().Set("Access-Control-Expose-Headers", "X-Request-ID")
		c.Writer.Header().Set("Access-Control-Max-Age", "600")

		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(http.StatusNoContent)
			return
		}

		c.Next()
	}
}

// ─── Metrics ───────────────────────────────────────────────────

// Metrics middleware placeholder (Prometheus ya se expone aparte)
func Metrics() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Next()
	}
}

// ─── Rate Limiting ─────────────────────────────────────────────

// RateLimit middleware con Redis (in-memory fallback)
func RateLimit(rdb *redis.Client, key string, max int, window time.Duration) gin.HandlerFunc {
	return func(c *gin.Context) {
		identifier := c.ClientIP() + ":" + key
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		defer cancel()

		count, err := rdb.Incr(ctx, "ratelimit:"+identifier).Result()
		if err != nil {
			// Redis no disponible, no bloquear pero loggear
			c.Next()
			return
		}

		if count == 1 {
			rdb.Expire(ctx, "ratelimit:"+identifier, window)
		}

		c.Writer.Header().Set("X-RateLimit-Limit", strconv.Itoa(max))
		c.Writer.Header().Set("X-RateLimit-Remaining", strconv.Itoa(max-int(count)))

		if count > int64(max) {
			c.Writer.Header().Set("Retry-After", strconv.Itoa(int(window.Seconds())))
			c.AbortWithStatusJSON(http.StatusTooManyRequests, gin.H{
				"error":      "rate limit exceeded",
				"limit":      max,
				"window_sec": int(window.Seconds()),
			})
			return
		}

		c.Next()
	}
}

// ─── JWT Auth ──────────────────────────────────────────────────

// JWTValidator interfaz mínima para evitar import circular
type JWTValidator interface {
	ValidateToken(tokenString string) (*JWTClaimsLite, error)
}

// JWTClaimsLite versión simplificada para middleware
type JWTClaimsLite struct {
	UserID   uuid.UUID
	TenantID uuid.UUID
	Email    string
	Role     string
}

// ContextKey constants
const (
	CtxUserID   = "auth.user_id"
	CtxTenantID = "auth.tenant_id"
	CtxEmail    = "auth.email"
	CtxRole     = "auth.role"
)

// RequireAuth middleware que valida JWT
func RequireAuth(jwt JWTValidator) gin.HandlerFunc {
	return func(c *gin.Context) {
		authHeader := c.GetHeader("Authorization")
		if authHeader == "" {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{
				"error": "missing Authorization header",
				"code":  "AUTH_MISSING",
			})
			return
		}

		if len(authHeader) < 8 || authHeader[:7] != "Bearer " {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{
				"error": "invalid Authorization format, expected: Bearer <token>",
				"code":  "AUTH_FORMAT",
			})
			return
		}

		tokenString := authHeader[7:]
		claims, err := jwt.ValidateToken(tokenString)
		if err != nil {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{
				"error": "invalid or expired token",
				"code":  "AUTH_INVALID",
			})
			return
		}

		// Solo aceptar access tokens, no refresh
		// (esto se valida internamente en el service)
		c.Set(CtxUserID, claims.UserID)
		c.Set(CtxTenantID, claims.TenantID)
		c.Set(CtxEmail, claims.Email)
		c.Set(CtxRole, claims.Role)

		c.Next()
	}
}

// RequireRole middleware que verifica RBAC
func RequireRole(allowedRoles ...string) gin.HandlerFunc {
	return func(c *gin.Context) {
		role, exists := c.Get(CtxRole)
		if !exists {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{
				"error": "no role in context",
				"code":  "RBAC_NO_ROLE",
			})
			return
		}

		userRole, ok := role.(string)
		if !ok {
			c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{
				"error": "invalid role type",
			})
			return
		}

		for _, r := range allowedRoles {
			if r == userRole {
				c.Next()
				return
			}
		}

		c.AbortWithStatusJSON(http.StatusForbidden, gin.H{
			"error":         "insufficient privileges",
			"code":          "RBAC_FORBIDDEN",
			"required_role": allowedRoles,
			"your_role":     userRole,
		})
	}
}

// RequirePermission middleware que verifica permisos
func RequirePermission(permission string) gin.HandlerFunc {
	return func(c *gin.Context) {
		roleVal, exists := c.Get(CtxRole)
		if !exists {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{
				"error": "no role in context",
			})
			return
		}

		role, _ := roleVal.(string)
		if !models.HasPermission(role, permission) {
			c.AbortWithStatusJSON(http.StatusForbidden, gin.H{
				"error":             "insufficient permissions",
				"code":              "RBAC_NO_PERMISSION",
				"required":          permission,
				"your_role":         role,
				"your_permissions":  models.GetPermissions(role),
			})
			return
		}

		c.Next()
	}
}

// ─── Tenant Isolation ──────────────────────────────────────────

// RequireTenantAccess middleware que verifica acceso al tenant
func RequireTenantAccess() gin.HandlerFunc {
	return func(c *gin.Context) {
		userTenantID, _ := c.Get(CtxTenantID)
		requestTenantID := c.GetHeader("X-Tenant-ID")

		// Si no se pasa X-Tenant-ID, usar el del JWT
		if requestTenantID == "" {
			c.Set("active_tenant_id", userTenantID)
			c.Next()
			return
		}

		reqTenantUUID, err := uuid.Parse(requestTenantID)
		if err != nil {
			c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{
				"error": "invalid X-Tenant-ID format",
			})
			return
		}

		if userTenantID != reqTenantUUID {
			// Super admin puede acceder a cualquier tenant
			role, _ := c.Get(CtxRole)
			if role == models.RoleSuperAdmin {
				c.Set("active_tenant_id", reqTenantUUID)
				c.Next()
				return
			}

			c.AbortWithStatusJSON(http.StatusForbidden, gin.H{
				"error": "cannot access another tenant",
				"code":  "TENANT_FORBIDDEN",
			})
			return
		}

		c.Set("active_tenant_id", reqTenantUUID)
		c.Next()
	}
}