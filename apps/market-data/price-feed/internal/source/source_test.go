package source

import (
	"context"
	"testing"
	"time"

	"github.com/tnsvt/price-feed/internal/models"
)

func TestParseSymbols(t *testing.T) {
	tests := []struct {
		name string
		raw  string
		want []string
	}{
		{"empty", "", []string{}},
		{"single", "EURUSD", []string{"EURUSD"}},
		{"comma_separated", "EURUSD,GBPUSD,XAUUSD", []string{"EURUSD", "GBPUSD", "XAUUSD"}},
		{"with_spaces", "EURUSD, GBPUSD, XAUUSD", []string{"EURUSD", "GBPUSD", "XAUUSD"}},
		{"empty_entries", "EURUSD,,GBPUSD,", []string{"EURUSD", "GBPUSD"}},
		{"trailing_comma", "EURUSD,", []string{"EURUSD"}},
		{"only_commas", ",,,", []string{}},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := ParseSymbols(tt.raw)
			if len(got) != len(tt.want) {
				t.Fatalf("len = %d, want %d (got %v)", len(got), len(tt.want), got)
			}
			for i := range got {
				if got[i] != tt.want[i] {
					t.Errorf("[%d] = %q, want %q", i, got[i], tt.want[i])
				}
			}
		})
	}
}

func TestBuiltinMockEmitsTicks(t *testing.T) {
	store := newTestStore()

	mock := NewBuiltinMockSource("test-mock", []string{"EURUSD", "XAUUSD"}, nopLogger{})
	mgr := NewManager(nopLogger{}, store, nil)
	mgr.Add(mock)

	done := make(chan struct{})
	go func() {
		time.Sleep(1200 * time.Millisecond) // 2+ ticks at 500ms cadence
		mgr.Stop()
		close(done)
	}()
	mgr.Start(context.Background())

	select {
	case <-done:
	case <-time.After(3 * time.Second):
		t.Fatal("manager didn't stop within 3s")
	}

	syms := store.Symbols()
	if len(syms) == 0 {
		t.Fatal("expected builtin mock to have emitted ticks for EURUSD/XAUUSD")
	}
	for _, want := range []string{"EURUSD", "XAUUSD"} {
		found := false
		for _, s := range syms {
			if s == want {
				found = true
				break
			}
		}
		if !found {
			t.Errorf("symbol %s not in store; got %v", want, syms)
		}
	}
}

func TestBuiltinMockPricesAreCoherent(t *testing.T) {
	store := newTestStore()
	mock := NewBuiltinMockSource("coherent", []string{"EURUSD"}, nopLogger{})
	mgr := NewManager(nopLogger{}, store, nil)
	mgr.Add(mock)

	mgr.Start(context.Background())
	defer mgr.Stop()

	// Wait for at least one tick to arrive (500ms cadence, allow 2s for CI jitter).
	deadline := time.Now().Add(2 * time.Second)
	var tick models.Tick
	var ok bool
	for time.Now().Before(deadline) {
		tick, ok = store.Get("EURUSD")
		if ok {
			break
		}
		time.Sleep(50 * time.Millisecond)
	}
	if !ok {
		t.Fatal("EURUSD tick missing after waiting 2s")
	}

	// Sanity: bid < ask (always), price > 0
	if tick.Bid <= 0 {
		t.Errorf("Bid = %v, want > 0", tick.Bid)
	}
	if tick.Ask <= tick.Bid {
		t.Errorf("Ask (%v) should be > Bid (%v)", tick.Ask, tick.Bid)
	}
	if tick.Last <= 0 {
		t.Errorf("Last = %v, want > 0", tick.Last)
	}
	if tick.Source != "coherent" {
		t.Errorf("Source = %q, want coherent", tick.Source)
	}
}

func TestNewMockSourceStoresURL(t *testing.T) {
	s := NewMockSource("ext", "wss://example.com/feed", []string{"EURUSD"}, nopLogger{})
	if s.URL != "wss://example.com/feed" {
		t.Errorf("URL = %q, want wss://example.com/feed", s.URL)
	}
	if s.Name != "ext" {
		t.Errorf("Name = %q, want ext", s.Name)
	}
	if len(s.Symbols) != 1 || s.Symbols[0] != "EURUSD" {
		t.Errorf("Symbols = %v, want [EURUSD]", s.Symbols)
	}
}

func TestErrString_Nil(t *testing.T) {
	if got := errString(nil); got != "" {
		t.Errorf("errString(nil) = %q, want empty", got)
	}
}

func TestErrString_RealError(t *testing.T) {
	err := &simpleErr{msg: "boom"}
	if got := errString(err); got != "boom" {
		t.Errorf("errString = %q, want boom", got)
	}
}

func TestFormatTick(t *testing.T) {
	got := FormatTick(models.Tick{Symbol: "EURUSD", Bid: 1.0849, Ask: 1.0851, Last: 1.0850, Source: "mock"})
	if got == "" {
		t.Error("FormatTick returned empty")
	}
	if !contains(got, "EURUSD") {
		t.Errorf("FormatTick missing symbol: %q", got)
	}
}

type simpleErr struct{ msg string }

func (e *simpleErr) Error() string { return e.msg }

func TestContains(t *testing.T) {
	if !contains("hello world", "world") {
		t.Error("contains(hello world, world) = false, want true")
	}
	if contains("hello", "world") {
		t.Error("contains(hello, world) = true, want false")
	}
	if !contains("", "") {
		t.Error("contains(empty, empty) = false, want true")
	}
}

func TestManager_AddAndSources(t *testing.T) {
	mgr := NewManager(nopLogger{}, newTestStore(), nil)
	mgr.Add(NewBuiltinMockSource("a", []string{"EURUSD"}, nopLogger{}))
	mgr.Add(NewBuiltinMockSource("b", []string{"GBPUSD"}, nopLogger{}))

	srcs := mgr.Sources()
	if len(srcs) != 2 {
		t.Errorf("Sources len = %d, want 2", len(srcs))
	}
	if srcs[0].Name != "a" || srcs[1].Name != "b" {
		t.Errorf("order/names wrong: %+v", srcs)
	}
}

func TestManager_DoubleStartIsNoop(t *testing.T) {
	mgr := NewManager(nopLogger{}, newTestStore(), nil)
	mgr.Add(NewBuiltinMockSource("x", []string{"EURUSD"}, nopLogger{}))

	mgr.Start(context.Background())
	mgr.Start(context.Background()) // should not panic

	time.Sleep(200 * time.Millisecond)
	mgr.Stop()
}