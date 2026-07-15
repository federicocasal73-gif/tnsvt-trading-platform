// Package service contiene la lógica de orquestación de ejecuciones.
package service

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"time"

	"github.com/google/uuid"
	"github.com/nats-io/nats.go"
	"github.com/redis/go-redis/v9"

	"github.com/tnsvt/execution-engine/internal/broker"
	"github.com/tnsvt/execution-engine/internal/models"
	"github.com/tnsvt/execution-engine/internal/repository"
)

// Config configuración del execution engine
type Config struct {
	DefaultBroker  models.BrokerName
	DefaultAccount string
	Timeout        time.Duration
	RetryMax       int
	RetryBackoff   time.Duration
}

// ErrNoBroker no hay broker configurado
var ErrNoBroker = errors.New("no broker configured")

// ErrExecutionFailed ejecución falló
var ErrExecutionFailed = errors.New("execution failed")

// ErrInvalidSignal señal inválida
var ErrInvalidSignal = errors.New("invalid signal")

// ExecutionService es el orquestador principal
type ExecutionService struct {
	repo            repository.ExecutionRepository
	redis           *redis.Client
	nats            *nats.Conn
	brokerFactory   *broker.Factory
	riskEngineURL   string
	config          Config
	log             interface {
		Info(string, ...any)
		Warn(string, ...any)
		Error(string, error, ...any)
	}
	httpClient      *http.Client
}

// NewExecutionService crea el service
func NewExecutionService(
	repo repository.ExecutionRepository,
	redis *redis.Client,
	nats *nats.Conn,
	brokerFactory *broker.Factory,
	riskEngineURL string,
	log interface {
		Info(string, ...any)
		Warn(string, ...any)
		Error(string, error, ...any)
	},
	cfg Config,
) *ExecutionService {
	if cfg.Timeout == 0 {
		cfg.Timeout = 30 * time.Second
	}
	return &ExecutionService{
		repo:          repo,
		redis:         redis,
		nats:          nats,
		brokerFactory: brokerFactory,
		riskEngineURL: riskEngineURL,
		config:        cfg,
		log:           log,
		httpClient: &http.Client{
			Timeout: cfg.Timeout,
		},
	}
}

// ─── Execute Signal (orquestador principal) ────────────────────

// ExecuteSignal toma una señal validada y la ejecuta
func (s *ExecutionService) ExecuteSignal(ctx context.Context, signal *models.SignalInput) (*models.Execution, error) {
	if signal.Symbol == "" || signal.Action == "" {
		return nil, ErrInvalidSignal
	}

	// Determinar broker y account
	brokerName := s.config.DefaultBroker
	accountID := s.config.DefaultAccount

	if signal.Symbol != "" && signal.Action == "CLOSE" {
		return s.executeClose(ctx, signal)
	}

	// Determinar side
	side := models.SideBuy
	if signal.Action == "SELL" {
		side = models.SideSell
	}

	// Determinar lot size (recomendado por risk o el original)
	lotSize := 0.0
	if signal.RecommendedLotSize != nil && *signal.RecommendedLotSize > 0 {
		lotSize = *signal.RecommendedLotSize
	} else if signal.LotSize != nil {
		lotSize = *signal.LotSize
	}

	if lotSize <= 0 {
		lotSize = 0.01 // default
	}

	// Determinar TP (primer TP)
	var tp *float64
	if len(signal.TakeProfits) > 0 {
		tp = &signal.TakeProfits[0]
	}

	// ─── Crear Execution (status=pending) ──────────────────────
	execution := &models.Execution{
		ID:         uuid.New(),
		TenantID:   signal.TenantID,
		SignalID:   signal.ID,
		UserID:     signal.UserID,
		Broker:     brokerName,
		AccountID:  accountID,
		Symbol:     signal.Symbol,
		Side:       side,
		OrderType:  models.OrderMarket,
		Quantity:   lotSize,
		Price:      signal.EntryPrice,
		StopLoss:   signal.StopLoss,
		TakeProfit: tp,
		TakeProfits: signal.TakeProfits,
		Status:     models.ExecStatusPending,
		RiskLevel:  signal.RiskLevel,
	}

	if err := s.repo.Create(ctx, execution); err != nil {
		return nil, fmt.Errorf("create execution: %w", err)
	}

	// ─── Place order via broker connector ───────────────────
	connector, ok := s.brokerFactory.Get(brokerName)
	if !ok {
		s.failExecution(ctx, execution, fmt.Sprintf("no connector for broker %s", brokerName))
		return execution, ErrNoBroker
	}

	// Check broker health
	if err := connector.HealthCheck(ctx); err != nil {
		s.failExecution(ctx, execution, fmt.Sprintf("broker health check failed: %v", err))
		return execution, fmt.Errorf("broker unhealthy: %w", err)
	}

	execution.Status = models.ExecStatusRouted
	execution.SubmittedAt = timePtr(time.Now())
	s.repo.Update(ctx, execution)

	orderReq := &broker.OrderRequest{
		SignalID:    signal.ID,
		AccountID:   accountID,
		Symbol:      signal.Symbol,
		Side:        side,
		OrderType:   models.OrderMarket,
		Quantity:    lotSize,
		Price:       signal.EntryPrice,
		StopLoss:    signal.StopLoss,
		TakeProfit:  tp,
		Comment:     fmt.Sprintf("TNSVT signal %s", signal.ID.String()),
		MagicNumber: 123456,
	}

	// Retry logic
	var lastErr error
	for attempt := 0; attempt <= s.config.RetryMax; attempt++ {
		if attempt > 0 {
			time.Sleep(s.config.RetryBackoff)
			execution.RetryCount = attempt
			s.log.Info("Retrying execution", "execution_id", execution.ID, "attempt", attempt+1)
		}

		orderResp, err := connector.PlaceOrder(ctx, orderReq)
		if err != nil {
			lastErr = err
			s.log.Warn("Place order failed", "attempt", attempt+1, "error", err.Error())
			continue
		}

		if !orderResp.Accepted {
			lastErr = fmt.Errorf("order rejected by broker: %s", orderResp.ErrorMessage)
			s.log.Warn("Order rejected", "attempt", attempt+1, "reason", orderResp.ErrorMessage)
			continue
		}

		// ─── Order filled ─────────────────────────────────────
		execution.Status = models.ExecStatusFilled
		execution.OrderID = orderResp.OrderID
		execution.Ticket = orderResp.Ticket
		execution.FilledPrice = &orderResp.FilledPrice
		execution.FilledQty = &orderResp.FilledQty
		execution.Commission = orderResp.Commission
		now := time.Now()
		execution.FilledAt = &now
		execution.CompletedAt = &now

		if err := s.repo.Update(ctx, execution); err != nil {
			s.log.Error("Failed to update execution after fill", err)
		}

		s.log.Info("Order filled",
			"execution_id", execution.ID,
			"symbol", execution.Symbol,
			"side", execution.Side,
			"quantity", execution.Quantity,
			"price", orderResp.FilledPrice,
			"ticket", orderResp.Ticket)

		// ─── Notify risk-engine (register position) ───────────
		positionID, err := s.notifyRiskOpened(ctx, execution, orderResp)
		if err != nil {
			s.log.Warn("Failed to notify risk-engine of opened position", "error", err.Error())
		} else {
			execution.PositionID = &positionID
			s.repo.Update(ctx, execution)
		}

		// ─── Publish NATS event ───────────────────────────────
		s.publishEvent(ctx, "executed", execution)

		return execution, nil
	}

	// All retries failed
	s.failExecution(ctx, execution, lastErr.Error())
	return execution, ErrExecutionFailed
}

// executeClose maneja cierres de posición
func (s *ExecutionService) executeClose(ctx context.Context, signal *models.SignalInput) (*models.Execution, error) {
	execution := &models.Execution{
		ID:        uuid.New(),
		TenantID:  signal.TenantID,
		SignalID:  signal.ID,
		UserID:    signal.UserID,
		Broker:    s.config.DefaultBroker,
		AccountID: s.config.DefaultAccount,
		Symbol:    signal.Symbol,
		Side:      models.SideSell, // placeholder
		OrderType: models.OrderMarket,
		Quantity:  0, // will be derived from position
		Status:    models.ExecStatusPending,
	}

	if err := s.repo.Create(ctx, execution); err != nil {
		return nil, err
	}

	// Get current positions from broker
	connector, ok := s.brokerFactory.Get(execution.Broker)
	if !ok {
		s.failExecution(ctx, execution, "no broker connector")
		return execution, ErrNoBroker
	}

	positions, err := connector.GetPositions(ctx, execution.AccountID)
	if err != nil {
		s.failExecution(ctx, execution, err.Error())
		return execution, err
	}

	// Find matching positions
	closed := 0
	for _, pos := range positions {
		if pos.Symbol != execution.Symbol {
			continue
		}
		closeResp, err := connector.ClosePosition(ctx, execution.AccountID, pos.Ticket)
		if err != nil {
			s.log.Warn("Failed to close position", "ticket", pos.Ticket, "error", err.Error())
			continue
		}
		if closeResp.Closed {
			closed++
			// Notify risk-engine
			s.notifyRiskClosed(ctx, signal.TenantID, pos.Ticket, closeResp.ExitPrice, closeResp.PnL, "signal")
		}
	}

	execution.Status = models.ExecStatusFilled
	now := time.Now()
	execution.CompletedAt = &now
	s.repo.Update(ctx, execution)

	s.log.Info("Closed positions via signal", "symbol", execution.Symbol, "count", closed)
	s.publishEvent(ctx, "executed", execution)

	return execution, nil
}

// failExecution marca la ejecución como fallida
func (s *ExecutionService) failExecution(ctx context.Context, e *models.Execution, errMsg string) {
	e.Status = models.ExecStatusFailed
	e.ErrorMessage = errMsg
	now := time.Now()
	e.CompletedAt = &now
	if err := s.repo.Update(ctx, e); err != nil {
		s.log.Error("Failed to update execution status", err)
	}
	s.log.Warn("Execution failed", "execution_id", e.ID, "error", errMsg)
	s.publishEvent(ctx, "failed", e)
}

// ─── Trade Monitor (detecta cierres por SL/TP) ─────────────────

// RunTradeMonitor corre cada N segundos y verifica posiciones abiertas
func (s *ExecutionService) RunTradeMonitor(ctx context.Context, interval time.Duration, brokerFactory *broker.Factory) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			s.checkOpenPositions(ctx, brokerFactory)
		}
	}
}

func (s *ExecutionService) checkOpenPositions(ctx context.Context, brokerFactory *broker.Factory) {
	// Obtener executions filled (asumimos un solo tenant por ahora en Fase 1)
	tenantID := uuid.MustParse("00000000-0000-0000-0000-000000000001")
	executions, err := s.repo.GetFilledExecutions(ctx, tenantID)
	if err != nil {
		return
	}

	connector, ok := brokerFactory.Get(s.config.DefaultBroker)
	if !ok {
		return
	}

	// Get current positions from broker
	positions, err := connector.GetPositions(ctx, s.config.DefaultAccount)
	if err != nil {
		s.log.Warn("Failed to get positions in monitor", "error", err.Error())
		return
	}

	// Build set of open tickets
	openTickets := make(map[string]bool)
	for _, pos := range positions {
		openTickets[pos.Ticket] = true
	}

	// Find executions that were filled but no longer open
	for _, exec := range executions {
		if exec.Ticket == "" || exec.Status != models.ExecStatusFilled {
			continue
		}

		// If ticket no longer open → trade was closed
		if !openTickets[exec.Ticket] {
			s.handleTradeClosed(ctx, exec)
		}
	}
}

func (s *ExecutionService) handleTradeClosed(ctx context.Context, exec *models.Execution) {
	// Determine close reason by checking final state
	// (Fase 1: simplified — just mark as closed)
	// En Fase 2: consultar deal history para saber si fue TP/SL/manual

	closeReason := "unknown"
	exitPrice := 0.0
	pnl := 0.0

	if exec.FilledPrice != nil {
		// Best effort: use filled price as exit (Fase 2 mejor)
		exitPrice = *exec.FilledPrice
	}

	// Notify risk-engine
	if exec.TenantID != uuid.Nil {
		if err := s.notifyRiskClosed(ctx, exec.TenantID, exec.Ticket, exitPrice, pnl, closeReason); err != nil {
			s.log.Warn("Failed to notify risk-engine of closed trade", "error", err.Error())
		}
	}

	// Update execution status
	exec.Status = models.ExecStatusFilled // sigue siendo filled (filled AND closed)
	exec.CompletedAt = timePtr(time.Now())
	if err := s.repo.Update(ctx, exec); err != nil {
		s.log.Error("Failed to update closed execution", err)
	}

	s.log.Info("Trade closed (detected by monitor)",
		"execution_id", exec.ID,
		"symbol", exec.Symbol,
		"ticket", exec.Ticket)

	// Publish NATS event
	s.publishEvent(ctx, "closed", exec)
}

// ─── Read operations ──────────────────────────────────────────

func (s *ExecutionService) GetByID(ctx context.Context, id uuid.UUID) (*models.Execution, error) {
	return s.repo.GetByID(ctx, id)
}

func (s *ExecutionService) List(ctx context.Context, tenantID *uuid.UUID, status *models.ExecutionStatus, broker *models.BrokerName, limit, offset int) ([]*models.Execution, int64, error) {
	return s.repo.List(ctx, tenantID, status, broker, limit, offset)
}

func (s *ExecutionService) Cancel(ctx context.Context, id uuid.UUID, reason string) (*models.Execution, error) {
	exec, err := s.repo.GetByID(ctx, id)
	if err != nil {
		return nil, err
	}

	if exec.Status != models.ExecStatusPending && exec.Status != models.ExecStatusRouted {
		return nil, fmt.Errorf("cannot cancel execution in status %s", exec.Status)
	}

	exec.Status = models.ExecStatusCancelled
	exec.ErrorMessage = reason
	now := time.Now()
	exec.CompletedAt = &now

	if err := s.repo.Update(ctx, exec); err != nil {
		return nil, err
	}

	s.publishEvent(ctx, "cancelled", exec)
	return exec, nil
}

func (s *ExecutionService) Stats(ctx context.Context, tenantID *uuid.UUID) (*models.StatsResponse, error) {
	return s.repo.Stats(ctx, tenantID, time.Now().Add(-7*24*time.Hour))
}

// ─── Risk-Engine Integration ──────────────────────────────────

func (s *ExecutionService) notifyRiskOpened(ctx context.Context, exec *models.Execution, orderResp *broker.OrderResponse) (uuid.UUID, error) {
	if s.riskEngineURL == "" {
		return uuid.Nil, nil
	}

	tpSide := "tp1"
	if exec.TakeProfit != nil && len(exec.TakeProfits) > 1 {
		tpSide = "tp1"
	}

	payload := map[string]any{
		"signal_id":   exec.SignalID.String(),
		"broker":      string(exec.Broker),
		"account_id":  exec.AccountID,
		"ticket":      orderResp.Ticket,
		"symbol":      exec.Symbol,
		"side":        string(exec.Side),
		"quantity":    exec.Quantity,
		"entry_price": orderResp.FilledPrice,
		"stop_loss":   derefFloat(exec.StopLoss),
		"take_profit": derefFloat(exec.TakeProfit),
		"tp_side":     tpSide,
	}

	body, _ := json.Marshal(payload)
	url := s.riskEngineURL + "/api/v1/risk/trade-opened"

	req, _ := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	if exec.TenantID != uuid.Nil {
		req.Header.Set("X-Tenant-ID", exec.TenantID.String())
	}

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return uuid.Nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 300 {
		return uuid.Nil, fmt.Errorf("risk-engine returned %d", resp.StatusCode)
	}

	var riskResp struct {
		ID uuid.UUID `json:"id"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&riskResp); err != nil {
		return uuid.Nil, err
	}

	return riskResp.ID, nil
}

func (s *ExecutionService) notifyRiskClosed(ctx context.Context, tenantID uuid.UUID, ticket string, exitPrice, pnl float64, closeReason string) error {
	if s.riskEngineURL == "" {
		return nil
	}

	payload := map[string]any{
		"ticket":       ticket,
		"exit_price":   exitPrice,
		"pnl":          pnl,
		"close_reason": closeReason,
	}

	body, _ := json.Marshal(payload)
	url := s.riskEngineURL + "/api/v1/risk/trade-closed"

	req, _ := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Tenant-ID", tenantID.String())

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 300 {
		return fmt.Errorf("risk-engine returned %d", resp.StatusCode)
	}

	return nil
}

// ─── NATS Publishing ──────────────────────────────────────────

func (s *ExecutionService) publishEvent(ctx context.Context, eventType string, e *models.Execution) {
	if s.nats == nil {
		return
	}

	subject := fmt.Sprintf("trading.execution.%s", eventType)
	payload, _ := json.Marshal(map[string]any{
		"execution_id": e.ID,
		"signal_id":    e.SignalID,
		"tenant_id":    e.TenantID,
		"broker":       e.Broker,
		"account_id":   e.AccountID,
		"symbol":       e.Symbol,
		"side":         e.Side,
		"quantity":     e.Quantity,
		"filled_price": e.FilledPrice,
		"ticket":       e.Ticket,
		"order_id":     e.OrderID,
		"status":       e.Status,
		"risk_level":   e.RiskLevel,
		"timestamp":    time.Now().UTC().Format(time.RFC3339Nano),
		"event":        eventType,
	})

	if err := s.nats.Publish(subject, payload); err != nil {
		s.log.Warn("NATS publish failed", "subject", subject, "error", err.Error())
	}
}

// ─── Helpers ───────────────────────────────────────────────────

func timePtr(t time.Time) *time.Time {
	return &t
}

func derefFloat(p *float64) float64 {
	if p == nil {
		return 0
	}
	return *p
}