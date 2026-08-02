// Package indicators implementa indicadores técnicos clásicos (RSI, MACD, Bollinger)
// usados por el signal-generator para decidir BUY/SELL.
//
// Las funciones son puras: reciben slices de precios y devuelven métricas.
// No tienen estado.
package indicators

import "math"

// Candle representa una vela OHLC. Sólo Close es obligatorio para
// los indicadores actuales; se mantienen los demás campos para futuras
// extensiones.
type Candle struct {
	Time   int64
	Open   float64
	High   float64
	Low    float64
	Close  float64
	Volume int64
}

// Closes devuelve los precios de cierre de una serie de velas.
func Closes(cs []Candle) []float64 {
	out := make([]float64, len(cs))
	for i, c := range cs {
		out[i] = c.Close
	}
	return out
}

// RSI calcula el Relative Strength Index sobre un periodo (típico 14).
// Retorna 0 si no hay suficientes datos.
//   rsi > 70 = sobrecomprado → potencial SELL
//   rsi < 30 = sobrevendido → potencial BUY
func RSI(closes []float64, period int) float64 {
	n := len(closes)
	if n < period+1 || period <= 0 {
		return 0
	}
	var gain, loss float64
	// Promedios iniciales (simple)
	for i := 1; i <= period; i++ {
		ch := closes[i] - closes[i-1]
		if ch > 0 {
			gain += ch
		} else {
			loss -= ch
		}
	}
	avgGain := gain / float64(period)
	avgLoss := loss / float64(period)
	// Wilder smoothing para el resto
	for i := period + 1; i < n; i++ {
		ch := closes[i] - closes[i-1]
		var g, l float64
		if ch > 0 {
			g = ch
		} else {
			l = -ch
		}
		avgGain = (avgGain*float64(period-1) + g) / float64(period)
		avgLoss = (avgLoss*float64(period-1) + l) / float64(period)
	}
	if avgLoss == 0 {
		return 100
	}
	rs := avgGain / avgLoss
	return 100 - (100 / (1 + rs))
}

// MACD calcula Moving Average Convergence Divergence.
// Retorna (macdLine, signalLine, histogram). Si no hay datos, los 3 = 0.
//   histogram > 0 y subiendo → momentum alcista → BUY
//   histogram < 0 y bajando → momentum bajista → SELL
func MACD(closes []float64, fastPeriod, slowPeriod, signalPeriod int) (float64, float64, float64) {
	n := len(closes)
	if n < slowPeriod+signalPeriod {
		return 0, 0, 0
	}
	emaFast := emaSeries(closes, fastPeriod)
	emaSlow := emaSeries(closes, slowPeriod)
	if len(emaFast) == 0 || len(emaSlow) == 0 {
		return 0, 0, 0
	}
	// MACD line = EMA_fast - EMA_slow (alineadas por el final de cada serie)
	macdLine := make([]float64, len(emaSlow))
	for i := range emaSlow {
		fastIdx := len(emaFast) - len(emaSlow) + i
		if fastIdx >= 0 && fastIdx < len(emaFast) {
			macdLine[i] = emaFast[fastIdx] - emaSlow[i]
		}
	}
	signal := emaSeries(macdLine, signalPeriod)
	if len(signal) == 0 {
		return 0, 0, 0
	}
	lastMACD := macdLine[len(macdLine)-1]
	lastSignal := signal[len(signal)-1]
	return lastMACD, lastSignal, lastMACD - lastSignal
}

// BollingerBands calcula las Bandas de Bollinger.
// Retorna (upper, middle, lower). La señal típica:
//   precio toca lower → potencial BUY (oversold)
//   precio toca upper → potencial SELL (overbought)
func BollingerBands(closes []float64, period int, stdDevMultiplier float64) (float64, float64, float64) {
	n := len(closes)
	if n < period || period <= 0 {
		return 0, 0, 0
	}
	// SMA de los últimos `period`
	var sum float64
	for i := n - period; i < n; i++ {
		sum += closes[i]
	}
	middle := sum / float64(period)
	// Desviación estándar muestral
	var sqDiff float64
	for i := n - period; i < n; i++ {
		d := closes[i] - middle
		sqDiff += d * d
	}
	stdDev := math.Sqrt(sqDiff / float64(period))
	upper := middle + stdDevMultiplier*stdDev
	lower := middle - stdDevMultiplier*stdDev
	return upper, middle, lower
}

// emaSeries calcula la serie EMA (Exponential Moving Average) sobre
// un slice de precios. Devuelve los primeros `period` elementos como 0
// (no hay suficiente data para EMA).
func emaSeries(closes []float64, period int) []float64 {
	n := len(closes)
	if n < period || period <= 0 {
		return nil
	}
	// SMA inicial (semilla de EMA)
	var seed float64
	for i := 0; i < period; i++ {
		seed += closes[i]
	}
	seed /= float64(period)
	// Multiplicador: 2 / (period+1)
	mult := 2.0 / float64(period+1)

	out := make([]float64, n)
	out[period-1] = seed
	for i := period; i < n; i++ {
		out[i] = (closes[i]-out[i-1])*mult + out[i-1]
	}
	return out
}
