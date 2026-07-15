// Package service contiene la lógica de negocio del signal-engine.
package service

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/nats-io/nats.go"
	"github.com/redis/go-redis/v9"

	"github.com/tnsvt/signal-engine/internal/models"
	"github.com/tnsvt/signal-engine/internal/parser"
	"github.com/tnsvt/signal-engine/internal/repository"
)

// ErrDuplicate signal duplicado
var ErrDuplicate = errors.New("signal duplicate")

// ErrInvalidFormat formato inválido
var ErrInvalidFormat = errors.New("invalid signal format")

// ErrExpired señal expirada
var ErrExpired = errors.New("signal expired")

// SignalService lógica principal
type SignalService struct {
	repo        repository.SignalRepository
	redis       *redis.Client
	nats        *nats.Conn
	parser      *parser.SignalParser
	dedupTTL    time.Duration
	log         interface {
		Info(string, ...any)
		Warn(string, ...any)
		Error(string, error, ...any)
	}
}

// NewSignalService crea el service
func NewSignalService(
	repo repository.SignalRepository,
	redis *redis.Client,
	nats *nats.Conn,
	parser *parser.SignalParser,
	dedupTTL time.Duration,
	log interface {
		Info(string, ...any)
		Warn(string, ...any)
		Error(string, error, ...any)
	},
) *SignalService {
	return &SignalService{
		repo:     repo,
		redis:    redis,
		nats:     nats,
		parser:   parser,
		dedupTTL: dedupTTL,
		log:      log,
	}
}

// SubmitSignal recibe, valida, deduplica y publica una señal
func (s *SignalService) SubmitSignal(ctx context.Context, req *models.SubmitSignalRequest) (*models.Signal, error) {
	// ─── Construir Signal desde request ─────────────────────────
	signal := &models.Signal{
		ID:         uuid.New(),
		TenantID:   req.TenantID,
		UserID:     req.UserID,
		Symbol:     strings.ToUpper(strings.TrimSpace(req.Symbol)),
		Action:     req.Action,
		EntryPrice: req.EntryPrice,
		StopLoss:   req.StopLoss,
		TakeProfits: req.TakeProfits,
		LotSize:    req.LotSize,
		LotMode:    req.LotMode,
		RiskPercent: req.RiskPercent,
		Comment:    req.Comment,
		Source:     models.SourceAPI,
		Status:     models.StatusReceived,
		ReceivedAt: time.Now(),
	}

	if req.ExpiresIn > 0 {
		expires := time.Now().Add(time.Duration(req.ExpiresIn) * time.Second)
		signal.ExpiresAt = &expires
	}

	// ─── Calcular hash para deduplicación ─────────────────────
	signal.Hash = s.computeHash(signal)

	// ─── Deduplicación (Redis primero, luego DB) ─────────────
	if dupe, err := s.isDuplicate(ctx, signal.Hash); err == nil && dupe {
		s.log.Warn("Duplicate signal rejected", "hash", signal.Hash, "symbol", signal.Symbol)
		return nil, ErrDuplicate
	}

	// ─── Validar formato ─────────────────────────────────────
	if err := s.validateFormat(signal); err != nil {
		signal.Status = models.StatusRejected
		signal.RejectReason = models.RejectInvalidFormat
		signal.RejectDetails = err.Error()
		_ = s.repo.Create(ctx, signal)
		s.publishEvent(ctx, "rejected", signal)
		return signal, err
	}

	// ─── Marcar como validated ────────────────────────────────
	signal.Status = models.StatusValidated
	now := time.Now()
	signal.ValidatedAt = &now

	if err := s.repo.Create(ctx, signal); err != nil {
		s.log.Error("Failed to save signal", err)
		return nil, fmt.Errorf("save signal: %w", err)
	}

	// ─── Publicar a NATS ─────────────────────────────────────
	s.publishEvent(ctx, "created", signal)

	s.log.Info("Signal accepted", "id", signal.ID, "symbol", signal.Symbol, "action", signal.Action)

	return signal, nil
}

// SubmitRawSignal procesa una señal cruda de Telegram (texto)
func (s *SignalService) SubmitRawSignal(ctx context.Context, raw *models.RawSignal) (*models.Signal, error) {
	signal, err := s.parser.ParseRawSignal(raw)
	if err != nil {
		// Guardar como rechazada
		rejected := &models.Signal{
			ID:         uuid.New(),
			TenantID:   uuid.Nil,
			Source:     models.SourceTelegram,
			SourceID:   fmt.Sprintf("%d_%d", raw.ChannelID, raw.MessageID),
			RawText:    raw.Text,
			Action:     models.ActionBuy, // placeholder
			Symbol:     "UNKNOWN",
			Status:     models.StatusRejected,
			RejectReason: models.RejectInvalidFormat,
			RejectDetails: err.Error(),
			Hash:       s.computeRawHash(raw.Text),
			ReceivedAt: raw.Timestamp,
		}
		_ = s.repo.Create(ctx, rejected)
		s.publishEvent(ctx, "rejected", rejected)
		return rejected, err
	}

	signal.TenantID = uuid.Nil // Se setea por defecto; en producción usar el del usuario que autorizó el canal
	signal.SourceID = fmt.Sprintf("%d_%d", raw.ChannelID, raw.MessageID)
	signal.Hash = s.computeRawHashWithSignal(raw.Text, signal)

	// Dedup
	if dupe, _ := s.isDuplicate(ctx, signal.Hash); dupe {
		s.log.Info("Telegram signal duplicate, skipping", "source_id", signal.SourceID)
		return nil, ErrDuplicate
	}

	// Validate
	if err := s.validateFormat(signal); err != nil {
		signal.Status = models.StatusRejected
		signal.RejectReason = models.RejectInvalidFormat
		signal.RejectDetails = err.Error()
		_ = s.repo.Create(ctx, signal)
		s.publishEvent(ctx, "rejected", signal)
		return signal, err
	}

	signal.Status = models.StatusValidated
	now := time.Now()
	signal.ValidatedAt = &now

	if err := s.repo.Create(ctx, signal); err != nil {
		return nil, err
	}

	s.publishEvent(ctx, "created", signal)
	s.log.Info("Telegram signal accepted", "id", signal.ID, "symbol", signal.Symbol, "action", signal.Action)

	return signal, nil
}

// ─── Deduplicación ────────────────────────────────────────────

// computeHash genera hash único basado en parámetros clave
func (s *SignalService) computeHash(sig *models.Signal) string {
	entryStr := ""
	if sig.EntryPrice != nil {
		entryStr = fmt.Sprintf("%.8f", *sig.EntryPrice)
	}
	slStr := ""
	if sig.StopLoss != nil {
		slStr = fmt.Sprintf("%.8f", *sig.StopLoss)
	}
	tpStr := ""
	for _, tp := range sig.TakeProfits {
		tpStr += fmt.Sprintf("%.8f,", tp)
	}
	lotStr := ""
	if sig.LotSize != nil {
		lotStr = fmt.Sprintf("%.4f", *sig.LotSize)
	}

	key := fmt.Sprintf("%s|%s|%s|%s|%s|%s|%s|%d",
		sig.Symbol, sig.Action, entryStr, slStr, tpStr, lotStr, sig.Source, sig.ReceivedAt.Unix()/300, // bucket de 5 min
	)
	h := sha256.Sum256([]byte(key))
	return hex.EncodeToString(h[:])
}

func (s *SignalService) computeRawHash(text string) string {
	h := sha256.Sum256([]byte(strings.ToLower(text)))
	return hex.EncodeToString(h[:])
}

func (s *SignalService) computeRawHashWithSignal(text string, sig *models.Signal) string {
	entryStr := ""
	if sig.EntryPrice != nil {
		entryStr = fmt.Sprintf("%.8f", *sig.EntryPrice)
	}
	slStr := ""
	if sig.StopLoss != nil {
		slStr = fmt.Sprintf("%.8f", *sig.StopLoss)
	}
	tpStr := ""
	for _, tp := range sig.TakeProfits {
		tpStr += fmt.Sprintf("%.8f,", tp)
	}

	key := fmt.Sprintf("%s|%s|%s|%s|%s|%s",
		strings.ToLower(text), sig.Symbol, sig.Action, entryStr, slStr, tpStr,
	)
	h := sha256.Sum256([]byte(key))
	return hex.EncodeToString(h[:])
}

// isDuplicate verifica si el hash ya existe (Redis fast path, luego DB)
func (s *SignalService) isDuplicate(ctx context.Context, hash string) (bool, error) {
	if s.redis != nil {
		// Fast path: Redis
		exists, err := s.redis.Exists(ctx, "signal:hash:"+hash).Result()
		if err == nil && exists > 0 {
			return true, nil
		}

		// Guardar hash con TTL
		s.redis.Set(ctx, "signal:hash:"+hash, "1", s.dedupTTL)
	}

	// Slow path: PostgreSQL
	_, err := s.repo.GetByHash(ctx, hash)
	if err == nil {
		return true, nil
	}
	if errors.Is(err, repository.ErrNotFound) {
		return false, nil
	}
	return false, err
}

// ─── Validación ───────────────────────────────────────────────

func (s *SignalService) validateFormat(sig *models.Signal) error {
	if sig.Symbol == "" {
		return fmt.Errorf("symbol is required")
	}

	if sig.Action == "" {
		return fmt.Errorf("action is required")
	}

	// Validar pattern del símbolo
	if !isValidSymbol(sig.Symbol) {
		return fmt.Errorf("invalid symbol format: %s (must match ^[A-Z0-9]+(\\.(m|M|r|R|pro|raw|Raw))?$)", sig.Symbol)
	}

	// Acciones que requieren precio de entrada
	if sig.Action == models.ActionBuy || sig.Action == models.ActionSell {
		if sig.EntryPrice == nil || *sig.EntryPrice <= 0 {
			return fmt.Errorf("entry_price is required and must be > 0 for BUY/SELL")
		}
		if sig.StopLoss == nil || *sig.StopLoss <= 0 {
			return fmt.Errorf("stop_loss is required and must be > 0 for BUY/SELL")
		}
		if len(sig.TakeProfits) == 0 {
			return fmt.Errorf("at least one take_profit is required for BUY/SELL")
		}

		// Validar coherencia BUY: TP > entry > SL
		if sig.Action == models.ActionBuy {
			for _, tp := range sig.TakeProfits {
				if tp <= *sig.EntryPrice {
					return fmt.Errorf("for BUY, take_profit must be > entry_price")
				}
			}
			if *sig.StopLoss >= *sig.EntryPrice {
				return fmt.Errorf("for BUY, stop_loss must be < entry_price")
			}
		}

		// Validar coherencia SELL: TP < entry < SL
		if sig.Action == models.ActionSell {
			for _, tp := range sig.TakeProfits {
				if tp >= *sig.EntryPrice {
					return fmt.Errorf("for SELL, take_profit must be < entry_price")
				}
			}
			if *sig.StopLoss <= *sig.EntryPrice {
				return fmt.Errorf("for SELL, stop_loss must be > entry_price")
			}
		}
	}

	// Validar lot size si está presente
	if sig.LotSize != nil && (*sig.LotSize <= 0 || *sig.LotSize > 100) {
		return fmt.Errorf("lot_size must be between 0.01 and 100")
	}

	// Validar expiración
	if sig.ExpiresAt != nil && sig.ExpiresAt.Before(time.Now()) {
		return ErrExpired
	}

	return nil
}

func isValidSymbol(symbol string) bool {
	if len(symbol) < 3 || len(symbol) > 20 {
		return false
	}
	for _, c := range symbol {
		ok := (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '.'
		if !ok {
			return false
		}
	}
	return true
}

// ─── NATS Publishing ──────────────────────────────────────────

func (s *SignalService) publishEvent(ctx context.Context, action string, signal *models.Signal) {
	if s.nats == nil {
		return
	}

	subject := fmt.Sprintf("trading.signal.%s", action)
	payload := map[string]any{
		"id":           signal.ID,
		"tenant_id":    signal.TenantID,
		"source":       signal.Source,
		"symbol":       signal.Symbol,
		"action":       signal.Action,
		"entry_price":  signal.EntryPrice,
		"stop_loss":    signal.StopLoss,
		"take_profits": signal.TakeProfits,
		"lot_size":     signal.LotSize,
		"lot_mode":     signal.LotMode,
		"risk_percent": signal.RiskPercent,
		"confidence":   signal.Confidence,
		"status":       signal.Status,
		"hash":         signal.Hash,
		"timestamp":    time.Now().UTC().Format(time.RFC3339Nano),
		"event":        action,
	}

	if signal.RejectReason != "" {
		payload["reject_reason"] = signal.RejectReason
		payload["reject_details"] = signal.RejectDetails
	}

	data, err := json.Marshal(payload)
	if err != nil {
		s.log.Error("Failed to marshal signal event", err)
		return
	}

	if err := s.nats.Publish(subject, data); err != nil {
		s.log.Warn("NATS publish failed", "subject", subject, "error", err.Error())
	}

	// Flush async para confirmar envío
	go func() {
		_ = s.nats.FlushTimeout(2 * time.Second)
	}()
}

// ─── Read operations ──────────────────────────────────────────

func (s *SignalService) GetByID(ctx context.Context, id uuid.UUID) (*models.Signal, error) {
	return s.repo.GetByID(ctx, id)
}

func (s *SignalService) List(ctx context.Context, tenantID *uuid.UUID, limit, offset int) ([]*models.Signal, int64, error) {
	return s.repo.List(ctx, tenantID, limit, offset)
}

func (s *SignalService) Stats(ctx context.Context, tenantID *uuid.UUID) (*models.StatsResponse, error) {
	since := time.Now().Add(-24 * time.Hour)
	return s.repo.Stats(ctx, tenantID, since)
}

func (s *SignalService) ParsePreview(ctx context.Context, text string) (*models.Signal, error) {
	return s.parser.Parse(text)
}

// ─── SSE Stream ───────────────────────────────────────────────

// Stream returns a channel for SSE streaming
func (s *SignalService) Stream(ctx context.Context) (<-chan *models.Signal, error) {
	out := make(chan *models.Signal, 10)

	if s.nats == nil {
		close(out)
		return out, fmt.Errorf("NATS not available")
	}

	sub, err := s.nats.Subscribe("trading.signal.>", func(msg *nats.Msg) {
		var signal models.Signal
		if err := json.Unmarshal(msg.Data, &signal); err != nil {
			return
		}
		select {
		case out <- &signal:
		case <-ctx.Done():
			return
		default:
			// Slow consumer, drop
		}
	})
	if err != nil {
		close(out)
		return out, err
	}

	go func() {
		<-ctx.Done()
		sub.Unsubscribe()
		close(out)
	}()

	return out, nil
}