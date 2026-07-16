// Package main implementa el User Service de TNSVT V2.
//
// Responsabilidades:
//   - CRUD de perfiles de usuario (full_name, avatar, timezone, language, phone)
//   - Preferencias y configuración de notificaciones
//   - Cache en Redis
//   - Publicación de eventos NATS en actualizaciones
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

	"github.com/tnsvt/user-service/internal/handlers"
	"github.com/tnsvt/user-service/internal/repository"
	sharedconfig "github.com/tnsvt/shared-go/config"
	sharedlogging "github.com/tnsvt/shared-go/logging"
)

func main() {
	cfg := sharedconfig.Load("user-service")
	port := cfg.Get("USER_SERVICE_PORT", "8401")
	log := sharedlogging.New("user-service", cfg.LogLevel)

	// Redis (cache)
	rdb := redis.NewClient(&redis.Options{
		Addr:     cfg.Redis.Addr(),
		Password: cfg.Redis.Password,
		DB:       cfg.Redis.DB,
	})
	defer rdb.Close()

	// PostgreSQL
	pgxCfg, err := pgxpool.ParseConfig(cfg.Postgres.DSN())
	if err != nil {
		log.Error("Invalid PostgreSQL DSN", err)
		os.Exit(1)
	}
	pgxCfg.MaxConns = 10
	pgPool, err := pgxpool.NewWithConfig(context.Background(), pgxCfg)
	if err != nil {
		log.Error("PostgreSQL pool failed", err)
		os.Exit(1)
	}
	defer pgPool.Close()

	repo := repository.New(pgPool)
	if err := repo.RunMigrations(context.Background()); err != nil {
		log.Error("Migrations failed", err)
		os.Exit(1)
	}

	// NATS
	var natsConn *nats.Conn
	for i := 0; i < 3; i++ {
		natsConn, err = nats.Connect(cfg.NATS.URL())
		if err == nil {
			break
		}
		log.Warn("NATS retry", "attempt", i+1, "error", err.Error())
		time.Sleep(2 * time.Second)
	}
	if err != nil {
		log.Error("NATS unavailable", err)
		os.Exit(1)
	}
	defer natsConn.Close()

	// Gin router
	gin.SetMode(gin.ReleaseMode)
	router := gin.New()
	router.Use(gin.Recovery())
	router.Use(handlers.AccessLog(log))
	router.Use(handlers.CORS())

	h := handlers.New(repo, log)
	api := router.Group("/api/v1/users")
	{
		api.GET("/:id/profile", h.GetProfile)
		api.POST("/:id/profile", h.CreateProfile)
		api.PUT("/:id/profile", h.UpdateProfile)
	}

	router.GET("/health", func(c *gin.Context) {
		if err := repo.Ping(c.Request.Context()); err != nil {
			c.JSON(http.StatusServiceUnavailable, gin.H{"status": "degraded"})
			return
		}
		c.JSON(http.StatusOK, gin.H{"status": "ok", "service": "user-service", "version": "0.1.0"})
	})
	router.GET("/health/live", func(c *gin.Context) { c.Status(http.StatusOK) })
	router.GET("/health/ready", func(c *gin.Context) {
		if err := repo.Ping(c.Request.Context()); err != nil {
			c.JSON(http.StatusServiceUnavailable, gin.H{"status": "not_ready"})
			return
		}
		if natsConn.Status() != nats.CONNECTED {
			c.JSON(http.StatusServiceUnavailable, gin.H{"status": "not_ready", "reason": "nats"})
			return
		}
		c.JSON(http.StatusOK, gin.H{"status": "ready"})
	})
	router.GET("/metrics", gin.WrapH(promhttp.Handler()))

	srv := &http.Server{
		Addr:              ":" + port,
		Handler:           router,
		ReadTimeout:       10 * time.Second,
		WriteTimeout:      10 * time.Second,
		IdleTimeout:       60 * time.Second,
		ReadHeaderTimeout: 5 * time.Second,
	}

	go func() {
		log.Info("user-service starting", "port", port, "env", cfg.Env)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Error("HTTP server failed", err)
			os.Exit(1)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Info("Shutting down...")
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	srv.Shutdown(ctx)
	log.Info("Stopped")
}
