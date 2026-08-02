// Package handlers contiene los HTTP handlers del account-manager.
package handlers

import (
	"errors"
	"net/http"
	"os"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"

	"github.com/tnsvt/account-manager/internal/models"
	"github.com/tnsvt/account-manager/internal/service"
	"github.com/tnsvt/shared-go/cors"
)

// AccountHandler es el HTTP handler principal.
type AccountHandler struct {
	svc *service.Service
}

// New crea un AccountHandler.
func New(svc *service.Service) *AccountHandler {
	return &AccountHandler{svc: svc}
}

// Register monta las rutas.
func Register(r *gin.Engine, h *AccountHandler) {
	api := r.Group("/api/v1/accounts")

	api.GET("", h.list)
	api.GET("/replicators", h.listReplicators)
	api.POST("", h.create)
	api.GET("/:id", h.get)
	api.PUT("/:id", h.update)
	api.DELETE("/:id", h.delete)
	api.POST("/:id/change-password", h.changePassword)
	api.POST("/:id/snapshot", h.updateSnapshot)
	api.GET("/:id/credentials", h.credentials) // restringido, sólo service-to-service
}

func tenantIDFromCtx(c *gin.Context) uuid.UUID {
	if t := c.GetHeader("X-Tenant-ID"); t != "" {
		if u, err := uuid.Parse(t); err == nil {
			return u
		}
	}
	if v := os.Getenv("DEFAULT_TENANT_ID"); v != "" {
		if u, err := uuid.Parse(v); err == nil {
			return u
		}
	}
	return uuid.Nil
}

// healthFull indica si el servicio puede responder.
func (h *AccountHandler) healthFull(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status":  "ok",
		"service": "account-manager",
		"ts":      time.Now().UTC().Format(time.RFC3339),
	})
}

// list GET /api/v1/accounts — Lista las cuentas del tenant
func (h *AccountHandler) list(c *gin.Context) {
	tenantID := tenantIDFromCtx(c)
	if tenantID == uuid.Nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "tenant_id required (X-Tenant-ID or DEFAULT_TENANT_ID)"})
		return
	}
	resp, err := h.svc.ListAccounts(c.Request.Context(), tenantID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, resp)
}

// listReplicators GET /api/v1/accounts/replicators — Solo cuentas con copy_enabled=true
func (h *AccountHandler) listReplicators(c *gin.Context) {
	tenantID := tenantIDFromCtx(c)
	if tenantID == uuid.Nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "tenant_id required (X-Tenant-ID or DEFAULT_TENANT_ID)"})
		return
	}
	resp, err := h.svc.ListReplicators(c.Request.Context(), tenantID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, resp)
}

// create POST /api/v1/accounts — Crea una cuenta nueva
func (h *AccountHandler) create(c *gin.Context) {
	tenantID := tenantIDFromCtx(c)
	if tenantID == uuid.Nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "tenant_id required (X-Tenant-ID or DEFAULT_TENANT_ID)"})
		return
	}
	var req models.CreateAccountRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request", "details": err.Error()})
		return
	}
	a, err := h.svc.CreateAccount(c.Request.Context(), &req, tenantID)
	if err != nil {
		if errors.Is(err, service.ErrAlreadyExists) {
			c.JSON(http.StatusConflict, gin.H{"error": err.Error()})
			return
		}
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusCreated, a)
}

// get GET /api/v1/accounts/:id
func (h *AccountHandler) get(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid id"})
		return
	}
	a, err := h.svc.GetAccount(c.Request.Context(), id)
	if err != nil {
		if errors.Is(err, service.ErrNotFound) {
			c.JSON(http.StatusNotFound, gin.H{"error": "not found"})
			return
		}
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, a)
}

// update PUT /api/v1/accounts/:id
func (h *AccountHandler) update(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid id"})
		return
	}
	var req models.UpdateAccountRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request", "details": err.Error()})
		return
	}
	a, err := h.svc.UpdateAccount(c.Request.Context(), id, &req)
	if err != nil {
		if errors.Is(err, service.ErrInvalidStatus) {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, a)
}

// delete DELETE /api/v1/accounts/:id
func (h *AccountHandler) delete(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid id"})
		return
	}
	if err := h.svc.DeleteAccount(c.Request.Context(), id); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"status": "deleted", "id": id})
}

// changePassword POST /api/v1/accounts/:id/change-password
func (h *AccountHandler) changePassword(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid id"})
		return
	}
	var req models.ChangePasswordRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request", "details": err.Error()})
		return
	}
	if err := h.svc.ChangePassword(c.Request.Context(), id, &req); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"status": "password updated", "id": id})
}

// updateSnapshot POST /api/v1/accounts/:id/snapshot
// Usado por el mt5-connector para refrescar datos en vivo.
func (h *AccountHandler) updateSnapshot(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid id"})
		return
	}
	var snap models.AccountSnapshot
	if err := c.ShouldBindJSON(&snap); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request", "details": err.Error()})
		return
	}
	if err := h.svc.UpdateSnapshot(c.Request.Context(), id, &snap); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"status": "snapshot updated", "id": id})
}

// credentials GET /api/v1/accounts/:id/credentials
// Devuelve login + password desencriptada. USO INTERNO sólo (mt5-connector).
// Requiere header X-Service-Token = $ACCOUNT_MGR_SERVICE_TOKEN.
func (h *AccountHandler) credentials(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid id"})
		return
	}
	expected := os.Getenv("ACCOUNT_MGR_SERVICE_TOKEN")
	if expected == "" {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "service token not configured"})
		return
	}
	got := c.GetHeader("X-Service-Token")
	if got == "" || got != expected {
		c.JSON(http.StatusForbidden, gin.H{"error": "forbidden"})
		return
	}
	a, err := h.svc.GetAccount(c.Request.Context(), id)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "not found"})
		return
	}
	pw, err := h.svc.DecryptPassword(c.Request.Context(), id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{
		"id":       a.ID,
		"login":    a.Login,
		"password": pw,
		"server":   a.Server,
		"broker":   a.Broker,
	})
}

// CORS middleware wrapper (usa shared-go/cors)
func CORS() gin.HandlerFunc {
	allowed := cors.AllowedOrigins()
	return func(c *gin.Context) {
		origin := c.GetHeader("Origin")
		if allowed[origin] {
			c.Writer.Header().Set("Access-Control-Allow-Origin", origin)
			c.Writer.Header().Set("Vary", "Origin")
		}
		c.Writer.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Request-ID, X-Tenant-ID, X-Service-Token")
		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(http.StatusNoContent)
			return
		}
		c.Next()
	}
}
