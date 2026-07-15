// Package handlers contiene los HTTP handlers del risk-engine.
package handlers

import (
	"context"
	"errors"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/nats-io/nats.go"
	"github.com/redis/go-redis/v9"

	"github.com/tnsvt/risk-engine/internal/models"
	"github.com/tnsvt/risk-engine/internal/repository"
	"github.com/tnsvt/risk-engine/internal/service"
)

// ─── Middlewares ──────────────────────────────────────────────

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

func AccessLog(log interface {
	Info(string, ...any)
	Warn(string, ...any)
	Error(string, error, ...any)
}) gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()
		c.Next()
		latency := time.Since(start)
		fields := []any{
			"method", c.Request.Method,
			"path", c.Request.URL.Path,
			"status", c.Writer.Status(),
			"latency_ms", latency.Milliseconds(),
			"ip", c.ClientIP(),
			"request_id", c.GetString("request_id"),
		}
		if c.Writer.Status() >= 500 {
			log.Error("Request error", errors.New(c.Errors.String()), fields...)
		} else if c.Writer.Status() >= 400 {
			log.Warn("Request warning", fields...)
		} else {
			log.Info("Request", fields...)
		}
	}
}

func CORS() gin.HandlerFunc {
	allowed := map[string]bool{
		"http://localhost:3000": true,
		"http://localhost:8501": true,
		"tauri://localhost":     true,
	}
	return func(c *gin.Context) {
		origin := c.GetHeader("Origin")
		if allowed[origin] {
			c.Writer.Header().Set("Access-Control-Allow-Origin", origin)
			c.Writer.Header().Set("Vary", "Origin")
		}
		c.Writer.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Request-ID, X-Tenant-ID")
		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(http.StatusNoContent)
			return
		}
		c.Next()
	}
}

// ─── Risk Handler ─────────────────────────────────────────────

// RiskHandler maneja endpoints de risk
type RiskHandler struct {
	service *service.RiskService
	log     interface {
		Info(string, ...any)
		Warn(string, ...any)
		Error(string, error, ...any)
	}
}

// NewRiskHandler crea el handler
func NewRiskHandler(s *service.RiskService, log interface {
	Info(string, ...any)
	Warn(string, ...any)
	Error(string, error, ...any)
}) *RiskHandler {
	return &RiskHandler{service: s, log: log}
}

// Evaluate POST /api/v1/risk/evaluate
func (h *RiskHandler) Evaluate(c *gin.Context) {
	var req models.EvaluateRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request", "details": err.Error()})
		return
	}

	if req.Signal.TenantID == uuid.Nil {
		if t := c.GetHeader("X-Tenant-ID"); t != "" {
			if u, err := uuid.Parse(t); err == nil {
				req.Signal.TenantID = u
			}
		}
		if req.Signal.TenantID == uuid.Nil {
			req.Signal.TenantID = uuid.MustParse("00000000-0000-0000-0000-000000000001")
		}
	}

	ev, err := h.service.EvaluateSignal(c.Request.Context(), &req.Signal)
	if err != nil {
		h.log.Error("Evaluation failed", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "evaluation failed"})
		return
	}

	status := http.StatusOK
	if ev.Decision == models.DecisionRejected {
		status = http.StatusUnprocessableEntity
	}

	c.JSON(status, ev)
}

// GetExposure GET /api/v1/risk/exposure
func (h *RiskHandler) GetExposure(c *gin.Context) {
	tenantID := getTenantID(c)

	exposure, err := h.service.GetExposure(c.Request.Context(), tenantID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"tenant_id":          tenantID,
		"exposure_per_symbol": exposure,
		"total_symbols":      len(exposure),
	})
}

// GetLimits GET /api/v1/risk/limits
func (h *RiskHandler) GetLimits(c *gin.Context) {
	tenantID := getTenantID(c)

	limits, err := h.service.GetLimits(c.Request.Context(), tenantID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
		return
	}

	c.JSON(http.StatusOK, limits)
}

// UpdateLimits PUT /api/v1/risk/limits
func (h *RiskHandler) UpdateLimits(c *gin.Context) {
	var req models.UpdateLimitsRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request"})
		return
	}

	tenantID := getTenantID(c)
	limits, err := h.service.UpdateLimits(c.Request.Context(), tenantID, &req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "update failed"})
		return
	}

	c.JSON(http.StatusOK, limits)
}

// Stats GET /api/v1/risk/stats
func (h *RiskHandler) Stats(c *gin.Context) {
	tenantID := getTenantID(c)

	stats, err := h.service.GetStats(c.Request.Context(), tenantID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
		return
	}

	c.JSON(http.StatusOK, stats)
}

// ListPositions GET /api/v1/risk/positions
func (h *RiskHandler) ListPositions(c *gin.Context) {
	tenantID := getTenantID(c)

	positions, err := h.service.ListPositions(c.Request.Context(), tenantID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"tenant_id": tenantID,
		"positions": positions,
		"count":     len(positions),
	})
}

// UpdatePositionPrice POST /api/v1/risk/positions/update
func (h *RiskHandler) UpdatePositionPrice(c *gin.Context) {
	var req models.UpdatePriceRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request"})
		return
	}

	if err := h.service.UpdatePositionPrice(c.Request.Context(), &req); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "update failed"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "updated"})
}

// TradeOpened POST /api/v1/risk/trade-opened
func (h *RiskHandler) TradeOpened(c *gin.Context) {
	var req models.TradeOpenedRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request"})
		return
	}

	tenantID := getTenantID(c)
	req.SignalID = req.SignalID // viene en payload

	pos, err := h.service.TradeOpened(c.Request.Context(), &req)
	if err != nil {
		h.log.Error("TradeOpened failed", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
		return
	}
	pos.TenantID = tenantID

	c.JSON(http.StatusCreated, pos)
}

// TradeClosed POST /api/v1/risk/trade-closed
func (h *RiskHandler) TradeClosed(c *gin.Context) {
	var req models.TradeClosedRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request"})
		return
	}

	if err := h.service.TradeClosed(c.Request.Context(), &req); err != nil {
		h.log.Error("TradeClosed failed", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "closed"})
}

// ─── Helpers ──────────────────────────────────────────────────

func getTenantID(c *gin.Context) uuid.UUID {
	if t := c.GetHeader("X-Tenant-ID"); t != "" {
		if u, err := uuid.Parse(t); err == nil {
			return u
		}
	}
	if t := c.GetString("tenant_id"); t != "" {
		if u, err := uuid.Parse(t); err == nil {
			return u
		}
	}
	return uuid.MustParse("00000000-0000-0000-0000-000000000001")
}

// ─── Health ───────────────────────────────────────────────────

func Health(repo repository.RiskRepository) gin.HandlerFunc {
	return func(c *gin.Context) {
		if err := repo.Ping(c.Request.Context()); err != nil {
			c.JSON(http.StatusServiceUnavailable, gin.H{"status": "degraded"})
			return
		}
		c.JSON(http.StatusOK, gin.H{"status": "ok", "service": "risk-engine", "version": "0.1.0"})
	}
}

func HealthReady(repo repository.RiskRepository, rdb *redis.Client, natsConn *nats.Conn) gin.HandlerFunc {
	return func(c *gin.Context) {
		checks := gin.H{}
		ready := true

		if err := repo.Ping(c.Request.Context()); err != nil {
			checks["db"] = "down"
			ready = false
		} else {
			checks["db"] = "up"
		}

		if rdb != nil {
			if err := rdb.Ping(c.Request.Context()).Err(); err != nil {
				checks["redis"] = "down"
			} else {
				checks["redis"] = "up"
			}
		}

		if natsConn != nil {
			if natsConn.Status() != nats.CONNECTED {
				checks["nats"] = "down"
				ready = false
			} else {
				checks["nats"] = "up"
			}
		}

		if !ready {
			c.JSON(http.StatusServiceUnavailable, gin.H{"status": "not_ready", "checks": checks})
			return
		}
		c.JSON(http.StatusOK, gin.H{"status": "ready", "checks": checks})
	}
}

var _ = pgxpool.Pool{}
var _ = context.Background()