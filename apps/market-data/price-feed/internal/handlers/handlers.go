package handlers

import (
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"

	"github.com/tnsvt/price-feed/internal/models"
	"github.com/tnsvt/price-feed/internal/source"
)

// ─── Middleware ──────────────────────────────────────────────────────────

func RequestID() gin.HandlerFunc {
	return func(c *gin.Context) {
		rid := c.GetHeader("X-Request-Id")
		if rid == "" {
			rid = uuid.NewString()
		}
		c.Set("request_id", rid)
		c.Writer.Header().Set("X-Request-Id", rid)
		c.Next()
	}
}

func AccessLog(log interface {
	Info(string, ...any)
	Warn(string, ...any)
}) gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()
		c.Next()
		dur := time.Since(start)
		rid, _ := c.Get("request_id")
		log.Info("http.request",
			"method", c.Request.Method,
			"path", c.Request.URL.Path,
			"status", c.Writer.Status(),
			"duration_ms", dur.Milliseconds(),
			"request_id", rid,
		)
	}
}

func CORS() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Writer.Header().Set("Access-Control-Allow-Origin", "*")
		c.Writer.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Request-Id")
		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}
		c.Next()
	}
}

// ─── Health ──────────────────────────────────────────────────────────────

type healthChecker interface {
	Sources() []source.SourceStatus
}

func Health(mgr healthChecker) gin.HandlerFunc {
	return func(c *gin.Context) {
		c.JSON(200, gin.H{
			"status":  "ok",
			"service": "price-feed",
			"version": "0.1.0",
			"sources": mgr.Sources(),
		})
	}
}

func HealthReady(mgr healthChecker) gin.HandlerFunc {
	return func(c *gin.Context) {
		sources := mgr.Sources()
		if len(sources) > 0 {
			c.JSON(200, gin.H{"status": "ready"})
			return
		}
		c.JSON(503, gin.H{"status": "no_sources"})
	}
}

// ─── Price handler ──────────────────────────────────────────────────────

type PriceHandler struct {
	store *models.TickStore
	mgr   healthChecker
	log   interface {
		Info(string, ...any)
		Warn(string, ...any)
	}
}

func NewPriceHandler(store *models.TickStore, mgr healthChecker, log interface {
	Info(string, ...any)
	Warn(string, ...any)
}) *PriceHandler {
	return &PriceHandler{store: store, mgr: mgr, log: log}
}

// List returns the list of symbols with at least one tick.
func (h *PriceHandler) List(c *gin.Context) {
	symbols := h.store.Symbols()
	c.JSON(200, gin.H{
		"count":   len(symbols),
		"symbols": symbols,
	})
}

// Snapshot returns the latest tick for every symbol.
func (h *PriceHandler) Snapshot(c *gin.Context) {
	ticks := h.store.Snapshot()
	out := make([]gin.H, 0, len(ticks))
	for _, t := range ticks {
		abs, pct := t.Spread()
		out = append(out, gin.H{
			"symbol":       t.Symbol,
			"bid":          t.Bid,
			"ask":          t.Ask,
			"last":         t.Last,
			"mid":          t.Mid(),
			"spread":       abs,
			"spread_pct":   pct,
			"volume":       t.Volume,
			"source":       t.Source,
			"timestamp":    t.Timestamp,
		})
	}
	c.JSON(200, gin.H{
		"count": len(out),
		"items": out,
	})
}

// Get returns the latest tick for a specific symbol.
func (h *PriceHandler) Get(c *gin.Context) {
	sym := c.Param("symbol")
	t, ok := h.store.Get(sym)
	if !ok {
		c.JSON(404, gin.H{"error": "symbol not found", "symbol": sym})
		return
	}
	abs, pct := t.Spread()
	c.JSON(200, gin.H{
		"symbol":     t.Symbol,
		"bid":        t.Bid,
		"ask":        t.Ask,
		"last":       t.Last,
		"mid":        t.Mid(),
		"spread":     abs,
		"spread_pct": pct,
		"volume":     t.Volume,
		"source":     t.Source,
		"timestamp":  t.Timestamp,
	})
}

// Stream is a Server-Sent Events endpoint that pushes new ticks as they arrive.
func (h *PriceHandler) Stream(c *gin.Context) {
	ch, cancel := h.store.Subscribe(256)
	defer cancel()

	c.Writer.Header().Set("Content-Type", "text/event-stream")
	c.Writer.Header().Set("Cache-Control", "no-cache")
	c.Writer.Header().Set("Connection", "keep-alive")
	c.Writer.Header().Set("X-Accel-Buffering", "no")

	flusher, ok := c.Writer.(interface{ Flush() })
	if !ok {
		c.JSON(500, gin.H{"error": "streaming unsupported"})
		return
	}

	// initial comment so the connection opens immediately
	_, _ = c.Writer.WriteString(": connected\n\n")
	flusher.Flush()

	heartbeat := time.NewTicker(15 * time.Second)
	defer heartbeat.Stop()

	clientGone := c.Writer.CloseNotify()
	for {
		select {
		case <-clientGone:
			return
		case t, ok := <-ch:
			if !ok {
				return
			}
			payload, err := tickJSON(t)
			if err != nil {
				h.log.Warn("sse.marshal_failed", "error", err.Error())
				continue
			}
			_, _ = c.Writer.WriteString("event: tick\ndata: " + payload + "\n\n")
			flusher.Flush()
		case <-heartbeat.C:
			_, _ = c.Writer.WriteString(": ping\n\n")
			flusher.Flush()
		}
	}
}

func tickJSON(t models.Tick) (string, error) {
	b, err := jsonMarshal(t)
	if err != nil {
		return "", err
	}
	return string(b), nil
}