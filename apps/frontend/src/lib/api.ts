const BASE = '/api/v1';
const TOKEN_KEY = 'tnsvt_token';

function token(): string | null {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}

// Circuit breaker: por endpoint, contar fallos consecutivos.
// Despues de 3 fallos, marcar el endpoint como abierto por 30s.
// Mientras esta abierto, devolver el error inmediatamente sin intentar la llamada.
const _failCount = new Map<string, number>();
const _openUntil = new Map<string, number>();
const BREAKER_THRESHOLD = 3;
const BREAKER_COOLDOWN_MS = 30_000;
const REQUEST_TIMEOUT_MS = 8_000;

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

// ─── Auto-refresh (single-flight) ─────────────────────────────────────
// El access token vence a los 15 min. Cuando un request falla con 401 por
// expiracion, renovamos la sesion con el refresh token una sola vez (aunque
// varios requests fallen a la vez) y reintentamos. El backend ROTA el refresh
// token en /auth/refresh, por lo que hay que persistir el NUEVO refresh token.
const REFRESH_KEY = 'tnsvt_refresh';
let _refreshPromise: Promise<string | null> | null = null;

function _refresh(): Promise<string | null> {
  if (_refreshPromise) return _refreshPromise;
  const raw = localStorage.getItem(REFRESH_KEY);
  if (!raw) return Promise.resolve(null);
  _refreshPromise = _callRefresh(raw).finally(() => { _refreshPromise = null; });
  return _refreshPromise;
}

async function _callRefresh(rawRefresh: string): Promise<string | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    // Llamada directa (sin pasar por request()) para evitar recursion.
    const res = await fetch(`${BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: rawRefresh }),
      signal: controller.signal,
    });
    if (!res.ok) return null;
    const data = await res.json().catch(() => null);
    if (!data || !data.access_token) return null;
    localStorage.setItem(TOKEN_KEY, data.access_token);
    if (data.refresh_token) localStorage.setItem(REFRESH_KEY, data.refresh_token);
    return data.access_token;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

// Renovacion proactiva (usada por el AuthProvider para refrescar ANTES de
// que el access token venza). Reutiliza el single-flight de _refresh().
export function renewToken(): Promise<string | null> {
  return _refresh();
}

// Codifica el exp del access token (epoch ms) para que el AuthProvider pueda
// programar la renovacion proactiva. -1 si no hay token o es ilegible.
export function accessTokenExpiryMs(): number {
  const t = token();
  if (!t) return -1;
  try {
    const b64 = t.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const pad = (4 - (b64.length % 4)) % 4;
    const payload = JSON.parse(atob(b64 + '='.repeat(pad)));
    return typeof payload.exp === 'number' ? payload.exp * 1000 : -1;
  } catch {
    return -1;
  }
}

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  if (_isOpen(path)) {
    throw new Error(`Circuit open for ${path}`);
  }

  // Reintento unico: si el access token vencio (401), renovar sesion una vez
  // y re-enviar. Evita cientos de 401 hasta que el usuario haga re-login.
  let retried = false;
  for (;;) {
    const currentHeaders: Record<string, string> = { 'Content-Type': 'application/json' };
    const cur = token();
    if (cur) currentHeaders['Authorization'] = `Bearer ${cur}`;
    const curOpts: RequestInit = {
      ...opts,
      headers: { ...currentHeaders, ...((opts?.headers as Record<string, string>) || {}) },
      signal: undefined,
    };

    // Timeout por request: aborta el fetch si el bridge no responde en 8s.
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    curOpts.signal = controller.signal;

    let res: Response;
    try {
      res = await fetch(`${BASE}${path}`, curOpts);
    } catch (e: any) {
      clearTimeout(timer);
      _recordFailure(path);
      if (e?.name === 'AbortError') {
        throw new Error(`Timeout (${REQUEST_TIMEOUT_MS / 1000}s) para ${path}`);
      }
      throw e;
    }
    clearTimeout(timer);

    console.debug(`[api] ${opts?.method || 'GET'} ${path} -> ${res.status}`);

    // 401 en cualquier endpoint (excepto /auth/refresh): renovar sesion y
    // reintentar UNA vez con el access token nuevo.
    if (res.status === 401 && path !== '/auth/refresh' && !retried && token()) {
      const newToken = await _refresh();
      if (newToken) {
        retried = true;
        continue;
      }
      // Refresh fallo (refresh token expirado/revocado): sesion muerta.
      console.warn(`[api] 401 y refresh invalido en ${path} - logging out`);
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(REFRESH_KEY);
      window.location.href = '/login';
      throw new Error('Unauthorized');
    }

    // Segundo 401 tras el retry, o 401 en /auth/refresh: el token nuevo
    // tampoco sirve → sesion invalida. No reintentar mas.
    if (res.status === 401 && path === '/auth/me') {
      console.warn(`[api] 401 en ${path} - logging out`);
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(REFRESH_KEY);
      window.location.href = '/login';
      throw new Error('Unauthorized');
    }

    if (!res.ok) {
      if (res.status >= 500) _recordFailure(path);
      const body = await res.json().catch(() => ({ error: res.statusText }));
      throw new Error(body.error || `HTTP ${res.status}`);
    }
    _recordSuccess(path);
    return res.json();
  }
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body: unknown) => request<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
  del: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  raw: (path: string) => `${BASE}${path}`,
  token,
  // ─── Bridge Replicators (datos live de cuentas con copy_enabled=true) ──
  bridgeReplicators: {
    list: (tenantId?: string) =>
      request<{ ok: boolean; count: number; accounts: any[]; aggregate: any }>(
        `/bridge/replicators${tenantId ? `?tenant_id=${encodeURIComponent(tenantId)}` : ''}`
      ),
  },
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
    accountKillSwitch: (accountId: string, reason = 'admin_manual') =>
      request<{ ok: boolean; closed_positions: number; errors: string[]; account_id: string }>(
        `/accounts/${accountId}/kill-switch`,
        { method: 'POST', body: JSON.stringify({ reason }) },
      ),
    closeTicket: (ticket: string, accountId?: string) =>
      request<{ ok: boolean; ticket: string; filled_price?: number; filled_qty?: number; detail?: string }>(
        '/bridge/copier/close-ticket',
        { method: 'POST', body: JSON.stringify({ ticket, account_id: accountId }) },
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
  // ─── Community (capa Bot/Comunidad: encuestas + calendario) ──────
  community: {
    surveys: (status?: 'active' | 'closed') =>
      request<{ success: boolean; surveys: CommunitySurvey[] }>(
        `/bridge/community/surveys${status ? `?status=${status}` : ''}`,
      ),
    survey: (id: string) =>
      request<{ success: boolean; survey: CommunitySurvey }>(`/bridge/community/surveys/${id}`),
    createSurvey: (data: { title: string; options: string[]; channel_id?: number | null; close_date?: string }) =>
      request<{ success: boolean; survey: CommunitySurvey }>(
        '/bridge/community/surveys',
        { method: 'POST', body: JSON.stringify(data) },
      ),
    vote: (id: string, data: { user_id: number; chat_id?: number | null; option_selected: number }) =>
      request<{ success: boolean; result: { status: string; vote_id: string } }>(
        `/bridge/community/surveys/${id}/vote`,
        { method: 'POST', body: JSON.stringify(data) },
      ),
    closeSurvey: (id: string) =>
      request<{ success: boolean }>(`/bridge/community/surveys/${id}/close`, { method: 'POST' }),
    events: (opts?: { days?: number; impact?: number; currency?: string }) => {
      const params = new URLSearchParams();
      if (opts?.days) params.set('days', String(opts.days));
      if (opts?.impact) params.set('impact', String(opts.impact));
      if (opts?.currency) params.set('currency', opts.currency);
      const qs = params.toString();
      return request<{ success: boolean; events: CommunityEvent[] }>(
        `/bridge/community/events${qs ? `?${qs}` : ''}`,
      );
    },
    pendingActual: (maxMinutes = 120) =>
      request<{ success: boolean; events: CommunityEvent[] }>(
        `/bridge/community/events/pending-actual?max_minutes=${maxMinutes}`,
      ),
    setEventNotify: (id: string, enabled: boolean) =>
      request<{ success: boolean; notify_enabled: boolean }>(
        `/bridge/community/events/${id}/notify?enabled=${enabled}`,
        { method: 'POST' },
      ),
  },
  // ─── Admin (Sub-fase 3, K2) ─────────────────────────────────────
  admin: {
    tenants: (limit = 50, offset = 0) =>
      request<AdminTenant[]>(`/admin/tenants?limit=${limit}&offset=${offset}`),
    stats: () =>
      request<AdminStats>('/admin/stats'),
    create: (payload: TenantPayload) =>
      request<{ success: boolean; tenant: AdminTenant }>('/admin/tenants', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    update: (id: string, payload: Partial<TenantPayload>) =>
      request<{ success: boolean; tenant: AdminTenant }>(`/admin/tenants/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      }),
    remove: (id: string) =>
      request<{ success: boolean }>(`/admin/tenants/${id}`, { method: 'DELETE' }),
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
  // ─── Accounts (account-manager :8510) ─────────────────────────
  accounts: {
    list: () => request<{
      ok?: boolean;
      accounts: Array<{
        id: string;
        login: number;
        alias: string | null;
        name: string | null;
        server: string;
        broker: string;
        status: string;
        balance: number | null;
        equity: number | null;
        profit: number | null;
        open_positions: number;
        updated_at: string | null;
        copy_enabled: boolean;
      }>;
      aggregate: { total_balance: number; total_equity: number; total_pnl: number; total_open_positions: number; active_accounts: number };
    }>('/accounts'),
    listReplicators: () => request<{
      ok?: boolean;
      accounts: Array<{
        id: string;
        login: number;
        alias: string | null;
        name: string | null;
        server: string;
        broker: string;
        status: string;
        copy_enabled: boolean;
        open_positions: number;
      }>;
      aggregate: { total_balance: number; total_equity: number; total_pnl: number; total_open_positions: number; active_accounts: number };
    }>('/accounts/replicators'),
    setCopyEnabled: (id: string, enabled: boolean) =>
      request<{ id: string; copy_enabled: boolean }>(`/accounts/${id}`, {
        method: 'PUT', body: JSON.stringify({ copy_enabled: enabled }),
      }),
    create: (data: { login: number; password: string; server: string; broker?: string; alias?: string; name?: string }) =>
      request<{ id: string; login: number; server: string; broker: string; status: string; created_at: string }>('/accounts', {
        method: 'POST', body: JSON.stringify(data),
      }),
    update: (id: string, data: { alias?: string; name?: string; status?: 'active' | 'paused' | 'disabled'; copy_enabled?: boolean }) =>
      request<{ id: string; alias: string | null; name: string | null; status: string; copy_enabled?: boolean }>(`/accounts/${id}`, {
        method: 'PUT', body: JSON.stringify(data),
      }),
    delete: (id: string) =>
      request<{ status: string; id: string }>(`/accounts/${id}`, { method: 'DELETE' }),
    changePassword: (id: string, newPassword: string) =>
      request<{ status: string; id: string }>(`/accounts/${id}/change-password`, {
        method: 'POST', body: JSON.stringify({ new_password: newPassword }),
      }),
    // Snapshot upload (internal: mt5-connector pushes live data here)
    pushSnapshot: (id: string, snap: { balance: number; equity: number; margin?: number; free_margin?: number; profit: number; open_positions: number; connected: boolean }) =>
      request<{ status: string }>(`/accounts/${id}/snapshot`, {
        method: 'POST', body: JSON.stringify(snap),
      }),
  },
  // ─── Signals (signal-engine :8003) ─────────────────────────
  // Sprint 2.2 + 2.3: inyección manual y webhook.
  signals: {
    list: (limit = 50, offset = 0) =>
      request<{ signals: any[]; total: number; limit: number; offset: number }>(`/signals?limit=${limit}&offset=${offset}`),
    get: (id: string) =>
      request<any>(`/signals/${id}`),
    submit: (data: any) =>
      request<any>('/signals', { method: 'POST', body: JSON.stringify(data) }),
    // Sprint 2.2: para el botón "Crear señal" en Signals.tsx / admin
    manual: (data: {
      symbol: string;
      action: 'BUY' | 'SELL';
      entry_price?: number;
      stop_loss: number;
      take_profits: number[];
      lot_size?: number;
      lot_mode?: 'fixed' | 'proportional' | 'risk_based';
      risk_percent?: number;
      comment?: string;
      account_id?: string;
    }) =>
      request<any>('/signals/manual', { method: 'POST', body: JSON.stringify(data) }),
    // Sprint 2.3: para proveedores externos (TradingView, etc.) — el
    // gateway ya inyecta X-API-Key desde la API key del provider.
    webhook: (provider: string, data: any) =>
      request<any>('/signals/webhook', {
        method: 'POST',
        headers: { 'X-Webhook-Provider': provider },
        body: JSON.stringify(data),
      }),
    parsePreview: (text: string) =>
      request<any>('/signals/parse', { method: 'POST', body: JSON.stringify({ text }) }),
    stats: () => request<any>('/signals/stats'),
  },
  // ─── Copy Trading (Go service :8005) ─────────────────────────
  copy: {
    listGroups: (limit = 50, offset = 0) =>
      request<{ groups: CopyGroup[]; total: number; limit: number; offset: number }>(`/copy/groups?limit=${limit}&offset=${offset}`),
    createGroup: (data: { name: string; description?: string; filters?: { symbols?: string[]; actions?: string[]; min_confidence?: number } }) =>
      request<CopyGroup>('/copy/groups', { method: 'POST', body: JSON.stringify(data) }),
    getGroup: (id: string) => request<CopyGroup>(`/copy/groups/${id}`),
    updateGroup: (id: string, data: Partial<CopyGroup>) =>
      request<CopyGroup>(`/copy/groups/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    deleteGroup: (id: string) => request<{ status: string; id: string }>(`/copy/groups/${id}`, { method: 'DELETE' }),

    listAccounts: (groupId: string, limit = 50, offset = 0) =>
      request<{ accounts: CopyAccount[]; total: number; limit: number; offset: number }>(`/copy/groups/${groupId}/accounts?limit=${limit}&offset=${offset}`),
    createAccount: (groupId: string, data: { name: string; broker: string; account_id: string; lot_mode: 'fixed' | 'proportional' | 'risk_based'; lot_size?: number; lot_multiplier?: number; risk_percent?: number; invert_side?: boolean; symbol_suffix?: string; enabled?: boolean }) =>
      request<CopyAccount>(`/copy/groups/${groupId}/accounts`, { method: 'POST', body: JSON.stringify(data) }),
    getAccount: (id: string) => request<CopyAccount>(`/copy/accounts/${id}`),
    updateAccount: (id: string, data: Partial<CopyAccount>) =>
      request<CopyAccount>(`/copy/accounts/${id}`, { method: 'PUT', body: JSON.stringify(data) }),

    listJobs: (limit = 50, offset = 0) =>
      request<{ jobs: CopyJob[]; total: number; limit: number; offset: number }>(`/copy/jobs?limit=${limit}&offset=${offset}`),
    getStats: () => request<{ total_jobs: number; successful_jobs: number; failed_jobs: number; success_rate: number; by_group: Record<string, number>; by_account: Record<string, number>; by_status: Record<string, number> }>('/copy/stats'),
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
  // ─── News Analyzer (F3) ─────────────────────────────────────────
  news: {
    latest: (opts?: { category?: string; limit?: number; minStars?: number; sentiment?: string }) => {
      const params = new URLSearchParams();
      params.set('category', opts?.category || 'all');
      params.set('limit', String(opts?.limit ?? 50));
      params.set('min_stars', String(opts?.minStars ?? 0));
      if (opts?.sentiment && opts.sentiment !== 'all') params.set('sentiment', opts.sentiment);
      return request<NewsListResponse>(`/news/latest?${params}`);
    },
    bySymbol: (symbol: string, limit = 20) =>
      request<NewsListResponse>(`/news/by-symbol/${symbol}?limit=${limit}`),
    sentimentSummary: () => request<NewsSentimentSummary>('/news/sentiment-summary'),
    refresh: () =>
      request<{ refreshed: boolean; count: number }>('/news/refresh', { method: 'POST' }),
  },
  // ─── Macro Dashboard (F2) ──────────────────────────────────────
  macro: {
    indicators: () => request<MacroIndicatorsResponse>('/macro/indicators'),
    marketState: () => request<MacroMarketState>('/macro/market-state'),
    radar: (days = 7) => request<MacroCalendarResponse>(`/macro/radar?days=${days}`),
    liquidity: () => request<MacroLiquidity>('/macro/liquidity'),
  },
  // ─── Auth (F1.3) ──────────────────────────────────────────────
  auth: {
    login: (email: string, password: string) =>
      request<LoginResponse>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      }),
    register: (payload: RegisterRequest) =>
      request<RegisterResponse>('/auth/register', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    me: () => request<AuthMeResponse>('/auth/me'),
    refresh: (refreshToken: string) =>
      request<LoginResponse>('/auth/refresh', {
        method: 'POST',
        body: JSON.stringify({ refresh_token: refreshToken }),
      }),
    logout: (refreshToken?: string) =>
      request<{ message: string }>('/auth/logout', {
        method: 'POST',
        body: JSON.stringify({ refresh_token: refreshToken || '' }),
      }),
    changePassword: (currentPassword: string, newPassword: string) =>
      request<{ message: string }>('/auth/password/change', {
        method: 'POST',
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      }),
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

// ─── Account Manager (cuenta MT5 registrada) ─────────────────
export interface AccountManagerAccount {
  id: string;
  tenant_id: string;
  login: number;
  server: string;
  broker: string;
  alias?: string | null;
  name?: string | null;
  status: string;
  copy_enabled: boolean;
  open_positions?: number;
  created_at?: string;
  updated_at?: string;
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

export interface CopyGroup {
  id: string;
  tenant_id: string;
  name: string;
  description?: string;
  filters: { symbols?: string[]; actions?: string[]; min_confidence?: number };
  total_accounts: number;
  success_rate: number;
  created_at: string;
  updated_at: string;
}

export interface CopyAccount {
  id: string;
  group_id: string;
  name: string;
  broker: string;
  account_id: string;  // MT5 login numérico
  lot_mode: 'fixed' | 'proportional' | 'risk_based';
  lot_size: number;
  lot_multiplier: number;
  risk_percent: number;
  override_sl: boolean;
  override_sl_pips?: number;
  override_tp: boolean;
  override_tp_pips?: number;
  invert_side: boolean;
  symbol_suffix: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface CopyStats {
  total_groups: number;
  total_accounts: number;
  total_jobs: number;
  success_rate: number;
  jobs_24h: number;
  jobs_24h_success: number;
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

export type TenantPlan = 'trimestral' | 'semestral' | 'anual';
export type TenantStatus = 'active' | 'trial' | 'suspended';

export interface AdminTenant {
  id: string;
  name: string;
  slug: string | null;
  email: string | null;
  plan: TenantPlan;
  status: TenantStatus;
  price_usd: number | null;
  price_ars: string | null;
  max_users: number;
  max_signals_per_day: number;
  started_at: string | null;
  expires_at: string | null;
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

export interface TenantPayload {
  name: string;
  plan: TenantPlan;
  email?: string;
  status?: TenantStatus;
  price_usd?: number;
  price_ars?: string;
  expires_at?: string;
  max_users?: number;
  max_signals_per_day?: number;
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
  drivers?: Array<{
    name: string;
    status: string;
    detail: string;
  }>;
  price_range?: {
    current: number;
    low: number;
    high: number;
    midpoint: number;
    zone: 'barata' | 'fair' | 'cara';
    barata_pct: number;
    cara_pct: number;
  };
  playbook_daily?: {
    horizon: string;
    title: string;
    action: string;
    zone?: string;
    entry?: number;
    sl?: number;
    tp1?: number;
    tp2?: number;
    invalidation?: string;
    size_pct?: number;
    horizon_days?: string;
  };
  playbook_intraday?: {
    horizon: string;
    title: string;
    action: string;
    entry?: number;
    stop?: number;
    tp1?: number;
    tp2?: number;
    entry_detail?: string;
    invalidation?: string;
    size_pct?: number;
    reglas?: string;
  };
  divergences?: Array<{
    timeframe: string;
    type: string;
    score: number;
    detail: string;
  }>;
  narrative?: string;
}

export interface OrchestratorSignalsResponse {
  count: number;
  limit: number;
  items: OrchestratorPublishedSignal[];
}

// ─── News Analyzer (F3) ─────────────────────────────────────────────

export interface NewsItem {
  id: string;
  title: string;
  description: string;
  url: string;
  source: string;
  category: string;
  published_at?: string;
  fetched_at: string;
  sentiment_score: number;
  sentiment_label: 'POSITIVE' | 'NEUTRAL' | 'NEGATIVE';
  star_rating: number;
  categories: string[];
  affected_symbols: string[];
  reactions: Record<string, string>;
}

export interface NewsListResponse {
  count: number;
  items: NewsItem[];
}

export interface NewsSentimentBySymbol {
  symbol: string;
  sentiment_score: number;
  sentiment_label: string;
  news_count: number;
  last_updated: string;
}

export interface NewsSentimentSummary {
  overall_score: number;
  overall_label: string;
  by_symbol: NewsSentimentBySymbol[];
  by_category: Record<string, number>;
  total_news: number;
  last_updated: string;
}

// ─── Macro Dashboard (F2) ─────────────────────────────────────────

export interface MacroIndicator {
  key: string;
  name: string;
  country: string;
  previous: string;
  actual: string;
  forecast: string;
  unit: string;
  direction: 'up' | 'down' | 'flat';
  vs_forecast: 'beat' | 'miss' | 'in-line' | 'unknown';
  release_date: string;
  next_release: string;
  fetched_at: string;
}

export interface MacroIndicatorsResponse {
  count: number;
  items: MacroIndicator[];
}

export interface MacroMarketTag {
  tag: string;
  label: string;
  value: string | number | null;
  source: string;
}

export interface MacroMarketState {
  tags: MacroMarketTag[];
  narrative: string;
  fetched_at: string;
}

export interface MacroCalendarEvent {
  date: string;
  time: string;
  currency: string;
  event: string;
  forecast: string;
  previous: string;
  impact: 'Low' | 'Medium' | 'High';
}

export interface MacroCalendarResponse {
  count: number;
  days: number;
  events: MacroCalendarEvent[];
}

export interface MacroLiquidity {
  tga_billion: number | null;
  rrp_billion: number | null;
  fetched_at: string;
}

// ─── Auth (F1.3) ────────────────────────────────────────────────

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: {
    id: string;
    tenant_id: string;
    email: string;
    username: string;
    role: string;
    status: string;
    two_factor_enabled: boolean;
    email_verified: boolean;
    created_at?: string;
  };
  tenant: {
    id: string;
    name: string;
    slug: string;
    plan: string;
    status: string;
  };
}

export interface RegisterRequest {
  email: string;
  username: string;
  password: string;
  tenant_name: string;
  full_name?: string;
}

export interface RegisterResponse {
  access_token?: string;
  refresh_token?: string;
  user?: LoginResponse['user'];
  tenant?: LoginResponse['tenant'];
  message?: string;
}

export interface AuthMeResponse {
  user_id: string;
  tenant_id: string;
  email: string;
  role: string;
  permissions: string[];
}

// ─── Community (capa Bot/Comunidad) ──────────────────────────────

export interface CommunitySurvey {
  id: string;
  title: string;
  options: string[];
  channel_id: number | null;
  created_by: number | null;
  close_date: string | null;
  is_active: number;
  created_at: string;
  votes: Array<{ option_selected: number; count: number }>;
}

export interface CommunityEvent {
  id: string;
  source: string;
  currency: string | null;
  indicator: string;
  announcement_dt: string | null;
  previous: string | null;
  forecast: string | null;
  actual: string | null;
  impact: number;
  notify_enabled: number;
  notified_pre: number;
  notified_actual: number;
  created_at: string;
}
