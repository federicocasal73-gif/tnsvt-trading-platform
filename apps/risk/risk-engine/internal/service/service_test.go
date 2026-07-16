package service

import (
	"testing"

	"github.com/tnsvt/risk-engine/internal/models"
)

// newTestService creates a RiskService with the given config and zero deps.
// All tested methods are pure functions that don't touch repo/redis/nats/log.
func newTestService(cfg Config) *RiskService {
	return &RiskService{config: cfg}
}

// ─── Position Sizing ────────────────────────────────────────────────────

func TestCalculatePositionSize_NormalCase(t *testing.T) {
	s := newTestService(Config{})

	// Risk 1% of $10,000 balance, entry 1.1000, SL 1.0950 (50 pips away)
	// pips = 50 * 10000 / 10000 = 50  → risk = $100
	// lot = 100 / (50 * 10) = 0.20
	got := s.calculatePositionSize(1.0, 1.1000, 1.0950, 10000.0)
	if got != 0.20 {
		t.Errorf("got %v, want 0.20", got)
	}
}

func TestCalculatePositionSize_HigherRiskPercent(t *testing.T) {
	s := newTestService(Config{})

	// 2% risk on 5000 → $100 risk, 50 pips → 0.20 lots
	got := s.calculatePositionSize(2.0, 1.1000, 1.0950, 5000.0)
	if got != 0.20 {
		t.Errorf("got %v, want 0.20", got)
	}
}

func TestCalculatePositionSize_TightStopGivesBiggerLot(t *testing.T) {
	s := newTestService(Config{})

	// 1% on 10000 = $100 risk, 10 pips → 1.00 lot
	got := s.calculatePositionSize(1.0, 1.1000, 1.0990, 10000.0)
	if got != 1.00 {
		t.Errorf("got %v, want 1.00", got)
	}
}

func TestCalculatePositionSize_ZeroSLReturnsMinLot(t *testing.T) {
	s := newTestService(Config{})
	got := s.calculatePositionSize(1.0, 1.1000, 1.1000, 10000.0)
	if got != 0.01 {
		t.Errorf("got %v, want 0.01 (min)", got)
	}
}

func TestCalculatePositionSize_ClampedToMax(t *testing.T) {
	s := newTestService(Config{})

	// Massive position: 100% risk, 1 pip SL, $1M balance
	// pips = 1, risk = $1M, lot = 1M / 10 = 100000 → clamped to 100
	got := s.calculatePositionSize(100.0, 1.1000, 1.0999, 1000000.0)
	if got != 100 {
		t.Errorf("got %v, want 100 (max)", got)
	}
}

func TestCalculatePositionSize_ClampedToMin(t *testing.T) {
	s := newTestService(Config{})

	// Tiny position: 0.01% risk on $100 balance, 50 pips SL
	// pips = 50, risk = $0.01, lot = 0.01/500 = 0.00002 → clamped to 0.01
	got := s.calculatePositionSize(0.01, 1.1000, 1.0950, 100.0)
	if got != 0.01 {
		t.Errorf("got %v, want 0.01 (min)", got)
	}
}

func TestCalculatePositionSize_RoundedTo2Decimals(t *testing.T) {
	s := newTestService(Config{})

	// Risk 1% on 7777 balance, 50 pips → 77.77 / 500 = 0.15554 → rounded to 0.16
	got := s.calculatePositionSize(1.0, 1.1000, 1.0950, 7777.0)
	if got != 0.16 {
		t.Errorf("got %v, want 0.16 (rounded)", got)
	}
}

func TestCalculatePositionSize_ZeroBalance(t *testing.T) {
	s := newTestService(Config{})
	got := s.calculatePositionSize(1.0, 1.1000, 1.0950, 0.0)
	if got != 0.01 {
		t.Errorf("got %v, want 0.01 (min, zero balance)", got)
	}
}

// ─── Trailing Stop Activation ───────────────────────────────────────────

func TestShouldActivateTrailing_DisabledByConfig(t *testing.T) {
	s := newTestService(Config{TrailingStop: false, TrailingStart: 10})
	p := &models.Position{CurrentPrice: 1.1050, EntryPrice: 1.1000, StopLoss: 1.0950, Side: "buy"}
	if s.shouldActivateTrailing(p) {
		t.Error("expected trailing NOT to activate when TrailingStop=false")
	}
}

func TestShouldActivateTrailing_NotEnoughProfit(t *testing.T) {
	s := newTestService(Config{TrailingStop: true, TrailingStart: 50})
	// Currently only 5 pips in profit (need 50)
	p := &models.Position{CurrentPrice: 1.1005, EntryPrice: 1.1000, StopLoss: 1.0950, Side: "buy"}
	if s.shouldActivateTrailing(p) {
		t.Error("expected trailing NOT to activate with < 50 pips profit")
	}
}

func TestShouldActivateTrailing_BuySideEnoughProfit(t *testing.T) {
	s := newTestService(Config{TrailingStop: true, TrailingStart: 50})
	// 60 pips in profit for buy → should activate
	p := &models.Position{CurrentPrice: 1.1060, EntryPrice: 1.1000, StopLoss: 1.0950, Side: "buy"}
	if !s.shouldActivateTrailing(p) {
		t.Error("expected trailing to activate for buy with 60 pips profit")
	}
}

func TestShouldActivateTrailing_SellSideEnoughProfit(t *testing.T) {
	s := newTestService(Config{TrailingStop: true, TrailingStart: 50})
	// For sell: profit = entry - current, need 50 pips
	p := &models.Position{CurrentPrice: 1.0940, EntryPrice: 1.1000, StopLoss: 1.1050, Side: "sell"}
	if !s.shouldActivateTrailing(p) {
		t.Error("expected trailing to activate for sell with 60 pips profit")
	}
}

// ─── Trailing Stop Calculation ──────────────────────────────────────────

func TestCalculateTrailingStop_DisabledReturnsZero(t *testing.T) {
	s := newTestService(Config{TrailingStop: false})
	p := &models.Position{CurrentPrice: 1.1100, EntryPrice: 1.1000, StopLoss: 1.0950, Side: "buy"}
	got := s.calculateTrailingStop(p)
	if got != 0 {
		t.Errorf("got %v, want 0 when trailing disabled", got)
	}
}

func TestCalculateTrailingStop_BuyMovesUp(t *testing.T) {
	// TrailingStep=10 pips = 0.0010 price for forex
	s := newTestService(Config{TrailingStop: true, TrailingStart: 50, TrailingStep: 10})
	p := &models.Position{
		CurrentPrice: 1.1100,  // 100 pips above entry
		EntryPrice:   1.1000,
		StopLoss:     1.0950,
		Side:         "buy",
	}
	// new SL = 1.1100 - 0.0010 = 1.1090
	// 1.1090 > 1.0950 → return 1.1090
	got := s.calculateTrailingStop(p)
	if got != 1.1090 {
		t.Errorf("got %v, want 1.1090", got)
	}
}

func TestCalculateTrailingStop_BuyKeepsCurrentSL(t *testing.T) {
	// Set up so trailing activates (>= 50 pips profit) but new SL < existing SL
	s := newTestService(Config{TrailingStop: true, TrailingStart: 50, TrailingStep: 10})
	p := &models.Position{
		CurrentPrice: 1.1060, // 60 pips in profit (above TrailingStart)
		EntryPrice:   1.1000,
		StopLoss:     1.1045, // very tight existing SL
		Side:         "buy",
		TrailingStopLoss: 1.1045,
	}
	// new SL = 1.1060 - 0.0010 = 1.1050
	// 1.1050 > 1.1045? Yes → would update
	// Let's make the existing SL even higher
	p.StopLoss = 1.1060
	// new SL = 1.1060 - 0.0010 = 1.1050
	// 1.1050 > 1.1060? No → don't move
	got := s.calculateTrailingStop(p)
	if got != 1.1045 { // TrailingStopLoss is the fallback (kept value)
		t.Errorf("got %v, want 1.1045 (existing TrailingStopLoss)", got)
	}
}

func TestCalculateTrailingStop_SellMovesDown(t *testing.T) {
	s := newTestService(Config{TrailingStop: true, TrailingStart: 50, TrailingStep: 10})
	p := &models.Position{
		CurrentPrice: 1.0900, // 100 pips below entry
		EntryPrice:   1.1000,
		StopLoss:     1.1050,
		Side:         "sell",
	}
	// new SL = 1.0900 + 0.0010 = 1.0910
	// 1.0910 < 1.1050 → return 1.0910
	got := s.calculateTrailingStop(p)
	if got != 1.0910 {
		t.Errorf("got %v, want 1.0910", got)
	}
}

func TestCalculateTrailingStop_SellFirstActivation(t *testing.T) {
	s := newTestService(Config{TrailingStop: true, TrailingStart: 50, TrailingStep: 10})
	p := &models.Position{
		CurrentPrice: 1.0900,
		EntryPrice:   1.1000,
		StopLoss:     0, // no SL yet
		Side:         "sell",
	}
	got := s.calculateTrailingStop(p)
	if got != 1.0910 {
		t.Errorf("got %v, want 1.0910", got)
	}
}