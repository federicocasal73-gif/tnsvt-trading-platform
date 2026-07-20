// Package service contiene la lógica de replicación multi-cuenta.
package service

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/nats-io/nats.go"
	"github.com/redis/go-redis/v9"

	"github.com/tnsvt/copy-trading/internal/models"
	"github.com/tnsvt/copy-trading/internal/repository"
)

// Config configuración del copy-trading
type Config struct {
	MaxAccountsPerGroup int
	Timeout             time.Duration
}

// CopyTradingService lógica principal
type CopyTradingService struct {
	repo              repository.CopyTradingRepository
	redis             *redis.Client
	nats              *nats.Conn
	executionEngineURL string
	config            Config
	log               interface {
		Info(string, ...any)
		Warn(string, ...any)
		Error(string, error, ...any)
	}
	httpClient        *http.Client
}

// NewCopyTradingService crea el service
func NewCopyTradingService(
	repo repository.CopyTradingRepository,
	redis *redis.Client,
	nats *nats.Conn,
	executionEngineURL string,
	log interface {
		Info(string, ...any)
		Warn(string, ...any)
		Error(string, error, ...any)
	},
	config Config,
) *CopyTradingService {
	if config.MaxAccountsPerGroup <= 0 {
		config.MaxAccountsPerGroup = 20
	}
	if config.Timeout == 0 {
		config.Timeout = 60 * time.Second
	}
	return &CopyTradingService{
		repo:               repo,
		redis:              redis,
		nats:               nats,
		executionEngineURL: executionEngineURL,
		config:             config,
		log:                log,
		httpClient: &http.Client{
			Timeout: config.Timeout,
		},
	}
}

// ─── Replication Engine ───────────────────────────────────────

// ReplicateSignal toma una señal y la replica a todos los grupos/cuentas configuradas
func (s *CopyTradingService) ReplicateSignal(ctx context.Context, signal *models.SignalInput) error {
	if signal.TenantID == uuid.Nil {
		return fmt.Errorf("signal missing tenant_id")
	}

	// 1. Buscar grupos enabled para este tenant
	groups, err := s.repo.ListEnabledGroupsForTenant(ctx, signal.TenantID)
	if err != nil {
		return fmt.Errorf("list groups: %w", err)
	}

	if len(groups) == 0 {
		s.log.Info("No copy groups enabled for tenant", "tenant_id", signal.TenantID)
		return nil
	}

	// 2. Para cada grupo, verificar filtros
	matchedGroups := 0
	totalAccounts := 0
	for _, group := range groups {
		if !s.groupMatches(group, signal) {
			s.log.Info("Group filter mismatch", "group", group.Name, "symbol", signal.Symbol, "action", signal.Action)
			continue
		}

		// 3. Listar cuentas enabled del grupo
		accounts, err := s.repo.ListEnabledAccountsByGroup(ctx, group.ID)
		if err != nil {
			s.log.Error("Failed to list accounts", err, "group", group.Name)
			continue
		}

		if len(accounts) == 0 {
			continue
		}

		if len(accounts) > s.config.MaxAccountsPerGroup {
			s.log.Warn("Group has too many accounts, skipping",
				"group", group.Name,
				"count", len(accounts),
				"max", s.config.MaxAccountsPerGroup)
			continue
		}

		matchedGroups++
		totalAccounts += len(accounts)

		// 4. Replicar a cada cuenta del grupo en paralelo
		s.replicateToGroup(ctx, signal, group, accounts)
	}

	if matchedGroups > 0 {
		s.log.Info("Signal replicated",
			"signal_id", signal.ID,
			"tenant_id", signal.TenantID,
			"groups_matched", matchedGroups,
			"total_accounts", totalAccounts)
	}

	return nil
}

// groupMatches verifica si un grupo pasa los filtros de symbol/action/confidence
func (s *CopyTradingService) groupMatches(group *models.CopyGroup, signal *models.SignalInput) bool {
	// Filter symbols (si está configurado)
	if len(group.Symbols) > 0 {
		matched := false
		for _, sym := range group.Symbols {
			if sym == signal.Symbol {
				matched = true
				break
			}
		}
		if !matched {
			return false
		}
	}

	// Filter actions
	if len(group.Actions) > 0 {
		matched := false
		for _, act := range group.Actions {
			if act == signal.Action {
				matched = true
				break
			}
		}
		if !matched {
			return false
		}
	}

	// Filter confidence
	if group.MinConfidence > 0 && signal.Confidence < group.MinConfidence {
		return false
	}

	return true
}

// replicateToGroup ejecuta la señal en paralelo para todas las cuentas del grupo
func (s *CopyTradingService) replicateToGroup(ctx context.Context, signal *models.SignalInput, group *models.CopyGroup, accounts []*models.CopyAccount) {
	var wg sync.WaitGroup
	results := make([]*models.CopyJob, len(accounts))

	for i, account := range accounts {
		wg.Add(1)
		go func(idx int, acc *models.CopyAccount) {
			defer wg.Done()
			job := s.executeForAccount(ctx, signal, group, acc)
			results[idx] = job
		}(i, account)
	}

	wg.Wait()

	// Aggregate results
	successCount := 0
	failedCount := 0
	for _, job := range results {
		if job == nil {
			continue
		}
		if job.Status == models.JobSuccess {
			successCount++
		} else if job.Status == models.JobFailed {
			failedCount++
		}
	}

	// Publish aggregate event
	s.publishGroupResult(signal, group, successCount, failedCount)
}

// executeForAccount ejecuta la señal en UNA cuenta con su config propia
func (s *CopyTradingService) executeForAccount(ctx context.Context, signal *models.SignalInput, group *models.CopyGroup, account *models.CopyAccount) *models.CopyJob {
	start := time.Now()

	job := &models.CopyJob{
		ID:             uuid.New(),
		TenantID:       signal.TenantID,
		GroupID:        group.ID,
		AccountID:      account.ID,
		SignalID:       signal.ID,
		Symbol:         signal.Symbol,
		Action:         signal.Action,
		OriginalLotSize: derefFloat(signal.LotSize),
		Status:         models.JobPending,
	}

	if signal.EntryPrice != nil {
		job.EntryPrice = *signal.EntryPrice
	}
	if signal.StopLoss != nil {
		job.StopLoss = *signal.StopLoss
	}
	if len(signal.TakeProfits) > 0 {
		job.TakeProfit = signal.TakeProfits[0]
	}

	// Calcular config aplicada a esta cuenta
	applied := s.applyAccountConfig(signal, account)
	job.AppliedLotSize = applied.LotSize
	job.AppliedSL = applied.SL
	job.AppliedTP = applied.TP
	job.AppliedSide = applied.Side
	job.AppliedSymbol = applied.Symbol

	// Persistir el job (pending)
	if err := s.repo.CreateJob(ctx, job); err != nil {
		s.log.Error("Failed to create job", err, "account", account.Name)
		return job
	}

	// Marcar como running
	now := time.Now()
	job.Status = models.JobRunning
	job.StartedAt = &now
	s.repo.UpdateJob(ctx, job)

	// Ejecutar vía execution-engine
	execReq := map[string]any{
		"signal": map[string]any{
			"id":            signal.ID.String(),
			"tenant_id":      signal.TenantID.String(),
			"source":         signal.Source,
			"symbol":         applied.Symbol,
			"action":         applied.Side,
			"entry_price":    signal.EntryPrice,
			"stop_loss":      applied.SL,
			"take_profits":   []float64{applied.TP},
			"lot_size":       applied.LotSize,
			"lot_mode":       signal.LotMode,
			"risk_percent":   applied.RiskPercent,
			"confidence":     signal.Confidence,
			"hash":           signal.Hash + ":" + account.ID.String(), // dedup per-account
			"recommended_lot_size": applied.LotSize,
			"risk_level":     signal.RiskLevel,
		},
		"broker":    account.Broker,
		"account_id": account.AccountID,
	}

	body, _ := json.Marshal(execReq)
	url := s.executionEngineURL + "/api/v1/executions"

	req, _ := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Tenant-ID", signal.TenantID.String())
	req.Header.Set("X-Account-ID", account.AccountID)

	resp, err := s.httpClient.Do(req)
	if err != nil {
		s.failJob(ctx, job, fmt.Sprintf("execution-engine request: %v", err), start)
		return job
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		var errBody struct {
			Error string `json:"error"`
			Details string `json:"details"`
		}
		json.NewDecoder(resp.Body).Decode(&errBody)
		s.failJob(ctx, job, fmt.Sprintf("execution-engine HTTP %d: %s", resp.StatusCode, errBody.Details), start)
		return job
	}

	var execResp struct {
		ID         uuid.UUID `json:"id"`
		Status     string    `json:"status"`
		ErrorMessage string `json:"error_message"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&execResp); err != nil {
		s.failJob(ctx, job, fmt.Sprintf("decode response: %v", err), start)
		return job
	}

	if execResp.Status == "failed" || execResp.Status == "rejected" {
		s.failJob(ctx, job, fmt.Sprintf("execution-engine reported %s: %s", execResp.Status, execResp.ErrorMessage), start)
		return job
	}

	// Success
	execID := execResp.ID
	job.Status = models.JobSuccess
	job.ExecutionID = &execID
	now = time.Now()
	job.CompletedAt = &now
	job.DurationMs = time.Since(start).Milliseconds()
	s.repo.UpdateJob(ctx, job)

	// Update account stats
	s.updateAccountStats(ctx, account.ID)

	s.log.Info("Replicated to account",
		"signal_id", signal.ID,
		"account", account.Name,
		"lot_size", applied.LotSize,
		"execution_id", execID,
		"duration_ms", job.DurationMs)

	return job
}

// AppliedConfig configuración aplicada a una cuenta
type AppliedConfig struct {
	LotSize     float64
	SL          float64
	TP          float64
	Side        string
	Symbol      string
	RiskPercent *float64
}

// applyAccountConfig calcula lot/SL/TP/side/symbol específicos para esta cuenta
func (s *CopyTradingService) applyAccountConfig(signal *models.SignalInput, account *models.CopyAccount) AppliedConfig {
	config := AppliedConfig{
		Side:   signal.Action,
		Symbol: signal.Symbol,
	}

	// ─── Symbol suffix ────────────────────────────────────────
	if account.SymbolSuffix != "" {
		base := stripSuffix(signal.Symbol)
		config.Symbol = base + account.SymbolSuffix
	}

	// ─── Invert side ──────────────────────────────────────────
	if account.InvertSide {
		if signal.Action == "BUY" {
			config.Side = "SELL"
		} else if signal.Action == "SELL" {
			config.Side = "BUY"
		}
	}

	// ─── Lot size ────────────────────────────────────────────
	switch account.LotMode {
	case models.LotModeFixed:
		if account.LotSize != nil {
			config.LotSize = *account.LotSize
		} else if signal.LotSize != nil {
			config.LotSize = *signal.LotSize
		} else {
			config.LotSize = 0.01
		}

	case models.LotModeProportional:
		originalLot := derefFloat(signal.LotSize)
		if originalLot <= 0 {
			originalLot = 0.01
		}
		config.LotSize = roundToStep(originalLot * account.LotMultiplier, 0.01)

	case models.LotModeRiskBased:
		config.LotSize = derefFloat(signal.LotSize) // riesgo viene del signal original
		if account.RiskPercent != nil {
			config.RiskPercent = account.RiskPercent
		}
	}

	// ─── SL/TP override ──────────────────────────────────────
	if signal.EntryPrice != nil {
		entry := *signal.EntryPrice
		pip := pipValue(signal.Symbol)

		// SL
		if account.OverrideSL && account.SLPips > 0 {
			pips := account.SLPips
			if config.Side == "BUY" {
				config.SL = entry - (pips * pip)
			} else {
				config.SL = entry + (pips * pip)
			}
		} else if signal.StopLoss != nil {
			config.SL = *signal.StopLoss
		}

		// TP
		if account.OverrideTP && account.TPPips > 0 {
			pips := account.TPPips
			if config.Side == "BUY" {
				config.TP = entry + (pips * pip)
			} else {
				config.TP = entry - (pips * pip)
			}
		} else if len(signal.TakeProfits) > 0 {
			config.TP = signal.TakeProfits[0]
		}
	}

	return config
}

func (s *CopyTradingService) failJob(ctx context.Context, job *models.CopyJob, errMsg string, start time.Time) {
	job.Status = models.JobFailed
	job.ErrorMessage = errMsg
	now := time.Now()
	job.CompletedAt = &now
	job.DurationMs = time.Since(start).Milliseconds()
	if err := s.repo.UpdateJob(ctx, job); err != nil {
		s.log.Error("Failed to update job", err)
	}
	s.log.Warn("Replication failed", "account_id", job.AccountID, "signal_id", job.SignalID, "error", errMsg)
}

func (s *CopyTradingService) updateAccountStats(ctx context.Context, accountID uuid.UUID) {
	// En Fase 2: implementar UPDATE con stats aggregation
}

// ─── Group CRUD ───────────────────────────────────────────────

func (s *CopyTradingService) CreateGroup(ctx context.Context, tenantID uuid.UUID, req *models.CreateGroupRequest) (*models.CopyGroup, error) {
	enabled := true
	if req.Enabled != nil {
		enabled = *req.Enabled
	}

	g := &models.CopyGroup{
		TenantID:      tenantID,
		Name:          req.Name,
		Description:   req.Description,
		Enabled:       enabled,
		Symbols:       req.Symbols,
		Actions:       req.Actions,
		MinConfidence: req.MinConfidence,
	}

	if err := s.repo.CreateGroup(ctx, g); err != nil {
		return nil, err
	}

	return g, nil
}

func (s *CopyTradingService) UpdateGroup(ctx context.Context, id uuid.UUID, req *models.UpdateGroupRequest) (*models.CopyGroup, error) {
	g, err := s.repo.GetGroup(ctx, id)
	if err != nil {
		return nil, err
	}

	if req.Name != nil {
		g.Name = *req.Name
	}
	if req.Description != nil {
		g.Description = *req.Description
	}
	if req.Enabled != nil {
		g.Enabled = *req.Enabled
	}
	if req.Symbols != nil {
		g.Symbols = *req.Symbols
	}
	if req.Actions != nil {
		g.Actions = *req.Actions
	}
	if req.MinConfidence != nil {
		g.MinConfidence = *req.MinConfidence
	}

	if err := s.repo.UpdateGroup(ctx, g); err != nil {
		return nil, err
	}

	return g, nil
}

func (s *CopyTradingService) DeleteGroup(ctx context.Context, id uuid.UUID) error {
	return s.repo.DeleteGroup(ctx, id)
}

func (s *CopyTradingService) GetGroup(ctx context.Context, id uuid.UUID) (*models.CopyGroup, error) {
	return s.repo.GetGroup(ctx, id)
}

func (s *CopyTradingService) ListGroups(ctx context.Context, tenantID uuid.UUID, limit, offset int) ([]*models.CopyGroup, int64, error) {
	return s.repo.ListGroups(ctx, tenantID, limit, offset)
}

// ─── Account CRUD ─────────────────────────────────────────────

func (s *CopyTradingService) CreateAccount(ctx context.Context, tenantID, groupID uuid.UUID, req *models.CreateAccountRequest) (*models.CopyAccount, error) {
	enabled := true
	if req.Enabled != nil {
		enabled = *req.Enabled
	}

	overrideSL := false
	if req.OverrideSL != nil {
		overrideSL = *req.OverrideSL
	}
	overrideTP := false
	if req.OverrideTP != nil {
		overrideTP = *req.OverrideTP
	}
	invertSide := false
	if req.InvertSide != nil {
		invertSide = *req.InvertSide
	}

	a := &models.CopyAccount{
		GroupID:      groupID,
		TenantID:     tenantID,
		Name:         req.Name,
		Broker:       req.Broker,
		AccountID:    req.AccountID,
		Enabled:      enabled,
		LotMode:      req.LotMode,
		LotSize:      req.LotSize,
		LotMultiplier: derefFloat(req.LotMultiplier),
		RiskPercent:  req.RiskPercent,
		OverrideSL:   overrideSL,
		SLPips:       derefFloat(req.SLPips),
		OverrideTP:   overrideTP,
		TPPips:       derefFloat(req.TPPips),
		InvertSide:   invertSide,
		SymbolSuffix: req.SymbolSuffix,
	}

	if a.LotMode == "" {
		a.LotMode = models.LotModeFixed
	}
	if a.LotMultiplier == 0 {
		a.LotMultiplier = 1.0
	}

	if err := s.repo.CreateAccount(ctx, a); err != nil {
		return nil, err
	}

	return a, nil
}

func (s *CopyTradingService) UpdateAccount(ctx context.Context, id uuid.UUID, req *models.UpdateAccountRequest) (*models.CopyAccount, error) {
	a, err := s.repo.GetAccount(ctx, id)
	if err != nil {
		return nil, err
	}

	if req.Name != nil {
		a.Name = *req.Name
	}
	if req.Enabled != nil {
		a.Enabled = *req.Enabled
	}
	if req.LotMode != nil {
		a.LotMode = *req.LotMode
	}
	if req.LotSize != nil {
		a.LotSize = req.LotSize
	}
	if req.LotMultiplier != nil {
		a.LotMultiplier = *req.LotMultiplier
	}
	if req.RiskPercent != nil {
		a.RiskPercent = req.RiskPercent
	}
	if req.OverrideSL != nil {
		a.OverrideSL = *req.OverrideSL
	}
	if req.SLPips != nil {
		a.SLPips = *req.SLPips
	}
	if req.OverrideTP != nil {
		a.OverrideTP = *req.OverrideTP
	}
	if req.TPPips != nil {
		a.TPPips = *req.TPPips
	}
	if req.InvertSide != nil {
		a.InvertSide = *req.InvertSide
	}
	if req.SymbolSuffix != nil {
		a.SymbolSuffix = *req.SymbolSuffix
	}

	if err := s.repo.UpdateAccount(ctx, a); err != nil {
		return nil, err
	}

	return a, nil
}

func (s *CopyTradingService) DeleteAccount(ctx context.Context, id uuid.UUID) error {
	return s.repo.DeleteAccount(ctx, id)
}

func (s *CopyTradingService) GetAccount(ctx context.Context, id uuid.UUID) (*models.CopyAccount, error) {
	return s.repo.GetAccount(ctx, id)
}

func (s *CopyTradingService) ListAccountsByGroup(ctx context.Context, groupID uuid.UUID, limit, offset int) ([]*models.CopyAccount, int64, error) {
	return s.repo.ListAccountsByGroup(ctx, groupID, limit, offset)
}

// ─── Jobs ──────────────────────────────────────────────────────

func (s *CopyTradingService) ListJobs(ctx context.Context, tenantID *uuid.UUID, groupID, accountID *uuid.UUID, status *models.JobStatus, limit, offset int) ([]*models.CopyJob, int64, error) {
	return s.repo.ListJobs(ctx, tenantID, groupID, accountID, status, limit, offset)
}

func (s *CopyTradingService) GetJob(ctx context.Context, id uuid.UUID) (*models.CopyJob, error) {
	return s.repo.GetJob(ctx, id)
}

func (s *CopyTradingService) Stats(ctx context.Context, tenantID *uuid.UUID) (*models.StatsResponse, error) {
	return s.repo.Stats(ctx, tenantID, time.Now().Add(-7*24*time.Hour))
}

// ─── NATS Publishing ──────────────────────────────────────────

func (s *CopyTradingService) publishGroupResult(signal *models.SignalInput, group *models.CopyGroup, success, failed int) {
	if s.nats == nil {
		return
	}

	status := "completed"
	if failed > 0 && success == 0 {
		status = "failed"
	} else if failed > 0 {
		status = "partial"
	}

	subject := "trading.copy." + status
	payload, _ := json.Marshal(map[string]any{
		"signal_id":   signal.ID,
		"group_id":    group.ID,
		"group_name":  group.Name,
		"tenant_id":   signal.TenantID,
		"success":     success,
		"failed":      failed,
		"total":       success + failed,
		"timestamp":   time.Now().UTC().Format(time.RFC3339Nano),
		"event":       status,
	})

	if err := s.nats.Publish(subject, payload); err != nil {
		s.log.Warn("NATS publish failed", "subject", subject, "error", err.Error())
	}
}

// ─── Helpers ───────────────────────────────────────────────────

func derefFloat(p *float64) float64 {
	if p == nil {
		return 0
	}
	return *p
}

func stripSuffix(symbol string) string {
	// Quitar suffixes comunes para evitar duplicación
	for _, suffix := range []string{".m", ".M", ".r", ".R", ".pro", ".raw", ".Raw"} {
		if len(symbol) > len(suffix) && symbol[len(symbol)-len(suffix):] == suffix {
			return symbol[:len(symbol)-len(suffix)]
		}
	}
	return symbol
}

func roundToStep(value, step float64) float64 {
	if step <= 0 {
		return value
	}
	return float64(int(value/step+0.5)) * step
}

func pipValue(symbol string) float64 {
	up := strings.ToUpper(symbol)
	if strings.Contains(up, "JPY") {
		return 0.01
	}
	if strings.HasPrefix(up, "XAU") || strings.HasPrefix(up, "XAG") || strings.Contains(up, "GOLD") || strings.Contains(up, "SILVER") {
		return 0.1
	}
	if strings.HasPrefix(up, "BTC") || strings.HasPrefix(up, "ETH") || strings.Contains(up, "XBT") {
		return 0.01
	}
	if strings.Contains(up, "US30") || strings.Contains(up, "SPX") || strings.Contains(up, "NAS") || strings.Contains(up, "DJI") {
		return 1.0
	}
	if strings.Contains(up, "XTI") || strings.Contains(up, "XBR") || strings.Contains(up, "OIL") {
		return 0.01
	}
	return 0.0001
}

// ErrInvalidSignal señal inválida
var ErrInvalidSignal = errors.New("invalid signal")