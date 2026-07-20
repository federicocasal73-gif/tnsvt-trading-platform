// Package main implementa el API Gateway de TNSVT V2.
//
// Responsabilidades:
//   - Reverse proxy a todos los microservicios
//   - Validación centralizada de JWT
//   - Rate limiting global (Redis)
//   - Circuit breaker por servicio
//   - Load balancing (round-robin entre instancias)
//   - Publicación de eventos a NATS (audit, métricas)
//   - Agregación de health checks
//   - CORS centralizado
//
// Routing:
//   /api/v1/auth/*          → auth-service:8001
//   /api/v1/users/*         → user-service:8401
//   /api/v1/signals/*       → signal-engine:8003
//   /api/v1/executions/*    → execution-engine:8004
//   /api/v1/copy/*          → copy-trading:8005
//   /api/v1/risk/*          → risk-engine:8006
//   /api/v1/brokers/*       → mt5-connector:8007
//   /api/v1/audit/*         → audit-engine:8600
//   /api/v1/ai/*            → ai-core:8200
//   /api/v1/prices/*        → price-feed:8300
//   /api/v1/notify/*        → telegram-bot-service:8503
//   /api/v1/users/*         → user-service:8401
//
// Endpoints propios:
//   GET    /health
//   GET    /health/full
//   GET    /metrics
package main

import (
	"context"
	"errors"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"os/signal"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/nats-io/nats.go"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/redis/go-redis/v9"

	"github.com/tnsvt/api-gateway/internal/config"
	"github.com/tnsvt/api-gateway/internal/handlers"
	"github.com/tnsvt/api-gateway/internal/middleware"
	"github.com/tnsvt/api-gateway/internal/proxy"
	sharedconfig "github.com/tnsvt/shared-go/config"
	sharedlogging "github.com/tnsvt/shared-go/logging"
)

func main() {
	// ─── Config ───
	cfg := sharedconfig.Load("api-gateway")
	port := cfg.Get("API_GATEWAY_PORT", "8000")
	servicesCfg := config.LoadServices(os.Getenv("SERVICES_CONFIG"))

	// ─── Logging ───
	log := sharedlogging.New("api-gateway", cfg.LogLevel)

	// ─── Redis ───
	redisClient := redis.NewClient(&redis.Options{
		Addr:     cfg.Redis.Addr(),
		Password: cfg.Redis.Password,
		DB:       cfg.Redis.DB,
	})
	defer redisClient.Close()

	// ─── NATS ───
	var natsConn *nats.Conn
	var ncErr error
	for i := 0; i < 3; i++ {
		natsConn, ncErr = nats.Connect(cfg.NATS.URL())
		if ncErr == nil {
			break
		}
		log.Warn("NATS connection retry", "attempt", i+1, "error", ncErr.Error())
		time.Sleep(2 * time.Second)
	}
	if ncErr != nil {
		log.Warn("NATS unavailable, continuing without event publishing", "error", ncErr.Error())
	} else {
		defer natsConn.Close()
	}

	// ─── Service Registry (con load balancer + circuit breaker) ───
	registry := proxy.NewServiceRegistry(servicesCfg, log)

	// Iniciar health checks
	healthCtx, healthCancel := context.WithCancel(context.Background())
	defer healthCancel()
	registry.StartHealthChecks(healthCtx, 10*time.Second)

	// ─── JWT Validator ───
	jwtValidator := middleware.NewJWTValidator(cfg.Auth.JWTAccessTokenExpire)

	// ─── Gin router ───
	if cfg.Env == "production" {
		gin.SetMode(gin.ReleaseMode)
	}

	router := gin.New()
	router.Use(gin.Recovery())
	router.Use(middleware.RequestID())
	router.Use(middleware.AccessLog(log))
	router.Use(middleware.CORS())
	router.Use(middleware.Metrics())

	// ─── Health endpoints ───
	healthHandler := handlers.NewHealthHandler(registry, redisClient, natsConn)
	router.GET("/health", healthHandler.Health)
	router.GET("/health/full", healthHandler.HealthFull)
	router.GET("/health/live", func(c *gin.Context) { c.Status(http.StatusOK) })

	// ─── Metrics ───
	router.GET("/metrics", gin.WrapH(promhttp.Handler()))

	// ─── API Routes (con JWT validation y proxy) ───
	v1 := router.Group("/api/v1")

	for _, svc := range servicesCfg {
		pathPrefix := svc.PathPrefix
		if pathPrefix == "" {
			continue
		}

		// Strip leading /api/v1 to avoid double prefix (router group is /api/v1)
		stripped := strings.TrimPrefix(pathPrefix, "/api/v1")

		svcCfg := svc
		v1.Group(stripped).
			Use(middleware.GlobalRateLimit(redisClient, svcCfg.RateLimit, time.Minute)).
			Use(middleware.OptionalAuth(jwtValidator)).
			Use(middleware.CircuitBreaker(registry, svcCfg.Name)).
			Any("/*proxyPath", proxy.ReverseProxy(registry, svcCfg.Name, log, natsConn))
	}

	// ─── Root catch-all ───
	router.GET("/", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"service":     "api-gateway",
			"version":     "0.1.0",
			"phase":       "1-mvp",
			"environment": cfg.Env,
			"endpoints": gin.H{
				"health": "/health",
				"health_full": "/health/full",
				"metrics": "/metrics",
				"docs": "https://docs.tnsvt.io",
			},
		})
	})

	router.NoRoute(func(c *gin.Context) {
		c.JSON(http.StatusNotFound, gin.H{
			"error": "endpoint not found",
			"path":  c.Request.URL.Path,
			"hint":  "try /api/v1/auth/login or see /health for service status",
		})
	})

	// ─── HTTP server ───
	srv := &http.Server{
		Addr:              ":" + port,
		Handler:           router,
		ReadTimeout:       30 * time.Second,
		WriteTimeout:      30 * time.Second,
		IdleTimeout:       120 * time.Second,
		ReadHeaderTimeout: 10 * time.Second,
	}

	// ─── Graceful shutdown ───
	go func() {
		log.Info("api-gateway starting", "port", port, "env", cfg.Env, "services", len(servicesCfg))
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Error("HTTP server failed", err)
			os.Exit(1)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Info("Shutting down api-gateway...")
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		log.Error("Forced shutdown", err)
	}
	log.Info("api-gateway stopped")
}

// ─── Standalone helper (kept for reference) ────────────────────

var _ = sync.Mutex{}
var _ = atomic.Int32{}
var _ = httputil.NewSingleHostReverseProxy
var _ = url.Parse