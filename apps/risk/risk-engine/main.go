// Package main implementa el Risk Engine de TNSVT V2.
//
// Responsabilidades:
//   - Suscribirse a trading.signal.created events de NATS
//   - Evaluar riesgo de cada signal (límites, exposición, drawdown)
//   - Calcular position sizing (lot size basado en % riesgo)
//   - Publicar trading.signal.validated o trading.signal.rejected
//   - Tracking de P&L diario/semanal
//   - Trailing stop dinámico
//   - Límites configurables por tenant
//
// Endpoints:
//   POST /api/v1/risk/evaluate          # Evalúa señal manual
//   GET  /api/v1/risk/exposure          # Exposición actual
//   GET  /api/v1/risk/limits            # Límites del tenant
//   PUT  /api/v1/risk/limits            # Update límites
//   GET  /api/v1/risk/stats             # Estadísticas P&L
//   GET  /api/v1/risk/positions         # Posiciones abiertas
//   POST /api/v1/risk/positions/update  # Update tras cambio de precio
//   POST /api/v1/risk/trade-opened      # Notificar trade abierto
//   POST /api/v1/risk/trade-closed      # Notificar trade cerrado
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

	"github.com/tnsvt/risk-engine/internal/handlers"
	"github.com/tnsvt/risk-engine/internal/repository"
	"github.com/tnsvt/risk-engine/internal/service"
	"github.com/tnsvt/risk-engine/internal/subscriber"
	sharedconfig "github.com/tnsvt/shared-go/config"
	sharedlogging "github.com/tnsvt/shared-go/logging"
)

func main() {
	cfg := sharedconfig.Load("risk-engine")
	port := cfg.Get("RISK_ENGINE_PORT", "8006")
	log := sharedlogging.New("risk-engine", cfg.LogLevel)

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

	repo := repository.NewRiskRepository(pgPool, log)
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
		log.Error("NATS unavailable, risk engine cannot function", err)
		os.Exit(1)
	}
	defer natsConn.Close()

	// ─── Service ───
	dailyLossLimit := cfg.GetFloat("RISK_DAILY_LOSS_LIMIT", 500.0)
	dailyProfitTarget := cfg.GetFloat("RISK_DAILY_PROFIT_TARGET", 1000.0)
	weeklyLossLimit := cfg.GetFloat("RISK_WEEKLY_LOSS_LIMIT", 1500.0)
	maxOpenPositions := cfg.GetInt("RISK_MAX_OPEN_POSITIONS", 5)
	trailingStop := cfg.GetBool("RISK_TRAILING_STOP", true)

	riskService := service.NewRiskService(
		repo, redisClient, natsConn, log,
		service.Config{
			DailyLossLimit:    dailyLossLimit,
			DailyProfitTarget: dailyProfitTarget,
			WeeklyLossLimit:   weeklyLossLimit,
			MaxOpenPositions:  maxOpenPositions,
			TrailingStop:      trailingStop,
			TrailingStep:      cfg.GetInt("RISK_TRAILING_STEP", 10),
			TrailingStart:     cfg.GetInt("RISK_TRAILING_START", 20),
		},
	)

	// ─── NATS Subscriber ───
	sub := subscriber.NewSignalSubscriber(natsConn, riskService, log)
	go func() {
		if err := sub.Start(context.Background()); err != nil {
			log.Error("Subscriber failed", err)
		}
	}()

	// ─── Position monitor (trailing stop) ───
	if trailingStop {
		monitorCtx, monitorCancel := context.WithCancel(context.Background())
		defer monitorCancel()
		go riskService.RunTrailingStopMonitor(monitorCtx, 10*time.Second)
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
	riskHandler := handlers.NewRiskHandler(riskService, log)
	api := router.Group("/api/v1/risk")
	{
		api.POST("/evaluate", riskHandler.Evaluate)
		api.GET("/exposure", riskHandler.GetExposure)
		api.GET("/limits", riskHandler.GetLimits)
		api.PUT("/limits", riskHandler.UpdateLimits)
		api.GET("/stats", riskHandler.Stats)
		api.GET("/positions", riskHandler.ListPositions)
		api.POST("/positions/update", riskHandler.UpdatePositionPrice)
		api.POST("/trade-opened", riskHandler.TradeOpened)
		api.POST("/trade-closed", riskHandler.TradeClosed)
	}

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
		log.Info("risk-engine starting", "port", port, "env", cfg.Env)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Error("HTTP server failed", err)
			os.Exit(1)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Info("Shutting down risk-engine...")
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	if err := srv.Shutdown(ctx); err != nil {
		log.Error("Forced shutdown", err)
	}
	log.Info("risk-engine stopped")
}