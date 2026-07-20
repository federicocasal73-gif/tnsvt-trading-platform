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

  // Auto-logout ONLY when the auth-service itself rejects our token.
  // A 401 from any other endpoint (downstream services that don't know
  // our token format, services temporarily unavailable, etc.) is "just" a
  // data unavailability and MUST NOT kick the user out — safeGet() in
  // AppStateProvider already swallows these for read-only dashboards.
  //
  // Public endpoints (login/register/refresh) take the regular error path.
  const isAuthValidation = path === '/api/v1/auth/me' || path === '/api/v1/auth/refresh';
  if (res.status === 401 && token() && isAuthValidation) {
    console.warn(`[api] 401 on auth validation ${path} - logging out`);
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
  },
  // ─── Admin (Sub-fase 3, K2) ─────────────────────────────────────
  admin: {
    tenants: (limit = 50, offset = 0) =>
      request<AdminTenant[]>(`/admin/tenants?limit=${limit}&offset=${offset}`),
    stats: () =>
      request<AdminStats>('/admin/stats'),
    tenantsDemo: () =>
      request<{ ok: boolean; tenants: AdminTenant[]; stats: AdminStats }>(`/admin/tenants_demo`),
    seedDemo: () =>
      request<{ ok: boolean; seeded?: number; skipped?: boolean }>(`/admin/seed_demo`, { method: 'POST' }),
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
