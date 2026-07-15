// Package main implementa el Signal Engine de TNSVT V2.
//
// Responsabilidades:
//   - Recibir señales de múltiples fuentes (Telegram, API, manual, AI)
//   - Validar formato y reglas de negocio (symbol pattern, prices > 0)
//   - Parsear mensajes de texto en lenguaje natural
//   - Deduplicar señales (SHA-256 hash + TTL 10min)
//   - Publicar eventos a NATS (trading.signal.*)
//   - Integración con risk-engine antes de ejecutar
//   - Stream de señales vía SSE para dashboards
//
// Endpoints:
//   POST   /api/v1/signals              # Submit signal
//   GET    /api/v1/signals/:id          # Get signal by ID
//   GET    /api/v1/signals              # List signals (paginated)
//   POST   /api/v1/signals/parse        # Parse raw text (preview)
//   GET    /api/v1/signals/stream       # SSE stream of new signals
//   GET    /api/v1/signals/stats        # Statistics
//
//   POST   /internal/ingest/telegram    # Webhook desde telegram-bridge
//
//   GET    /health, /health/live, /health/ready, /metrics
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
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/nats-io/nats.go"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/redis/go-redis/v9"

	"github.com/tnsvt/signal-engine/internal/handlers"
	"github.com/tnsvt/signal-engine/internal/parser"
	"github.com/tnsvt/signal-engine/internal/repository"
	"github.com/tnsvt/signal-engine/internal/service"
	sharedconfig "github.com/tnsvt/shared-go/config"
	sharedlogging "github.com/tnsvt/shared-go/logging"
)

func main() {
	cfg := sharedconfig.Load("signal-engine")
	port := cfg.Get("SIGNAL_ENGINE_PORT", "8003")
	log := sharedlogging.New("signal-engine", cfg.LogLevel)

	// ─── Redis ───
	redisClient := redis.NewClient(&redis.Options{
		Addr:     cfg.Redis.Addr(),
		Password: cfg.Redis.Password,
		DB:       cfg.Redis.DB,
	})
	defer redisClient.Close()

	// ─── PostgreSQL ───
	pgxCfg, err := pgxpool.ParseConfig(cfg.Postgres.DSN())
	if err != nil {
		log.Error("Invalid PostgreSQL DSN", err)
		os.Exit(1)
	}
	pgxCfg.MaxConns = 20
	pgxCfg.MinConns = 2
	pgPool, err := pgxpool.NewWithConfig(context.Background(), pgxCfg)
	if err != nil {
		log.Error("PostgreSQL pool creation failed", err)
		os.Exit(1)
	}
	defer pgPool.Close()

	repo := repository.NewSignalRepository(pgPool, log)
	if err := repo.RunMigrations(context.Background()); err != nil {
		log.Error("Migrations failed", err)
		os.Exit(1)
	}

	// ─── NATS ───
	var natsConn *nats.Conn
	for i := 0; i < 3; i++ {
		natsConn, err = nats.Connect(cfg.NATS.URL())
		if err == nil {
			break
		}
		log.Warn("NATS connection retry", "attempt", i+1, "error", err.Error())
		time.Sleep(2 * time.Second)
	}
	if err != nil {
		log.Warn("NATS unavailable, signals won't be published", "error", err.Error())
	} else {
		defer natsConn.Close()
	}

	// ─── NATS JetStream setup ───
	if natsConn != nil {
		setupJetStream(natsConn, log)
	}

	// ─── Parser & Service ───
	signalParser := parser.NewSignalParser()
	dedupTTL := time.Duration(cfg.GetInt("SIGNAL_DEDUP_TTL_MINUTES", 10)) * time.Minute
	signalService := service.NewSignalService(repo, redisClient, natsConn, signalParser, dedupTTL, log)

	// ─── Gin router ───
	if cfg.Env == "production" {
		gin.SetMode(gin.ReleaseMode)
	}
	router := gin.New()
	router.Use(gin.Recovery())
	router.Use(handlers.RequestID())
	router.Use(handlers.AccessLog(log))
	router.Use(handlers.CORS())
	router.Use(handlers.Metrics())

	// ─── Health ───
	router.GET("/health", handlers.Health(repo))
	router.GET("/health/live", func(c *gin.Context) { c.Status(http.StatusOK) })
	router.GET("/health/ready", handlers.HealthReady(repo, redisClient, natsConn))
	router.GET("/metrics", gin.WrapH(promhttp.Handler()))

	// ─── Public API ───
	signalHandler := handlers.NewSignalHandler(signalService, log)
	api := router.Group("/api/v1/signals")
	{
		api.POST("", signalHandler.Submit)
		api.GET("", signalHandler.List)
		api.GET("/:id", signalHandler.Get)
		api.POST("/parse", signalHandler.Parse)
		api.GET("/stream", signalHandler.Stream)
		api.GET("/stats", signalHandler.Stats)
	}

	// ─── Internal: webhook from telegram-bridge ───
	router.POST("/internal/ingest/telegram", handlers.IngestAPIKeyMiddleware(cfg.Get("SIGNAL_INGEST_API_KEY", "")), signalHandler.IngestTelegram)

	router.NoRoute(func(c *gin.Context) {
		c.JSON(http.StatusNotFound, gin.H{"error": "endpoint not found"})
	})

	// ─── HTTP server ───
	srv := &http.Server{
		Addr:              ":" + port,
		Handler:           router,
		ReadTimeout:       15 * time.Second,
		WriteTimeout:      30 * time.Second,
		IdleTimeout:       120 * time.Second,
		ReadHeaderTimeout: 5 * time.Second,
	}

	go func() {
		log.Info("signal-engine starting", "port", port, "env", cfg.Env)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Error("HTTP server failed", err)
			os.Exit(1)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Info("Shutting down signal-engine...")
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	if err := srv.Shutdown(ctx); err != nil {
		log.Error("Forced shutdown", err)
	}
	log.Info("signal-engine stopped")
}

// setupJetStream crea los streams necesarios
func setupJetStream(nc *nats.Conn, log interface{ Info(string, ...any); Warn(string, ...any) }) {
	js, err := nc.JetStream()
	if err != nil {
		log.Warn("JetStream not available", "error", err.Error())
		return
	}

	streams := []nats.StreamConfig{
		{
			Name:     "TRADING_SIGNALS",
			Subjects: []string{"trading.signal.>"},
			Storage:  nats.FileStorage,
			MaxAge:   24 * time.Hour,
			MaxMsgs:  100000,
		},
		{
			Name:     "GATEWAY_EVENTS",
			Subjects: []string{"gateway.request.>"},
			Storage:  nats.FileStorage,
			MaxAge:   7 * 24 * time.Hour,
			MaxMsgs:  1000000,
		},
	}

	for _, stream := range streams {
		_, err := js.AddStream(&stream)
		if err != nil {
			log.Warn("Failed to add stream", "stream", stream.Name, "error", err.Error())
			continue
		}
		log.Info("JetStream ready", "stream", stream.Name)
	}
}