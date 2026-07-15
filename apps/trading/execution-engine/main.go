// Package main implementa el Execution Engine de TNSVT V2.
//
// Responsabilidades:
//   - Consumir trading.signal.validated de NATS
//   - Orquestar la ejecución de la orden en el broker apropiado
//   - Registrar la posición en risk-engine
//   - Monitorear trades abiertos (detectar cierres por SL/TP)
//   - Publicar trading.execution.executed / .failed / .closed a NATS
//   - Cancelar ejecuciones pendientes
//
// Flujo:
//   signal validated → execution-engine → broker connector → risk-engine (position)
//                                                                  ↓
//                                                          monitor (SL/TP hit)
//                                                                  ↓
//                                                          risk-engine (closed)
//                                                                  ↓
//                                                          NATS event
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

	"github.com/tnsvt/execution-engine/internal/broker"
	"github.com/tnsvt/execution-engine/internal/handlers"
	"github.com/tnsvt/execution-engine/internal/repository"
	"github.com/tnsvt/execution-engine/internal/service"
	"github.com/tnsvt/execution-engine/internal/subscriber"
	sharedconfig "github.com/tnsvt/shared-go/config"
	sharedlogging "github.com/tnsvt/shared-go/logging"
)

func main() {
	cfg := sharedconfig.Load("execution-engine")
	port := cfg.Get("EXECUTION_ENGINE_PORT", "8004")
	log := sharedlogging.New("execution-engine", cfg.LogLevel)

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
	pgxCfg.MaxConns = 30
	pgPool, err := pgxpool.NewWithConfig(context.Background(), pgxCfg)
	if err != nil {
		log.Error("PostgreSQL pool creation failed", err)
		os.Exit(1)
	}
	defer pgPool.Close()

	repo := repository.NewExecutionRepository(pgPool, log)
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
		log.Error("NATS unavailable, execution engine cannot function", err)
		os.Exit(1)
	}
	defer natsConn.Close()

	// ─── Broker Factory ───
	brokerFactory := broker.NewFactory(log)
	// MT5 connector (Fase 1) — apunta al mt5-connector service
	// En Fase 2: agregar ctrader, binance, bybit, ibkr
	if mt5URL := cfg.Get("MT5_CONNECTOR_URL", "http://mt5-connector:8007"); mt5URL != "" {
		brokerFactory.Register("mt5", broker.NewHTTPBrokerConnector("mt5", mt5URL, log))
	}

	// ─── HTTP Client for risk-engine ───
	riskEngineURL := cfg.Get("RISK_ENGINE_URL", "http://risk-engine:8006")

	// ─── Service ───
	execService := service.NewExecutionService(
		repo, redisClient, natsConn, brokerFactory, riskEngineURL, log,
		service.Config{
			DefaultBroker:  cfg.Get("DEFAULT_BROKER", "mt5"),
			DefaultAccount: cfg.Get("DEFAULT_ACCOUNT_ID", "default"),
			Timeout:        time.Duration(cfg.GetInt("EXECUTION_TIMEOUT_SECONDS", 30)) * time.Second,
			RetryMax:       cfg.GetInt("EXECUTION_RETRY_MAX", 3),
			RetryBackoff:   time.Duration(cfg.GetInt("EXECUTION_RETRY_BACKOFF", 2)) * time.Second,
		},
	)

	// ─── NATS Subscriber ───
	subCtx, subCancel := context.WithCancel(context.Background())
	defer subCancel()

	sub := subscriber.NewSignalSubscriber(natsConn, execService, log)
	if err := sub.Start(subCtx); err != nil {
		log.Error("Subscriber failed to start", err)
		os.Exit(1)
	}

	// ─── Trade Monitor (detecta cierres por SL/TP cada 10s) ───
	monitorCtx, monitorCancel := context.WithCancel(context.Background())
	defer monitorCancel()
	go execService.RunTradeMonitor(monitorCtx, 10*time.Second, brokerFactory)

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
	router.GET("/health/ready", handlers.HealthReady(repo, redisClient, natsConn, brokerFactory))
	router.GET("/metrics", gin.WrapH(promhttp.Handler()))

	// ─── API ───
	execHandler := handlers.NewExecutionHandler(execService, log)
	api := router.Group("/api/v1/executions")
	{
		api.POST("", execHandler.Execute)
		api.GET("", execHandler.List)
		api.GET("/:id", execHandler.Get)
		api.POST("/:id/cancel", execHandler.Cancel)
		api.GET("/stats", execHandler.Stats)
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
		log.Info("execution-engine starting", "port", port, "env", cfg.Env)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Error("HTTP server failed", err)
			os.Exit(1)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Info("Shutting down execution-engine...")
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	if err := srv.Shutdown(ctx); err != nil {
		log.Error("Forced shutdown", err)
	}
	log.Info("execution-engine stopped")
}