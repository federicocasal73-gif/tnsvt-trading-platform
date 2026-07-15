// Package mt5 implementa el cliente para MetaTrader 5.
//
// Compilación condicional:
//
//   - windows: usa la librería MetaTrader5 (vía cgo o subprocess Python)
//   - linux/dev: stub que retorna errores (para CI/CD sin MT5 instalado)
//
// Recomendado para Fase 1: usar subprocess Python con la librería MetaTrader5
// oficial. Esto evita cgo y simplifica el deployment.
//
// Para Fase 2/3: considerar cgo directo con la DLL mt5api para menor latencia.
package mt5

import (
	"context"
	"encoding/json"
	"fmt"
	"os/exec"
	"sync"
	"time"
)

// Config configuración del cliente MT5
type Config struct {
	Path         string        // Path a terminal64.exe
	Login        int           // Login de la cuenta
	Password     string        // Password
	Server       string        // Servidor (ej: "FTMO-Demo")
	SymbolSuffix string        // Suffix para símbolos (ej: ".m", ".pro")
	MagicNumber  int64         // Magic number para identificar nuestras órdenes
	Timeout      time.Duration // Timeout para operaciones
	PythonPath   string        // Path a python (default: "python")
	BridgeScript string        // Path al script Python bridge
}

// OrderRequest solicitud de orden (compatible con execution-engine)
type OrderRequest struct {
	AccountID  string  `json:"account_id"`
	Symbol     string  `json:"symbol"`
	Side       string  `json:"side"`        // "buy" / "sell"
	OrderType  string  `json:"order_type"`  // "market" / "limit" / "stop"
	Quantity   float64 `json:"quantity"`
	Price      float64 `json:"price,omitempty"`
	StopLoss   float64 `json:"stop_loss,omitempty"`
	TakeProfit float64 `json:"take_profit,omitempty"`
	Comment    string  `json:"comment,omitempty"`
	Magic      int64   `json:"magic,omitempty"`
	Deviation  int     `json:"deviation,omitempty"` // Max price deviation in points
}

// OrderResponse respuesta de orden
type OrderResponse struct {
	OrderID     string  `json:"order_id"`
	Ticket      string  `json:"ticket"`
	FilledPrice float64 `json:"filled_price"`
	FilledQty   float64 `json:"filled_qty"`
	Commission  float64 `json:"commission"`
	Accepted    bool    `json:"accepted"`
	Error       string  `json:"error,omitempty"`
}

// Position posición abierta
type Position struct {
	Ticket       string    `json:"ticket"`
	Symbol       string    `json:"symbol"`
	Side         string    `json:"side"`
	Quantity     float64   `json:"quantity"`
	OpenPrice    float64   `json:"open_price"`
	CurrentPrice float64   `json:"current_price"`
	StopLoss     float64   `json:"stop_loss"`
	TakeProfit   float64   `json:"take_profit"`
	PnL          float64   `json:"pnl"`
	Swap         float64   `json:"swap"`
	Commission   float64   `json:"commission"`
	OpenedAt     time.Time `json:"opened_at"`
	Magic        int64     `json:"magic"`
	Comment      string    `json:"comment"`
}

// AccountInfo info de cuenta
type AccountInfo struct {
	AccountID     string  `json:"account_id"`
	Login         int64   `json:"login"`
	Balance       float64 `json:"balance"`
	Equity        float64 `json:"equity"`
	Margin        float64 `json:"margin"`
	FreeMargin    float64 `json:"free_margin"`
	Currency      string  `json:"currency"`
	Leverage      int     `json:"leverage"`
	OpenPositions int     `json:"open_positions"`
	Server        string  `json:"server"`
	Name          string  `json:"name"`
}

// SymbolInfo info de símbolo
type SymbolInfo struct {
	Symbol        string  `json:"symbol"`
	Digits        int     `json:"digits"`
	Point         float64 `json:"point"`
	TradeContract float64 `json:"trade_contract_size"`
	VolumeMin     float64 `json:"volume_min"`
	VolumeMax     float64 `json:"volume_max"`
	VolumeStep    float64 `json:"volume_step"`
	Spread        int     `json:"spread"`
	Visible       bool    `json:"visible"`
	TradeMode     int     `json:"trade_mode"`
}

// ─── Client ─────────────────────────────────────────────────────

// Client interfaz para el cliente MT5
type Client struct {
	config Config
	log    interface {
		Info(string, ...any)
		Warn(string, ...any)
		Error(string, error, ...any)
	}

	mu             sync.RWMutex
	connected      bool
	lastConnect    time.Time
	lastError      string
	activeAccount  *AccountInfo
}

// NewClient crea un nuevo cliente
func NewClient(config Config, log interface {
	Info(string, ...any)
	Warn(string, ...any)
	Error(string, error, ...any)
}) *Client {
	if config.Timeout == 0 {
		config.Timeout = 30 * time.Second
	}
	if config.PythonPath == "" {
		config.PythonPath = "python"
	}
	if config.BridgeScript == "" {
		config.BridgeScript = "mt5_bridge.py"
	}
	return &Client{
		config: config,
		log:    log,
	}
}

// Connect intenta conectar a MT5
func (c *Client) Connect(ctx context.Context) error {
	c.log.Info("Connecting to MT5", "path", c.config.Path, "login", c.config.Login, "server", c.config.Server)

	result, err := c.callBridge(ctx, "initialize", map[string]any{
		"path":     c.config.Path,
		"login":    c.config.Login,
		"password": c.config.Password,
		"server":   c.config.Server,
	})
	if err != nil {
		c.mu.Lock()
		c.connected = false
		c.lastError = err.Error()
		c.mu.Unlock()
		return fmt.Errorf("mt5 initialize: %w", err)
	}

	if !result.Success {
		c.mu.Lock()
		c.connected = false
		c.lastError = result.Error
		c.mu.Unlock()
		return fmt.Errorf("mt5 init failed: %s", result.Error)
	}

	c.mu.Lock()
	c.connected = true
	c.lastConnect = time.Now()
	c.lastError = ""
	c.mu.Unlock()

	c.log.Info("MT5 connected", "login", c.config.Login)
	return nil
}

// RunReconnectLoop reintenta conectar cada N segundos si está desconectado
func (c *Client) RunReconnectLoop(ctx context.Context, interval time.Duration) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if !c.IsConnected() {
				c.log.Info("Attempting MT5 reconnect...")
				if err := c.Connect(ctx); err != nil {
					c.log.Warn("MT5 reconnect failed", "error", err.Error())
				}
			}
		}
	}
}

// IsConnected retorna si MT5 está conectado
func (c *Client) IsConnected() bool {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.connected
}

// Shutdown desconecta MT5
func (c *Client) Shutdown() {
	c.mu.Lock()
	defer c.mu.Unlock()

	_, _ = c.callBridge(context.Background(), "shutdown", nil)
	c.connected = false
}

// ─── Account Operations ────────────────────────────────────────

// GetAccountInfo retorna info de cuenta
func (c *Client) GetAccountInfo(ctx context.Context, accountID string) (*AccountInfo, error) {
	result, err := c.callBridge(ctx, "account_info", map[string]any{
		"login": c.config.Login,
	})
	if err != nil {
		return nil, err
	}

	if !result.Success {
		return nil, fmt.Errorf("account info failed: %s", result.Error)
	}

	info := &AccountInfo{
		AccountID: accountID,
		Login:     c.config.Login,
		Server:    c.config.Server,
	}

	if err := mapToStruct(result.Data, info); err != nil {
		return nil, err
	}

	c.mu.Lock()
	c.activeAccount = info
	c.mu.Unlock()

	return info, nil
}

// ─── Order Operations ──────────────────────────────────────────

// PlaceOrder coloca una orden
func (c *Client) PlaceOrder(ctx context.Context, req *OrderRequest) (*OrderResponse, error) {
	symbol := c.normalizeSymbol(req.Symbol)

	args := map[string]any{
		"symbol":     symbol,
		"side":       req.Side,
		"order_type": req.OrderType,
		"quantity":   req.Quantity,
		"comment":    req.Comment,
		"magic":      c.config.MagicNumber,
		"deviation":  req.Deviation,
	}
	if req.Deviation == 0 {
		args["deviation"] = 20 // default
	}
	if req.Price > 0 {
		args["price"] = req.Price
	}
	if req.StopLoss > 0 {
		args["sl"] = req.StopLoss
	}
	if req.TakeProfit > 0 {
		args["tp"] = req.TakeProfit
	}

	result, err := c.callBridge(ctx, "place_order", args)
	if err != nil {
		return nil, err
	}

	resp := &OrderResponse{Accepted: false}
	if err := mapToStruct(result.Data, resp); err != nil {
		return nil, err
	}

	if !result.Success {
		resp.Accepted = false
		resp.Error = result.Error
	}

	return resp, nil
}

// ClosePosition cierra una posición
func (c *Client) ClosePosition(ctx context.Context, accountID, ticket string) (*OrderResponse, error) {
	result, err := c.callBridge(ctx, "close_position", map[string]any{
		"ticket": ticket,
	})
	if err != nil {
		return nil, err
	}

	resp := &OrderResponse{Accepted: false}
	if err := mapToStruct(result.Data, resp); err != nil {
		return nil, err
	}

	if !result.Success {
		resp.Error = result.Error
	}

	return resp, nil
}

// ModifyPosition modifica SL/TP de una posición abierta
func (c *Client) ModifyPosition(ctx context.Context, ticket string, sl, tp float64) error {
	args := map[string]any{
		"ticket": ticket,
	}
	if sl > 0 {
		args["sl"] = sl
	}
	if tp > 0 {
		args["tp"] = tp
	}

	result, err := c.callBridge(ctx, "modify_position", args)
	if err != nil {
		return err
	}

	if !result.Success {
		return fmt.Errorf("modify failed: %s", result.Error)
	}

	return nil
}

// ─── Position Queries ─────────────────────────────────────────

// GetPositions retorna posiciones abiertas
func (c *Client) GetPositions(ctx context.Context, accountID string) ([]*Position, error) {
	result, err := c.callBridge(ctx, "positions_get", map[string]any{
		"magic": c.config.MagicNumber, // solo nuestras posiciones
	})
	if err != nil {
		return nil, err
	}

	if !result.Success {
		return nil, fmt.Errorf("positions_get failed: %s", result.Error)
	}

	var positions []*Position
	if data, ok := result.Data["positions"].([]any); ok {
		for _, p := range data {
			pos := &Position{}
			if err := mapToStruct(p, pos); err != nil {
				continue
			}
			positions = append(positions, pos)
		}
	}

	return positions, nil
}

// GetSymbolInfo retorna info del símbolo
func (c *Client) GetSymbolInfo(ctx context.Context, symbol string) (*SymbolInfo, error) {
	symbol = c.normalizeSymbol(symbol)

	result, err := c.callBridge(ctx, "symbol_info", map[string]any{
		"symbol": symbol,
	})
	if err != nil {
		return nil, err
	}

	info := &SymbolInfo{Symbol: symbol}
	if result.Success {
		if err := mapToStruct(result.Data, info); err != nil {
			return nil, err
		}
	}

	return info, nil
}

// ─── Symbol Normalization ──────────────────────────────────────

// normalizeSymbol agrega suffix si está configurado
func (c *Client) normalizeSymbol(symbol string) string {
	if c.config.SymbolSuffix == "" {
		return symbol
	}

	// No agregar suffix si ya lo tiene
	if containsAny(symbol, []string{c.config.SymbolSuffix}) {
		return symbol
	}

	return symbol + c.config.SymbolSuffix
}

func containsAny(s string, subs []string) bool {
	for _, sub := range subs {
		if len(sub) > 0 && len(s) >= len(sub) {
			for i := 0; i+len(sub) <= len(s); i++ {
				if s[i:i+len(sub)] == sub {
					return true
				}
			}
		}
	}
	return false
}

// ─── Bridge Communication ──────────────────────────────────────

// bridgeResult resultado del bridge Python
type bridgeResult struct {
	Success bool           `json:"success"`
	Error   string         `json:"error,omitempty"`
	Data    map[string]any `json:"data,omitempty"`
}

// callBridge ejecuta el script Python bridge con la operación solicitada
//
// Formato: python mt5_bridge.py <op> [--json <args>]
func (c *Client) callBridge(ctx context.Context, operation string, args map[string]any) (*bridgeResult, error) {
	if !c.IsConnected() {
		// Intentar reconectar
		if err := c.Connect(ctx); err != nil {
			return nil, fmt.Errorf("not connected to MT5: %w", err)
		}
	}

	argsJSON, _ := json.Marshal(args)

	// Use context with timeout
	callCtx, cancel := context.WithTimeout(ctx, c.config.Timeout)
	defer cancel()

	cmd := exec.CommandContext(callCtx, c.config.PythonPath, c.config.BridgeScript, operation, "--json", string(argsJSON))
	cmd.WaitDelay = c.config.Timeout

	output, err := cmd.Output()
	if err != nil {
		c.mu.Lock()
		c.connected = false
		c.lastError = err.Error()
		c.mu.Unlock()
		return nil, fmt.Errorf("bridge call: %w", err)
	}

	var result bridgeResult
	if err := json.Unmarshal(output, &result); err != nil {
		return nil, fmt.Errorf("unmarshal bridge result: %w (raw: %s)", err, string(output))
	}

	return &result, nil
}

// ─── Helpers ───────────────────────────────────────────────────

func mapToStruct(src any, dst any) error {
	jsonBytes, err := json.Marshal(src)
	if err != nil {
		return err
	}
	return json.Unmarshal(jsonBytes, dst)
}