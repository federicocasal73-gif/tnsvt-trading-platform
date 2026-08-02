package service

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/tnsvt/execution-engine/internal/broker"
	"github.com/tnsvt/execution-engine/internal/models"
)

type mockRepo struct {
	executions map[uuid.UUID]*models.Execution
	errCreate  error
	errUpdate  error
}

func newMockRepo() *mockRepo {
	return &mockRepo{executions: make(map[uuid.UUID]*models.Execution)}
}

func (m *mockRepo) Create(_ context.Context, e *models.Execution) error {
	if m.errCreate != nil {
		return m.errCreate
	}
	m.executions[e.ID] = e
	return nil
}

func (m *mockRepo) Update(_ context.Context, e *models.Execution) error {
	if m.errUpdate != nil {
		return m.errUpdate
	}
	m.executions[e.ID] = e
	return nil
}

func (m *mockRepo) GetByID(_ context.Context, id uuid.UUID) (*models.Execution, error) {
	e, ok := m.executions[id]
	if !ok {
		return nil, errors.New("not found")
	}
	return e, nil
}

func (m *mockRepo) GetBySignalID(_ context.Context, _ uuid.UUID) (*models.Execution, error) {
	return nil, nil
}

func (m *mockRepo) UpdateStatus(_ context.Context, _ uuid.UUID, _ models.ExecutionStatus, _ string) error {
	return nil
}

func (m *mockRepo) List(_ context.Context, _ *uuid.UUID, _ *models.ExecutionStatus, _ *models.BrokerName, limit, offset int) ([]*models.Execution, int64, error) {
	return nil, 0, nil
}

func (m *mockRepo) GetFilledExecutions(_ context.Context, _ uuid.UUID) ([]*models.Execution, error) {
	var res []*models.Execution
	for _, e := range m.executions {
		if e.Status == models.ExecStatusFilled {
			res = append(res, e)
		}
	}
	return res, nil
}

func (m *mockRepo) Stats(_ context.Context, _ *uuid.UUID, _ time.Time) (*models.StatsResponse, error) {
	return &models.StatsResponse{}, nil
}

func (m *mockRepo) RunMigrations(_ context.Context) error {
	return nil
}

func (m *mockRepo) Ping(_ context.Context) error {
	return nil
}

type mockConnector struct {
	name      models.BrokerName
	placeResp *broker.OrderResponse
	placeErr  error
}

func (m *mockConnector) Name() models.BrokerName {
	return m.name
}

func (m *mockConnector) PlaceOrder(_ context.Context, _ *broker.OrderRequest) (*broker.OrderResponse, error) {
	return m.placeResp, m.placeErr
}

func (m *mockConnector) ClosePosition(_ context.Context, _, _ string) (*broker.CloseResponse, error) {
	return &broker.CloseResponse{Closed: true}, nil
}

func (m *mockConnector) GetAccountInfo(_ context.Context, _ string) (*broker.AccountInfo, error) {
	return nil, nil
}

func (m *mockConnector) GetPositions(_ context.Context, _ string) ([]*broker.Position, error) {
	return nil, nil
}

func (m *mockConnector) HealthCheck(_ context.Context) error {
	return nil
}

type noopLogger struct{}

func (noopLogger) Info(string, ...any)  {}
func (noopLogger) Warn(string, ...any)  {}
func (noopLogger) Error(string, error, ...any) {}

func newTestService(repo *mockRepo, bf *broker.Factory) *ExecutionService {
	cfg := Config{
		DefaultBroker:  models.BrokerMT5,
		DefaultAccount: "test-acc-1",
		Timeout:        5 * time.Second,
		RetryMax:       1,
		RetryBackoff:   10 * time.Millisecond,
	}
	return NewExecutionService(
		repo,
		nil,
		nil,
		bf,
		"",
		noopLogger{},
		cfg,
	)
}

func TestExecuteSignal_InvalidSignal(t *testing.T) {
	s := newTestService(newMockRepo(), broker.NewFactory(noopLogger{}))
	_, err := s.ExecuteSignal(context.Background(), &models.SignalInput{})
	if !errors.Is(err, ErrInvalidSignal) {
		t.Errorf("expected ErrInvalidSignal, got %v", err)
	}
}

func TestExecuteSignal_NoBrokerReturnsErrNoBroker(t *testing.T) {
	repo := newMockRepo()
	bf := broker.NewFactory(noopLogger{})
	s := newTestService(repo, bf)

	signal := &models.SignalInput{
		ID:       uuid.New(),
		TenantID: uuid.New(),
		Symbol:   "XAUUSD",
		Action:   "BUY",
		LotSize:  ptr(0.10),
	}

	exec, err := s.ExecuteSignal(context.Background(), signal)
	if !errors.Is(err, ErrNoBroker) {
		t.Errorf("expected ErrNoBroker, got %v", err)
	}
	if exec.Status != models.ExecStatusFailed {
		t.Errorf("expected status failed, got %s", exec.Status)
	}
}

func TestExecuteSignal_BrokerRejectsOrder(t *testing.T) {
	repo := newMockRepo()
	bf := broker.NewFactory(noopLogger{})
	bf.Register("mt5", &mockConnector{
		name: models.BrokerMT5,
		placeResp: &broker.OrderResponse{
			Accepted:     false,
			ErrorMessage: "insufficient margin",
		},
	})
	s := newTestService(repo, bf)

	signal := &models.SignalInput{
		ID:       uuid.New(),
		TenantID: uuid.New(),
		Symbol:   "XAUUSD",
		Action:   "BUY",
		LotSize:  ptr(0.10),
	}

	exec, err := s.ExecuteSignal(context.Background(), signal)
	if !errors.Is(err, ErrExecutionFailed) {
		t.Errorf("expected ErrExecutionFailed, got %v", err)
	}
	if exec.Status != models.ExecStatusFailed {
		t.Errorf("expected status failed, got %s", exec.Status)
	}
}

func TestExecuteSignal_Success(t *testing.T) {
	repo := newMockRepo()
	bf := broker.NewFactory(noopLogger{})
	bf.Register("mt5", &mockConnector{
		name: models.BrokerMT5,
		placeResp: &broker.OrderResponse{
			OrderID:     "order-123",
			Ticket:      "ticket-456",
			FilledPrice: 4075.00,
			FilledQty:   0.10,
			Commission:  1.50,
			Accepted:    true,
		},
	})
	s := newTestService(repo, bf)

	signal := &models.SignalInput{
		ID:       uuid.New(),
		TenantID: uuid.New(),
		Symbol:   "XAUUSD",
		Action:   "BUY",
		LotSize:  ptr(0.10),
	}

	exec, err := s.ExecuteSignal(context.Background(), signal)
	if err != nil {
		t.Errorf("expected no error, got %v", err)
	}
	if exec.Status != models.ExecStatusFilled {
		t.Errorf("expected status filled, got %s", exec.Status)
	}
	if exec.Ticket != "ticket-456" {
		t.Errorf("expected ticket-456, got %s", exec.Ticket)
	}
	if exec.OrderID != "order-123" {
		t.Errorf("expected order-123, got %s", exec.OrderID)
	}
	if *exec.FilledPrice != 4075.00 {
		t.Errorf("expected filled price 4075.00, got %v", *exec.FilledPrice)
	}
}

func TestExecuteSignal_CloseAction(t *testing.T) {
	repo := newMockRepo()
	bf := broker.NewFactory(noopLogger{})
	bf.Register("mt5", &mockConnector{
		name: models.BrokerMT5,
	})
	s := newTestService(repo, bf)

	signal := &models.SignalInput{
		ID:       uuid.New(),
		TenantID: uuid.New(),
		Symbol:   "XAUUSD",
		Action:   "CLOSE",
	}

	exec, err := s.ExecuteSignal(context.Background(), signal)
	if err != nil {
		t.Errorf("expected no error for CLOSE, got %v", err)
	}
	if exec.Status != models.ExecStatusFilled {
		t.Errorf("expected status filled for CLOSE, got %s", exec.Status)
	}
}

func TestExecuteSignal_UsesRecommendedLotSize(t *testing.T) {
	repo := newMockRepo()
	bf := broker.NewFactory(noopLogger{})
	bf.Register("mt5", &mockConnector{
		name: models.BrokerMT5,
		placeResp: &broker.OrderResponse{
			Accepted:    true,
			FilledPrice: 100.0,
			FilledQty:   0.50,
		},
	})
	s := newTestService(repo, bf)

	signal := &models.SignalInput{
		ID:                 uuid.New(),
		TenantID:           uuid.New(),
		Symbol:             "EURUSD",
		Action:             "SELL",
		LotSize:            ptr(1.00),
		RecommendedLotSize: ptr(0.50),
	}

	exec, err := s.ExecuteSignal(context.Background(), signal)
	if err != nil {
		t.Errorf("expected no error, got %v", err)
	}
	if exec.Quantity != 0.50 {
		t.Errorf("expected quantity 0.50 (recommended), got %v", exec.Quantity)
	}
}

func TestExecuteSignal_DefaultLotSizeZero(t *testing.T) {
	repo := newMockRepo()
	bf := broker.NewFactory(noopLogger{})
	bf.Register("mt5", &mockConnector{
		name: models.BrokerMT5,
		placeResp: &broker.OrderResponse{
			Accepted:    true,
			FilledPrice: 100.0,
			FilledQty:   0.01,
		},
	})
	s := newTestService(repo, bf)

	signal := &models.SignalInput{
		ID:       uuid.New(),
		TenantID: uuid.New(),
		Symbol:   "EURUSD",
		Action:   "BUY",
	}

	exec, err := s.ExecuteSignal(context.Background(), signal)
	if err != nil {
		t.Errorf("expected no error, got %v", err)
	}
	if exec.Quantity != 0.01 {
		t.Errorf("expected default quantity 0.01, got %v", exec.Quantity)
	}
}

func TestCancelExecution_PendingOK(t *testing.T) {
	repo := newMockRepo()
	bf := broker.NewFactory(noopLogger{})
	s := newTestService(repo, bf)

	exec := &models.Execution{
		ID:       uuid.New(),
		TenantID: uuid.New(),
		Symbol:   "XAUUSD",
		Side:     models.SideBuy,
		Status:   models.ExecStatusPending,
	}
	repo.executions[exec.ID] = exec

	cancelled, err := s.Cancel(context.Background(), exec.ID, "manual cancel")
	if err != nil {
		t.Errorf("expected no error, got %v", err)
	}
	if cancelled.Status != models.ExecStatusCancelled {
		t.Errorf("expected status cancelled, got %s", cancelled.Status)
	}
}

func TestCancelExecution_FilledRejected(t *testing.T) {
	repo := newMockRepo()
	bf := broker.NewFactory(noopLogger{})
	s := newTestService(repo, bf)

	exec := &models.Execution{
		ID:       uuid.New(),
		TenantID: uuid.New(),
		Symbol:   "XAUUSD",
		Side:     models.SideBuy,
		Status:   models.ExecStatusFilled,
	}
	repo.executions[exec.ID] = exec

	_, err := s.Cancel(context.Background(), exec.ID, "too late")
	if err == nil {
		t.Error("expected error cancelling filled execution")
	}
}

func TestGetByID(t *testing.T) {
	repo := newMockRepo()
	bf := broker.NewFactory(noopLogger{})
	s := newTestService(repo, bf)

	exec := &models.Execution{
		ID:       uuid.New(),
		TenantID: uuid.New(),
		Symbol:   "XAUUSD",
		Side:     models.SideBuy,
		Status:   models.ExecStatusFilled,
	}
	repo.executions[exec.ID] = exec

	got, err := s.GetByID(context.Background(), exec.ID)
	if err != nil {
		t.Errorf("expected no error, got %v", err)
	}
	if got.ID != exec.ID {
		t.Errorf("expected id %v, got %v", exec.ID, got.ID)
	}
}

func ptr(v float64) *float64 {
	return &v
}
