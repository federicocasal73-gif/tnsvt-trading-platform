// Package middleware contiene middlewares del API Gateway.
package middleware

import (
	"errors"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"

	"github.com/tnsvt/api-gateway/internal/proxy"
)

// ─── Request ID ────────────────────────────────────────────────

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

// ─── Access Log ────────────────────────────────────────────────

func AccessLog(log interface {
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
			"size", c.Writer.Size(),
			"request_id", c.GetString("request_id"),
		}

		if userID, exists := c.Get("user_id"); exists {
			fields = append(fields, "user_id", userID)
		}

		switch {
		case status >= 500:
			log.Error("Upstream error", errors.New("status >= 500"), fields...)
		case status >= 400:
			log.Warn("Client error", fields...)
		default:
			log.Info("Request", fields...)
		}
	}
}

// ─── CORS ──────────────────────────────────────────────────────

func CORS() gin.HandlerFunc {
	allowed := map[string]bool{
		"http://localhost:3000":   true,
		"http://localhost:3001":   true,
		"http://localhost:8501":   true,
		"http://127.0.0.1:3000":   true,
		"http://127.0.0.1:8501":   true,
		"tauri://localhost":       true,
		"https://app.tnsvt.io":    true,
		"https://dashboard.tnsvt.io": true,
	}

	return func(c *gin.Context) {
		origin := c.GetHeader("Origin")
		if allowed[origin] {
			c.Writer.Header().Set("Access-Control-Allow-Origin", origin)
			c.Writer.Header().Set("Vary", "Origin")
		}

		c.Writer.Header().Set("Access-Control-Allow-Credentials", "true")
		c.Writer.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Request-ID, X-Tenant-ID, X-Signature, X-Timestamp")
		c.Writer.Header().Set("Access-Control-Expose-Headers", "X-Request-ID, X-RateLimit-Limit, X-RateLimit-Remaining")
		c.Writer.Header().Set("Access-Control-Max-Age", "600")

		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(http.StatusNoContent)
			return
		}

		c.Next()
	}
}

// ─── Metrics ───────────────────────────────────────────────────

func Metrics() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Next()
	}
}

// ─── Global Rate Limit ─────────────────────────────────────────

func GlobalRateLimit(rdb *redis.Client, maxPerMinute int, window time.Duration) gin.HandlerFunc {
	if maxPerMinute <= 0 {
		maxPerMinute = 100
	}

	return func(c *gin.Context) {
		identifier := c.ClientIP()
		ctx, cancel := context.WithTimeout(c.Request.Context(), 2*time.Second)
		defer cancel()

		key := "ratelimit:gateway:" + c.FullPath() + ":" + identifier
		count, err := rdb.Incr(ctx, key).Result()
		if err != nil {
			// Redis no disponible, fail open
			c.Next()
			return
		}

		if count == 1 {
			rdb.Expire(ctx, key, window)
		}

		c.Writer.Header().Set("X-RateLimit-Limit", strconv.Itoa(maxPerMinute))
		remaining := maxPerMinute - int(count)
		if remaining < 0 {
			remaining = 0
		}
		c.Writer.Header().Set("X-RateLimit-Remaining", strconv.Itoa(remaining))

		if count > int64(maxPerMinute) {
			c.Writer.Header().Set("Retry-After", strconv.Itoa(int(window.Seconds())))
			c.AbortWithStatusJSON(http.StatusTooManyRequests, gin.H{
				"error":      "rate limit exceeded",
				"limit":      maxPerMinute,
				"window_sec": int(window.Seconds()),
			})
			return
		}

		c.Next()
	}
}

// ─── JWT Validation ────────────────────────────────────────────

// JWTValidator valida tokens JWT
type JWTValidator struct {
	secret     []byte
	expiration time.Duration
}

// JWTClaims claims simplificados para el gateway
type JWTClaims struct {
	UserID   uuid.UUID `json:"uid"`
	TenantID uuid.UUID `json:"tid"`
	Email    string    `json:"email"`
	Role     string    `json:"role"`
	Type     string    `json:"type"`
	jwt.RegisteredClaims
}

// NewJWTValidator crea un nuevo validador
func NewJWTValidator(_ time.Duration) *JWTValidator {
	secret := getEnv("JWT_SECRET", "")
	if secret == "" {
		secret = "dev_secret_change_me_min_32_chars_abc"
	}
	return &JWTValidator{secret: []byte(secret)}
}

// Validate valida un JWT
func (v *JWTValidator) Validate(tokenString string) (*JWTClaims, error) {
	token, err := jwt.ParseWithClaims(tokenString, &JWTClaims{}, func(token *jwt.Token) (any, error) {
		if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, errors.New("invalid signing method")
		}
		return v.secret, nil
	})

	if err != nil {
		return nil, err
	}

	if claims, ok := token.Claims.(*JWTClaims); ok && token.Valid {
		return claims, nil
	}
	return nil, errors.New("invalid token")
}

// OptionalAuth valida el JWT si está presente, pero no lo requiere
func OptionalAuth(validator *JWTValidator) gin.HandlerFunc {
	return func(c *gin.Context) {
		authHeader := c.GetHeader("Authorization")
		if authHeader == "" || !strings.HasPrefix(authHeader, "Bearer ") {
			c.Next()
			return
		}

		token := strings.TrimPrefix(authHeader, "Bearer ")
		claims, err := validator.Validate(token)
		if err != nil {
			// Si el token es inválido pero estamos en OptionalAuth, rechazar
			// a menos que sea un endpoint público conocido
			if isPublicEndpoint(c.FullPath()) {
				c.Next()
				return
			}
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{
				"error": "invalid token",
				"code":  "AUTH_INVALID",
			})
			return
		}

		c.Set("user_id", claims.UserID.String())
		c.Set("tenant_id", claims.TenantID.String())
		c.Set("email", claims.Email)
		c.Set("role", claims.Role)
		c.Set("auth_type", claims.Type)

		c.Next()
	}
}

// RequireAuth middleware que requiere JWT válido
func RequireAuth(validator *JWTValidator) gin.HandlerFunc {
	return func(c *gin.Context) {
		authHeader := c.GetHeader("Authorization")
		if authHeader == "" || !strings.HasPrefix(authHeader, "Bearer ") {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{
				"error": "Authorization header required",
				"code":  "AUTH_MISSING",
			})
			return
		}

		token := strings.TrimPrefix(authHeader, "Bearer ")
		claims, err := validator.Validate(token)
		if err != nil {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{
				"error": "invalid or expired token",
				"code":  "AUTH_INVALID",
			})
			return
		}

		c.Set("user_id", claims.UserID.String())
		c.Set("tenant_id", claims.TenantID.String())
		c.Set("email", claims.Email)
		c.Set("role", claims.Role)

		c.Next()
	}
}

// ─── Circuit Breaker ───────────────────────────────────────────

// CircuitBreaker rechaza requests si el servicio está fallando
var (
	circuitStates = sync.Map{} // service name -> *breakerState
)

type breakerState struct {
	mu              sync.Mutex
	failures        int
	lastFailure     time.Time
	open            bool
	failureThresh   int
	recoveryTimeout time.Duration
}

func getBreaker(serviceName string) *breakerState {
	if v, ok := circuitStates.Load(serviceName); ok {
		return v.(*breakerState)
	}
	s := &breakerState{
		failureThresh:   5,
		recoveryTimeout: 30 * time.Second,
	}
	circuitStates.Store(serviceName, s)
	return s
}

// CircuitBreaker middleware que abre el circuito si un servicio falla
func CircuitBreaker(registry *proxy.ServiceRegistry, serviceName string) gin.HandlerFunc {
	return func(c *gin.Context) {
		state := getBreaker(serviceName)

		state.mu.Lock()
		if state.open {
			if time.Since(state.lastFailure) > state.recoveryTimeout {
				// Half-open: probar de nuevo
				state.open = false
				state.failures = 0
			} else {
				state.mu.Unlock()
				c.AbortWithStatusJSON(http.StatusServiceUnavailable, gin.H{
					"error":   "service circuit breaker open",
					"service": serviceName,
					"retry_after_sec": int(state.recoveryTimeout.Seconds()),
				})
				return
			}
		}
		state.mu.Unlock()

		c.Next()

		// Si el request falló, incrementar contador
		if c.Writer.Status() >= 500 {
			state.mu.Lock()
			state.failures++
			state.lastFailure = time.Now()
			if state.failures >= state.failureThresh {
				state.open = true
			}
			state.mu.Unlock()
		} else if c.Writer.Status() < 400 {
			// Reset en éxito
			state.mu.Lock()
			state.failures = 0
			state.mu.Unlock()
		}
	}
}

// ─── Helpers ───────────────────────────────────────────────────

func isPublicEndpoint(path string) bool {
	publicPaths := map[string]bool{
		"/api/v1/auth/login":     true,
		"/api/v1/auth/register":  true,
		"/api/v1/auth/refresh":   true,
		"/":                      true,
		"/health":                true,
		"/health/live":           true,
		"/health/ready":          true,
		"/metrics":               true,
	}
	return publicPaths[path]
}

func getEnv(key, def string) string {
	if v := getEnvImpl(key); v != "" {
		return v
	}
	return def
}