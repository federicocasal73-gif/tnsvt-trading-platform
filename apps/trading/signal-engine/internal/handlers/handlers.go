// Package handlers contiene los HTTP handlers del signal-engine.
package handlers

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/nats-io/nats.go"
	"github.com/redis/go-redis/v9"

	"github.com/tnsvt/signal-engine/internal/models"
	"github.com/tnsvt/signal-engine/internal/repository"
	"github.com/tnsvt/signal-engine/internal/service"
)

// ─── Middlewares (local) ─────────────────────────────────────

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

func AccessLog(log interface{ Info(string, ...any); Warn(string, ...any); Error(string, error, ...any) }) gin.HandlerFunc {
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
		if status := c.Writer.Status(); status >= 500 {
			log.Error("Request error", errors.New(c.Errors.String()), fields...)
		} else if status >= 400 {
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

func Metrics() gin.HandlerFunc { return func(c *gin.Context) { c.Next() } }

// IngestAPIKeyMiddleware valida el API key para webhooks internos
func IngestAPIKeyMiddleware(apiKey string) gin.HandlerFunc {
	return func(c *gin.Context) {
		if apiKey == "" {
			c.AbortWithStatusJSON(http.StatusServiceUnavailable, gin.H{
				"error": "ingest endpoint disabled (no API key configured)",
			})
			return
		}
		provided := c.GetHeader("X-API-Key")
		if provided == "" {
			provided = c.GetHeader("X-Ingest-Key")
		}
		if provided != apiKey {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{
				"error": "invalid or missing X-API-Key header",
			})
			return
		}
		c.Next()
	}
}

// ─── Signal Handler ───────────────────────────────────────────

// SignalHandler maneja endpoints de signals
type SignalHandler struct {
	service *service.SignalService
	log     interface {
		Info(string, ...any)
		Warn(string, ...any)
		Error(string, error, ...any)
	}
}

// NewSignalHandler crea el handler
func NewSignalHandler(s *service.SignalService, log interface {
	Info(string, ...any)
	Warn(string, ...any)
	Error(string, error, ...any)
}) *SignalHandler {
	return &SignalHandler{service: s, log: log}
}

// Submit POST /api/v1/signals
func (h *SignalHandler) Submit(c *gin.Context) {
	var req models.SubmitSignalRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "invalid request body",
			"details": err.Error(),
		})
		return
	}

	// Get tenant from header (passed by api-gateway from JWT)
	tenantStr := c.GetHeader("X-Tenant-ID")
	if tenantStr != "" {
		if t, err := uuid.Parse(tenantStr); err == nil {
			req.TenantID = t
		}
	}
	if req.TenantID == uuid.Nil {
		req.TenantID = uuid.MustParse("00000000-0000-0000-0000-000000000001") // Default tenant
	}

	signal, err := h.service.SubmitSignal(c.Request.Context(), &req)
	if err != nil {
		switch {
		case errors.Is(err, service.ErrDuplicate):
			c.JSON(http.StatusConflict, gin.H{
				"error": "duplicate signal",
				"code":  "DUPLICATE",
			})
		case errors.Is(err, service.ErrInvalidFormat):
			c.JSON(http.StatusBadRequest, gin.H{
				"error":   "invalid signal format",
				"details": err.Error(),
			})
		case errors.Is(err, service.ErrExpired):
			c.JSON(http.StatusBadRequest, gin.H{
				"error": "signal expired",
			})
		default:
			h.log.Error("Submit signal failed", err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
		}
		return
	}

	status := http.StatusCreated
	if signal.Status == models.StatusRejected {
		status = http.StatusUnprocessableEntity
	}

	c.JSON(status, signal)
}

// Get GET /api/v1/signals/:id
func (h *SignalHandler) Get(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid ID format"})
		return
	}

	signal, err := h.service.GetByID(c.Request.Context(), id)
	if err != nil {
		if errors.Is(err, repository.ErrNotFound) {
			c.JSON(http.StatusNotFound, gin.H{"error": "signal not found"})
			return
		}
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
		return
	}

	c.JSON(http.StatusOK, signal)
}

// List GET /api/v1/signals
func (h *SignalHandler) List(c *gin.Context) {
	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "20"))
	offset, _ := strconv.Atoi(c.DefaultQuery("offset", "0"))

	var tenantID *uuid.UUID
	if t := c.GetHeader("X-Tenant-ID"); t != "" {
		if u, err := uuid.Parse(t); err == nil {
			tenantID = &u
		}
	}

	signals, total, err := h.service.List(c.Request.Context(), tenantID, limit, offset)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
		return
	}

	c.JSON(http.StatusOK, models.ListResponse{
		Signals: signals,
		Total:   total,
		Limit:   limit,
		Offset:  offset,
	})
}

// Parse POST /api/v1/signals/parse
func (h *SignalHandler) Parse(c *gin.Context) {
	var req models.ParseRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request", "details": err.Error()})
		return
	}

	signal, err := h.service.ParsePreview(c.Request.Context(), req.Text)
	if err != nil {
		c.JSON(http.StatusUnprocessableEntity, gin.H{
			"error":   "could not parse text",
			"details": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"parsed":    signal,
		"raw_text":  req.Text,
	})
}

// Stream GET /api/v1/signals/stream (SSE)
func (h *SignalHandler) Stream(c *gin.Context) {
	c.Writer.Header().Set("Content-Type", "text/event-stream")
	c.Writer.Header().Set("Cache-Control", "no-cache")
	c.Writer.Header().Set("Connection", "keep-alive")
	c.Writer.Header().Set("X-Accel-Buffering", "no")

	ctx, cancel := context.WithCancel(c.Request.Context())
	defer cancel()

	ch, err := h.service.Stream(ctx)
	if err != nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": err.Error()})
		return
	}

	c.Stream(func(w http.ResponseWriter) bool {
		select {
		case signal, ok := <-ch:
			if !ok {
				return false
			}
			data, _ := json.Marshal(signal)
			fmt.Fprintf(w, "event: signal\ndata: %s\n\n", data)
			return true
		case <-ctx.Done():
			return false
		case <-time.After(30 * time.Second):
			// Keepalive
			fmt.Fprintf(w, ": keepalive\n\n")
			return true
		}
	})
}

// Stats GET /api/v1/signals/stats
func (h *SignalHandler) Stats(c *gin.Context) {
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

// IngestTelegram POST /internal/ingest/telegram (webhook desde telegram-bridge)
func (h *SignalHandler) IngestTelegram(c *gin.Context) {
	var raw models.RawSignal
	if err := c.ShouldBindJSON(&raw); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid raw signal", "details": err.Error()})
		return
	}

	// Trim y validar
	raw.Text = strings.TrimSpace(raw.Text)
	if raw.Text == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "empty text"})
		return
	}

	signal, err := h.service.SubmitRawSignal(c.Request.Context(), &raw)
	if err != nil {
		if errors.Is(err, service.ErrDuplicate) {
			c.JSON(http.StatusOK, gin.H{
				"status":   "duplicate",
				"skipped":  true,
				"source":   "telegram",
				"channel":  raw.ChannelName,
			})
			return
		}
		if signal != nil && signal.Status == models.StatusRejected {
			c.JSON(http.StatusUnprocessableEntity, gin.H{
				"status":    "rejected",
				"reason":    signal.RejectReason,
				"details":   signal.RejectDetails,
				"raw_text":  raw.Text,
			})
			return
		}
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, gin.H{
		"status":  "accepted",
		"signal":  signal,
		"channel": raw.ChannelName,
	})
}

// ─── Health ────────────────────────────────────────────────────

func Health(repo repository.SignalRepository) gin.HandlerFunc {
	return func(c *gin.Context) {
		if err := repo.Ping(c.Request.Context()); err != nil {
			c.JSON(http.StatusServiceUnavailable, gin.H{"status": "degraded"})
			return
		}
		c.JSON(http.StatusOK, gin.H{
			"status":  "ok",
			"service": "signal-engine",
			"version": "0.1.0",
		})
	}
}

func HealthReady(repo repository.SignalRepository, rdb *redis.Client, natsConn *nats.Conn) gin.HandlerFunc {
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