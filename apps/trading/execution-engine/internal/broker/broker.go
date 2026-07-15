// Package broker define la interfaz abstracta para connectors de brokers.
package broker

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/tnsvt/execution-engine/internal/models"
)

// Connector interfaz para cualquier broker
type Connector interface {
	Name() models.BrokerName
	PlaceOrder(ctx context.Context, req *OrderRequest) (*OrderResponse, error)
	ClosePosition(ctx context.Context, accountID, ticket string) (*CloseResponse, error)
	GetAccountInfo(ctx context.Context, accountID string) (*AccountInfo, error)
	GetPositions(ctx context.Context, accountID string) ([]*Position, error)
	HealthCheck(ctx context.Context) error
}

// ─── Common types ─────────────────────────────────────────────

// OrderRequest solicitud de orden
type OrderRequest struct {
	SignalID   uuid.UUID
	AccountID  string
	Symbol     string
	Side       models.OrderSide
	OrderType  models.OrderType
	Quantity   float64
	Price      *float64
	StopLoss   *float64
	TakeProfit *float64
	Comment    string
	MagicNumber int64
}

// OrderResponse respuesta del broker
type OrderResponse struct {
	OrderID      string  `json:"order_id"`     // broker-side order ID
	Ticket       string  `json:"ticket"`       // exchange-side ticket
	FilledPrice  float64 `json:"filled_price"`
	FilledQty    float64 `json:"filled_qty"`
	Commission   float64 `json:"commission"`
	Accepted     bool    `json:"accepted"`
	ErrorMessage string  `json:"error_message,omitempty"`
}

// CloseResponse respuesta de cierre
type CloseResponse struct {
	Ticket   string  `json:"ticket"`
	Closed   bool    `json:"closed"`
	ExitPrice float64 `json:"exit_price"`
	PnL      float64 `json:"pnl"`
	Error    string  `json:"error,omitempty"`
}

// AccountInfo info de cuenta
type AccountInfo struct {
	Broker       string  `json:"broker"`
	AccountID    string  `json:"account_id"`
	Balance      float64 `json:"balance"`
	Equity       float64 `json:"equity"`
	Margin       float64 `json:"margin"`
	FreeMargin   float64 `json:"free_margin"`
	Currency     string  `json:"currency"`
	Leverage     int     `json:"leverage"`
	OpenPositions int    `json:"open_positions"`
}

// Position posición abierta del broker
type Position struct {
	Ticket       string  `json:"ticket"`
	Symbol       string  `json:"symbol"`
	Side         string  `json:"side"`
	Quantity     float64 `json:"quantity"`
	OpenPrice    float64 `json:"open_price"`
	CurrentPrice float64 `json:"current_price"`
	StopLoss     float64 `json:"stop_loss"`
	TakeProfit   float64 `json:"take_profit"`
	PnL          float64 `json:"pnl"`
	OpenedAt     time.Time `json:"opened_at"`
}

// ─── Factory ──────────────────────────────────────────────────

// Factory registra y retorna connectors
type Factory struct {
	connectors map[models.BrokerName]Connector
	log        interface {
		Info(string, ...any)
		Warn(string, ...any)
		Error(string, error, ...any)
	}
}

// NewFactory crea un factory
func NewFactory(log interface {
	Info(string, ...any)
	Warn(string, ...any)
	Error(string, error, ...any)
}) *Factory {
	return &Factory{
		connectors: make(map[models.BrokerName]Connector),
		log:        log,
	}
}

// Register registra un connector
func (f *Factory) Register(name string, c Connector) {
	f.connectors[models.BrokerName(name)] = c
	f.log.Info("Broker connector registered", "broker", name)
}

// Get obtiene un connector por nombre
func (f *Factory) Get(name models.BrokerName) (Connector, bool) {
	c, ok := f.connectors[name]
	return c, ok
}

// All retorna todos los connectors
func (f *Factory) All() map[models.BrokerName]Connector {
	return f.connectors
}

// HealthCheck verifica todos los connectors
func (f *Factory) HealthCheck(ctx context.Context) map[string]bool {
	status := make(map[string]bool)
	for name, c := range f.connectors {
		status[string(name)] = c.HealthCheck(ctx) == nil
	}
	return status
}

// ─── HTTP Connector (generic) ─────────────────────────────────

// HTTPBrokerConnector implementa Connector via HTTP (proxy a mt5-connector, etc.)
type HTTPBrokerConnector struct {
	name    models.BrokerName
	baseURL string
	client  *http.Client
	log     interface {
		Info(string, ...any)
		Warn(string, ...any)
		Error(string, error, ...any)
	}
}

// NewHTTPBrokerConnector crea connector HTTP
func NewHTTPBrokerConnector(name, baseURL string, log interface {
	Info(string, ...any)
	Warn(string, ...any)
	Error(string, error, ...any)
}) *HTTPBrokerConnector {
	return &HTTPBrokerConnector{
		name:    models.BrokerName(name),
		baseURL: strings.TrimRight(baseURL, "/"),
		client: &http.Client{
			Timeout: 30 * time.Second,
		},
		log: log,
	}
}

// Name retorna el nombre del broker
func (h *HTTPBrokerConnector) Name() models.BrokerName {
	return h.name
}

// PlaceOrder envía orden vía HTTP al broker-connector
func (h *HTTPBrokerConnector) PlaceOrder(ctx context.Context, req *OrderRequest) (*OrderResponse, error) {
	payload := map[string]any{
		"signal_id":   req.SignalID.String(),
		"account_id":  req.AccountID,
		"symbol":      req.Symbol,
		"side":        string(req.Side),
		"order_type":  string(req.OrderType),
		"quantity":    req.Quantity,
		"comment":     req.Comment,
		"magic":       req.MagicNumber,
	}
	if req.Price != nil {
		payload["price"] = *req.Price
	}
	if req.StopLoss != nil {
		payload["stop_loss"] = *req.StopLoss
	}
	if req.TakeProfit != nil {
		payload["take_profit"] = *req.TakeProfit
	}

	respBody, err := h.doRequest(ctx, "POST", "/api/v1/brokers/orders", payload)
	if err != nil {
		return nil, fmt.Errorf("place order: %w", err)
	}

	var resp OrderResponse
	if err := json.Unmarshal(respBody, &resp); err != nil {
		return nil, fmt.Errorf("unmarshal response: %w", err)
	}

	return &resp, nil
}

// ClosePosition cierra posición vía HTTP
func (h *HTTPBrokerConnector) ClosePosition(ctx context.Context, accountID, ticket string) (*CloseResponse, error) {
	payload := map[string]any{
		"account_id": accountID,
		"ticket":     ticket,
	}

	respBody, err := h.doRequest(ctx, "POST", "/api/v1/brokers/positions/close", payload)
	if err != nil {
		return nil, fmt.Errorf("close position: %w", err)
	}

	var resp CloseResponse
	if err := json.Unmarshal(respBody, &resp); err != nil {
		return nil, fmt.Errorf("unmarshal response: %w", err)
	}

	return &resp, nil
}

// GetAccountInfo obtiene info de cuenta
func (h *HTTPBrokerConnector) GetAccountInfo(ctx context.Context, accountID string) (*AccountInfo, error) {
	respBody, err := h.doRequest(ctx, "GET", "/api/v1/brokers/accounts/"+accountID, nil)
	if err != nil {
		return nil, fmt.Errorf("get account info: %w", err)
	}

	var info AccountInfo
	if err := json.Unmarshal(respBody, &info); err != nil {
		return nil, fmt.Errorf("unmarshal response: %w", err)
	}

	return &info, nil
}

// GetPositions obtiene posiciones abiertas
func (h *HTTPBrokerConnector) GetPositions(ctx context.Context, accountID string) ([]*Position, error) {
	respBody, err := h.doRequest(ctx, "GET", "/api/v1/brokers/accounts/"+accountID+"/positions", nil)
	if err != nil {
		return nil, fmt.Errorf("get positions: %w", err)
	}

	var positions []*Position
	if err := json.Unmarshal(respBody, &positions); err != nil {
		return nil, fmt.Errorf("unmarshal response: %w", err)
	}

	return positions, nil
}

// HealthCheck verifica que el connector está vivo
func (h *HTTPBrokerConnector) HealthCheck(ctx context.Context) error {
	_, err := h.doRequest(ctx, "GET", "/health", nil)
	return err
}

// ─── HTTP helper ───────────────────────────────────────────────

func (h *HTTPBrokerConnector) doRequest(ctx context.Context, method, path string, body any) ([]byte, error) {
	var bodyReader *jsonReader
	if body != nil {
		bodyReader = newJSONReader(body)
	}

	req, err := http.NewRequestWithContext(ctx, method, h.baseURL+path, bodyReader)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")

	resp, err := h.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("HTTP %d from broker connector", resp.StatusCode)
	}

	return readAll(resp.Body)
}