// Package main implementa el Telegram Bot Service de TNSVT V2.
//
// Responsabilidades:
//   - Enviar notificaciones vía Telegram Bot API (HTTP)
//   - Responder a comandos slash (/status, /balance, etc.)
//   - Sin base de datos — solo NATS + HTTP outbound a Telegram
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

	"github.com/tnsvt/telegram-bot-service/internal/sender"
	"github.com/tnsvt/telegram-bot-service/internal/subscriber"
	"github.com/nats-io/nats.go"
	sharedconfig "github.com/tnsvt/shared-go/config"
	sharedlogging "github.com/tnsvt/shared-go/logging"
)

func main() {
	cfg := sharedconfig.Load("telegram-bot-service")
	port := cfg.Get("TELEGRAM_BOT_PORT", "8503")
	botToken := cfg.Get("TELEGRAM_BOT_TOKEN", "")
	log := sharedlogging.New("telegram-bot-service", cfg.LogLevel)

	if botToken == "" {
		log.Error("TELEGRAM_BOT_TOKEN is required", errors.New("missing token"))
		os.Exit(1)
	}

	var natsConn *nats.Conn
	var err error
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

	s := sender.New(botToken, log)
	subCtx, subCancel := context.WithCancel(context.Background())
	defer subCancel()

	sub := subscriber.New(natsConn, s, log)
	if err := sub.Start(subCtx); err != nil {
		log.Error("Subscriber start failed", err)
		os.Exit(1)
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"status":"ok","service":"telegram-bot-service","version":"0.1.0"}`))
	})
	mux.HandleFunc("/health/live", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})
	mux.HandleFunc("/health/ready", func(w http.ResponseWriter, r *http.Request) {
		if natsConn.Status() != nats.CONNECTED {
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
		log.Info("telegram-bot-service starting", "port", port, "env", cfg.Env)
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
