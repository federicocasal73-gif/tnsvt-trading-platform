// Package handlers contiene handlers HTTP del API Gateway.
package handlers

import (
	"context"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/nats-io/nats.go"
	"github.com/redis/go-redis/v9"

	"github.com/tnsvt/api-gateway/internal/proxy"
)

// HealthHandler maneja los endpoints de health check
type HealthHandler struct {
	registry  *proxy.ServiceRegistry
	redis     *redis.Client
	natsConn  *nats.Conn
}

// NewHealthHandler crea el handler
func NewHealthHandler(registry *proxy.ServiceRegistry, redis *redis.Client, natsConn *nats.Conn) *HealthHandler {
	return &HealthHandler{
		registry: registry,
		redis:    redis,
		natsConn: natsConn,
	}
}

// Health GET /health (basic - solo verifica que el gateway está vivo)
func (h *HealthHandler) Health(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status":    "ok",
		"service":   "api-gateway",
		"version":   "0.1.0",
		"phase":     "1-mvp",
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	})
}

// HealthFull GET /health/full (verifica todas las dependencias)
func (h *HealthHandler) HealthFull(c *gin.Context) {
	ctx, cancel := context.WithTimeout(c.Request.Context(), 5*time.Second)
	defer cancel()

	checks := gin.H{}
	overallOK := true

	// Check Redis
	if h.redis != nil {
		if err := h.redis.Ping(ctx).Err(); err != nil {
			checks["redis"] = gin.H{"status": "down", "error": err.Error()}
			overallOK = false
		} else {
			checks["redis"] = gin.H{"status": "up"}
		}
	} else {
		checks["redis"] = gin.H{"status": "not_configured"}
	}

	// Check NATS
	if h.natsConn != nil {
		if h.natsConn.Status() != nats.CONNECTED {
			checks["nats"] = gin.H{"status": "down", "state": h.natsConn.Status().String()}
			overallOK = false
		} else {
			checks["nats"] = gin.H{"status": "up"}
		}
	} else {
		checks["nats"] = gin.H{"status": "not_configured"}
	}

	// Check all microservices via registry
	allHealthy, servicesStatus := h.registry.AllHealthy()
	servicesMap := gin.H{}
	for name, healthy := range servicesStatus {
		servicesMap[name] = gin.H{"status": boolToStatus(healthy)}
	}
	checks["services"] = servicesMap

	if !allHealthy {
		overallOK = false
	}

	status := http.StatusOK
	if !overallOK {
		status = http.StatusServiceUnavailable
	}

	c.JSON(status, gin.H{
		"status":    boolToStatus(overallOK),
		"service":   "api-gateway",
		"version":   "0.1.0",
		"phase":     "1-mvp",
		"checks":    checks,
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	})
}

func boolToStatus(b bool) string {
	if b {
		return "ok"
	}
	return "degraded"
}