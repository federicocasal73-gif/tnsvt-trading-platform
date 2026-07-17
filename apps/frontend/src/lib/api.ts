const BASE = '/api/v1';

function token(): string | null {
  try { return localStorage.getItem('tnsvt_token'); } catch { return null; }
}

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const t = token();
  if (t) headers['Authorization'] = `Bearer ${t}`;

  const res = await fetch(`${BASE}${path}`, { ...opts, headers: { ...headers, ...((opts?.headers as Record<string, string>) || {}) } });

  // Debug: log every response so we can diagnose auto-logout issues.
  console.debug(`[api] ${opts?.method || 'GET'} ${path} -> ${res.status}`);

  // Auto-logout only when 401 hits a protected endpoint (user already has
  // a token in localStorage). Public endpoints like /auth/login or
  // /auth/register return 401 for bad credentials and should NOT trigger
  // a logout/redirect.
  if (res.status === 401 && token() && !isPublicAuthPath(path)) {
    console.warn(`[api] 401 on protected ${path} - logging out`);
    localStorage.removeItem('tnsvt_token');
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(body.error || `HTTP ${res.status}`);
  }
  return res.json();
}

function isPublicAuthPath(path: string): boolean {
  return /^\/auth\/(login|register|refresh)/.test(path);
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
    metrics: () => request<Metrics>('/api/v1/bridge/analytics/metrics'),
    equityCurve: () => request<EquityPoint[]>('/api/v1/bridge/analytics/equity-curve'),
    byChannel: () => request<ChannelAgg[]>('/api/v1/bridge/analytics/by-channel'),
    bySymbol: () => request<SymbolAgg[]>('/api/v1/bridge/analytics/by-symbol'),
    livePositions: () => request<LivePosition[]>('/api/v1/bridge/analytics/live-positions'),
    trades: (status?: string) => request<LivePosition[]>(`/api/v1/bridge/analytics/trades${status ? `?status=${status}` : ''}`),
    config: () => request<BotConfig>('/api/v1/bridge/config'),
    updateConfig: (patch: Partial<BotConfig>) =>
      request<{ ok: boolean; updated_keys: string[] }>(
        '/api/v1/bridge/config',
        { method: 'POST', body: JSON.stringify(patch) },
      ),
    triggerScan: () =>
      request<{ accepted: boolean; request_id: string }>(
        '/api/v1/bridge/telegram/scan',
        { method: 'POST' },
      ),
    scanResult: () =>
      request<ScanResult>('/api/v1/bridge/telegram/channels'),
    controlState: () =>
      request<{ status: string; updated_at?: string }>(
        '/api/v1/bridge/control/state',
      ),
    control: (action: 'start' | 'stop' | 'wait_config') =>
      request<{ ok: boolean; status: string }>(
        '/api/v1/bridge/control',
        { method: 'POST', body: JSON.stringify({ action }) },
      ),
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
}

export interface ScanResult {
  status: 'NO_SCAN' | 'PENDING' | 'OK' | 'ERROR';
  error?: string;
  completed_at?: string;
  request_id?: string;
  data?: ChannelProfile[];
}
