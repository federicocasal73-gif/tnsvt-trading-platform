package models

import (
	"sync"
	"time"

	"github.com/redis/go-redis/v9"
)

// Tick is the normalized price tick published to NATS and stored
// in memory for the most recent values.
type Tick struct {
	Symbol    string    `json:"symbol"`
	Bid       float64   `json:"bid"`
	Ask       float64   `json:"ask"`
	Last      float64   `json:"last"`
	Volume    float64   `json:"volume"`
	Source    string    `json:"source"`
	Timestamp time.Time `json:"timestamp"`
}

// Mid returns the mid price (average of bid and ask).
func (t Tick) Mid() float64 {
	if t.Bid == 0 && t.Ask == 0 {
		return t.Last
	}
	if t.Bid == 0 {
		return t.Ask
	}
	if t.Ask == 0 {
		return t.Bid
	}
	return (t.Bid + t.Ask) / 2.0
}

// Spread returns bid/ask spread (absolute and percent).
func (t Tick) Spread() (abs float64, pct float64) {
	if t.Bid == 0 || t.Ask == 0 {
		return 0, 0
	}
	abs = t.Ask - t.Bid
	mid := (t.Bid + t.Ask) / 2.0
	if mid > 0 {
		pct = (abs / mid) * 100.0
	}
	return
}

// TickStore keeps the most recent tick per symbol in memory, with
// optional TTL cache in Redis for cross-instance sharing.
type TickStore struct {
	mu      sync.RWMutex
	ticks   map[string]Tick
	subs    map[chan Tick]struct{}
	subsMu  sync.RWMutex
	redis   *redis.Client
	maxAge  time.Duration
}

// NewTickStore returns a tick store backed by an in-memory map and (optionally) Redis.
func NewTickStore(rdb *redis.Client, maxAge time.Duration) *TickStore {
	return &TickStore{
		ticks:  make(map[string]Tick),
		subs:   make(map[chan Tick]struct{}),
		redis:  rdb,
		maxAge: maxAge,
	}
}

// Set stores a new tick, replaces any existing entry for that symbol,
// and broadcasts it to all subscribers (non-blocking).
func (s *TickStore) Set(t Tick) {
	s.mu.Lock()
	s.ticks[t.Symbol] = t
	s.mu.Unlock()

	if s.redis != nil {
		go s.persistRedis(t)
	}

	s.broadcast(t)
}

// Get returns the latest tick for the given symbol, if present.
func (s *TickStore) Get(symbol string) (Tick, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	t, ok := s.ticks[symbol]
	return t, ok
}

// Snapshot returns a copy of all currently cached ticks.
func (s *TickStore) Snapshot() []Tick {
	s.mu.RLock()
	defer s.mu.RUnlock()
	out := make([]Tick, 0, len(s.ticks))
	for _, t := range s.ticks {
		out = append(out, t)
	}
	return out
}

// Symbols returns the list of symbols with at least one tick.
func (s *TickStore) Symbols() []string {
	s.mu.RLock()
	defer s.mu.RUnlock()
	out := make([]string, 0, len(s.ticks))
	for sym := range s.ticks {
		out = append(out, sym)
	}
	return out
}

// Subscribe returns a buffered channel that receives every new tick.
// Call the returned cancel func to stop receiving.
func (s *TickStore) Subscribe(bufferSize int) (<-chan Tick, func()) {
	if bufferSize <= 0 {
		bufferSize = 64
	}
	ch := make(chan Tick, bufferSize)
	s.subsMu.Lock()
	s.subs[ch] = struct{}{}
	s.subsMu.Unlock()

	cancel := func() {
		s.subsMu.Lock()
		delete(s.subs, ch)
		s.subsMu.Unlock()
		close(ch)
	}
	return ch, cancel
}

func (s *TickStore) broadcast(t Tick) {
	s.subsMu.RLock()
	defer s.subsMu.RUnlock()
	for ch := range s.subs {
		select {
		case ch <- t:
		default:
			// drop on slow subscriber
		}
	}
}

func (s *TickStore) persistRedis(t Tick) {
	ctx, cancel := contextWithTimeout()
	defer cancel()
	key := "price-feed:tick:" + t.Symbol
	if err := s.redis.Set(ctx, key, marshalTick(t), s.maxAge).Err(); err != nil {
		// best-effort; ignore errors
		_ = err
	}
}

// MarshalJSON helper that uses a fixed time format for stability.
func marshalTick(t Tick) string {
	b, _ := jsonMarshal(t)
	return string(b)
}