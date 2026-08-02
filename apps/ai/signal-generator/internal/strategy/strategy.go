// Package strategy evalúa indicadores y decide BUY/SELL/HOLD.
//
// Sprint 3.2: implementa la estrategia "RSI + MACD + Bollinger multi-indicator".
// Combina tres señales para reducir falsos positivos:
//
//   BUY cuando:
//     - RSI < oversoldThreshold (típico 30)  → sobrevendido
//     - MACD histogram cruza de negativo a positivo (momentum alcista)
//     - Precio <= Bollinger lower (oversold extremo)
//
//   SELL cuando (simétrico):
//     - RSI > overboughtThreshold (típico 70)
//     - MACD histogram cruza de positivo a negativo
//     - Precio >= Bollinger upper
//
// Confidence se calcula como promedio ponderado de las tres señales.
package strategy

import (
	"fmt"

	"github.com/tnsvt/signal-generator/internal/indicators"
)

// Config del scanner. Defaults razonables.
type Config struct {
	RSIPeriod         int     // default 14
	MACDFast          int     // default 12
	MACDSlow          int     // default 26
	MACDSignal        int     // default 9
	BollingerPeriod   int     // default 20
	BollingerStdDev   float64 // default 2.0
	RSIOversold       float64 // default 30
	RSIOverbought     float64 // default 70
	MinConfidence     float64 // default 0.6 (no publica < 60%)
}

// DefaultConfig retorna una config con defaults sensatos.
func DefaultConfig() Config {
	return Config{
		RSIPeriod:       14,
		MACDFast:        12,
		MACDSlow:        26,
		MACDSignal:      9,
		BollingerPeriod: 20,
		BollingerStdDev: 2.0,
		RSIOversold:     30,
		RSIOverbought:   70,
		MinConfidence:   0.6,
	}
}

// Decision del scanner.
type Decision struct {
	Action     string  // "BUY" / "SELL" / "HOLD"
	Confidence float64 // 0..1
	Reason     string
}

// Scan evalúa la estrategia sobre una serie de velas y devuelve una Decision.
// Devuelve HOLD + reason explicativo si no hay acuerdo entre indicadores.
func Scan(closes []float64, cfg Config) (Decision, error) {
	if len(closes) < cfg.MACDSlow+cfg.MACDSignal+5 {
		return Decision{Action: "HOLD", Reason: "insufficient data"}, fmt.Errorf("not enough candles (need %d, have %d)", cfg.MACDSlow+cfg.MACDSignal+5, len(closes))
	}

	rsi := indicators.RSI(closes, cfg.RSIPeriod)
	macd, signalLine, histogram := indicators.MACD(closes, cfg.MACDFast, cfg.MACDSlow, cfg.MACDSignal)
	upper, _, lower := indicators.BollingerBands(closes, cfg.BollingerPeriod, cfg.BollingerStdDev)
	price := closes[len(closes)-1]

	// Scoring: cada indicador aporta 1 punto si coincide, 0 si no.
	buyScore := 0.0
	sellScore := 0.0

	// RSI
	rsiWeight := 0.4
	if rsi < cfg.RSIOversold {
		buyScore += rsiWeight
	} else if rsi > cfg.RSIOverbought {
		sellScore += rsiWeight
	}

	// MACD (histogram + cruce)
	macdWeight := 0.35
	if histogram > 0 && signalLine > 0 && macd > signalLine {
		buyScore += macdWeight
	} else if histogram < 0 && signalLine < 0 && macd < signalLine {
		sellScore += macdWeight
	}

	// Bollinger (extremos)
	bbWeight := 0.25
	if price <= lower {
		buyScore += bbWeight
	} else if price >= upper {
		sellScore += bbWeight
	}

	if buyScore > sellScore && buyScore >= cfg.MinConfidence {
		return Decision{
			Action:     "BUY",
			Confidence: buyScore,
			Reason: fmt.Sprintf("rsi=%.1f macd_hist=%.4f price=%.5f lower=%.5f upper=%.5f", rsi, histogram, price, lower, upper),
		}, nil
	}
	if sellScore > buyScore && sellScore >= cfg.MinConfidence {
		return Decision{
			Action:     "SELL",
			Confidence: sellScore,
			Reason: fmt.Sprintf("rsi=%.1f macd_hist=%.4f price=%.5f lower=%.5f upper=%.5f", rsi, histogram, price, lower, upper),
		}, nil
	}
	return Decision{
		Action:     "HOLD",
		Confidence: 0,
		Reason: fmt.Sprintf("rsi=%.1f macd_hist=%.4f price=%.5f lower=%.5f upper=%.5f (no consensus)", rsi, histogram, price, lower, upper),
	}, nil
}

// SuggestSLTP sugiere SL/TP heurísticos desde la última vela + Bollinger.
//   SL = entry ± 2× ATR o el Bollinger opuesto
//   TP = entry + 1× Bollinger width (BUY) / entry - 1× Bollinger width (SELL)
func SuggestSLTP(price float64, lower, upper float64, action string) (sl, tp1, tp2 float64) {
	width := (upper - lower) / 2 // Bollinger half-width
	if action == "BUY" {
		sl = price - width
		tp1 = price + width
		tp2 = price + 2*width
	} else {
		sl = price + width
		tp1 = price - width
		tp2 = price - 2*width
	}
	return
}
