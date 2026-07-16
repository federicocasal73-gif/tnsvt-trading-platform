// Package main implementa el Price Feed service de TNSVT V2.
//
// Responsabilidades:
//   - Conectar con múltiples fuentes WebSocket de precios (exchanges, brokers)
//   - Normalizar formato de cada fuente a un schema unificado
//   - Publicar ticks a NATS (marketdata.tick.<symbol>)
//   - Exponer últimos precios via REST + SSE stream
//   - Heartbeat, reconnect automático, buffer en memoria
//
// Endpoints:
//   GET    /health                   # Liveness + dependencias
//   GET    /health/live              # Liveness
//   GET    /health/ready             # Readiness
//   GET    /metrics                  # Prometheus
//   GET    /api/v1/prices            # Lista símbolos activos
//   GET    /api/v1/prices/:symbol    # Último tick de un símbolo
//   GET    /api/v1/prices/snapshot   # Snapshot de todos los símbolos
//   GET    /api/v1/prices/stream     # SSE stream de ticks nuevos
package main

import (
	"context"
	"errors"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/redis/go-redis/v9"

	"github.com/tnsvt/price-feed/internal/handlers"
	"github.com/tnsvt/price-feed/internal/models"
	"github.com/tnsvt/price-feed/internal/publisher"
	"github.com/tnsvt/price-feed/internal/source"

	sharedconfig "github.com/tnsvt/shared-go/config"
	sharedlogging "github.com/tnsvt/shared-go/logging"
)

func main() {
	cfg := sharedconfig.Load("price-feed")
	port := cfg.Get("PRICE_FEED_PORT", "8300")
	log := sharedlogging.New("price-feed", cfg.LogLevel)

	// ─── Redis ────────────────────────────────────────────────
	redisClient := redis.NewClient(&redis.Options{
		Addr:     cfg.Redis.Addr(),
		Password: cfg.Redis.Password,
		DB:       cfg.Redis.DB,
	})
	defer redisClient.Close()

	// ─── NATS ─────────────────────────────────────────────────
	var natsPub *publisher.NatsPublisher
	for i := 0; i < 3; i++ {
		p, err := publisher.NewNatsPublisher(cfg.NATS.URL())
		if err == nil {
			natsPub = p
			break
		}
		log.Warn("NATS connection retry", "attempt", i+1, "error", err.Error())
		time.Sleep(2 * time.Second)
	}
	if natsPub == nil {
		log.Warn("NATS unavailable, ticks will not be published")
	} else {
		defer natsPub.Close()
	}

	// ─── Tick store (memoria + Redis para los últimos N) ──────
	store := models.NewTickStore(redisClient, 10*time.Minute)

	// ─── Source manager ───────────────────────────────────────
	symbols := parseSymbols(cfg.Get("PRICE_FEED_SYMBOLS", "EURUSD,GBPUSD,USDJPY,XAUUSD,BTCUSD"))
	srcMgr := source.NewManager(log, store, natsPub)

	if mockURL := cfg.Get("PRICE_FEED_MOCK_URL", ""); mockURL != "" {
		srcMgr.Add(source.NewMockSource("mock", mockURL, symbols, log))
	} else {
		// Sin fuente externa configurada → usamos MockSource local que emite ticks sintéticos
		srcMgr.Add(source.NewBuiltinMockSource("builtin-mock", symbols, log))
	}

	// ─── Arranca el manager ──────────────────────────────────
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	srcMgr.Start(ctx)

	// ─── HTTP router ──────────────────────────────────────────
	if cfg.Env == "production" {
		gin.SetMode(gin.ReleaseMode)
	}
	router := gin.New()
	router.Use(gin.Recovery())
	router.Use(handlers.RequestID())
	router.Use(handlers.AccessLog(log))
	router.Use(handlers.CORS())

	router.GET("/health", handlers.Health(srcMgr))
	router.GET("/health/live", func(c *gin.Context) { c.Status(http.StatusOK) })
	router.GET("/health/ready", handlers.HealthReady(srcMgr))
	router.GET("/metrics", gin.WrapH(promhttp.Handler()))

	priceHandler := handlers.NewPriceHandler(store, srcMgr, log)
	api := router.Group("/api/v1/prices")
	{
		api.GET("", priceHandler.List)
		api.GET("/snapshot", priceHandler.Snapshot)
		api.GET("/:symbol", priceHandler.Get)
		api.GET("/stream", priceHandler.Stream)
	}

	router.NoRoute(func(c *gin.Context) {
		c.JSON(http.StatusNotFound, gin.H{"error": "endpoint not found"})
	})

	// ─── HTTP server ──────────────────────────────────────────
	srv := &http.Server{
		Addr:              ":" + port,
		Handler:           router,
		ReadTimeout:       15 * time.Second,
		WriteTimeout:      30 * time.Second,
		IdleTimeout:       120 * time.Second,
		ReadHeaderTimeout: 5 * time.Second,
	}
	go func() {
		log.Info("price-feed starting", "port", port, "env", cfg.Env, "symbols", len(symbols))
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Error("HTTP server failed", err)
			os.Exit(1)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Info("Shutting down price-feed...")
	cancel()
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer shutdownCancel()
	if err := srv.Shutdown(shutdownCtx); err != nil {
		log.Error("Forced shutdown", err)
	}
	log.Info("price-feed stopped")
}

// parseSymbols parses a comma-separated list of symbols, trimming spaces
// and uppercasing each entry. Empty entries are dropped.
func parseSymbols(raw string) []string {
	out := make([]string, 0, 8)
	start := 0
	for i := 0; i <= len(raw); i++ {
		if i == len(raw) || raw[i] == ',' {
			tok := raw[start:i]
			// trim spaces
			for len(tok) > 0 && tok[0] == ' ' {
				tok = tok[1:]
			}
			for len(tok) > 0 && tok[len(tok)-1] == ' ' {
				tok = tok[:len(tok)-1]
			}
			if tok != "" {
				out = append(out, tok)
			}
			start = i + 1
		}
	}
	return out
}