// Package main implementa el Account Manager de TNSVT V2.
//
// Responsabilidades:
//   - CRUD de cuentas MT5 (con credenciales encriptadas AES-GCM)
//   - Decrypt de credenciales para el mt5-connector (auth service-to-service)
//   - Cache de snapshots en vivo (último balance/equity/PnL por cuenta)
//   - Multi-tenant (cada tenant ve sólo sus cuentas)
//
// Endpoints:
//   GET    /health                 → health check
//   GET    /api/v1/accounts        → listar cuentas del tenant
//   POST   /api/v1/accounts        → crear cuenta
//   GET    /api/v1/accounts/:id    → detalle
//   PUT    /api/v1/accounts/:id    → editar alias/name/status
//   DELETE /api/v1/accounts/:id    → eliminar
//   POST   /api/v1/accounts/:id/change-password
//   POST   /api/v1/accounts/:id/snapshot (mt5-connector → refresca datos)
//   GET    /api/v1/accounts/:id/credentials (mt5-connector, X-Service-Token)
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
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/redis/go-redis/v9"

	"github.com/tnsvt/account-manager/internal/cipher"
	"github.com/tnsvt/account-manager/internal/handlers"
	"github.com/tnsvt/account-manager/internal/repository"
	"github.com/tnsvt/account-manager/internal/service"
	sharedconfig "github.com/tnsvt/shared-go/config"
	sharedlogging "github.com/tnsvt/shared-go/logging"
)

func main() {
	cfg := sharedconfig.Load("account-manager")
	port := cfg.Get("ACCOUNT_MANAGER_PORT", "8510")
	log := sharedlogging.New("account-manager", cfg.LogLevel)

	// ─── Cipher (AES-GCM) ─────────────────────────────────────
	cph, err := cipher.New(cfg.Get("MT5_PASSWORD_KEY", ""))
	if err != nil {
		log.Error("cipher init failed", err)
		os.Exit(1)
	}
	log.Info("cipher initialized (AES-GCM, 256-bit)")

	// ─── Redis (opcional, para cache de snapshots) ─────────────
	var redisClient *redis.Client
	if cfg.Redis.Host != "" {
		redisClient = redis.NewClient(&redis.Options{
			Addr:     cfg.Redis.Addr(),
			Password: cfg.Redis.Password,
			DB:       cfg.Redis.DB,
		})
		defer redisClient.Close()
		_ = redisClient
	}

	// ─── PostgreSQL ────────────────────────────────────────────
	pgxCfg, err := pgxpool.ParseConfig(cfg.Postgres.DSN())
	if err != nil {
		log.Error("invalid PostgreSQL DSN", err)
		os.Exit(1)
	}
	pgxCfg.MaxConns = 20
	pgPool, err := pgxpool.NewWithConfig(context.Background(), pgxCfg)
	if err != nil {
		log.Error("PostgreSQL pool failed", err)
		os.Exit(1)
	}
	defer pgPool.Close()

	repo := repository.NewPostgresRepository(pgPool)
	if err := repo.RunMigrations(context.Background()); err != nil {
		log.Error("migrations failed", err)
		os.Exit(1)
	}
	log.Info("PostgreSQL ready, migrations applied")

	// ─── Service ───────────────────────────────────────────────
	svc := service.New(repo, cph)

	// ─── Gin router ────────────────────────────────────────────
	if cfg.Env == "production" {
		gin.SetMode(gin.ReleaseMode)
	}
	router := gin.New()
	router.Use(gin.Recovery())
	router.Use(handlers.CORS())
	router.Use(requestIDMiddleware())
	router.Use(accessLogMiddleware(log))

	router.GET("/health", func(c *gin.Context) { c.JSON(http.StatusOK, gin.H{"status": "ok", "service": "account-manager"}) })
	router.GET("/health/live", func(c *gin.Context) { c.Status(http.StatusOK) })
	router.GET("/health/full", func(c *gin.Context) { c.JSON(http.StatusOK, gin.H{"status": "ok", "service": "account-manager", "ts": time.Now().UTC().Format(time.RFC3339)}) })
	router.GET("/metrics", gin.WrapH(promhttp.Handler()))

	h := handlers.New(svc)
	handlers.Register(router, h)

	// ─── HTTP server ───────────────────────────────────────────
	srv := &http.Server{
		Addr:              ":" + port,
		Handler:           router,
		ReadTimeout:       15 * time.Second,
		WriteTimeout:      30 * time.Second,
		IdleTimeout:       120 * time.Second,
		ReadHeaderTimeout: 5 * time.Second,
	}

	go func() {
		log.Info("account-manager starting", "port", port, "env", cfg.Env)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Error("HTTP server failed", err)
			os.Exit(1)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Info("Shutting down account-manager...")
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	if err := srv.Shutdown(ctx); err != nil {
		log.Error("Forced shutdown", err)
	}
	log.Info("account-manager stopped")
}

// ─── Middlewares ────────────────────────────────────────────────

func requestIDMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		rid := c.GetHeader("X-Request-ID")
		if rid == "" {
			rid = time.Now().Format("20060102T150405.000000000")
		}
		c.Set("request_id", rid)
		c.Writer.Header().Set("X-Request-ID", rid)
		c.Next()
	}
}

func accessLogMiddleware(log interface {
	Info(string, ...any)
	Warn(string, ...any)
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
		}
		rid, _ := c.Get("request_id")
		if rid != nil {
			fields = append(fields, "request_id", rid)
		}
		if c.Writer.Status() >= 400 {
			log.Warn("request", fields...)
		} else {
			log.Info("request", fields...)
		}
	}
}
