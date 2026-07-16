// Package main implementa el Copy Trading Engine de TNSVT V2.
//
// Responsabilidades:
//   - Replicar una señal validada a múltiples cuentas MT5
//   - Cada cuenta tiene configuración propia: lot_size, lot_mode, SL/TP, suffix
//   - Routing basado en CopyGroup (un grupo = N cuentas que reciben la misma señal)
//   - Scaling de lot (ej: cuenta B recibe 5x lo que recibe cuenta A)
//   - Modo inverso (puede invertir BUY/SELL por cuenta)
//   - Tracking de cada réplica (CopyJob) con estado individual
//
// Flujo:
//   1. NATS: trading.signal.validated
//   2. Lookup CopyGroups del tenant
//   3. Por cada grupo: N cuentas × config propia
//   4. Por cada cuenta: HTTP POST /api/v1/executions (ejecutar signal)
//   5. Trackear cada CopyJob en PostgreSQL
//   6. Publicar NATS: trading.copy.completed / .partial / .failed
//
// Endpoints:
//   GET/POST/PUT/DELETE /api/v1/copy/groups       # CRUD de grupos
//   GET/POST/PUT/DELETE /api/v1/copy/accounts     # CRUD de cuentas en grupo
//   GET/POST            /api/v1/copy/jobs          # Historial de réplicas
//   GET                 /api/v1/copy/stats         # Estadísticas
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

	"github.com/tnsvt/copy-trading/internal/handlers"
	"github.com/tnsvt/copy-trading/internal/repository"
	"github.com/tnsvt/copy-trading/internal/service"
	"github.com/tnsvt/copy-trading/internal/subscriber"
	sharedconfig "github.com/tnsvt/shared-go/config"
	sharedlogging "github.com/tnsvt/shared-go/logging"
)

func main() {
	cfg := sharedconfig.Load("copy-trading")
	port := cfg.Get("COPY_TRADING_PORT", "8005")
	log := sharedlogging.New("copy-trading", cfg.LogLevel)

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
	pgPool, err := pgxpool.NewWithConfig(context.Background(), pgxCfg)
	if err != nil {
		log.Error("PostgreSQL pool creation failed", err)
		os.Exit(1)
	}
	defer pgPool.Close()

	repo := repository.NewCopyTradingRepository(pgPool, log)
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
		log.Error("NATS unavailable, copy-trading cannot function", err)
		os.Exit(1)
	}
	defer natsConn.Close()

	// ─── HTTP Client for execution-engine ───
	executionEngineURL := cfg.Get("EXECUTION_ENGINE_URL", "http://execution-engine:8004")

	// ─── Service ───
	maxAccounts := cfg.GetInt("COPY_TRADING_MAX_ACCOUNTS", 20)
	timeout := time.Duration(cfg.GetInt("COPY_TRADING_TIMEOUT_SECONDS", 60)) * time.Second
	copyService := service.NewCopyTradingService(repo, redisClient, natsConn, executionEngineURL, log, service.Config{
		MaxAccountsPerGroup: maxAccounts,
		Timeout:             timeout,
	})

	// ─── NATS Subscriber ───
	subCtx, subCancel := context.WithCancel(context.Background())
	defer subCancel()

	sub := subscriber.NewSignalSubscriber(natsConn, copyService, log)
	if err := sub.Start(subCtx); err != nil {
		log.Error("Subscriber failed", err)
		os.Exit(1)
	}

	// ─── Gin router ───
	if cfg.Env == "production" {
		gin.SetMode(gin.ReleaseMode)
	}
	router := gin.New()
	router.Use(gin.Recovery())
	router.Use(handlers.RequestID())
	router.Use(handlers.AccessLog(log))
	router.Use(handlers.CORS())

	// ─── Health ───
	router.GET("/health", handlers.Health(repo))
	router.GET("/health/live", func(c *gin.Context) { c.Status(http.StatusOK) })
	router.GET("/health/ready", handlers.HealthReady(repo, redisClient, natsConn))
	router.GET("/metrics", gin.WrapH(promhttp.Handler()))

	// ─── API ───
	api := router.Group("/api/v1/copy")
	{
		groupsHandler := handlers.NewGroupsHandler(copyService, log)
		api.GET("/groups", groupsHandler.List)
		api.POST("/groups", groupsHandler.Create)
		api.GET("/groups/:id", groupsHandler.Get)
		api.PUT("/groups/:id", groupsHandler.Update)
		api.DELETE("/groups/:id", groupsHandler.Delete)

		accountsHandler := handlers.NewAccountsHandler(copyService, log)
		api.GET("/groups/:id/accounts", accountsHandler.List)
		api.POST("/groups/:id/accounts", accountsHandler.Create)
		api.GET("/accounts/:id", accountsHandler.Get)
		api.PUT("/accounts/:id", accountsHandler.Update)
		api.DELETE("/accounts/:id", accountsHandler.Delete)

		jobsHandler := handlers.NewJobsHandler(copyService, log)
		api.GET("/jobs", jobsHandler.List)
		api.GET("/jobs/:id", jobsHandler.Get)
		api.GET("/stats", jobsHandler.Stats)

		// Manual trigger
		api.POST("/replicate/:signal_id", groupsHandler.ManualReplicate)
	}

	router.NoRoute(func(c *gin.Context) {
		c.JSON(http.StatusNotFound, gin.H{"error": "endpoint not found"})
	})

	// ─── HTTP server ───
	srv := &http.Server{
		Addr:              ":" + port,
		Handler:           router,
		ReadTimeout:       15 * time.Second,
		WriteTimeout:      60 * time.Second,
		IdleTimeout:       120 * time.Second,
		ReadHeaderTimeout: 5 * time.Second,
	}

	go func() {
		log.Info("copy-trading starting", "port", port, "env", cfg.Env, "max_accounts_per_group", maxAccounts)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Error("HTTP server failed", err)
			os.Exit(1)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Info("Shutting down copy-trading...")
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	if err := srv.Shutdown(ctx); err != nil {
		log.Error("Forced shutdown", err)
	}
	log.Info("copy-trading stopped")
}