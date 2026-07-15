// Package parser parsea mensajes de texto en lenguaje natural a señales estructuradas.
//
// Soporta formatos comunes:
//
//   "BUY EURUSD @ 1.0850 SL 1.0830 TP 1.0890"
//   "SELL XAUUSD\nEntry: 2050.50\nSL: 2055\nTP: 2045, 2040"
//   "🔵 BUY GBPUSD\nEntry 1.2650\nStop Loss 1.2620\nTake Profit 1.2700"
//   "CLOSE ALL EURUSD"
//   "📈 BUY EURUSD\n🎯 Entry: 1.0850\n🛑 SL: 1.0820\n✅ TP1: 1.0870\n✅ TP2: 1.0890"
package parser

import (
	"fmt"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/tnsvt/signal-engine/internal/models"
)

// SignalParser parsea texto a señales
type SignalParser struct {
	// Compilados una sola vez para performance
	actionRe     *regexp.Regexp
	symbolRe     *regexp.Regexp
	priceRe      *regexp.Regexp
	slRe         *regexp.Regexp
	tpRe         *regexp.Regexp
	lotRe        *regexp.Regexp
	closeAllRe   *regexp.Regexp
	closeRe      *regexp.Regexp
	modifyRe     *regexp.Regexp
}

// NewSignalParser crea un nuevo parser
func NewSignalParser() *SignalParser {
	return &SignalParser{
		actionRe: regexp.MustCompile(`(?i)\b(BUY|SELL|LONG|SHORT|CLOSE|MODIFY|CLOSE ALL)\b`),
		symbolRe: regexp.MustCompile(`\b([A-Z]{6}|[A-Z]{3}/[A-Z]{3}|XAU[A-Z]*|XAG[A-Z]*|BTC[A-Z]*|ETH[A-Z]*|US30[A-Z]*|NAS[A-Z]*)\b`),
		priceRe:  regexp.MustCompile(`(?i)(?:entry|@|entry\s*price|precio\s*de\s*entrada|@)?\s*[:\s]?\s*(\d+\.?\d*)`),
		slRe:     regexp.MustCompile(`(?i)(?:sl|stop\s*loss|stoploss|stop)\s*[:\s@]?\s*(\d+\.?\d*)`),
		tpRe:     regexp.MustCompile(`(?i)(?:tp|take\s*profit|takeprofit|tp\d+)\s*[:\s@]?\s*(\d+\.?\d*)`),
		lotRe:    regexp.MustCompile(`(?i)(?:lot|lots|lot\s*size|size|volumen|volume)\s*[:\s]?\s*(\d+\.?\d*)`),
		closeAllRe: regexp.MustCompile(`(?i)\bCLOSE\s*ALL\b`),
		closeRe:    regexp.MustCompile(`(?i)\bCLOSE\b`),
		modifyRe:   regexp.MustCompile(`(?i)\b(MODIFY|MOVE\s*SL|MOVE\s*TP)\b`),
	}
}

// Parse parsea un texto y retorna una señal o un error
func (p *SignalParser) Parse(text string) (*models.Signal, error) {
	if text == "" {
		return nil, fmt.Errorf("empty text")
	}

	// Normalizar texto
	normalized := normalizeText(text)
	upper := strings.ToUpper(normalized)

	signal := &models.Signal{
		RawText:     text,
		ReceivedAt:  time.Now(),
		Source:      models.SourceTelegram,
		TakeProfits: []float64{},
	}

	// ─── Detectar acción ──────────────────────────────────────
	action, err := p.extractAction(upper)
	if err != nil {
		return nil, err
	}
	signal.Action = action

	// ─── Detectar símbolo ─────────────────────────────────────
	symbol, err := p.extractSymbol(upper)
	if err != nil {
		return nil, fmt.Errorf("symbol not found: %w", err)
	}
	signal.Symbol = symbol

	// ─── Extraer precios según acción ─────────────────────────
	switch action {
	case models.ActionClose:
		// Para CLOSE no se requieren precios
		// Pero si hay "CLOSE ALL", no se requiere símbolo
	case models.ActionModify:
		// Modify requiere SL/TP nuevos pero no entry
		sl, _ := p.extractSL(normalized)
		if sl > 0 {
			signal.StopLoss = &sl
		}
		tps, _ := p.extractTPs(normalized)
		if len(tps) > 0 {
			signal.TakeProfits = tps
		}
	default:
		// BUY o SELL: entry, SL, TP
		entry, err := p.extractEntry(normalized, action)
		if err != nil {
			return nil, fmt.Errorf("entry price not found: %w", err)
		}
		signal.EntryPrice = &entry

		sl, _ := p.extractSL(normalized)
		if sl > 0 {
			signal.StopLoss = &sl
		}

		tps, _ := p.extractTPs(normalized)
		signal.TakeProfits = tps
	}

	// ─── Extraer lot size (opcional) ──────────────────────────
	lot, _ := p.extractLot(normalized)
	if lot > 0 {
		signal.LotSize = &lot
	}

	return signal, nil
}

// ParseRawSignal parsea una RawSignal (de Telegram)
func (p *SignalParser) ParseRawSignal(raw *models.RawSignal) (*models.Signal, error) {
	signal, err := p.Parse(raw.Text)
	if err != nil {
		return nil, err
	}
	signal.Source = models.SourceTelegram
	signal.SourceID = fmt.Sprintf("%d_%d", raw.ChannelID, raw.MessageID)
	if signal.Comment == "" {
		signal.Comment = fmt.Sprintf("Channel: %s (msg %d)", raw.ChannelName, raw.MessageID)
	}
	return signal, nil
}

// ─── Extractors ───────────────────────────────────────────────

func (p *SignalParser) extractAction(upper string) (models.Action, error) {
	if p.closeAllRe.MatchString(upper) {
		// CLOSE ALL se trata como CLOSE
		return models.ActionClose, nil
	}

	match := p.actionRe.FindStringSubmatch(upper)
	if len(match) < 2 {
		return "", fmt.Errorf("action not found in text")
	}

	actionStr := match[1]
	switch actionStr {
	case "BUY", "LONG":
		return models.ActionBuy, nil
	case "SELL", "SHORT":
		return models.ActionSell, nil
	case "CLOSE":
		return models.ActionClose, nil
	case "MODIFY", "MOVE SL", "MOVE TP":
		return models.ActionModify, nil
	default:
		return "", fmt.Errorf("unknown action: %s", actionStr)
	}
}

func (p *SignalParser) extractSymbol(upper string) (string, error) {
	match := p.symbolRe.FindStringSubmatch(upper)
	if len(match) < 2 {
		return "", fmt.Errorf("symbol not found")
	}

	symbol := match[1]

	// Normalizar formato
	switch {
	case strings.Contains(symbol, "/"):
		parts := strings.Split(symbol, "/")
		symbol = parts[0] + parts[1]
	case strings.HasPrefix(symbol, "XAU"):
		symbol = "XAUUSD"
	case strings.HasPrefix(symbol, "XAG"):
		symbol = "XAGUSD"
	case strings.HasPrefix(symbol, "BTC"):
		symbol = "BTCUSD"
	case strings.HasPrefix(symbol, "ETH"):
		symbol = "ETHUSD"
	case strings.HasPrefix(symbol, "US30"):
		symbol = "US30"
	case strings.HasPrefix(symbol, "NAS"):
		symbol = "NAS100"
	}

	// Validar pattern (MT5 symbols)
	if !isValidSymbol(symbol) {
		return "", fmt.Errorf("invalid symbol format: %s", symbol)
	}

	return symbol, nil
}

func (p *SignalParser) extractEntry(text string, action models.Action) (float64, error) {
	// Patrones específicos para entry price
	patterns := []string{
		`(?i)entry[:\s@]+(\d+\.?\d*)`,
		`(?i)@\s*(\d+\.?\d*)`,
		`(?i)precio[:\s]+(\d+\.?\d*)`,
		`(?i)price[:\s]+(\d+\.?\d*)`,
		`(?i)open[:\s]+(\d+\.?\d*)`,
		`(?i)open\s*price[:\s]+(\d+\.?\d*)`,
	}

	for _, pattern := range patterns {
		re := regexp.MustCompile(pattern)
		match := re.FindStringSubmatch(text)
		if len(match) >= 2 {
			price, err := strconv.ParseFloat(match[1], 64)
			if err == nil && price > 0 {
				return price, nil
			}
		}
	}

	// Si no se encuentra con patrones específicos, buscar primer número
	// después de la acción
	priceRe := regexp.MustCompile(`(\d+\.?\d*)`)
	matches := priceRe.FindAllStringSubmatch(text, -1)
	for _, match := range matches {
		price, err := strconv.ParseFloat(match[1], 64)
		if err == nil && price > 0 && price < 1000000 {
			return price, nil
		}
	}

	return 0, fmt.Errorf("no entry price found")
}

func (p *SignalParser) extractSL(text string) (float64, error) {
	patterns := []string{
		`(?i)sl[:\s]+(\d+\.?\d*)`,
		`(?i)stop[:\s]+(\d+\.?\d*)`,
		`(?i)stop\s*loss[:\s]+(\d+\.?\d*)`,
		`(?i)stoploss[:\s]+(\d+\.?\d*)`,
		`(?i)sl\s*@\s*(\d+\.?\d*)`,
	}

	for _, pattern := range patterns {
		re := regexp.MustCompile(pattern)
		match := re.FindStringSubmatch(text)
		if len(match) >= 2 {
			price, err := strconv.ParseFloat(match[1], 64)
			if err == nil && price > 0 {
				return price, nil
			}
		}
	}

	return 0, fmt.Errorf("no SL found")
}

func (p *SignalParser) extractTPs(text string) ([]float64, error) {
	tps := []float64{}

	// TP1, TP2, TP3, ...
	multiTPRe := regexp.MustCompile(`(?i)tp(\d+)[:\s@]+(\d+\.?\d*)`)
	matches := multiTPRe.FindAllStringSubmatch(text, -1)

	if len(matches) > 0 {
		// Ordenar por número de TP
		tpMap := make(map[int]float64)
		for _, match := range matches {
			num, _ := strconv.Atoi(match[1])
			price, err := strconv.ParseFloat(match[2], 64)
			if err == nil && price > 0 {
				tpMap[num] = price
			}
		}

		// Retornar en orden
		for i := 1; i <= len(tpMap); i++ {
			if p, ok := tpMap[i]; ok {
				tps = append(tps, p)
			}
		}
		return tps, nil
	}

	// Single TP
	singleTPRe := regexp.MustCompile(`(?i)tp[:\s@]+(\d+\.?\d*)`)
	match := singleTPRe.FindStringSubmatch(text)
	if len(match) >= 2 {
		price, err := strconv.ParseFloat(match[1], 64)
		if err == nil && price > 0 {
			return []float64{price}, nil
		}
	}

	// TP con coma
	commaTPRe := regexp.MustCompile(`(?i)tp[s]?[:\s@]+([\d.,\s]+)`)
	match = commaTPRe.FindStringSubmatch(text)
	if len(match) >= 2 {
		parts := strings.Split(match[1], ",")
		for _, part := range parts {
			price, err := strconv.ParseFloat(strings.TrimSpace(part), 64)
			if err == nil && price > 0 {
				tps = append(tps, price)
			}
		}
	}

	return tps, nil
}

func (p *SignalParser) extractLot(text string) (float64, error) {
	match := p.lotRe.FindStringSubmatch(text)
	if len(match) < 2 {
		return 0, fmt.Errorf("no lot found")
	}
	lot, err := strconv.ParseFloat(match[1], 64)
	if err != nil || lot <= 0 {
		return 0, fmt.Errorf("invalid lot")
	}
	return lot, nil
}

// ─── Helpers ───────────────────────────────────────────────────

func normalizeText(text string) string {
	// Remover emojis comunes de trading
	emojis := []string{"🔵", "🟢", "🔴", "🟡", "🟠", "🟣", "⚫", "⚪", "🟤",
		"📈", "📉", "💹", "💰", "💵", "💲", "💱", "✅", "❌", "🎯", "🛑", "⛔",
		"🚀", "⭐", "🔥", "⚡", "💎", "🏆", "🔔", "📊", "📋", "📝", "🏷️"}

	normalized := text
	for _, emoji := range emojis {
		normalized = strings.ReplaceAll(normalized, emoji, "")
	}

	// Normalizar espacios
	normalized = regexp.MustCompile(`\s+`).ReplaceAllString(normalized, " ")
	return strings.TrimSpace(normalized)
}

func isValidSymbol(symbol string) bool {
	// Pattern: ^[A-Z0-9]+(\.(m|M|r|R|pro|raw|Raw))?$
	if len(symbol) < 3 || len(symbol) > 20 {
		return false
	}

	re := regexp.MustCompile(`^[A-Z0-9]+(\.(m|M|r|R|pro|raw|Raw))?$`)
	return re.MatchString(symbol)
}