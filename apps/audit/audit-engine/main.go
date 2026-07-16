// Package main implementa el Audit Engine de TNSVT V2.
//
// Responsabilidades:
//   - Consumir eventos de negocio de NATS (trading.>, audit.>, platform.>, risk.>)
//   - Almacenar de forma append-only e inmutable en audit.events
//   - Exponer health checks y métricas
//
// Es el servicio más simple: sin lógica de negocio, solo persistencia.
package main

import (
	"context"
	"errors"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/prometheus/client_golang/prometheus/promhttp"

	"github.com/tnsvt/audit-engine/internal/repository"
	"github.com/tnsvt/audit-engine/internal/subscriber"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/nats-io/nats.go"
	sharedconfig "github.com/tnsvt/shared-go/config"
	sharedlogging "github.com/tnsvt/shared-go/logging"
)

func main() {
	cfg := sharedconfig.Load("audit-engine")
	port := cfg.Get("AUDIT_ENGINE_PORT", "8600")
	log := sharedlogging.New("audit-engine", cfg.LogLevel)

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

	// Subscriber
	subCtx, subCancel := context.WithCancel(context.Background())
	defer subCancel()

	sub := subscriber.New(natsConn, repo, log)
	if err := sub.Start(subCtx); err != nil {
		log.Error("Subscriber start failed", err)
		os.Exit(1)
	}

	// HTTP server (solo health + metrics)
	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		if err := repo.Ping(r.Context()); err != nil {
			w.WriteHeader(http.StatusServiceUnavailable)
			w.Write([]byte(`{"status":"degraded"}`))
			return
		}
		w.Write([]byte(`{"status":"ok","service":"audit-engine","version":"0.1.0"}`))
	})
	mux.HandleFunc("/health/live", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})
	mux.HandleFunc("/health/ready", func(w http.ResponseWriter, r *http.Request) {
		if err := repo.Ping(r.Context()); err != nil {
			w.WriteHeader(http.StatusServiceUnavailable)
			w.Write([]byte(`{"status":"not_ready"}`))
			return
		}
		w.Write([]byte(`{"status":"ready"}`))
	})
	mux.Handle("/metrics", promhttp.Handler())

	srv := &http.Server{
		Addr:              ":" + port,
		Handler:           mux,
		ReadTimeout:       10 * time.Second,
		WriteTimeout:      10 * time.Second,
		IdleTimeout:       60 * time.Second,
		ReadHeaderTimeout: 5 * time.Second,
	}

	go func() {
		log.Info("audit-engine starting", "port", port, "env", cfg.Env)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Error("HTTP server failed", err)
			os.Exit(1)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Info("Shutting down audit-engine...")
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	srv.Shutdown(ctx)
	log.Info("audit-engine stopped")
}
