// Package handlers contiene los HTTP handlers del mt5-connector.
package handlers

import (
	"errors"
	"net/http"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"

	"github.com/tnsvt/mt5-connector/internal/mt5"
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
		c.Writer.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Request-ID, X-Tenant-ID")
		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(http.StatusNoContent)
			return
		}
		c.Next()
	}
}

// ─── Broker Handler ──────────────────────────────────────────

// BrokerHandler maneja endpoints de broker
type BrokerHandler struct {
	client *mt5.Client
	log    interface {
		Info(string, ...any)
		Warn(string, ...any)
		Error(string, error, ...any)
	}
}

// NewBrokerHandler crea el handler
func NewBrokerHandler(client *mt5.Client, log interface {
	Info(string, ...any)
	Warn(string, ...any)
	Error(string, error, ...any)
}) *BrokerHandler {
	return &BrokerHandler{client: client, log: log}
}

// PlaceOrder POST /api/v1/brokers/orders
func (h *BrokerHandler) PlaceOrder(c *gin.Context) {
	if !h.client.IsConnected() {
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"error":   "MT5 not connected",
			"code":    "BROKER_NOT_CONNECTED",
			"details": "check MT5 terminal is running and credentials are correct",
		})
		return
	}

	var req mt5.OrderRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request", "details": err.Error()})
		return
	}

	if req.Symbol == "" || req.Quantity <= 0 || (req.Side != "buy" && req.Side != "sell") {
		c.JSON(http.StatusBadRequest, gin.H{"error": "missing required fields: symbol, quantity, side"})
		return
	}

	if req.OrderType == "" {
		req.OrderType = "market"
	}

	resp, err := h.client.PlaceOrder(c.Request.Context(), &req)
	if err != nil {
		h.log.Error("PlaceOrder failed", err, "symbol", req.Symbol, "side", req.Side)
		c.JSON(http.StatusBadGateway, gin.H{
			"error":   "broker error",
			"code":    "BROKER_ERROR",
			"details": err.Error(),
		})
		return
	}

	if !resp.Accepted {
		c.JSON(http.StatusUnprocessableEntity, gin.H{
			"error":   "order rejected by broker",
			"code":    "ORDER_REJECTED",
			"details": resp.Error,
		})
		return
	}

	h.log.Info("Order placed",
		"symbol", req.Symbol,
		"side", req.Side,
		"quantity", req.Quantity,
		"ticket", resp.Ticket,
		"filled_price", resp.FilledPrice)

	c.JSON(http.StatusOK, resp)
}

// ClosePosition POST /api/v1/brokers/positions/close
func (h *BrokerHandler) ClosePosition(c *gin.Context) {
	if !h.client.IsConnected() {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "MT5 not connected"})
		return
	}

	var req struct {
		AccountID string `json:"account_id"`
		Ticket    string `json:"ticket"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request"})
		return
	}

	if req.Ticket == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "ticket is required"})
		return
	}

	resp, err := h.client.ClosePosition(c.Request.Context(), req.AccountID, req.Ticket)
	if err != nil {
		h.log.Error("ClosePosition failed", err, "ticket", req.Ticket)
		c.JSON(http.StatusBadGateway, gin.H{
			"error":   "broker error",
			"details": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, resp)
}

// GetAccountInfo GET /api/v1/brokers/accounts/:id
func (h *BrokerHandler) GetAccountInfo(c *gin.Context) {
	if !h.client.IsConnected() {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "MT5 not connected"})
		return
	}

	accountID := c.Param("id")
	info, err := h.client.GetAccountInfo(c.Request.Context(), accountID)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, info)
}

// GetPositions GET /api/v1/brokers/accounts/:id/positions
func (h *BrokerHandler) GetPositions(c *gin.Context) {
	if !h.client.IsConnected() {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "MT5 not connected"})
		return
	}

	accountID := c.Param("id")
	positions, err := h.client.GetPositions(c.Request.Context(), accountID)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"account_id": accountID,
		"positions":  positions,
		"count":      len(positions),
	})
}

// ModifyPosition POST /api/v1/brokers/positions/:ticket/modify
func (h *BrokerHandler) ModifyPosition(c *gin.Context) {
	if !h.client.IsConnected() {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "MT5 not connected"})
		return
	}

	ticket := c.Param("ticket")
	var req struct {
		StopLoss   float64 `json:"stop_loss"`
		TakeProfit float64 `json:"take_profit"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request"})
		return
	}

	if err := h.client.ModifyPosition(c.Request.Context(), ticket, req.StopLoss, req.TakeProfit); err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "modified", "ticket": ticket})
}

// GetSymbolInfo GET /api/v1/brokers/symbols/:symbol
func (h *BrokerHandler) GetSymbolInfo(c *gin.Context) {
	if !h.client.IsConnected() {
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "MT5 not connected"})
		return
	}

	symbol := c.Param("symbol")
	info, err := h.client.GetSymbolInfo(c.Request.Context(), symbol)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, info)
}

// ─── Health ────────────────────────────────────────────────────

// Health GET /health
func Health(client *mt5.Client) gin.HandlerFunc {
	return func(c *gin.Context) {
		if !client.IsConnected() {
			c.JSON(http.StatusServiceUnavailable, gin.H{
				"status":  "degraded",
				"service": "mt5-connector",
				"mt5":     "disconnected",
			})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"status":  "ok",
			"service": "mt5-connector",
			"version": "0.1.0",
			"mt5":     "connected",
		})
	}
}

// HealthReady GET /health/ready
func HealthReady(client *mt5.Client) gin.HandlerFunc {
	return func(c *gin.Context) {
		if !client.IsConnected() {
			c.JSON(http.StatusServiceUnavailable, gin.H{
				"status": "not_ready",
				"reason": "MT5 not connected",
			})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"status": "ready",
			"mt5":    "connected",
		})
	}
}

// ─── Helpers ──────────────────────────────────────────────────

func mustInt(s string, def int) int {
	if i, err := strconv.Atoi(s); err == nil {
		return i
	}
	return def
}

func floatToPtr(f float64) *float64 {
	return &f
}