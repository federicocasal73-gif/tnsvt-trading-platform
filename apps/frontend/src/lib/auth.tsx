import { createContext, ReactNode, useContext, useState, useCallback } from 'react';
import { api } from './api';

interface AuthUser {
  user_id: string;
  tenant_id: string;
  email: string;
  username: string;
  role: string;
}

interface AuthState {
  user: AuthUser | null;
  loading: boolean;
  error: string | null;
}

interface AuthCtx extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthCtx = createContext<AuthCtx | null>(null);

export function useAuth() {
  const c = useContext(AuthCtx);
  if (!c) throw new Error('useAuth outside AuthProvider');
  return c;
}

function decodeToken(t: string): AuthUser | null {
  try {
    const payload = JSON.parse(atob(t.split('.')[1]));
    return {
      user_id: payload.uid || payload.sub || payload.user_id,
      tenant_id: payload.tid || payload.tenant_id || '00000000-0000-0000-0000-000000000001',
      email: payload.email || '',
      username: payload.username || '',
      role: payload.role || 'viewer',
    };
  } catch { return null; }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const existing = api.token() ? decodeToken(api.token()!) : null;
  const [state, setState] = useState<AuthState>({ user: existing, loading: false, error: null });

  const login = useCallback(async (email: string, password: string) => {
    setState(s => ({ ...s, loading: true, error: null }));
    try {
      const res = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: 'Login failed' }));
        throw new Error(err.error || 'Login failed');
      }
      const data = await res.json();
      const t = data.access_token || data.token;
      localStorage.setItem('tnsvt_token', t);
      const user = decodeToken(t);
      setState({ user, loading: false, error: null });
    } catch (e: any) {
      setState(s => ({ ...s, loading: false, error: e.message }));
      throw e;
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('tnsvt_token');
    setState({ user: null, loading: false, error: null });
    // Hard redirect so the router unmounts the protected shell.
    window.location.href = '/login';
  }, []);

  return (
    <AuthCtx.Provider value={{ ...state, login, logout, isAuthenticated: !!state.user }}>
      {children}
    </AuthCtx.Provider>
  );
}
