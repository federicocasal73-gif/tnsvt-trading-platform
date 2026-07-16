// Package handlers expone la API HTTP del user-service.
package handlers

import (
	"net/http"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"

	"github.com/tnsvt/user-service/internal/models"
	"github.com/tnsvt/user-service/internal/repository"
	sharedlogging "github.com/tnsvt/shared-go/logging"
)

// Handler maneja endpoints de perfil
type Handler struct {
	repo repository.UserRepository
	log  *sharedlogging.Logger
}

// New crea el handler
func New(repo repository.UserRepository, log *sharedlogging.Logger) *Handler {
	return &Handler{repo: repo, log: log}
}

// GetProfile GET /api/v1/users/:id/profile
func (h *Handler) GetProfile(c *gin.Context) {
	userID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid user ID"})
		return
	}

	profile, err := h.repo.GetProfile(c.Request.Context(), userID)
	if err == repository.ErrNotFound {
		c.JSON(http.StatusNotFound, gin.H{"error": "profile not found"})
		return
	}
	if err != nil {
		h.log.Error("GetProfile failed", err, "user_id", userID)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
		return
	}

	c.JSON(http.StatusOK, profile)
}

// CreateProfile POST /api/v1/users/:id/profile
func (h *Handler) CreateProfile(c *gin.Context) {
	userID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid user ID"})
		return
	}

	var req models.CreateProfileRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request", "details": err.Error()})
		return
	}

	if req.FullName == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "full_name is required"})
		return
	}

	if req.Timezone == "" {
		req.Timezone = "UTC"
	}
	if req.Language == "" {
		req.Language = "en"
	}

	tenantID := getTenantID(c)

	profile := &models.UserProfile{
		UserID:    userID,
		TenantID:  tenantID,
		FullName:  req.FullName,
		AvatarURL: req.AvatarURL,
		Timezone:  req.Timezone,
		Language:  req.Language,
		Phone:     req.Phone,
		CreatedAt: time.Now(),
		UpdatedAt: time.Now(),
	}

	if err := h.repo.UpsertProfile(c.Request.Context(), profile); err != nil {
		h.log.Error("UpsertProfile failed", err, "user_id", userID)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
		return
	}

	c.JSON(http.StatusCreated, profile)
}

// UpdateProfile PUT /api/v1/users/:id/profile
func (h *Handler) UpdateProfile(c *gin.Context) {
	userID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid user ID"})
		return
	}

	var req models.UpdateProfileRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request", "details": err.Error()})
		return
	}

	existing, err := h.repo.GetProfile(c.Request.Context(), userID)
	if err == repository.ErrNotFound {
		c.JSON(http.StatusNotFound, gin.H{"error": "profile not found"})
		return
	}
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
		return
	}

	if req.FullName != nil {
		existing.FullName = *req.FullName
	}
	if req.AvatarURL != nil {
		existing.AvatarURL = *req.AvatarURL
	}
	if req.Timezone != nil {
		existing.Timezone = *req.Timezone
	}
	if req.Language != nil {
		existing.Language = *req.Language
	}
	if req.Phone != nil {
		existing.Phone = *req.Phone
	}
	if req.Preferences != nil {
		existing.Preferences = mergeMaps(existing.Preferences, req.Preferences)
	}
	if req.NotifySettings != nil {
		existing.NotifySettings = mergeMaps(existing.NotifySettings, req.NotifySettings)
	}

	if err := h.repo.UpsertProfile(c.Request.Context(), existing); err != nil {
		h.log.Error("UpdateProfile failed", err, "user_id", userID)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
		return
	}

	c.JSON(http.StatusOK, existing)
}

func getTenantID(c *gin.Context) uuid.UUID {
	if t := c.GetHeader("X-Tenant-ID"); t != "" {
		if u, err := uuid.Parse(t); err == nil {
			return u
		}
	}
	return uuid.MustParse("00000000-0000-0000-0000-000000000001")
}

func mergeMaps(a, b map[string]interface{}) map[string]interface{} {
	if a == nil {
		a = make(map[string]interface{})
	}
	for k, v := range b {
		a[k] = v
	}
	return a
}

func AccessLog(log *sharedlogging.Logger) gin.HandlerFunc {
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
			log.Error("Request error", nil, fields...)
		} else {
			log.Info("Request", fields...)
		}
	}
}

func CORS() gin.HandlerFunc {
	return func(c *gin.Context) {
		origin := c.GetHeader("Origin")
		if origin != "" && (strings.HasPrefix(origin, "http://localhost") || strings.HasPrefix(origin, "https://app")) {
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
