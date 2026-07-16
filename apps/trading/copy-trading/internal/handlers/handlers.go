// Package handlers contiene los HTTP handlers del copy-trading.
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

	"github.com/tnsvt/copy-trading/internal/models"
	"github.com/tnsvt/copy-trading/internal/repository"
	"github.com/tnsvt/copy-trading/internal/service"
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
		c.Writer.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Request-ID, X-Tenant-ID")
		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(http.StatusNoContent)
			return
		}
		c.Next()
	}
}

// ─── Groups Handler ──────────────────────────────────────────

// GroupsHandler CRUD de grupos
type GroupsHandler struct {
	service *service.CopyTradingService
	log     interface {
		Info(string, ...any)
		Warn(string, ...any)
		Error(string, error, ...any)
	}
}

// NewGroupsHandler crea el handler
func NewGroupsHandler(s *service.CopyTradingService, log interface {
	Info(string, ...any)
	Warn(string, ...any)
	Error(string, error, ...any)
}) *GroupsHandler {
	return &GroupsHandler{service: s, log: log}
}

// List GET /api/v1/copy/groups
func (h *GroupsHandler) List(c *gin.Context) {
	tenantID := getTenantID(c)
	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "20"))
	offset, _ := strconv.Atoi(c.DefaultQuery("offset", "0"))

	groups, total, err := h.service.ListGroups(c.Request.Context(), tenantID, limit, offset)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
		return
	}

	c.JSON(http.StatusOK, models.ListGroupsResponse{
		Groups: groups,
		Total:  total,
		Limit:  limit,
		Offset: offset,
	})
}

// Create POST /api/v1/copy/groups
func (h *GroupsHandler) Create(c *gin.Context) {
	var req models.CreateGroupRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request", "details": err.Error()})
		return
	}

	tenantID := getTenantID(c)
	group, err := h.service.CreateGroup(c.Request.Context(), tenantID, &req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
		return
	}

	c.JSON(http.StatusCreated, group)
}

// Get GET /api/v1/copy/groups/:id
func (h *GroupsHandler) Get(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid ID"})
		return
	}

	group, err := h.service.GetGroup(c.Request.Context(), id)
	if err != nil {
		if errors.Is(err, repository.ErrNotFound) {
			c.JSON(http.StatusNotFound, gin.H{"error": "group not found"})
			return
		}
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
		return
	}

	c.JSON(http.StatusOK, group)
}

// Update PUT /api/v1/copy/groups/:id
func (h *GroupsHandler) Update(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid ID"})
		return
	}

	var req models.UpdateGroupRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request"})
		return
	}

	group, err := h.service.UpdateGroup(c.Request.Context(), id, &req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
		return
	}

	c.JSON(http.StatusOK, group)
}

// Delete DELETE /api/v1/copy/groups/:id
func (h *GroupsHandler) Delete(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid ID"})
		return
	}

	if err := h.service.DeleteGroup(c.Request.Context(), id); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "deleted"})
}

// ManualReplicate POST /api/v1/copy/replicate/:signal_id
func (h *GroupsHandler) ManualReplicate(c *gin.Context) {
	signalID, err := uuid.Parse(c.Param("signal_id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid signal ID"})
		return
	}

	var signal models.SignalInput
	if err := c.ShouldBindJSON(&signal); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request"})
		return
	}

	signal.ID = signalID
	tenantID := getTenantID(c)
	if signal.TenantID == uuid.Nil {
		signal.TenantID = tenantID
	}

	ctx, cancel := context.WithTimeout(c.Request.Context(), 90*time.Second)
	defer cancel()

	if err := h.service.ReplicateSignal(ctx, &signal); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusAccepted, gin.H{
		"status": "replication_started",
		"signal_id": signalID,
	})
}

// ─── Accounts Handler ────────────────────────────────────────

// AccountsHandler CRUD de cuentas
type AccountsHandler struct {
	service *service.CopyTradingService
	log     interface {
		Info(string, ...any)
		Warn(string, ...any)
		Error(string, error, ...any)
	}
}

// NewAccountsHandler crea el handler
func NewAccountsHandler(s *service.CopyTradingService, log interface {
	Info(string, ...any)
	Warn(string, ...any)
	Error(string, error, ...any)
}) *AccountsHandler {
	return &AccountsHandler{service: s, log: log}
}

// List GET /api/v1/copy/groups/:id/accounts
func (h *AccountsHandler) List(c *gin.Context) {
	groupID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid group ID"})
		return
	}

	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "20"))
	offset, _ := strconv.Atoi(c.DefaultQuery("offset", "0"))

	accounts, total, err := h.service.ListAccountsByGroup(c.Request.Context(), groupID, limit, offset)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
		return
	}

	c.JSON(http.StatusOK, models.ListAccountsResponse{
		Accounts: accounts,
		Total:    total,
		Limit:    limit,
		Offset:   offset,
	})
}

// Create POST /api/v1/copy/groups/:id/accounts
func (h *AccountsHandler) Create(c *gin.Context) {
	groupID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid group ID"})
		return
	}

	var req models.CreateAccountRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request", "details": err.Error()})
		return
	}

	tenantID := getTenantID(c)
	account, err := h.service.CreateAccount(c.Request.Context(), tenantID, groupID, &req)
	if err != nil {
		if errors.Is(err, repository.ErrDuplicate) {
			c.JSON(http.StatusConflict, gin.H{"error": "account already exists in this group"})
			return
		}
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
		return
	}

	c.JSON(http.StatusCreated, account)
}

// Get GET /api/v1/copy/accounts/:id
func (h *AccountsHandler) Get(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid ID"})
		return
	}

	account, err := h.service.GetAccount(c.Request.Context(), id)
	if err != nil {
		if errors.Is(err, repository.ErrNotFound) {
			c.JSON(http.StatusNotFound, gin.H{"error": "account not found"})
			return
		}
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
		return
	}

	c.JSON(http.StatusOK, account)
}

// Update PUT /api/v1/copy/accounts/:id
func (h *AccountsHandler) Update(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid ID"})
		return
	}

	var req models.UpdateAccountRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request"})
		return
	}

	account, err := h.service.UpdateAccount(c.Request.Context(), id, &req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
		return
	}

	c.JSON(http.StatusOK, account)
}

// Delete DELETE /api/v1/copy/accounts/:id
func (h *AccountsHandler) Delete(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid ID"})
		return
	}

	if err := h.service.DeleteAccount(c.Request.Context(), id); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "deleted"})
}

// ─── Jobs Handler ─────────────────────────────────────────────

// JobsHandler historial y stats
type JobsHandler struct {
	service *service.CopyTradingService
	log     interface {
		Info(string, ...any)
		Warn(string, ...any)
		Error(string, error, ...any)
	}
}

// NewJobsHandler crea el handler
func NewJobsHandler(s *service.CopyTradingService, log interface {
	Info(string, ...any)
	Warn(string, ...any)
	Error(string, error, ...any)
}) *JobsHandler {
	return &JobsHandler{service: s, log: log}
}

// List GET /api/v1/copy/jobs
func (h *JobsHandler) List(c *gin.Context) {
	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "20"))
	offset, _ := strconv.Atoi(c.DefaultQuery("offset", "0"))

	var tenantID *uuid.UUID
	if t := c.GetHeader("X-Tenant-ID"); t != "" {
		if u, err := uuid.Parse(t); err == nil {
			tenantID = &u
		}
	}

	var groupID, accountID *uuid.UUID
	if g := c.Query("group_id"); g != "" {
		if u, err := uuid.Parse(g); err == nil {
			groupID = &u
		}
	}
	if a := c.Query("account_id"); a != "" {
		if u, err := uuid.Parse(a); err == nil {
			accountID = &u
		}
	}

	var status *models.JobStatus
	if s := c.Query("status"); s != "" {
		js := models.JobStatus(s)
		status = &js
	}

	jobs, total, err := h.service.ListJobs(c.Request.Context(), tenantID, groupID, accountID, status, limit, offset)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
		return
	}

	c.JSON(http.StatusOK, models.ListJobsResponse{
		Jobs:   jobs,
		Total:  total,
		Limit:  limit,
		Offset: offset,
	})
}

// Get GET /api/v1/copy/jobs/:id
func (h *JobsHandler) Get(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid ID"})
		return
	}

	job, err := h.service.GetJob(c.Request.Context(), id)
	if err != nil {
		if errors.Is(err, repository.ErrNotFound) {
			c.JSON(http.StatusNotFound, gin.H{"error": "job not found"})
			return
		}
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
		return
	}

	c.JSON(http.StatusOK, job)
}

// Stats GET /api/v1/copy/stats
func (h *JobsHandler) Stats(c *gin.Context) {
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

// ─── Health ────────────────────────────────────────────────────

func Health(repo repository.CopyTradingRepository) gin.HandlerFunc {
	return func(c *gin.Context) {
		if err := repo.Ping(c.Request.Context()); err != nil {
			c.JSON(http.StatusServiceUnavailable, gin.H{"status": "degraded"})
			return
		}
		c.JSON(http.StatusOK, gin.H{"status": "ok", "service": "copy-trading", "version": "0.1.0"})
	}
}

func HealthReady(repo repository.CopyTradingRepository, rdb *redis.Client, natsConn *nats.Conn) gin.HandlerFunc {
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