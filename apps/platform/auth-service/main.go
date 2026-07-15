// Package main implementa el servicio de autenticación de TNSVT V2.
//
// Responsabilidades:
//   - Registro y login de usuarios
//   - Multi-tenant (cada usuario pertenece a un tenant)
//   - OAuth2 password grant + refresh tokens
//   - JWT (HS256) con access (15min) + refresh (7d)
//   - bcrypt para passwords (rounds=12)
//   - RBAC: 12 roles, 30+ permisos
//   - Rate limiting por IP y usuario
//   - Audit log de cada intento (login, logout, refresh)
//
// Endpoints:
//   POST   /api/v1/auth/register
//   POST   /api/v1/auth/login
//   POST   /api/v1/auth/refresh
//   POST   /api/v1/auth/logout
//   GET    /api/v1/auth/me
//   POST   /api/v1/auth/password/change
//   POST   /api/v1/auth/2fa/setup
//   POST   /api/v1/auth/2fa/verify
//
//   GET    /health
//   GET    /health/live
//   GET    /health/ready
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

	"github.com/tnsvt/auth-service/internal/handlers"
	"github.com/tnsvt/auth-service/internal/middleware"
	"github.com/tnsvt/auth-service/internal/repository"
	"github.com/tnsvt/auth-service/internal/services"
	sharedconfig "github.com/tnsvt/shared-go/config"
	sharedlogging "github.com/tnsvt/shared-go/logging"
)

func main() {
	// ─── Config ───
	cfg := sharedconfig.Load("auth-service")
	port := cfg.Get("AUTH_SERVICE_PORT", "8001")

	// ─── Logging ───
	log := sharedlogging.New("auth-service", cfg.LogLevel)

	// ─── Redis (rate limiting, sessions) ───
	redisClient := redis.NewClient(&redis.Options{
		Addr:     cfg.Redis.Addr(),
		Password: cfg.Redis.Password,
		DB:       cfg.Redis.DB,
	})
	defer redisClient.Close()

	if err := redisClient.Ping(context.Background()).Err(); err != nil {
		log.Warn("Redis no disponible, continuando sin rate limiting", "error", err.Error())
	}

	// ─── PostgreSQL ───
	repo, err := repository.NewPostgresRepository(cfg.Postgres.DSN(), log)
	if err != nil {
		log.Error("No se pudo conectar a PostgreSQL", err)
		os.Exit(1)
	}
	defer repo.Close()

	if err := repo.RunMigrations(context.Background()); err != nil {
		log.Error("Migraciones fallaron", err)
		os.Exit(1)
	}

	// ─── Services ───
	jwtService := services.NewJWTService(cfg.Auth, log)
	authService := services.NewAuthService(repo, redisClient, jwtService, cfg.Auth, log)

	// ─── Gin router ───
	if cfg.Env == "production" {
		gin.SetMode(gin.ReleaseMode)
	}
	router := gin.New()
	router.Use(gin.Recovery())
	router.Use(middleware.RequestID())
	router.Use(middleware.Logging(log))
	router.Use(middleware.CORS())
	router.Use(middleware.Metrics())

	// ─── Health endpoints ───
	router.GET("/health", handlers.Health(repo))
	router.GET("/health/live", func(c *gin.Context) { c.Status(http.StatusOK) })
	router.GET("/health/ready", handlers.HealthReady(repo, redisClient))

	// ─── Prometheus metrics ───
	router.GET("/metrics", gin.WrapH(promhttp.Handler()))

	// ─── Auth endpoints ───
	authHandler := handlers.NewAuthHandler(authService, log)
	v1 := router.Group("/api/v1/auth")
	{
		v1.POST("/register", middleware.RateLimit(redisClient, "register", 5, 1*time.Minute), authHandler.Register)
		v1.POST("/login", middleware.RateLimit(redisClient, "login", 10, 1*time.Minute), authHandler.Login)
		v1.POST("/refresh", authHandler.Refresh)
		v1.POST("/logout", middleware.RequireAuth(jwtService), authHandler.Logout)
		v1.GET("/me", middleware.RequireAuth(jwtService), authHandler.Me)
		v1.POST("/password/change", middleware.RequireAuth(jwtService), authHandler.ChangePassword)
		v1.POST("/2fa/setup", middleware.RequireAuth(jwtService), authHandler.Setup2FA)
		v1.POST("/2fa/verify", middleware.RequireAuth(jwtService), authHandler.Verify2FA)

		// Admin only
		v1.GET("/users", middleware.RequireAuth(jwtService), middleware.RequireRole("admin", "super_admin"), authHandler.ListUsers)
	}

	// ─── 404 ───
	router.NoRoute(func(c *gin.Context) {
		c.JSON(http.StatusNotFound, gin.H{
			"error": "endpoint not found",
			"path":  c.Request.URL.Path,
		})
	})

	// ─── HTTP server ───
	srv := &http.Server{
		Addr:              ":" + port,
		Handler:           router,
		ReadTimeout:       10 * time.Second,
		WriteTimeout:      10 * time.Second,
		IdleTimeout:       60 * time.Second,
		ReadHeaderTimeout: 5 * time.Second,
	}

	// ─── Graceful shutdown ───
	go func() {
		log.Info("auth-service starting", "port", port, "env", cfg.Env)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Error("HTTP server failed", err)
			os.Exit(1)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Info("Shutting down auth-service...")
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		log.Error("Forced shutdown", err)
	}
	log.Info("auth-service stopped")
}