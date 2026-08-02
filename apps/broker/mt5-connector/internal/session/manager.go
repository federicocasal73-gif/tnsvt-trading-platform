// Package session implementa el manejo multi-cuenta del mt5-connector.
//
// Estrategia: el proceso mt5-connector mantiene UNA sola sesión de MT5
// (un solo terminal64.exe), pero puede cambiar entre cuentas vía
// mt5.login(login, password, server) sin reiniciar el terminal.
//
// El client original (client.go) asume un único login. Esta capa agrega:
//   - Pool de credenciales cargado del account-manager (service-to-service)
//   - Switch de cuenta bajo demanda: cada PlaceOrder/ClosePosition/GetPositions
//     puede target una cuenta distinta
//   - Cache de última cuenta activa para evitar logins repetidos
package session

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"sync"
	"time"

	"github.com/google/uuid"
)

// AccountCreds credenciales desencriptadas de una cuenta.
type AccountCreds struct {
	ID       string
	Login    int64
	Password string
	Server   string
	Broker   string
}

// Manager gestiona credenciales y estado de la cuenta activa.
type Manager struct {
	accountMgrURL string
	serviceToken  string
	tenantID      string
	httpClient    *http.Client

	mu               sync.RWMutex
	creds            map[string]*AccountCreds // id → creds
	lastRefresh      time.Time
	activeAccountID  string
	activeLogin      int64
}

// NewManager crea un manager que consulta el account-manager.
func NewManager() *Manager {
	return &Manager{
		accountMgrURL: ifEmpty(os.Getenv("ACCOUNT_MANAGER_URL"), "http://localhost:8510"),
		serviceToken:  os.Getenv("ACCOUNT_MGR_SERVICE_TOKEN"),
		tenantID:      os.Getenv("DEFAULT_TENANT_ID"),
		httpClient:    &http.Client{Timeout: 5 * time.Second},
		creds:         make(map[string]*AccountCreds),
	}
}

func ifEmpty(v, def string) string {
	if v == "" {
		return def
	}
	return v
}

// RefreshCreds recarga credenciales desde account-manager.
// Service-to-service: usa X-Service-Token.
func (m *Manager) RefreshCreds() error {
	if m.accountMgrURL == "" {
		return fmt.Errorf("ACCOUNT_MANAGER_URL not set")
	}
	if m.serviceToken == "" {
		return fmt.Errorf("ACCOUNT_MGR_SERVICE_TOKEN not set")
	}

	req, _ := http.NewRequest("GET", m.accountMgrURL+"/api/v1/accounts", nil)
	req.Header.Set("X-Service-Token", m.serviceToken)
	if m.tenantID != "" {
		req.Header.Set("X-Tenant-ID", m.tenantID)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := m.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("account-manager unreachable: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("account-manager %d: %s", resp.StatusCode, string(body))
	}

	var listResp struct {
		Accounts []struct {
			ID     string `json:"id"`
			Login  int64  `json:"login"`
			Server string `json:"server"`
			Broker string `json:"broker"`
			Status string `json:"status"`
		} `json:"accounts"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&listResp); err != nil {
		return fmt.Errorf("decode accounts: %w", err)
	}

	// Para cada cuenta activa, obtener credenciales
	m.mu.Lock()
	defer m.mu.Unlock()
	m.creds = make(map[string]*AccountCreds, len(listResp.Accounts))
	for _, a := range listResp.Accounts {
		if a.Status == "disabled" {
			continue
		}
		creds, err := m.fetchCreds(a.ID)
		if err != nil {
			continue // log pero no abortar
		}
		m.creds[a.ID] = creds
	}
	m.lastRefresh = time.Now()
	return nil
}

// fetchCreds obtiene credenciales desencriptadas para una cuenta.
func (m *Manager) fetchCreds(accountID string) (*AccountCreds, error) {
	aid, err := uuid.Parse(accountID)
	if err != nil {
		return nil, fmt.Errorf("invalid account id: %w", err)
	}

	req, _ := http.NewRequest("GET", fmt.Sprintf("%s/api/v1/accounts/%s/credentials", m.accountMgrURL, aid.String()), nil)
	req.Header.Set("X-Service-Token", m.serviceToken)
	if m.tenantID != "" {
		req.Header.Set("X-Tenant-ID", m.tenantID)
	}

	resp, err := m.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("credentials %d: %s", resp.StatusCode, string(body))
	}

	var c struct {
		ID       string `json:"id"`
		Login    int64  `json:"login"`
		Password string `json:"password"`
		Server   string `json:"server"`
		Broker   string `json:"broker"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&c); err != nil {
		return nil, err
	}
	return &AccountCreds{
		ID:       c.ID,
		Login:    c.Login,
		Password: c.Password,
		Server:   c.Server,
		Broker:   c.Broker,
	}, nil
}

// GetCredsByID retorna credenciales cacheadas por account_id.
func (m *Manager) GetCredsByID(accountID string) (*AccountCreds, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	c, ok := m.creds[accountID]
	return c, ok
}

// GetCredsByLogin retorna credenciales por login numérico.
func (m *Manager) GetCredsByLogin(login int64) (*AccountCreds, string, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	for id, c := range m.creds {
		if c.Login == login {
			return c, id, true
		}
	}
	return nil, "", false
}

// SetActive marca la cuenta actualmente logueada en MT5.
// El cliente MT5 la usa para evitar logins repetidos.
func (m *Manager) SetActive(accountID string, login int64) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.activeAccountID = accountID
	m.activeLogin = login
}

// GetActive retorna la cuenta activa.
func (m *Manager) GetActive() (string, int64) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.activeAccountID, m.activeLogin
}

// IsStale retorna si el cache de credenciales está vencido (> 5 min).
func (m *Manager) IsStale() bool {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return time.Since(m.lastRefresh) > 5*time.Minute
}

// Count retorna cuántas cuentas están cacheadas.
func (m *Manager) Count() int {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return len(m.creds)
}
