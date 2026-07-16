// Package service contiene la lógica de negocio del risk-engine.
package service

import (
	"context"
	"encoding/json"
	"fmt"
	"math"
	"time"

	"github.com/google/uuid"
	"github.com/nats-io/nats.go"
	"github.com/redis/go-redis/v9"

	"github.com/tnsvt/risk-engine/internal/models"
	"github.com/tnsvt/risk-engine/internal/repository"
)

// Config configuración del risk engine
type Config struct {
	DailyLossLimit      float64
	DailyProfitTarget   float64
	WeeklyLossLimit     float64
	MaxOpenPositions    int
	TrailingStop        bool
	TrailingStep        int
	TrailingStart       int
}

// RiskService lógica principal
type RiskService struct {
	repo   repository.RiskRepository
	redis  *redis.Client
	nats   *nats.Conn
	config Config
	log    interface {
		Info(string, ...any)
		Warn(string, ...any)
		Error(string, error, ...any)
	}
}

// NewRiskService crea el service
func NewRiskService(
	repo repository.RiskRepository,
	redis *redis.Client,
	nats *nats.Conn,
	log interface {
		Info(string, ...any)
		Warn(string, ...any)
		Error(string, error, ...any)
	},
	cfg Config,
) *RiskService {
	return &RiskService{
		repo:   repo,
		redis:  redis,
		nats:   nats,
		config: cfg,
		log:    log,
	}
}

// ─── Risk Evaluation ───────────────────────────────────────────

// EvaluateSignal evalúa el riesgo de una señal
func (s *RiskService) EvaluateSignal(ctx context.Context, signal *models.SignalInput) (*models.RiskEvaluation, error) {
	// Get limits del tenant
	limits, err := s.repo.GetLimits(ctx, signal.TenantID)
	if err != nil {
		return nil, fmt.Errorf("get limits: %w", err)
	}

	// Calcular P&L actual
	now := time.Now()
	dailyPnL := s.getDailyPnLCached(ctx, signal.TenantID, now)
	weeklyPnL := s.getWeeklyPnLCached(ctx, signal.TenantID, now)

	// Open positions
	openPositions, err := s.repo.ListOpenPositions(ctx, signal.TenantID)
	if err != nil {
		return nil, fmt.Errorf("list positions: %w", err)
	}

	// Exposure per symbol
	exposurePerSymbol := make(map[string]float64)
	totalUnrealizedPnL := 0.0
	for _, pos := range openPositions {
		exposurePerSymbol[pos.Symbol] += pos.Quantity * pos.CurrentPrice
		totalUnrealizedPnL += pos.UnrealizedPnL
	}

	evaluation := &models.RiskEvaluation{
		SignalID:           signal.ID,
		TenantID:           signal.TenantID,
		CurrentDailyPnL:    dailyPnL,
		CurrentWeeklyPnL:   weeklyPnL,
		CurrentDrawdown:    0, // calculado aparte
		OpenPositionsCount: len(openPositions),
		ExposurePerSymbol:  exposurePerSymbol,
		EvaluatedAt:        now,
		Warnings:           []string{},
	}

	// ─── Check 1: Daily loss limit ─────────────────────────────
	if dailyPnL <= -limits.DailyLossLimit {
		evaluation.Decision = models.DecisionRejected
		evaluation.RejectReason = models.RejectDailyLossLimit
		evaluation.RiskLevel = models.RiskLevelCritical
		evaluation.Reason = fmt.Sprintf("daily loss limit reached: $%.2f (limit: $%.2f)", dailyPnL, limits.DailyLossLimit)
		s.publishRejected(ctx, evaluation)
		return evaluation, nil
	}

	// ─── Check 2: Weekly loss limit ────────────────────────────
	if weeklyPnL <= -limits.WeeklyLossLimit {
		evaluation.Decision = models.DecisionRejected
		evaluation.RejectReason = models.RejectWeeklyLossLimit
		evaluation.RiskLevel = models.RiskLevelCritical
		evaluation.Reason = fmt.Sprintf("weekly loss limit reached: $%.2f (limit: $%.2f)", weeklyPnL, limits.WeeklyLossLimit)
		s.publishRejected(ctx, evaluation)
		return evaluation, nil
	}

	// ─── Check 3: Daily profit target (si está en profit, deja de operar) ──
	if dailyPnL >= limits.DailyProfitTarget {
		evaluation.Decision = models.DecisionRejected
		evaluation.RejectReason = models.RejectDailyProfitTarget
		evaluation.RiskLevel = models.RiskLevelLow
		evaluation.Reason = fmt.Sprintf("daily profit target reached: $%.2f — preserving gains", dailyPnL)
		s.publishRejected(ctx, evaluation)
		return evaluation, nil
	}

	// ─── Check 4: Max open positions ──────────────────────────
	if len(openPositions) >= limits.MaxOpenPositions {
		evaluation.Decision = models.DecisionRejected
		evaluation.RejectReason = models.RejectMaxOpenPositions
		evaluation.RiskLevel = models.RiskLevelHigh
		evaluation.Reason = fmt.Sprintf("max open positions reached: %d (limit: %d)", len(openPositions), limits.MaxOpenPositions)
		s.publishRejected(ctx, evaluation)
		return evaluation, nil
	}

	// ─── Check 5: Max exposure per symbol ──────────────────────
	if signal.EntryPrice != nil && signal.LotSize != nil {
		// Asumir 1 lot = 100,000 unidades; pip value aproximado
		estimatedExposure := *signal.LotSize * *signal.EntryPrice * 100000
		currentExposure := exposurePerSymbol[signal.Symbol]
		if currentExposure+estimatedExposure > limits.MaxExposurePerSymbol {
			evaluation.Decision = models.DecisionRejected
			evaluation.RejectReason = models.RejectMaxExposurePerSymbol
			evaluation.RiskLevel = models.RiskLevelHigh
			evaluation.Reason = fmt.Sprintf("max exposure per symbol would be exceeded: $%.2f (limit: $%.2f)",
				currentExposure+estimatedExposure, limits.MaxExposurePerSymbol)
			s.publishRejected(ctx, evaluation)
			return evaluation, nil
		}
	}

	// ─── Check 6: Min confidence (si AI-scored) ────────────────
	if signal.Confidence > 0 && signal.Confidence < limits.MinConfidence {
		evaluation.Decision = models.DecisionRejected
		evaluation.RejectReason = models.RejectLowConfidence
		evaluation.RiskLevel = models.RiskLevelHigh
		evaluation.Reason = fmt.Sprintf("AI confidence too low: %.2f (min: %.2f)", signal.Confidence, limits.MinConfidence)
		s.publishRejected(ctx, evaluation)
		return evaluation, nil
	}

	// ─── Si todas las checks pasan: APPROVED ──────────────────
	evaluation.Decision = models.DecisionApproved

	// Calcular risk level
	if dailyPnL < -limits.DailyLossLimit*0.5 {
		evaluation.RiskLevel = models.RiskLevelHigh
	} else if dailyPnL < 0 {
		evaluation.RiskLevel = models.RiskLevelMedium
	} else {
		evaluation.RiskLevel = models.RiskLevelLow
	}

	// ─── Position sizing (si lot_mode = risk_based) ──────────
	if signal.LotMode == "risk_based" && signal.RiskPercent != nil && signal.EntryPrice != nil && signal.StopLoss != nil {
		recommendedLot := s.calculatePositionSize(
			*signal.RiskPercent,
			*signal.EntryPrice,
			*signal.StopLoss,
			10000, // Asumir balance $10k (en producción consultar broker)
		)
		evaluation.RecommendedLotSize = &recommendedLot
		if signal.LotSize != nil {
			orig := *signal.LotSize
			evaluation.OriginalLotSize = &orig
		}
		// Warnings si difiere mucho
		if signal.LotSize != nil && math.Abs(*signal.LotSize-recommendedLot) > 0.01 {
			evaluation.Warnings = append(evaluation.Warnings,
				fmt.Sprintf("recommended lot (%.2f) differs from requested (%.2f)",
					recommendedLot, *signal.LotSize))
		}
	}

	// Publicar validación
	s.publishValidated(ctx, evaluation)

	s.log.Info("Signal approved",
		"signal_id", signal.ID,
		"symbol", signal.Symbol,
		"action", signal.Action,
		"risk_level", evaluation.RiskLevel,
		"daily_pnl", dailyPnL,
		"open_positions", len(openPositions))

	return evaluation, nil
}

// ─── Position Sizing ──────────────────────────────────────────

// calculatePositionSize calcula el lot size basado en % de riesgo
//
// Formula: lot = (balance * risk%) / (sl_distance_in_pips * pip_value)
//
// Para simplificar (Fase 1): usamos aproximación standard lot ($10/pip en EURUSD)
func (s *RiskService) calculatePositionSize(riskPercent, entry, stop, balance float64) float64 {
	slDistance := math.Abs(entry - stop)

	// Convertir a pips (asumir 4 decimales para forex, 2 para JPY pairs)
	pips := slDistance * 10000
	if pips == 0 {
		return 0.01
	}

	riskAmount := balance * (riskPercent / 100)
	// Asumir pip value = $10 per standard lot (100,000 unidades)
	// En producción esto varía por par (USD/JPY, etc.)
	pipValue := 10.0

	lot := riskAmount / (pips * pipValue)

	// Clamp entre 0.01 y 100
	if lot < 0.01 {
		lot = 0.01
	}
	if lot > 100 {
		lot = 100
	}

	// Round a 2 decimales
	return math.Round(lot*100) / 100
}

// ─── Trailing Stop ─────────────────────────────────────────────

// RunTrailingStopMonitor corre cada 10s y ajusta trailing stops
func (s *RiskService) RunTrailingStopMonitor(ctx context.Context, interval time.Duration) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			s.updateAllTrailingStops(ctx)
		}
	}
}

func (s *RiskService) updateAllTrailingStops(ctx context.Context) {
	// En Fase 1: simplificado — solo actualizamos cuando llega UpdatePositionPrice
	// En Fase 2: integrar con price-feed para updates en tiempo real

	// Listar todas las posiciones abiertas con trailing activo
	rows, err := s.fetchAllOpenWithTrailing(ctx)
	if err != nil {
		s.log.Warn("Failed to fetch positions for trailing stop", "error", err.Error())
		return
	}

	for _, pos := range rows {
		newTrailingSL := s.calculateTrailingStop(pos)
		if newTrailingSL > 0 && newTrailingSL != pos.TrailingStopLoss {
			s.repo.UpdateTrailingStop(ctx, pos.ID, true, newTrailingSL)
			s.log.Info("Trailing stop updated",
				"position_id", pos.ID,
				"symbol", pos.Symbol,
				"old_sl", pos.StopLoss,
				"new_trailing_sl", newTrailingSL,
				"current_price", pos.CurrentPrice)
		}
	}
}

func (s *RiskService) fetchAllOpenWithTrailing(ctx context.Context) ([]*models.Position, error) {
	// Obtener todos los tenants activos (simplificado: en Fase 2 usar tenants service)
	tenants, err := s.listAllTenants(ctx)
	if err != nil {
		return nil, err
	}

	var all []*models.Position
	for _, tid := range tenants {
		positions, err := s.repo.ListOpenPositions(ctx, tid)
		if err != nil {
			continue
		}
		for _, p := range positions {
			if p.TrailingActive || s.shouldActivateTrailing(p) {
				all = append(all, p)
			}
		}
	}
	return all, nil
}

func (s *RiskService) listAllTenants(ctx context.Context) ([]uuid.UUID, error) {
	// En producción: consultar user-service o tenant-manager
	// Por ahora retornamos solo el default tenant (Fase 1)
	return []uuid.UUID{uuid.MustParse("00000000-0000-0000-0000-000000000001")}, nil
}

func (s *RiskService) shouldActivateTrailing(p *models.Position) bool {
	if !s.config.TrailingStop {
		return false
	}

	// Activar trailing cuando el precio se ha movido N pips a favor
	startThreshold := float64(s.config.TrailingStart) / 10000 // pips → price

	if p.Side == "buy" {
		return p.CurrentPrice-p.EntryPrice >= startThreshold
	}
	return p.EntryPrice-p.CurrentPrice >= startThreshold
}

func (s *RiskService) calculateTrailingStop(p *models.Position) float64 {
	if !s.shouldActivateTrailing(p) {
		return 0
	}

	step := float64(s.config.TrailingStep) / 10000 // pips → price

	if p.Side == "buy" {
		// SL = max(current_price - step, current_sl)
		newSL := p.CurrentPrice - step
		if newSL > p.StopLoss {
			return math.Round(newSL*100000) / 100000
		}
	} else {
		// Sell: SL = min(current_price + step, current_sl)
		newSL := p.CurrentPrice + step
		if newSL < p.StopLoss || p.StopLoss == 0 {
			return math.Round(newSL*100000) / 100000
		}
	}

	return p.TrailingStopLoss
}

// ─── Trades Lifecycle ──────────────────────────────────────────

// TradeOpened registra un trade abierto
func (s *RiskService) TradeOpened(ctx context.Context, req *models.TradeOpenedRequest) (*models.Position, error) {
	pos := &models.Position{
		ID:         uuid.New(),
		TenantID:   uuid.Nil, // Se setea desde el signal original
		SignalID:   req.SignalID,
		Broker:     req.Broker,
		AccountID:  req.AccountID,
		Ticket:     req.Ticket,
		Symbol:     req.Symbol,
		Side:       req.Side,
		Quantity:   req.Quantity,
		EntryPrice: req.EntryPrice,
		CurrentPrice: req.EntryPrice,
		StopLoss:   req.StopLoss,
		TakeProfit: req.TakeProfit,
		TPSide:     req.TPSide,
		OpenedAt:   time.Now(),
		UpdatedAt:  time.Now(),
	}

	if err := s.repo.CreatePosition(ctx, pos); err != nil {
		return nil, err
	}

	s.repo.IncrementTradesOpened(ctx, pos.TenantID, time.Now())

	// Activate trailing si está configurado
	if s.config.TrailingStop {
		pos.TrailingActive = true
		pos.TrailingStopLoss = req.StopLoss
	}

	s.log.Info("Trade opened",
		"position_id", pos.ID,
		"symbol", pos.Symbol,
		"side", pos.Side,
		"quantity", pos.Quantity,
		"entry", req.EntryPrice)

	// Publicar evento
	s.publishPositionOpened(ctx, pos)

	return pos, nil
}

// TradeClosed registra un trade cerrado
func (s *RiskService) TradeClosed(ctx context.Context, req *models.TradeClosedRequest) error {
	// Buscar position
	var pos *models.Position
	var err error
	if req.PositionID != uuid.Nil {
		pos, err = s.repo.GetPositionByID(ctx, req.PositionID)
	} else if req.Ticket != "" {
		pos, err = s.repo.GetPositionByTicket(ctx, req.Ticket)
	} else {
		return fmt.Errorf("must provide position_id or ticket")
	}

	if err != nil {
		return err
	}

	// Update daily P&L
	today := time.Now()
	newDailyPnL := s.getDailyPnLCached(ctx, pos.TenantID, today) + req.PnL

	if err := s.repo.ClosePosition(ctx, pos.ID, req.PnL, req.CloseReason); err != nil {
		return err
	}

	// Update stats
	won := req.PnL > 0
	s.repo.IncrementTradesClosed(ctx, pos.TenantID, today, won)

	// Cache update
	if s.redis != nil {
		s.redis.Set(ctx, s.pnlCacheKey(pos.TenantID, today), fmt.Sprintf("%.2f", newDailyPnL), 24*time.Hour)
	}

	s.log.Info("Trade closed",
		"position_id", pos.ID,
		"symbol", pos.Symbol,
		"pnl", req.PnL,
		"reason", req.CloseReason)

	// Publicar evento
	s.publishPositionClosed(ctx, pos, req)

	return nil
}

// UpdatePositionPrice actualiza precio actual de posición
func (s *RiskService) UpdatePositionPrice(ctx context.Context, req *models.UpdatePriceRequest) error {
	pos, err := s.repo.GetPositionByID(ctx, req.PositionID)
	if err != nil {
		return err
	}

	// Calcular P&L
	var unrealizedPnL, pnlPercent float64
	if pos.Side == "buy" {
		unrealizedPnL = (req.CurrentPrice - pos.EntryPrice) * pos.Quantity * 100000
	} else {
		unrealizedPnL = (pos.EntryPrice - req.CurrentPrice) * pos.Quantity * 100000
	}

	if pos.EntryPrice > 0 {
		pnlPercent = (unrealizedPnL / (pos.EntryPrice * pos.Quantity * 100000)) * 100
	}

	if err := s.repo.UpdatePositionPrice(ctx, pos.ID, req.CurrentPrice, unrealizedPnL, pnlPercent); err != nil {
		return err
	}

	// Update trailing stop si aplica
	pos.CurrentPrice = req.CurrentPrice
	if s.shouldActivateTrailing(pos) {
		newSL := s.calculateTrailingStop(pos)
		if newSL > 0 && newSL != pos.TrailingStopLoss {
			s.repo.UpdateTrailingStop(ctx, pos.ID, true, newSL)
		}
	}

	return nil
}

// ─── Cache helpers ────────────────────────────────────────────

func (s *RiskService) pnlCacheKey(tenantID uuid.UUID, day time.Time) string {
	return fmt.Sprintf("risk:pnl:%s:%s", tenantID.String(), day.Format("2006-01-02"))
}

func (s *RiskService) getDailyPnLCached(ctx context.Context, tenantID uuid.UUID, day time.Time) float64 {
	if s.redis != nil {
		key := s.pnlCacheKey(tenantID, day)
		if v, err := s.redis.Get(ctx, key).Float64(); err == nil {
			return v
		}
	}

	pnl, _ := s.repo.GetDailyPnL(ctx, tenantID, day)
	if s.redis != nil {
		key := s.pnlCacheKey(tenantID, day)
		s.redis.Set(ctx, key, fmt.Sprintf("%.2f", pnl), 24*time.Hour)
	}
	return pnl
}

func (s *RiskService) getWeeklyPnLCached(ctx context.Context, tenantID uuid.UUID, now time.Time) float64 {
	// Calcular inicio de semana (lunes)
	weekday := int(now.Weekday())
	if weekday == 0 {
		weekday = 7
	}
	weekStart := now.AddDate(0, 0, -(weekday - 1))
	weekStart = time.Date(weekStart.Year(), weekStart.Month(), weekStart.Day(), 0, 0, 0, 0, weekStart.Location())

	pnl, _ := s.repo.GetWeeklyPnL(ctx, tenantID, weekStart)
	return pnl
}

// ─── Limits ────────────────────────────────────────────────────

func (s *RiskService) GetLimits(ctx context.Context, tenantID uuid.UUID) (*models.RiskLimits, error) {
	return s.repo.GetLimits(ctx, tenantID)
}

func (s *RiskService) UpdateLimits(ctx context.Context, tenantID uuid.UUID, req *models.UpdateLimitsRequest) (*models.RiskLimits, error) {
	limits, err := s.repo.GetLimits(ctx, tenantID)
	if err != nil {
		return nil, err
	}

	if req.DailyLossLimit != nil {
		limits.DailyLossLimit = *req.DailyLossLimit
	}
	if req.DailyProfitTarget != nil {
		limits.DailyProfitTarget = *req.DailyProfitTarget
	}
	if req.WeeklyLossLimit != nil {
		limits.WeeklyLossLimit = *req.WeeklyLossLimit
	}
	if req.MaxOpenPositions != nil {
		limits.MaxOpenPositions = *req.MaxOpenPositions
	}
	if req.MaxExposurePerSymbol != nil {
		limits.MaxExposurePerSymbol = *req.MaxExposurePerSymbol
	}
	if req.MaxDrawdownPercent != nil {
		limits.MaxDrawdownPercent = *req.MaxDrawdownPercent
	}
	if req.MinConfidence != nil {
		limits.MinConfidence = *req.MinConfidence
	}
	if req.TrailingStop != nil {
		limits.TrailingStop = *req.TrailingStop
	}
	if req.TrailingStep != nil {
		limits.TrailingStep = *req.TrailingStep
	}
	if req.TrailingStart != nil {
		limits.TrailingStart = *req.TrailingStart
	}

	if err := s.repo.UpsertLimits(ctx, limits); err != nil {
		return nil, err
	}

	// Invalidar cache
	if s.redis != nil {
		s.redis.Del(ctx, fmt.Sprintf("risk:limits:%s", tenantID.String()))
	}

	return limits, nil
}

// ─── Stats ─────────────────────────────────────────────────────

func (s *RiskService) GetStats(ctx context.Context, tenantID uuid.UUID) (*models.StatsResponse, error) {
	now := time.Now()
	dailyPnL := s.getDailyPnLCached(ctx, tenantID, now)
	weeklyPnL := s.getWeeklyPnLCached(ctx, tenantID, now)

	monthStart := time.Date(now.Year(), now.Month(), 1, 0, 0, 0, 0, now.Location())
	monthlyPnL, _ := s.repo.GetMonthlyPnL(ctx, tenantID, monthStart)

	openPositions, _ := s.repo.ListOpenPositions(ctx, tenantID)
	limits, _ := s.repo.GetLimits(ctx, tenantID)

	// Convert []*Position → []Position for the response DTO
	openPositionsValue := make([]models.Position, 0, len(openPositions))
	for _, p := range openPositions {
		if p != nil {
			openPositionsValue = append(openPositionsValue, *p)
		}
	}

	stats := &models.StatsResponse{
		Daily: models.DailyStats{
			TenantID:      tenantID,
			Date:          now,
			DailyPnL:      dailyPnL,
			WeeklyPnL:     weeklyPnL,
			OpenPositions: len(openPositions),
		},
		WeeklyPnL:     weeklyPnL,
		MonthlyPnL:    monthlyPnL,
		OpenPositions: openPositionsValue,
		Limits:        *limits,
	}

	return stats, nil
}

func (s *RiskService) GetExposure(ctx context.Context, tenantID uuid.UUID) (map[string]float64, error) {
	positions, err := s.repo.ListOpenPositions(ctx, tenantID)
	if err != nil {
		return nil, err
	}

	exposure := make(map[string]float64)
	for _, pos := range positions {
		exposure[pos.Symbol] += pos.Quantity * pos.CurrentPrice * 100000
	}
	return exposure, nil
}

func (s *RiskService) ListPositions(ctx context.Context, tenantID uuid.UUID) ([]*models.Position, error) {
	return s.repo.ListOpenPositions(ctx, tenantID)
}

// ─── NATS Publishing ──────────────────────────────────────────

func (s *RiskService) publishValidated(ctx context.Context, ev *models.RiskEvaluation) {
	subject := "trading.signal.validated"
	payload, _ := json.Marshal(map[string]any{
		"signal_id":            ev.SignalID,
		"tenant_id":            ev.TenantID,
		"decision":             ev.Decision,
		"risk_level":           ev.RiskLevel,
		"original_lot_size":    ev.OriginalLotSize,
		"recommended_lot_size": ev.RecommendedLotSize,
		"warnings":             ev.Warnings,
		"timestamp":            time.Now().UTC().Format(time.RFC3339Nano),
	})
	if err := s.nats.Publish(subject, payload); err != nil {
		s.log.Warn("NATS publish failed", "subject", subject, "error", err.Error())
	}
}

func (s *RiskService) publishRejected(ctx context.Context, ev *models.RiskEvaluation) {
	subject := "trading.signal.rejected"
	payload, _ := json.Marshal(map[string]any{
		"signal_id":     ev.SignalID,
		"tenant_id":     ev.TenantID,
		"decision":      ev.Decision,
		"reject_reason": ev.RejectReason,
		"reason":        ev.Reason,
		"risk_level":    ev.RiskLevel,
		"timestamp":     time.Now().UTC().Format(time.RFC3339Nano),
	})
	if err := s.nats.Publish(subject, payload); err != nil {
		s.log.Warn("NATS publish failed", "subject", subject, "error", err.Error())
	}
}

func (s *RiskService) publishPositionOpened(ctx context.Context, pos *models.Position) {
	subject := "trading.position.opened"
	payload, _ := json.Marshal(map[string]any{
		"position_id": pos.ID,
		"signal_id":   pos.SignalID,
		"tenant_id":   pos.TenantID,
		"symbol":      pos.Symbol,
		"side":        pos.Side,
		"quantity":    pos.Quantity,
		"entry":       pos.EntryPrice,
		"sl":          pos.StopLoss,
		"tp":          pos.TakeProfit,
		"timestamp":   time.Now().UTC().Format(time.RFC3339Nano),
	})
	s.nats.Publish(subject, payload)
}

func (s *RiskService) publishPositionClosed(ctx context.Context, pos *models.Position, req *models.TradeClosedRequest) {
	subject := "trading.position.closed"
	payload, _ := json.Marshal(map[string]any{
		"position_id":  pos.ID,
		"signal_id":    pos.SignalID,
		"tenant_id":    pos.TenantID,
		"symbol":       pos.Symbol,
		"exit_price":   req.ExitPrice,
		"pnl":          req.PnL,
		"close_reason": req.CloseReason,
		"timestamp":    time.Now().UTC().Format(time.RFC3339Nano),
	})
	s.nats.Publish(subject, payload)
}