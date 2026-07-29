const BASE = '/api/v1';

function token(): string | null {
  try { return localStorage.getItem('tnsvt_token'); } catch { return null; }
}

// Circuit breaker: por endpoint, contar fallos consecutivos.
// Despues de 3 fallos, marcar el endpoint como abierto por 30s.
// Mientras esta abierto, devolver el error inmediatamente sin intentar la llamada.
const _failCount = new Map<string, number>();
const _openUntil = new Map<string, number>();
const BREAKER_THRESHOLD = 3;
const BREAKER_COOLDOWN_MS = 30_000;

function _isOpen(path: string): boolean {
  const until = _openUntil.get(path);
  if (!until) return false;
  if (Date.now() < until) return true;
  _openUntil.delete(path);
  _failCount.delete(path);
  return false;
}

function _recordSuccess(path: string): void {
  _failCount.delete(path);
  _openUntil.delete(path);
}

function _recordFailure(path: string): void {
  const c = (_failCount.get(path) || 0) + 1;
  _failCount.set(path, c);
  if (c >= BREAKER_THRESHOLD) {
    _openUntil.set(path, Date.now() + BREAKER_COOLDOWN_MS);
    console.warn(`[api] circuit breaker abierto para ${path} por ${BREAKER_COOLDOWN_MS / 1000}s`);
  }
}

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  if (_isOpen(path)) {
    throw new Error(`Circuit open for ${path}`);
  }

  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const t = token();
  if (t) headers['Authorization'] = `Bearer ${t}`;

  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { ...opts, headers: { ...headers, ...((opts?.headers as Record<string, string>) || {}) } });
  } catch (e) {
    _recordFailure(path);
    throw e;
  }

  console.debug(`[api] ${opts?.method || 'GET'} ${path} -> ${res.status}`);

  const isAuthValidation = path === '/api/v1/auth/me' || path === '/api/v1/auth/refresh';
  if (res.status === 401 && token() && isAuthValidation) {
    console.warn(`[api] 401 on auth validation ${path} - logging out`);
    localStorage.removeItem('tnsvt_token');
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    _recordFailure(path);
    const body = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(body.error || `HTTP ${res.status}`);
  }
  _recordSuccess(path);
  return res.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body: unknown) => request<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
  del: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  raw: (path: string) => `${BASE}${path}`,
  token,
  // ─── MT5 Bridge ────────────────────────────────────────
  bridge: {
    metrics: () => request<Metrics>('/bridge/analytics/metrics'),
    equityCurve: () => request<EquityPoint[]>('/bridge/analytics/equity-curve'),
    byChannel: (tenantId?: string, sinceDays?: number) => {
      const params = new URLSearchParams();
      if (tenantId) params.set('tenant_id', tenantId);
      if (sinceDays) params.set('since_days', String(sinceDays));
      const qs = params.toString();
      return request<ChannelAgg[]>(`/bridge/analytics/by-channel${qs ? `?${qs}` : ''}`);
    },
    bySymbol: (tenantId?: string, sinceDays?: number) => {
      const params = new URLSearchParams();
      if (tenantId) params.set('tenant_id', tenantId);
      if (sinceDays) params.set('since_days', String(sinceDays));
      const qs = params.toString();
      return request<SymbolAgg[]>(`/bridge/analytics/by-symbol${qs ? `?${qs}` : ''}`);
    },
    livePositions: () => request<LivePosition[]>('/bridge/analytics/live-positions'),
    signalCopierStatus: () => request<{ ok: boolean; data?: { connected: boolean; balance: number; equity: number; margin: number; profit: number; open_positions: number }; error?: string }>('/bridge/mt5/signal_copier_status'),
    calendar: (year?: number) => request<CalendarDay[]>(`/bridge/analytics/calendar${year ? `?year=${year}` : ''}`),
    trades: (status?: string, sinceDays?: number) => {
      const params = new URLSearchParams();
      if (status) params.set('status', status);
      if (sinceDays) params.set('since_days', String(sinceDays));
      const qs = params.toString();
      return request<LivePosition[]>(`/bridge/analytics/trades${qs ? `?${qs}` : ''}`);
    },
    account: (login?: number | string) => {
      const qs = login != null ? `?login=${login}` : '';
      return request<{ ok: boolean; data: Mt5AccountSnapshot; login?: number }>(`/bridge/mt5/account${qs}`);
    },
    accounts: () => request<{
      ok: boolean;
      count: number;
      accounts: Array<{
        login: number;
        alias: string;
        name: string;
        server: string;
        balance: number | null;
        equity: number | null;
        margin: number | null;
        profit: number | null;
        open_positions: number | null;
        updated_at: string | null;
      }>;
      aggregate: { total_balance: number; total_equity: number; total_pnl: number; total_open_positions: number };
    }>('/bridge/mt5/accounts'),
    accountPositions: (login?: number | string) => {
      const qs = login != null ? `?login=${login}` : '';
      return request<{ ok: boolean; data: Mt5PositionSnapshot[]; count: number }>(`/bridge/mt5/positions${qs}`);
    },
    positionsLive: (login?: number | string) => {
      const qs = login != null ? `?login=${login}` : '';
      return request<{ ok: boolean; data: Mt5PositionSnapshot[]; count: number }>(`/bridge/mt5/positions${qs}`);
    },
    config: () => request<BotConfig>('/bridge/config'),
    updateConfig: (patch: Partial<BotConfig>) =>
      request<{ ok: boolean; updated_keys: string[] }>(
        '/bridge/config',
        { method: 'POST', body: JSON.stringify(patch) },
      ),
    triggerScan: () =>
      request<{ accepted: boolean; request_id: string }>(
        '/bridge/telegram/scan',
        { method: 'POST' },
      ),
    scanResult: () =>
      request<ScanResult>('/bridge/telegram/channels'),
    controlState: () =>
      request<{ status: string; updated_at?: string }>(
        '/bridge/control/state',
      ),
    control: (action: 'start' | 'stop' | 'wait_config') =>
      request<{ ok: boolean; status: string }>(
        '/bridge/control',
        { method: 'POST', body: JSON.stringify({ action }) },
      ),
    candles: (symbol: string, tf = 'M5', from?: string, to?: string, bars = 60) => {
      const params = new URLSearchParams({ symbol, tf, bars: String(bars) });
      if (from) params.set('from', from);
      if (to) params.set('to', to);
      return request<{ ok: boolean; symbol: string; tf: string; count: number; candles: BridgeCandle[] }>(
        `/bridge/mt5/candles?${params}`,
      );
    },
    tradeCandles: (ticket: number, tf?: string) =>
      request<{ ok: boolean; symbol: string; tf: string; count: number; candles: BridgeCandle[] }>(
        `/bridge/trades/${ticket}/candles${tf ? `?tf=${tf}` : ''}`,
      ),
    riskState: () => request<RiskState>('/bridge/risk/state'),
    killSwitch: (reason: string) =>
      request<{ ok: boolean; closed_positions: number; errors: string[]; paused: string[] }>(
        '/bridge/risk/kill-switch',
        { method: 'POST', body: JSON.stringify({ reason }) },
      ),
    riskHistory: (limit = 50) =>
      request<{ count: number; items: RiskHistoryEvent[] }>(
        `/bridge/risk/history?limit=${limit}`,
      ),
    retryDeadLetter: (eventId: number) =>
      request<{ ok: boolean; retried: boolean; event_id: number }>(
        `/bridge/copier/retry/${eventId}`,
        { method: 'POST' },
      ),
  },
  // ─── Admin (Sub-fase 3, K2) ─────────────────────────────────────
  admin: {
    tenants: (limit = 50, offset = 0) =>
      request<AdminTenant[]>(`/admin/tenants?limit=${limit}&offset=${offset}`),
    stats: () =>
      request<AdminStats>('/admin/stats'),
  },
  // ─── Brokers (mt5-connector) ─────────────────────────────────
  brokers: {
    account: (accountId = 'default') =>
      request<Mt5AccountInfo>(`/brokers/accounts/${accountId}`),
    positions: (accountId = 'default') =>
      request<Mt5PositionsResponse>(`/brokers/accounts/${accountId}/positions`),
    close: (ticket: string, accountId = 'default') =>
      request<{ order_id?: string; ticket?: string; filled_price?: number; filled_qty?: number; accepted: boolean; error?: string }>(
        '/brokers/positions/close',
        { method: 'POST', body: JSON.stringify({ account_id: accountId, ticket }) },
      ),
  },
  // ─── Orchestrator (multi-symbol) ─────────────────────────────
  orchestrator: {
    health: () => request<OrchestratorHealth>('/orchestrator/health'),
    stats: () => request<OrchestratorStats>('/orchestrator/stats'),
    signals: (limit = 50, symbol?: string) => {
      const params = new URLSearchParams({ limit: String(limit) });
      if (symbol) params.set('symbol', symbol);
      return request<OrchestratorSignalsResponse>(`/orchestrator/signals?${params}`);
    },
    analysis: (symbol: string) => request<SymbolAnalysis>(`/orchestrator/analysis/${symbol}`),
    pause: () => request<{ status: string }>('/orchestrator/pause', { method: 'POST' }),
    resume: () => request<{ status: string }>('/orchestrator/resume', { method: 'POST' }),
  },
};

export interface UserProfile {
  user_id: string;
  tenant_id: string;
  full_name: string;
  avatar_url?: string;
  timezone: string;
  language: string;
  phone?: string;
  preferences?: Record<string, unknown>;
  notify_settings?: Record<string, unknown>;
}

export interface Signal {
  id: string;
  symbol: string;
  action: string;
  lot_size: number;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  confidence?: number;
  source?: string;
  status: string;
  created_at: string;
}

export interface Trade {
  id: string;
  symbol: string;
  side: string;
  quantity: number;
  entry_price: number;
  stop_loss?: number;
  take_profit?: number;
  status: string;
  ticket?: string;
  pnl?: number;
  created_at: string;
  closed_at?: string;
}

export interface Position {
  id: string;
  symbol: string;
  side: string;
  quantity: number;
  entry_price: number;
  current_price: number;
  stop_loss: number;
  take_profit?: number;
  unrealized_pnl: number;
  status: string;
  created_at: string;
  closed_at?: string;
}

export interface CopyJob {
  id: string;
  group_id: string;
  account_id: string;
  signal_id: string;
  symbol: string;
  action: string;
  status: string;
  applied_lot_size: number;
  applied_side: string;
  applied_symbol: string;
  error_message?: string;
  created_at: string;
}

export interface Stats {
  total_jobs: number;
  successful_jobs: number;
  failed_jobs: number;
  success_rate: number;
  last_24h: number;
  by_status: Record<string, number>;
  by_group: Record<string, number>;
}

// ─── MT5 Bridge Analytics ───────────────────────────────────────────────

export interface Metrics {
  total: number;
  wins: number;
  losses: number;
  win_rate: number;
  profit_factor: number | null;
  expectancy: number;
  sharpe: number;
  sortino: number | null;
  max_drawdown: number;
  gross_profit: number;
  gross_loss: number;
}

export interface EquityPoint {
  date: string;
  equity: number;
  drawdown: number;
}

export interface ChannelAgg {
  channel_id: number | null;
  channel_title: string;
  trades: number;
  wins: number;
  pnl: number;
  win_rate: number;
}

export interface SymbolAgg {
  symbol: string;
  trades: number;
  pnl: number;
  best?: boolean;
  worst?: boolean;
}

export interface BridgeCandle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  spread: number;
  real_volume: number;
}

export interface LivePosition {
  id: number;
  ticket: number;
  symbol: string;
  action: string;
  volume: number;
  open_price: number;
  close_price: number | null;
  sl: number | null;
  tp: number | null;
  pnl: number;
  commission: number;
  swap: number;
  opened_at: string;
  closed_at: string | null;
  channel_id: number | null;
  channel_title: string | null;
  topic_id: number | null;
  status: string;
  received_at: string;
}

// ─── MT5 Bot Config (Bloque E: Mt5ChannelsPage) ─────────────────────────

export interface Topic {
  id: number;
  title: string;
}

export interface ChannelProfile {
  name: string;
  id: number;
  is_forum: boolean;
  topics: Topic[];
}

export interface ChannelSelection {
  id: number;
  name: string;
  topic_id: number | null;
  profile?: ChannelProfileData;
}

export interface ChannelProfileData {
  default_symbol?: string | null;
  allow_symbols?: string[];
  block_symbols?: string[];
  multi_same_symbol?: boolean;
  max_positions?: number;
  max_spread_pips?: number;
}

export interface RiskManagement {
  active_daily_profit: boolean;
  daily_profit_target: number;
  active_daily_loss: boolean;
  daily_loss_limit: number;
  active_weekly_profit: boolean;
  weekly_profit: number;
  active_weekly_loss: boolean;
  weekly_loss: number;
  active_monthly_profit: boolean;
  monthly_profit: number;
  active_monthly_loss: boolean;
  monthly_loss: number;
  max_open_positions?: number;
  correlation_threshold?: number;
  correlation_guard?: boolean;
}

export interface BotConfig {
  api_id?: string;
  api_hash?: string;
  bridge_url?: string;
  symbol_suffix?: string;
  lot_size?: number;
  lot_mode?: string;
  lot_percentage?: number;
  deviation?: number;
  channels_data?: ChannelSelection[];
  risk_management?: RiskManagement;
  trailing_stop?: TrailingStopConfig;
  scale_out?: ScaleOutConfig;
}

export interface CalendarDay {
  date: string;
  pnl: number;
  trades: number;
}

export interface TrailingStopConfig {
  enabled: boolean;
  step_pips: number;
  start_pips: number;
}

export interface ScaleOutLevel {
  pips: number;
  percent: number;
}

export interface ScaleOutConfig {
  enabled: boolean;
  levels: ScaleOutLevel[];
}

// ─── Risk State (F6) ──────────────────────────────────────────────────────

export interface SymbolExposure {
  symbol: string;
  volume: number;
  pnl: number;
  positions: number;
  exposure_pct: number;
}

export interface RiskState {
  ok: boolean;
  dd_pct: number;
  peak_equity: number;
  equity: number;
  balance: number;
  open_count: number;
  open_pnl: number;
  daily_pnl: number;
  by_symbol: SymbolExposure[];
  ts: number;
}

export interface RiskHistoryEvent {
  ts: number;
  iso: string;
  type: string;
  value: Record<string, unknown>;
  reason: string;
}

// ─── MT5 Live Snapshot ───────────────────────────────────────────────────

export interface Mt5AccountSnapshot {
  login: number;
  balance: number;
  equity: number;
  margin: number;
  margin_free: number;
  margin_level: number | null;
  profit: number;
  leverage: number;
  currency: string;
  server: string;
  name: string;
  updated_at: string;
}

export interface Mt5PositionSnapshot {
  ticket: number;
  symbol: string;
  type: 'BUY' | 'SELL';
  volume: number;
  price_open: number;
  price_current: number;
  sl: number | null;
  tp: number | null;
  profit: number;
  swap: number;
  commission: number;
  magic: number;
  comment: string;
  time: string;
}

export interface ScanResult {
  status: 'NO_SCAN' | 'PENDING' | 'OK' | 'ERROR';
  error?: string;
  completed_at?: string;
  request_id?: string;
  data?: ChannelProfile[];
}

// ─── Admin (Sub-fase 3, K2) ─────────────────────────────────────────────

export interface AdminTenant {
  id: string;
  name: string;
  slug: string;
  schema: string;
  status: 'active' | 'trial' | 'suspended';
  plan: 'free' | 'starter' | 'pro' | 'enterprise';
  max_users: number;
  max_signals_per_day: number;
  created_at: string;
  updated_at: string;
}

export interface AdminStats {
  total_tenants: number;
  active_subscriptions: number;
  mrr_usd: number;
  churn_pct: number;
  by_plan: { plan: string; count: number }[];
  pricing_per_plan_usd: Record<string, number>;
}

// ─── Brokers (mt5-connector) ─────────────────────────────
export interface Mt5AccountInfo {
  account_id: string;
  login: number;
  balance: number;
  equity: number;
  margin: number;
  free_margin: number;
  currency: string;
  leverage: number;
  open_positions: number;
  server: string;
  name: string;
}

export interface Mt5Position {
  ticket: string;
  symbol: string;
  side: 'buy' | 'sell';
  quantity: number;
  open_price: number;
  current_price: number;
  stop_loss: number;
  take_profit: number;
  pnl: number;
  swap: number;
  commission: number;
  opened_at: string;
  magic: number;
  comment: string;
}

export interface Mt5PositionsResponse {
  account_id: string;
  count: number;
  positions: Mt5Position[] | null;
}

// ─── Orchestrator ─────────────────────────────
export interface OrchestratorHealth {
  status: string;
  service: string;
  symbols: string[];
  timeframes: string[];
}

export interface OrchestratorStats {
  paused: boolean;
  pending_signals: number;
  buffer_sizes: Record<string, number>;
  published_signals_buffer: number;
  portfolio: {
    equity_peak: number;
    current_equity: number;
    drawdown: number;
    open_positions: number;
    max_drawdown_limit: number;
    max_positions_limit: number;
  };
}

export interface OrchestratorPublishedSignal {
  id?: string;
  symbol: string;
  action: string;
  lot_size?: number;
  stop_loss?: number;
  take_profits?: number[];
  confidence?: number;
  source?: string;
  reasons?: string[];
  atr?: number;
  rr_ratio?: number;
  correlation_count?: number;
  lot_multiplier?: number;
  filtered_out?: boolean;
  published_at?: number;
  // F5: multi-horizon + macro
  bias?: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  master_score?: number;
  horizon_scores?: Record<string, HorizonScore>;
  macro_risk_off?: boolean;
  macro_reasons?: string[];
  macro_confidence_multiplier?: number;
  macro_lot_multiplier?: number;
}

export interface HorizonScore {
  timeframe: string;
  bias: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  score: number;
  components?: Record<string, number>;
}

export interface MacroAssessment {
  risk_off: boolean;
  reasons: string[];
  confidence_multiplier: number;
  lot_multiplier: number;
}

export interface SymbolAnalysis {
  symbol: string;
  master_bias: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  master_score: number;
  horizons: Record<string, HorizonScore>;
  macro: MacroAssessment;
  ts?: number;
  error?: string;
}

export interface OrchestratorSignalsResponse {
  count: number;
  limit: number;
  items: OrchestratorPublishedSignal[];
}
