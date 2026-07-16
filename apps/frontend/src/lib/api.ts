const BASE = '/api/v1';

function token(): string | null {
  try { return localStorage.getItem('tnsvt_token'); } catch { return null; }
}

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const t = token();
  if (t) headers['Authorization'] = `Bearer ${t}`;

  const res = await fetch(`${BASE}${path}`, { ...opts, headers: { ...headers, ...((opts?.headers as Record<string, string>) || {}) } });

  if (res.status === 401) {
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
