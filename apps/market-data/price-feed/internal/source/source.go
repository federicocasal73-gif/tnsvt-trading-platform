package source

import (
	"context"
	"encoding/json"
	"fmt"
	"math"
	"math/rand"
	"net/http"
	"sync"
	"time"

	"github.com/gorilla/websocket"

	"github.com/tnsvt/price-feed/internal/models"
)

// Logger is the minimal logging interface required by sources.
type Logger interface {
	Info(string, ...any)
	Warn(string, ...any)
	Error(string, error, ...any)
}

// Source is a single upstream price feed (one WebSocket connection).
type Source struct {
	Name     string
	URL      string
	Symbols  []string
	OnTick   func(models.Tick)
	Log      Logger

	mu      sync.Mutex
	stopped bool
	cancel  context.CancelFunc
}

// ─── Manager ─────────────────────────────────────────────────────────────

// Manager owns a set of sources and orchestrates their lifecycle.
type Manager struct {
	log     Logger
	store   *models.TickStore
	pub     Publisher
	mu      sync.Mutex
	sources []*Source
	running bool
}

// Publisher is the minimal interface the manager needs to publish ticks.
type Publisher interface {
	Publish(t models.Tick) error
}

// NewManager returns a fresh manager.
func NewManager(log Logger, store *models.TickStore, pub Publisher) *Manager {
	return &Manager{log: log, store: store, pub: pub}
}

// Add registers a source. Safe to call before Start.
func (m *Manager) Add(s *Source) {
	m.mu.Lock()
	m.sources = append(m.sources, s)
	m.mu.Unlock()
}

// Sources returns a snapshot of registered sources.
func (m *Manager) Sources() []SourceStatus {
	m.mu.Lock()
	defer m.mu.Unlock()
	out := make([]SourceStatus, 0, len(m.sources))
	for _, s := range m.sources {
		out = append(out, SourceStatus{Name: s.Name, URL: s.URL, Symbols: s.Symbols})
	}
	return out
}

// Start kicks off all registered sources. Idempotent.
func (m *Manager) Start(ctx context.Context) {
	m.mu.Lock()
	if m.running {
		m.mu.Unlock()
		return
	}
	m.running = true
	srcs := make([]*Source, len(m.sources))
	copy(srcs, m.sources)
	m.mu.Unlock()

	for _, s := range srcs {
		sCtx, cancel := context.WithCancel(ctx)
		s.cancel = cancel
		s.OnTick = m.handleTick
		go s.run(sCtx)
	}
}

// Stop cancels all source goroutines.
func (m *Manager) Stop() {
	m.mu.Lock()
	defer m.mu.Unlock()
	for _, s := range m.sources {
		if s.cancel != nil {
			s.cancel()
		}
		s.stopped = true
	}
	m.running = false
}

func (m *Manager) handleTick(t models.Tick) {
	m.store.Set(t)
	if m.pub != nil {
		if err := m.pub.Publish(t); err != nil {
			m.log.Warn("nats.publish_failed", "symbol", t.Symbol, "error", err.Error())
		}
	}
}

// SourceStatus is the public view of a source (no internal state).
type SourceStatus struct {
	Name    string   `json:"name"`
	URL     string   `json:"url,omitempty"`
	Symbols []string `json:"symbols"`
}

// ─── MockSource (remote or builtin) ──────────────────────────────────────

// NewMockSource returns a Source that connects to an external mock server via WebSocket.
func NewMockSource(name, url string, symbols []string, log Logger) *Source {
	return &Source{Name: name, URL: url, Symbols: symbols, Log: log}
}

// NewBuiltinMockSource returns a Source that emits synthetic ticks without any network.
// Useful for local development and tests.
func NewBuiltinMockSource(name string, symbols []string, log Logger) *Source {
	return &Source{Name: name, Symbols: symbols, Log: log}
}

// run starts the source's event loop. For external mocks it opens a WebSocket;
// for builtin mocks it generates ticks in a ticker.
func (s *Source) run(ctx context.Context) {
	if s.URL == "" {
		s.runBuiltin(ctx)
		return
	}
	s.runWebSocket(ctx)
}

func (s *Source) runBuiltin(ctx context.Context) {
	interval := 500 * time.Millisecond
	t := time.NewTicker(interval)
	defer t.Stop()

	rng := rand.New(rand.NewSource(time.Now().UnixNano()))
	// Seed prices with sane defaults
	seedPrices := map[string]float64{
		"EURUSD": 1.0850, "GBPUSD": 1.2650, "USDJPY": 154.20, "XAUUSD": 2025.50,
		"BTCUSD": 60000.00, "ETHUSD": 3500.00, "XAGUSD": 25.00, "NAS100": 17000.00,
	}
	for _, sym := range s.Symbols {
		if _, ok := seedPrices[sym]; !ok {
			seedPrices[sym] = 1.0000
		}
	}

	s.Log.Info("source.builtin_mock_started", "name", s.Name, "symbols", len(s.Symbols))

	for {
		select {
		case <-ctx.Done():
			s.Log.Info("source.builtin_mock_stopped", "name", s.Name)
			return
		case <-t.C:
			for _, sym := range s.Symbols {
				base := seedPrices[sym]
				// Random walk: ±0.05% per tick
				delta := (rng.Float64() - 0.5) * 0.001 * base
				base += delta
				seedPrices[sym] = base
				spread := base * 0.0001 // 1 pip for forex-like
				s.emit(models.Tick{
					Symbol:    sym,
					Bid:       base - spread/2,
					Ask:       base + spread/2,
					Last:      base,
					Volume:    math.Floor(rng.Float64() * 1000),
					Source:    s.Name,
					Timestamp: time.Now().UTC(),
				})
			}
		}
	}
}

func (s *Source) runWebSocket(ctx context.Context) {
	backoff := time.Second
	maxBackoff := 30 * time.Second

	for {
		if ctx.Err() != nil {
			return
		}
		err := s.connectAndRead(ctx)
		if ctx.Err() != nil {
			return
		}
		s.Log.Warn("source.ws_disconnected", "name", s.Name, "error", errString(err))
		time.Sleep(backoff)
		backoff *= 2
		if backoff > maxBackoff {
			backoff = maxBackoff
		}
	}
}

func (s *Source) connectAndRead(ctx context.Context) error {
	dialer := websocket.Dialer{HandshakeTimeout: 10 * time.Second}
	conn, _, err := dialer.Dial(s.URL, http.Header{})
	if err != nil {
		return err
	}
	defer conn.Close()

	s.Log.Info("source.ws_connected", "name", s.Name, "url", s.URL)

	// Send subscribe message if any (format depends on source)
	subscribe := map[string]any{"action": "subscribe", "symbols": s.Symbols}
	if err := conn.WriteJSON(subscribe); err != nil {
		return err
	}

	// Set a read deadline and reset on each message
	conn.SetReadDeadline(time.Now().Add(60 * time.Second))

	for {
		if ctx.Err() != nil {
			return ctx.Err()
		}
		_, msg, err := conn.ReadMessage()
		if err != nil {
			return err
		}
		conn.SetReadDeadline(time.Now().Add(60 * time.Second))

		var raw struct {
			Symbol string  `json:"symbol"`
			Bid    float64 `json:"bid"`
			Ask    float64 `json:"ask"`
			Last   float64 `json:"last"`
			Volume float64 `json:"volume"`
			Time   int64   `json:"timestamp"`
		}
		if err := json.Unmarshal(msg, &raw); err != nil {
			s.Log.Warn("source.ws_bad_payload", "name", s.Name, "error", err.Error())
			continue
		}
		if raw.Symbol == "" {
			continue
		}
		ts := time.Now().UTC()
		if raw.Time > 0 {
			ts = time.UnixMilli(raw.Time).UTC()
		}
		s.emit(models.Tick{
			Symbol:    raw.Symbol,
			Bid:       raw.Bid,
			Ask:       raw.Ask,
			Last:      raw.Last,
			Volume:    raw.Volume,
			Source:    s.Name,
			Timestamp: ts,
		})
	}
}

func (s *Source) emit(t models.Tick) {
	if s.OnTick != nil {
		s.OnTick(t)
	}
}

func errString(e error) string {
	if e == nil {
		return ""
	}
	return e.Error()
}

// ─── Test helpers ────────────────────────────────────────────────────────

// ParseSymbols is exposed for tests and main().
func ParseSymbols(raw string) []string {
	out := make([]string, 0, 8)
	start := 0
	for i := 0; i <= len(raw); i++ {
		if i == len(raw) || raw[i] == ',' {
			tok := raw[start:i]
			// trim
			for len(tok) > 0 && tok[0] == ' ' {
				tok = tok[1:]
			}
			for len(tok) > 0 && tok[len(tok)-1] == ' ' {
				tok = tok[:len(tok)-1]
			}
			if tok != "" {
				out = append(out, tok)
			}
			start = i + 1
		}
	}
	return out
}

// FormatTick returns a JSON-ish representation (for logging).
func FormatTick(t models.Tick) string {
	return fmt.Sprintf("%s bid=%.5f ask=%.5f last=%.5f src=%s", t.Symbol, t.Bid, t.Ask, t.Last, t.Source)
}