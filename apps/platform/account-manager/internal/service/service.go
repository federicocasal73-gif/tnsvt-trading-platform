// Package service contiene la lógica de negocio del account-manager.
package service

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"

	"github.com/tnsvt/account-manager/internal/cipher"
	"github.com/tnsvt/account-manager/internal/models"
	"github.com/tnsvt/account-manager/internal/repository"
)

// Service errores
var (
	ErrAlreadyExists  = errors.New("account already exists for this tenant/login/server")
	ErrNotFound       = errors.New("account not found")
	ErrEmptyLogin     = errors.New("login is required")
	ErrEmptyServer    = errors.New("server is required")
	ErrEmptyPassword  = errors.New("password is required")
	ErrInvalidStatus  = errors.New("invalid account status")
)

// Service orquesta repositorio + cipher.
type Service struct {
	repo   repository.Repository
	cipher *cipher.Cipher
}

// New crea un service.
func New(repo repository.Repository, c *cipher.Cipher) *Service {
	return &Service{repo: repo, cipher: c}
}

// CreateAccount crea una cuenta nueva con credenciales encriptadas.
func (s *Service) CreateAccount(ctx context.Context, req *models.CreateAccountRequest, tenantID uuid.UUID) (*models.Account, error) {
	if req.Login == 0 {
		return nil, ErrEmptyLogin
	}
	if req.Server == "" {
		return nil, ErrEmptyServer
	}
	if req.Password == "" {
		return nil, ErrEmptyPassword
	}

	// Verificar duplicado
	existing, err := s.repo.GetByLogin(ctx, tenantID, req.Login, req.Server)
	if err != nil {
		return nil, fmt.Errorf("check duplicate: %w", err)
	}
	if existing != nil {
		return nil, ErrAlreadyExists
	}

	// Encriptar password
	enc, err := s.cipher.Encrypt(req.Password)
	if err != nil {
		return nil, fmt.Errorf("encrypt password: %w", err)
	}

	broker := req.Broker
	if broker == "" {
		broker = "mt5"
	}

	var aliasPtr, namePtr *string
	if req.Alias != "" {
		aliasStr := req.Alias
		aliasPtr = &aliasStr
	}
	if req.Name != "" {
		nameStr := req.Name
		namePtr = &nameStr
	}

	a := &models.Account{
		ID:       uuid.New(),
		TenantID: tenantID,
		Login:    req.Login,
		Server:   req.Server,
		Broker:   broker,
		Alias:    aliasPtr,
		Name:     namePtr,
		Status:   models.AccountStatusActive,
	}

	if err := s.repo.Create(ctx, a, enc); err != nil {
		return nil, fmt.Errorf("create: %w", err)
	}

	// Recargar para tener created_at/updated_at
	full, _, err := s.repo.GetByID(ctx, a.ID)
	if err != nil {
		return nil, err
	}
	return full, nil
}

// ListAccounts devuelve las cuentas de un tenant con agregado.
func (s *Service) ListAccounts(ctx context.Context, tenantID uuid.UUID) (*models.AccountListResponse, error) {
	accounts, err := s.repo.ListByTenant(ctx, tenantID)
	if err != nil {
		return nil, err
	}
	agg := models.AggregateSnapshot{}
	agg.ActiveAccounts = 0
	for _, a := range accounts {
		if a.Status == models.AccountStatusActive || a.Status == models.AccountStatusConnected {
			agg.ActiveAccounts++
		}
		if a.LastBalance != nil {
			agg.TotalBalance += *a.LastBalance
		}
		if a.LastEquity != nil {
			agg.TotalEquity += *a.LastEquity
		}
		if a.LastPnL != nil {
			agg.TotalPnL += *a.LastPnL
		}
		agg.TotalOpenPositions += a.LastOpenPos
	}
	return &models.AccountListResponse{Accounts: toAccountSlice(accounts), Aggregate: agg}, nil
}

// ListReplicators devuelve solo las cuentas con copy_enabled=true.
// Usado por el modulo Copy Trading del frontend.
func (s *Service) ListReplicators(ctx context.Context, tenantID uuid.UUID) (*models.AccountListResponse, error) {
	accounts, err := s.repo.ListReplicatorsByTenant(ctx, tenantID)
	if err != nil {
		return nil, err
	}
	agg := models.AggregateSnapshot{}
	agg.ActiveAccounts = 0
	for _, a := range accounts {
		if a.Status == models.AccountStatusActive || a.Status == models.AccountStatusConnected {
			agg.ActiveAccounts++
		}
		if a.LastBalance != nil {
			agg.TotalBalance += *a.LastBalance
		}
		if a.LastEquity != nil {
			agg.TotalEquity += *a.LastEquity
		}
		if a.LastPnL != nil {
			agg.TotalPnL += *a.LastPnL
		}
		agg.TotalOpenPositions += a.LastOpenPos
	}
	return &models.AccountListResponse{Accounts: toAccountSlice(accounts), Aggregate: agg}, nil
}

// GetAccount devuelve una cuenta por id (sin password).
func (s *Service) GetAccount(ctx context.Context, id uuid.UUID) (*models.Account, error) {
	a, _, err := s.repo.GetByID(ctx, id)
	if err != nil {
		return nil, err
	}
	if a == nil {
		return nil, ErrNotFound
	}
	return a, nil
}

// UpdateAccount actualiza alias/name/status.
func (s *Service) UpdateAccount(ctx context.Context, id uuid.UUID, req *models.UpdateAccountRequest) (*models.Account, error) {
	a, _, err := s.repo.GetByID(ctx, id)
	if err != nil {
		return nil, err
	}
	if a == nil {
		return nil, ErrNotFound
	}
	if req.Alias != nil {
		newAlias := *req.Alias
		a.Alias = &newAlias
	}
	if req.Name != nil {
		newName := *req.Name
		a.Name = &newName
	}
	if req.Status != nil {
		valid := *req.Status == models.AccountStatusActive ||
			*req.Status == models.AccountStatusPaused ||
			*req.Status == models.AccountStatusDisabled
		if !valid {
			return nil, ErrInvalidStatus
		}
		a.Status = *req.Status
	}
	if req.CopyEnabled != nil {
		a.CopyEnabled = *req.CopyEnabled
	}
	if err := s.repo.Update(ctx, a); err != nil {
		return nil, err
	}
	return a, nil
}

// ChangePassword re-encripta la password.
func (s *Service) ChangePassword(ctx context.Context, id uuid.UUID, req *models.ChangePasswordRequest) error {
	if req.NewPassword == "" {
		return ErrEmptyPassword
	}
	enc, err := s.cipher.Encrypt(req.NewPassword)
	if err != nil {
		return err
	}
	return s.repo.UpdatePassword(ctx, id, enc)
}

// DecryptPassword devuelve la password en claro (uso interno: para que el
// mt5-connector pueda hacer login). El handler restringe quién puede llamar.
func (s *Service) DecryptPassword(ctx context.Context, id uuid.UUID) (string, error) {
	_, enc, err := s.repo.GetByID(ctx, id)
	if err != nil {
		return "", err
	}
	if enc == "" {
		return "", ErrNotFound
	}
	return s.cipher.Decrypt(enc)
}

// DeleteAccount elimina la cuenta.
func (s *Service) DeleteAccount(ctx context.Context, id uuid.UUID) error {
	return s.repo.Delete(ctx, id)
}

// UpdateSnapshot actualiza los datos en vivo cacheados.
func (s *Service) UpdateSnapshot(ctx context.Context, id uuid.UUID, snap *models.AccountSnapshot) error {
	return s.repo.UpdateSnapshot(ctx, id, snap)
}

// UpdateStatus actualiza el estado de la cuenta.
func (s *Service) UpdateStatus(ctx context.Context, id uuid.UUID, status models.AccountStatus, lastError string) error {
	return s.repo.UpdateStatus(ctx, id, status, lastError)
}

// ─── helpers ────────────────────────────────────────────────────

func toAccountSlice(in []*models.Account) []models.Account {
	out := make([]models.Account, len(in))
	for i, a := range in {
		if a != nil {
			out[i] = *a
		}
	}
	return out
}

// SnapshotForLogin construye un AccountSnapshot desde datos crudos del MT5.
func SnapshotForLogin(login int64, server string, balance, equity, margin, freeMargin, profit float64, leverage int, currency string, openPos int, connected bool) *models.AccountSnapshot {
	return &models.AccountSnapshot{
		Login:         login,
		Server:        server,
		Balance:       balance,
		Equity:        equity,
		Margin:        margin,
		FreeMargin:    freeMargin,
		Profit:        profit,
		Leverage:      leverage,
		Currency:      currency,
		OpenPositions: openPos,
		Connected:     connected,
		LastUpdate:    time.Now(),
	}
}
