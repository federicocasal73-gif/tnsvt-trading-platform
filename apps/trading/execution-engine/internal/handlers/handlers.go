// Package handlers contiene los HTTP handlers del execution-engine.
package handlers

import (
	"context"
	"errors"
	"net/http"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/nats-io/nats.go"
	"github.com/redis/go-redis/v9"

	"github.com/tnsvt/execution-engine/internal/broker"
	"github.com/tnsvt/execution-engine/internal/models"
	"github.com/tnsvt/execution-engine/internal/repository"
	"github.com/tnsvt/execution-engine/internal/service"
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
		c.Writer.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Request-ID, X-Tenant-ID")
		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(http.StatusNoContent)
			return
		}
		c.Next()
	}
}

// ─── Execution Handler ────────────────────────────────────────

// ExecutionHandler maneja endpoints de executions
type ExecutionHandler struct {
	service *service.ExecutionService
	log     interface {
		Info(string, ...any)
		Warn(string, ...any)
		Error(string, error, ...any)
	}
}

// NewExecutionHandler crea el handler
func NewExecutionHandler(s *service.ExecutionService, log interface {
	Info(string, ...any)
	Warn(string, ...any)
	Error(string, error, ...any)
}) *ExecutionHandler {
	return &ExecutionHandler{service: s, log: log}
}

// Execute POST /api/v1/executions
func (h *ExecutionHandler) Execute(c *gin.Context) {
	var req models.ExecuteRequest
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

	if req.DryRun {
		c.JSON(http.StatusOK, gin.H{
			"status": "dry_run",
			"signal": req.Signal,
		})
		return
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), 60*time.Second)
	defer cancel()

	exec, err := h.service.ExecuteSignal(ctx, &req.Signal)
	if err != nil {
		if errors.Is(err, service.ErrNoBroker) || errors.Is(err, service.ErrExecutionFailed) {
			c.JSON(http.StatusBadGateway, gin.H{
				"error":   "execution failed",
				"details": err.Error(),
			})
			return
		}
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
		return
	}

	status := http.StatusOK
	if exec.Status == models.ExecStatusFailed {
		status = http.StatusUnprocessableEntity
	}
	c.JSON(status, exec)
}

// Get GET /api/v1/executions/:id
func (h *ExecutionHandler) Get(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid ID"})
		return
	}

	exec, err := h.service.GetByID(c.Request.Context(), id)
	if err != nil {
		if errors.Is(err, repository.ErrNotFound) {
			c.JSON(http.StatusNotFound, gin.H{"error": "execution not found"})
			return
		}
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
		return
	}

	c.JSON(http.StatusOK, exec)
}

// List GET /api/v1/executions
func (h *ExecutionHandler) List(c *gin.Context) {
	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "20"))
	offset, _ := strconv.Atoi(c.DefaultQuery("offset", "0"))

	var tenantID *uuid.UUID
	if t := c.GetHeader("X-Tenant-ID"); t != "" {
		if u, err := uuid.Parse(t); err == nil {
			tenantID = &u
		}
	}

	var status *models.ExecutionStatus
	if s := c.Query("status"); s != "" {
		es := models.ExecutionStatus(s)
		status = &es
	}

	var broker *models.BrokerName
	if b := c.Query("broker"); b != "" {
		bn := models.BrokerName(b)
		broker = &bn
	}

	execs, total, err := h.service.List(c.Request.Context(), tenantID, status, broker, limit, offset)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
		return
	}

	c.JSON(http.StatusOK, models.ListResponse{
		Executions: execs,
		Total:      total,
		Limit:      limit,
		Offset:     offset,
	})
}

// Cancel POST /api/v1/executions/:id/cancel
func (h *ExecutionHandler) Cancel(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid ID"})
		return
	}

	var req models.CancelRequest
	c.ShouldBindJSON(&req)

	exec, err := h.service.Cancel(c.Request.Context(), id, req.Reason)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, exec)
}

// Stats GET /api/v1/executions/stats
func (h *ExecutionHandler) Stats(c *gin.Context) {
	var tenantID *uuid.UUID
	if t := c.GetHeader("X-Tenant-ID"); t != "" {
		if u, err := uuid.Parse(t); err == nil {
			tenantID = &u
		}
	}

	stats, err := h.service.Stats(c.Request.Context(), tenantID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
		return
	}

	c.JSON(http.StatusOK, stats)
}

// ─── Health ────────────────────────────────────────────────────

func Health(repo repository.ExecutionRepository) gin.HandlerFunc {
	return func(c *gin.Context) {
		if err := repo.Ping(c.Request.Context()); err != nil {
			c.JSON(http.StatusServiceUnavailable, gin.H{"status": "degraded"})
			return
		}
		c.JSON(http.StatusOK, gin.H{"status": "ok", "service": "execution-engine", "version": "0.1.0"})
	}
}

func HealthReady(repo repository.ExecutionRepository, rdb *redis.Client, natsConn *nats.Conn, factory *broker.Factory) gin.HandlerFunc {
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

		// Brokers
		brokerChecks := factory.HealthCheck(c.Request.Context())
		allBrokersOK := true
		for _, ok := range brokerChecks {
			if !ok {
				allBrokersOK = false
			}
		}
		checks["brokers"] = brokerChecks
		if !allBrokersOK {
			ready = false
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