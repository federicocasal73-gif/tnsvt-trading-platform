package parser

import (
	"testing"

	"github.com/tnsvt/signal-engine/internal/models"
)

func newParser() *SignalParser { return NewSignalParser() }

func TestParse_EmptyText(t *testing.T) {
	p := newParser()
	_, err := p.Parse("")
	if err == nil {
		t.Fatal("expected error for empty text")
	}
}

func TestParse_BuyFormatSimple(t *testing.T) {
	p := newParser()
	s, err := p.Parse("BUY EURUSD @ 1.0850 SL 1.0830 TP 1.0890")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if s.Action != models.ActionBuy {
		t.Errorf("Action = %q, want buy", s.Action)
	}
	if s.Symbol != "EURUSD" {
		t.Errorf("Symbol = %q, want EURUSD", s.Symbol)
	}
	if s.EntryPrice == nil || *s.EntryPrice != 1.0850 {
		t.Errorf("EntryPrice = %v, want 1.0850", s.EntryPrice)
	}
	if s.StopLoss == nil || *s.StopLoss != 1.0830 {
		t.Errorf("StopLoss = %v, want 1.0830", s.StopLoss)
	}
	if len(s.TakeProfits) == 0 || s.TakeProfits[0] != 1.0890 {
		t.Errorf("TakeProfits = %v, want [1.0890]", s.TakeProfits)
	}
}

func TestParse_SellFormatMultiline(t *testing.T) {
	p := newParser()
	text := "SELL XAUUSD\nEntry: 2050.50\nSL: 2055\nTP: 2045, 2040"
	s, err := p.Parse(text)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if s.Action != models.ActionSell {
		t.Errorf("Action = %q, want sell", s.Action)
	}
	if s.Symbol != "XAUUSD" {
		t.Errorf("Symbol = %q, want XAUUSD", s.Symbol)
	}
	if s.EntryPrice == nil || *s.EntryPrice != 2050.50 {
		t.Errorf("EntryPrice = %v, want 2050.50", s.EntryPrice)
	}
	if s.StopLoss == nil || *s.StopLoss != 2055 {
		t.Errorf("StopLoss = %v, want 2055", s.StopLoss)
	}
	if len(s.TakeProfits) < 2 || s.TakeProfits[0] != 2045 || s.TakeProfits[1] != 2040 {
		t.Errorf("TakeProfits = %v, want [2045 2040]", s.TakeProfits)
	}
}

func TestParse_WithEmojis(t *testing.T) {
	p := newParser()
	text := "🔵 BUY GBPUSD\nEntry 1.2650\nStop Loss 1.2620\nTake Profit 1.2700"
	s, err := p.Parse(text)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if s.Action != models.ActionBuy {
		t.Errorf("Action = %q, want buy", s.Action)
	}
	if s.Symbol != "GBPUSD" {
		t.Errorf("Symbol = %q, want GBPUSD", s.Symbol)
	}
	if s.StopLoss == nil || *s.StopLoss != 1.2620 {
		t.Errorf("StopLoss = %v, want 1.2620", s.StopLoss)
	}
}

func TestParse_CloseAll(t *testing.T) {
	p := newParser()
	s, err := p.Parse("CLOSE ALL EURUSD")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if s.Action != models.ActionClose {
		t.Errorf("Action = %q, want close", s.Action)
	}
	if s.Symbol != "EURUSD" {
		t.Errorf("Symbol = %q, want EURUSD", s.Symbol)
	}
	if s.EntryPrice != nil {
		t.Errorf("EntryPrice = %v, want nil for CLOSE", s.EntryPrice)
	}
}

func TestParse_MultipleTPs(t *testing.T) {
	p := newParser()
	text := "📈 BUY EURUSD\n🎯 Entry: 1.0850\n🛑 SL: 1.0820\n✅ TP1: 1.0870\n✅ TP2: 1.0890"
	s, err := p.Parse(text)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(s.TakeProfits) < 2 {
		t.Fatalf("expected at least 2 TPs, got %v", s.TakeProfits)
	}
}

func TestParse_WithLotSize(t *testing.T) {
	p := newParser()
	s, err := p.Parse("BUY EURUSD @ 1.0850 SL 1.0830 TP 1.0890 Lot 0.10")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if s.LotSize == nil || *s.LotSize != 0.10 {
		t.Errorf("LotSize = %v, want 0.10", s.LotSize)
	}
}

func TestParse_LongShortAliases(t *testing.T) {
	p := newParser()
	s1, _ := p.Parse("LONG EURUSD @ 1.0850 SL 1.0830 TP 1.0890")
	if s1.Action != models.ActionBuy {
		t.Errorf("LONG Action = %q, want buy", s1.Action)
	}
	s2, _ := p.Parse("SHORT EURUSD @ 1.0850 SL 1.0870 TP 1.0830")
	if s2.Action != models.ActionSell {
		t.Errorf("SHORT Action = %q, want sell", s2.Action)
	}
}

func TestParse_CryptoSymbols(t *testing.T) {
	p := newParser()
	tests := []struct {
		text string
		want string
	}{
		{"BUY BTC @ 60000 SL 59000 TP 62000", "BTCUSD"},
		{"SELL ETHUSD @ 3500 SL 3600 TP 3400", "ETHUSD"},
		{"BUY XAUUSD @ 2000 SL 1990 TP 2020", "XAUUSD"},
		{"BUY XAGUSD @ 25 SL 24 TP 26", "XAGUSD"},
		{"BUY US30 @ 38000 SL 37900 TP 38200", "US30"},
		{"BUY NAS100 @ 17000 SL 16900 TP 17200", "NAS100"},
	}
	for _, tt := range tests {
		t.Run(tt.want, func(t *testing.T) {
			s, err := p.Parse(tt.text)
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if s.Symbol != tt.want {
				t.Errorf("Symbol = %q, want %q", s.Symbol, tt.want)
			}
		})
	}
}

func TestParse_MissingSymbol(t *testing.T) {
	p := newParser()
	_, err := p.Parse("BUY @ 1.0850 SL 1.0830 TP 1.0890")
	if err == nil {
		t.Fatal("expected error for missing symbol")
	}
}

func TestParse_NoExplicitEntry_StillExtractsFirstNumber(t *testing.T) {
	// The parser falls back to the first positive number it finds.
	// This is by design — the regex-based fallback in extractEntry picks up any number.
	// To avoid mis-parsing signals without explicit entry, callers should validate before sending.
	p := newParser()
	s, err := p.Parse("BUY EURUSD SL 1.0830 TP 1.0890")
	if err != nil {
		t.Fatalf("parser unexpectedly failed: %v", err)
	}
	if s.EntryPrice == nil {
		t.Fatal("expected parser to fall back to first number")
	}
}

func TestParse_NoAction(t *testing.T) {
	p := newParser()
	_, err := p.Parse("EURUSD 1.0850 SL 1.0830 TP 1.0890")
	if err == nil {
		t.Fatal("expected error for missing action")
	}
}

func TestParse_InvalidSymbol(t *testing.T) {
	p := newParser()
	_, err := p.Parse("BUY XXX @ 1.0850 SL 1.0830 TP 1.0890")
	if err == nil {
		t.Fatal("expected error for invalid symbol")
	}
}

func TestParse_ForexPairWithoutSlash(t *testing.T) {
	p := newParser()
	s, err := p.Parse("BUY EUR/USD @ 1.0850 SL 1.0830 TP 1.0890")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if s.Symbol != "EURUSD" {
		t.Errorf("Symbol = %q, want EURUSD", s.Symbol)
	}
}

func TestParse_RawSignalSetsSource(t *testing.T) {
	p := newParser()
	raw := &models.RawSignal{
		Text:        "BUY EURUSD @ 1.0850 SL 1.0830 TP 1.0890",
		ChannelID:   12345,
		MessageID:   67890,
		ChannelName: "VIP_Signals",
	}
	s, err := p.ParseRawSignal(raw)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if s.Source != models.SourceTelegram {
		t.Errorf("Source = %q, want telegram", s.Source)
	}
	if s.SourceID != "12345_67890" {
		t.Errorf("SourceID = %q, want 12345_67890", s.SourceID)
	}
}

func TestParse_StopLossLong(t *testing.T) {
	p := newParser()
	s, err := p.Parse("BUY EURUSD @ 1.0850 Stop Loss 1.0820 TP 1.0890")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if s.StopLoss == nil || *s.StopLoss != 1.0820 {
		t.Errorf("StopLoss = %v, want 1.0820", s.StopLoss)
	}
}