// Package main implementa el MT5 Connector de TNSVT V2.
//
// IMPORTANTE: Este servicio SOLO corre en Windows (donde está instalado MT5).
// Compilación cross-platform con tags de build.
//
// Responsabilidades:
//   - Conectar a MetaTrader 5 terminal (librería MetaTrader5 Python via gRPC, OR DLL via cgo)
//   - Exponer API HTTP para que execution-engine coloque/cierre órdenes
//   - Implementar la interfaz Connector (PlaceOrder, ClosePosition, GetPositions, etc.)
//   - Publicar eventos a NATS (trading.execution.*, trading.position.*)
//   - Multi-cuenta: las credenciales vienen del account-manager (PostgreSQL, AES-GCM).
//     El proceso mantiene UNA sesión de MT5 y cambia entre cuentas vía mt5.login().
//
// Endpoints:
//   POST /api/v1/brokers/orders                  # Place order (con account_id)
//   POST /api/v1/brokers/positions/close        # Close position
//   GET  /api/v1/brokers/accounts/:id           # Account info
//   GET  /api/v1/brokers/accounts/:id/positions # Open positions
//   POST /api/v1/brokers/positions/:ticket/modify  # Modify SL/TP
//   GET  /health, /health/live, /health/ready, /metrics
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

	"github.com/tnsvt/mt5-connector/internal/handlers"
	"github.com/tnsvt/mt5-connector/internal/mt5"
	"github.com/tnsvt/mt5-connector/internal/session"
	sharedconfig "github.com/tnsvt/shared-go/config"
	sharedlogging "github.com/tnsvt/shared-go/logging"
)

func main() {
	cfg := sharedconfig.Load("mt5-connector")
	port := cfg.Get("MT5_CONNECTOR_PORT", "8007")
	log := sharedlogging.New("mt5-connector", cfg.LogLevel)

	// ─── MT5 Client (single session, multi-account via login switch) ───
	mt5Path := cfg.Get("MT5_PATH", "C:\\Program Files\\FTMO MetaTrader 5\\terminal64.exe")
	// MT5_LOGIN ya NO se usa para autenticar; las credenciales vienen
	// del account-manager. Sólo se conserva como hint de qué cuenta
	// intentar primero al arranque.
	mt5Login := cfg.GetInt("MT5_LOGIN", 0)
	symbolSuffix := cfg.Get("MT5_SYMBOL_SUFFIX", "")
	magicNumber := int64(cfg.GetInt("MT5_MAGIC_NUMBER", 123456))

	mt5Client := mt5.NewClient(mt5.Config{
		Path:         mt5Path,
		Login:        mt5Login,
		SymbolSuffix: symbolSuffix,
		MagicNumber:  magicNumber,
		Timeout:      time.Duration(cfg.GetInt("MT5_TIMEOUT_SECONDS", 30)) * time.Second,
	}, log)

	// ─── Multi-account credentials manager ───
	credMgr := session.NewManager()
	if err := credMgr.RefreshCreds(); err != nil {
		log.Warn("account-manager unreachable at startup, will retry in background", "error", err.Error())
	} else {
		log.Info("loaded credentials from account-manager", "accounts", credMgr.Count())
	}

	// Try to connect (non-fatal — service can start without MT5)
	if err := mt5Client.Connect(context.Background()); err != nil {
		log.Warn("MT5 not connected at startup, will retry on demand", "error", err.Error())
	}

	// Background reconnect loop
	connectCtx, connectCancel := context.WithCancel(context.Background())
	defer connectCancel()
	go mt5Client.RunReconnectLoop(connectCtx, 30*time.Second)

	// Background credentials refresh (cada 5 min)
	go func() {
		ticker := time.NewTicker(5 * time.Minute)
		defer ticker.Stop()
		for {
			select {
			case <-connectCtx.Done():
				return
			case <-ticker.C:
				if err := credMgr.RefreshCreds(); err != nil {
					log.Warn("creds refresh failed", "error", err.Error())
				} else {
					log.Debug("creds refreshed", "accounts", credMgr.Count())
				}
			}
		}
	}()

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
	router.GET("/health", handlers.Health(mt5Client))
	router.GET("/health/live", func(c *gin.Context) { c.Status(http.StatusOK) })
	router.GET("/health/ready", handlers.HealthReady(mt5Client))
	router.GET("/metrics", gin.WrapH(promhttp.Handler()))

	// ─── API ───
	brokerHandler := handlers.NewBrokerHandler(mt5Client, credMgr, log)

	router.GET("/rates", brokerHandler.GetRatesAll)
	v1 := router.Group("/api/v1/brokers")
	{
		v1.POST("/orders", brokerHandler.PlaceOrder)
		v1.POST("/positions/close", brokerHandler.ClosePosition)
		v1.GET("/accounts/:id", brokerHandler.GetAccountInfo)
		v1.GET("/accounts/:id/positions", brokerHandler.GetPositions)
		v1.POST("/positions/:ticket/modify", brokerHandler.ModifyPosition)
		v1.GET("/symbols/:symbol", brokerHandler.GetSymbolInfo)
		v1.GET("/symbols/:symbol/rates", brokerHandler.GetRates)
		v1.GET("/rates", brokerHandler.GetRatesAll)
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
		log.Info("mt5-connector starting", "port", port, "env", cfg.Env, "mt5_path", mt5Path, "multi_account", true)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Error("HTTP server failed", err)
			os.Exit(1)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Info("Shutting down mt5-connector...")
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	mt5Client.Shutdown()
	if err := srv.Shutdown(ctx); err != nil {
		log.Error("Forced shutdown", err)
	}
	log.Info("mt5-connector stopped")
}