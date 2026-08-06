import { createContext, ReactNode, useContext, useState, useCallback, useEffect } from 'react';
import { api, renewToken, accessTokenExpiryMs } from './api';

const TOKEN_KEY = 'tnsvt_token';
const REFRESH_KEY = 'tnsvt_refresh';

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
  logout: () => Promise<void>;
  isAuthenticated: boolean;
  refreshProfile: () => Promise<void>;
}

const AuthCtx = createContext<AuthCtx | null>(null);

export function useAuth() {
  const c = useContext(AuthCtx);
  if (!c) throw new Error('useAuth outside AuthProvider');
  return c;
}

function decodeToken(t: string): AuthUser | null {
  try {
    let b64 = t.split('.')[1];
    b64 = b64.replace(/-/g, '+').replace(/_/g, '/');
    const pad = (4 - (b64.length % 4)) % 4;
    b64 += '='.repeat(pad);
    const payload = JSON.parse(atob(b64));
    return {
      user_id: payload.uid || payload.sub || payload.user_id || '',
      tenant_id: payload.tid || payload.tenant_id || '',
      email: payload.email || '',
      username: payload.username || '',
      role: payload.role || 'viewer',
    };
  } catch {
    return null;
  }
}

/** Verifica que el JWT sea valido, vigente y de tipo access. */
function isTokenValid(t: string): boolean {
  if (!t) return false;
  try {
    let b64 = t.split('.')[1];
    b64 = b64.replace(/-/g, '+').replace(/_/g, '/');
    const pad = (4 - (b64.length % 4)) % 4;
    b64 += '='.repeat(pad);
    const payload = JSON.parse(atob(b64));
    if (payload.type && payload.type !== 'access') return false;
    if (payload.exp && Date.now() / 1000 >= payload.exp) return false;
    return true;
  } catch {
    return false;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const existingToken = typeof window !== 'undefined' ? localStorage.getItem(TOKEN_KEY) : null;
  const initialUser = existingToken && isTokenValid(existingToken)
    ? decodeToken(existingToken)
    : null;

  const [state, setState] = useState<AuthState>({
    user: initialUser,
    loading: false,
    error: null,
  });

  // Cargar profile real desde /auth/me SOLO cuando se llama explicitamente
  // (no en mount automatico — evita spam de /auth/me en cada dashboard).
  const refreshProfile = useCallback(async () => {
    if (!api.token() || !isTokenValid(api.token()!)) return;
    try {
      const data = await api.auth.me();
      setState(s => ({
        ...s,
        user: {
          user_id: data.user_id,
          tenant_id: data.tenant_id,
          email: data.email,
          username: s.user?.username || '',
          role: data.role,
        },
        loading: false,
        error: null,
      }));
    } catch (e: any) {
      if (e?.message?.includes('401') || e?.message?.includes('Unauthorized')) {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(REFRESH_KEY);
        setState({ user: null, loading: false, error: null });
        window.location.href = '/login';
      }
    }
  }, []);

  // NOT: useEffect con refreshProfile en mount — eso causaba que /auth/me se
  // llamara cada vez que se monta el provider (que pasa en cada navegacion
  // entre paginas del shell). El usuario tiene un boton explicito en Settings
  // para forzar refresh.

  // Renovacion proactiva: agenda renovar el access token ~30s antes de que
  // venza (15 min). Evita los cientos de 401 reactivos y el re-login manual.
  useEffect(() => {
    if (!api.token()) return;
    const exp = accessTokenExpiryMs();
    if (exp <= Date.now()) return; // ya vencido; el flujo reactivo lo resuelve
    const SAFETY_MS = 30_000;
    const delay = Math.max(0, exp - Date.now() - SAFETY_MS);
    const t = setTimeout(() => {
      renewToken();
    }, Math.min(delay, 10 * 60 * 1000));
    return () => clearTimeout(t);
  }, [state.user, state.loading]);

  const login = useCallback(async (email: string, password: string) => {
    setState(s => ({ ...s, loading: true, error: null }));
    try {
      const data = await api.auth.login(email.trim(), password);
      if (!data.access_token) {
        throw new Error('Respuesta invalida del servidor');
      }
      localStorage.setItem(TOKEN_KEY, data.access_token);
      if (data.refresh_token) {
        localStorage.setItem(REFRESH_KEY, data.refresh_token);
      }
      const user: AuthUser = {
        user_id: data.user.id,
        tenant_id: data.user.tenant_id,
        email: data.user.email,
        username: data.user.username,
        role: data.user.role,
      };
      setState({ user, loading: false, error: null });
    } catch (e: any) {
      const msg = e?.message || 'Login failed';
      setState(s => ({ ...s, loading: false, error: msg }));
      throw e;
    }
  }, []);

  const logout = useCallback(async () => {
    const refreshToken = localStorage.getItem(REFRESH_KEY);
    try {
      await api.auth.logout(refreshToken || undefined);
    } catch {
      // best-effort
    }
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
    setState({ user: null, loading: false, error: null });
    window.location.href = '/login';
  }, []);

  return (
    <AuthCtx.Provider
      value={{
        ...state,
        login,
        logout,
        refreshProfile,
        isAuthenticated: !!state.user,
      }}
    >
      {children}
    </AuthCtx.Provider>
  );
}