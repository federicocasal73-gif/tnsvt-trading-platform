package models

import (
	"sync"
	"testing"
	"time"
)

func TestTick_Mid(t *testing.T) {
	tests := []struct {
		name string
		tick Tick
		want float64
	}{
		{"both_set", Tick{Bid: 1.0000, Ask: 1.0010, Last: 1.0005}, 1.0005},
		{"only_bid", Tick{Bid: 1.0000, Last: 0}, 1.0000},
		{"only_ask", Tick{Ask: 1.0010, Last: 0}, 1.0010},
		{"only_last", Tick{Last: 1.2345}, 1.2345},
		{"bid_zero_last_set", Tick{Bid: 0, Ask: 0, Last: 1.5}, 1.5},
		{"all_zero", Tick{}, 0},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := tt.tick.Mid(); got != tt.want {
				t.Errorf("Mid() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestTick_Spread(t *testing.T) {
	tests := []struct {
		name    string
		tick    Tick
		wantAbs float64
		wantPct float64
	}{
		{"normal_forex", Tick{Bid: 1.0000, Ask: 1.0002}, 0.0002, 0.02},
		{"crypto", Tick{Bid: 60000, Ask: 60100}, 100, 0.1666},
		{"no_bid", Tick{Ask: 1.0010}, 0, 0},
		{"no_ask", Tick{Bid: 1.0000}, 0, 0},
		{"all_zero", Tick{}, 0, 0},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			abs, pct := tt.tick.Spread()
			if abs < tt.wantAbs-1e-9 || abs > tt.wantAbs+1e-9 {
				t.Errorf("abs = %v, want %v (tolerance 1e-9)", abs, tt.wantAbs)
			}
			if pct < tt.wantPct-0.01 || pct > tt.wantPct+0.01 {
				t.Errorf("pct = %v, want ~%v", pct, tt.wantPct)
			}
		})
	}
}

func TestTickStore_SetAndGet(t *testing.T) {
	store := NewTickStore(nil, time.Minute)
	tick := Tick{Symbol: "EURUSD", Bid: 1.0849, Ask: 1.0851, Last: 1.0850, Source: "test", Timestamp: time.Now()}
	store.Set(tick)

	got, ok := store.Get("EURUSD")
	if !ok {
		t.Fatal("expected EURUSD to be present")
	}
	if got.Last != 1.0850 {
		t.Errorf("Last = %v, want 1.0850", got.Last)
	}
}

func TestTickStore_GetMissing(t *testing.T) {
	store := NewTickStore(nil, time.Minute)
	_, ok := store.Get("UNKNOWN")
	if ok {
		t.Error("expected Get on unknown symbol to return ok=false")
	}
}

func TestTickStore_Snapshot(t *testing.T) {
	store := NewTickStore(nil, time.Minute)
	store.Set(Tick{Symbol: "EURUSD", Last: 1.0850})
	store.Set(Tick{Symbol: "GBPUSD", Last: 1.2650})
	store.Set(Tick{Symbol: "XAUUSD", Last: 2025.50})

	snap := store.Snapshot()
	if len(snap) != 3 {
		t.Errorf("Snapshot length = %d, want 3", len(snap))
	}
}

func TestTickStore_Symbols(t *testing.T) {
	store := NewTickStore(nil, time.Minute)
	store.Set(Tick{Symbol: "EURUSD"})
	store.Set(Tick{Symbol: "GBPUSD"})

	syms := store.Symbols()
	if len(syms) != 2 {
		t.Errorf("Symbols length = %d, want 2", len(syms))
	}
	seen := map[string]bool{}
	for _, s := range syms {
		seen[s] = true
	}
	if !seen["EURUSD"] || !seen["GBPUSD"] {
		t.Errorf("Symbols missing expected entries: %v", syms)
	}
}

func TestTickStore_SetOverwrites(t *testing.T) {
	store := NewTickStore(nil, time.Minute)
	store.Set(Tick{Symbol: "EURUSD", Last: 1.0850, Source: "src-a"})
	store.Set(Tick{Symbol: "EURUSD", Last: 1.0860, Source: "src-b"})

	got, _ := store.Get("EURUSD")
	if got.Last != 1.0860 {
		t.Errorf("Last = %v, want 1.0860 (newer)", got.Last)
	}
	if got.Source != "src-b" {
		t.Errorf("Source = %q, want src-b", got.Source)
	}
}

func TestTickStore_SubscribeReceive(t *testing.T) {
	store := NewTickStore(nil, time.Minute)
	ch, cancel := store.Subscribe(8)
	defer cancel()

	var wg sync.WaitGroup
	wg.Add(1)
	go func() {
		defer wg.Done()
		store.Set(Tick{Symbol: "EURUSD", Last: 1.0850})
		store.Set(Tick{Symbol: "GBPUSD", Last: 1.2650})
	}()

	timeout := time.After(2 * time.Second)
	got := map[string]bool{}
	for len(got) < 2 {
		select {
		case t := <-ch:
			got[t.Symbol] = true
		case <-timeout:
			t.Fatal("timed out waiting for ticks")
		}
	}
	if !got["EURUSD"] || !got["GBPUSD"] {
		t.Errorf("missing expected ticks: %v", got)
	}
	wg.Wait()
}

func TestTickStore_SubscribeCancelClosesChannel(t *testing.T) {
	store := NewTickStore(nil, time.Minute)
	ch, cancel := store.Subscribe(8)
	cancel()

	// After cancel, channel should be closed and drainable.
	_, ok := <-ch
	if ok {
		t.Error("expected channel to be closed after cancel")
	}
}

func TestTickStore_SubscribeBufferDropsOnSlowConsumer(t *testing.T) {
	store := NewTickStore(nil, time.Minute)
	// Buffer of 1, but never read; the broadcast should drop, not block.
	ch, cancel := store.Subscribe(1)
	defer cancel()

	done := make(chan struct{})
	go func() {
		// Push 100 ticks quickly; broadcaster must not block.
		for i := 0; i < 100; i++ {
			store.Set(Tick{Symbol: "X", Last: float64(i)})
		}
		close(done)
	}()

	select {
	case <-done:
		// ok
	case <-time.After(2 * time.Second):
		t.Fatal("broadcaster blocked when consumer buffer full")
	}
	// Drain at least one
	<-ch
}