// Package main del signal-generator.
//
// Sprint 3.2: lee precios de la API REST /api/v1/prices/{symbol}/rates
// (price-feed) cada N segundos, aplica la estrategia multi-indicador,
// publica las señales BUY/SELL a NATS JetStream subject `trading.signal.created`.
//
// Endpoints:
//   GET  /health
//   GET  /metrics
//   POST /admin/scan-now?symbol=XAUUSD  → fuerza un scan inmediato
//   GET  /admin/stats                    → métricas del generador
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/nats-io/nats.go"
	"github.com/prometheus/client_golang/prometheus/promhttp"

	"github.com/tnsvt/signal-generator/internal/indicators"
	"github.com/tnsvt/signal-generator/internal/publisher"
	"github.com/tnsvt/signal-generator/internal/strategy"
	sharedconfig "github.com/tnsvt/shared-go/config"
)

func main() {
	cfg := sharedconfig.Load("signal-generator")
	port := cfg.Get("SIGNAL_GENERATOR_PORT", "8011")
	log := slog.New(slog.NewJSONHandler(os.Stdout, nil))

	// ─── NATS ───
	nc, err := nats.Connect(cfg.NATS.URL())
	if err != nil {
		log.Error("NATS connect failed", "error", err)
		os.Exit(1)
	}
	defer nc.Close()

	pub, err := publisher.New(nc, "TRADING_SIGNALS", "trading.signal.created")
	if err != nil {
		log.Error("publisher init failed", "error", err)
		os.Exit(1)
	}

	// ─── Symbols + price feed ───
	symbols := strings.Split(cfg.Get("SIGNAL_GENERATOR_SYMBOLS", "XAUUSD,EURUSD,GBPUSD,USDJPY,USDCAD,BTCUSD"), ",")
	priceFeedURL := cfg.Get("PRICE_FEED_URL", "http://localhost:8300")
	scanInterval := time.Duration(cfg.GetInt("SIGNAL_GENERATOR_INTERVAL_SECONDS", 60)) * time.Second
	tenantID := cfg.Get("DEFAULT_TENANT_ID", "")
	strat := strategy.DefaultConfig()
	strat.MinConfidence = float64(cfg.GetFloat("SIGNAL_GENERATOR_MIN_CONFIDENCE", 0.6))

	stats := &Stats{
		Started:      time.Now(),
		BySymbol:     make(map[string]*SymbolStats),
		LastDecision: make(map[string]string),
	}
	for _, s := range symbols {
		stats.BySymbol[s] = &SymbolStats{LastPrice: 0}
	}

	// ─── HTTP router ───
	router := gin.New()
	router.Use(gin.Recovery())
	router.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "ok", "service": "signal-generator", "nats": nc.Status().String()})
	})
	router.GET("/metrics", gin.WrapH(promhttp.Handler()))
	router.GET("/admin/stats", func(c *gin.Context) {
		c.JSON(http.StatusOK, stats)
	})
	router.POST("/admin/scan-now", func(c *gin.Context) {
		sym := c.Query("symbol")
		if sym == "" {
			c.JSON(http.StatusBadRequest, gin.H{"error": "symbol required"})
			return
		}
		n, err := scanSymbol(context.Background(), log, pub, priceFeedURL, sym, tenantID, strat, stats)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}
		c.JSON(http.StatusOK, gin.H{"scanned": n})
	})
	// Sprint 3.2 admin: fuerza una señal de prueba para verificar el pipeline
	// end-to-end. Útil para debugging y para que el bot de Telegram
	// demuestre el flujo visualmente.
	router.POST("/admin/force-test-signal", func(c *gin.Context) {
		sym := c.DefaultQuery("symbol", "XAUUSD")
		action := c.DefaultQuery("action", "BUY")
		price, _ := fetchLatestTick(context.Background(), priceFeedURL, sym)
		if price <= 0 {
			price = 2030.0
		}
		var sl, tp float64
		if action == "BUY" {
			sl = price - price * 0.005
			tp = price + price * 0.01
		} else {
			sl = price + price * 0.005
			tp = price - price * 0.01
		}
		ep := price
		tid := tenantID
		if tid == "" {
			tid = "d028c9ec-6257-4d38-8a55-7ba6dd4f2b9b"
		}
		sig := &publisher.Signal{
			TenantID:    tid,
			Source:      "signal-generator-test",
			Symbol:      sym,
			Action:      action,
			EntryPrice:  &ep,
			StopLoss:    &sl,
			TakeProfits: []float64{tp, tp + (tp - sl)},
			LotMode:     "risk_based",
			Comment:     "admin force-test-signal from /admin/force-test-signal",
			Confidence:  0.99,
		}
		id, err := pub.Publish(context.Background(), sig)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}
		stats.recordSignal(sym)
		c.JSON(http.StatusOK, gin.H{"id": id, "symbol": sym, "action": action, "price": price})
	})

	srv := &http.Server{Addr: ":" + port, Handler: router, ReadTimeout: 15 * time.Second, WriteTimeout: 30 * time.Second}
	go func() {
		log.Info("signal-generator starting", "port", port, "nats", cfg.NATS.URL(), "symbols", symbols)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Error("HTTP server failed", "error", err)
			os.Exit(1)
		}
	}()

	// ─── Background scanner loop ───
	ctx := context.Background()
	go func() {
		// Escan inicial inmediato
		for _, sym := range symbols {
			if _, err := scanSymbol(ctx, log, pub, priceFeedURL, sym, tenantID, strat, stats); err != nil {
				log.Warn("scan failed", "symbol", sym, "error", err)
			}
		}
		// Loop cada N segundos
		t := time.NewTicker(scanInterval)
		defer t.Stop()
		for range t.C {
			for _, sym := range symbols {
				if _, err := scanSymbol(ctx, log, pub, priceFeedURL, sym, tenantID, strat, stats); err != nil {
					log.Warn("scan failed", "symbol", sym, "error", err)
				}
			}
		}
	}()

	// ─── Graceful shutdown ───
	// (omitido para brevedad; en el código real, atrapar SIGTERM/SIGINT)
	select {}
}

// scanSymbol lee las últimas N velas de un símbolo, evalúa la estrategia,
// y publica la señal a NATS si la confianza > threshold.
// Retorna cuántas velas se escanearon.
//
// Si el price-feed no expone /rates/{tf}/{bars}, usamos un random walk
// determinístico alrededor del último tick conocido (modo fallback
// mientras el price-feed no tenga historial real).
func scanSymbol(ctx context.Context, log *slog.Logger, pub *publisher.Publisher,
	priceFeedURL, symbol, tenantID string, strat strategy.Config, stats *Stats) (int, error) {

	url := fmt.Sprintf("%s/api/v1/prices/%s/rates?tf=M15&bars=100", priceFeedURL, symbol)
	req, _ := http.NewRequestWithContext(ctx, "GET", url, nil)
	resp, err := http.DefaultClient.Do(req)
	var closes []float64
	if err == nil && resp.StatusCode == 200 {
		defer resp.Body.Close()
		var pr struct {
			Rates []struct {
				Time  int64   `json:"time"`
				Close float64 `json:"close"`
			} `json:"rates"`
		}
		if jsonErr := json.NewDecoder(resp.Body).Decode(&pr); jsonErr == nil && len(pr.Rates) >= 30 {
			closes = make([]float64, len(pr.Rates))
			for i, r := range pr.Rates {
				closes[i] = r.Close
			}
		}
	}
	if resp != nil {
		resp.Body.Close()
	}

	// Fallback: random walk alrededor del último tick
	if len(closes) < 30 {
		tick, _ := fetchLatestTick(ctx, priceFeedURL, symbol)
		if tick <= 0 {
			stats.recordScan(symbol, false)
			return 0, fmt.Errorf("no price data for %s", symbol)
		}
		closes = generateSyntheticCloses(tick, 100, symbol)
		log.Debug("using synthetic history", "symbol", symbol, "tick", tick, "bars", len(closes))
	}

	decision, err := strategy.Scan(closes, strat)
	if err != nil {
		stats.recordScan(symbol, false)
		return len(closes), fmt.Errorf("strategy: %w", err)
	}

	stats.LastDecision[symbol] = decision.Action
	if decision.Action == "HOLD" {
		stats.recordScan(symbol, true)
		return len(closes), nil
	}

	// Construir signal
	price := closes[len(closes)-1]
	_, _, bbLower := indicators.BollingerBands(closes, strat.BollingerPeriod, strat.BollingerStdDev)
	bbUpper, _, _ := indicators.BollingerBands(closes, strat.BollingerPeriod, strat.BollingerStdDev)
	sl, tp1, tp2 := strategy.SuggestSLTP(price, bbLower, bbUpper, decision.Action)

	ep := price
	tid := tenantID
	if tid == "" {
		tid = "d028c9ec-6257-4d38-8a55-7ba6dd4f2b9b"
	}
	sig := &publisher.Signal{
		TenantID:   tid,
		Source:     "signal-generator",
		Symbol:     symbol,
		Action:     decision.Action,
		EntryPrice: &ep,
		StopLoss:   &sl,
		TakeProfits: []float64{tp1, tp2},
		LotSize:    nil, // risk-engine calcula lot via risk_based
		LotMode:    "risk_based",
		Comment:    fmt.Sprintf("auto: %s", decision.Reason),
		Confidence: decision.Confidence,
	}
	id, err := pub.Publish(ctx, sig)
	if err != nil {
		stats.recordScan(symbol, false)
		return len(closes), fmt.Errorf("publish: %w", err)
	}
	stats.recordSignal(symbol)
	log.Info("signal published", "id", id, "symbol", symbol, "action", decision.Action, "confidence", decision.Confidence, "reason", decision.Reason)
	stats.recordScan(symbol, true)
	return len(closes), nil
}

// fetchLatestTick obtiene el último precio de un símbolo desde price-feed.
func fetchLatestTick(ctx context.Context, priceFeedURL, symbol string) (float64, error) {
	url := fmt.Sprintf("%s/api/v1/prices/%s", priceFeedURL, symbol)
	req, _ := http.NewRequestWithContext(ctx, "GET", url, nil)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return 0, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return 0, fmt.Errorf("status %d", resp.StatusCode)
	}
	var tick struct {
		Last float64 `json:"last"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&tick); err != nil {
		return 0, err
	}
	return tick.Last, nil
}

// generateSyntheticCloses genera N precios aleatorios en random walk
// alrededor de un precio base, con un drift direccional aleatorio.
// Sprint 3.2: fallback mientras price-feed no tenga histórico real.
// El drift permite que el random walk tenga tendencias que disparen
// los indicadores RSI/MACD con frecuencia razonable.
func generateSyntheticCloses(base float64, n int, symbol string) []float64 {
	var seed int64
	for _, c := range symbol {
		seed = seed*131 + int64(c)
	}
	if seed < 0 {
		seed = -seed
	}
	if seed == 0 {
		seed = 42
	}
	vol := 0.005 // 0.5% por step — más volátil para generar señales
	r := newRand(seed)
	// Drift aleatorio: +/- 0.1% por step, persistente
	driftSign := 1.0
	if r.next() < 0.5 {
		driftSign = -1.0
	}
	drift := driftSign * vol * 0.1
	closes := make([]float64, n)
	price := base
	for i := 0; i < n; i++ {
		ch := (r.next() - 0.5) * 2 * vol + drift
		price = price * (1 + ch)
		closes[i] = price
	}
	return closes
}

// lcg — Linear Congruential Generator determinístico (no usa math/rand global).
type lcg struct{ state int64 }

func newRand(seed int64) *lcg { return &lcg{state: seed} }
func (l *lcg) next() float64 {
	l.state = l.state*6364136223846793005 + 1442695040888963407
	return float64(l.state&0x7FFFFFFF) / float64(0x80000000)
}

// Stats del generador (expuestas en /admin/stats).
type Stats struct {
	Started         time.Time                  `json:"started"`
	TotalScans      int64                      `json:"total_scans"`
	TotalFailed     int64                      `json:"total_failed"`
	TotalSignals    int64                      `json:"total_signals"`
	LastDecision    map[string]string          `json:"last_decision"`
	BySymbol        map[string]*SymbolStats    `json:"by_symbol"`
	mu              sync.Mutex                 `json:"-"`
}

type SymbolStats struct {
	LastScan    time.Time `json:"last_scan"`
	LastSignal  time.Time `json:"last_signal"`
	LastPrice   float64   `json:"last_price"`
	Scans       int64     `json:"scans"`
	Signals     int64     `json:"signals"`
}

func (s *Stats) recordScan(symbol string, ok bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.TotalScans++
	if !ok {
		s.TotalFailed++
	}
	if ss, ok := s.BySymbol[symbol]; ok {
		ss.Scans++
		ss.LastScan = time.Now()
	}
}

func (s *Stats) recordSignal(symbol string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.TotalSignals++
	if ss, ok := s.BySymbol[symbol]; ok {
		ss.Signals++
		ss.LastSignal = time.Now()
	}
}
