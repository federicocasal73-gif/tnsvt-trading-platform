import { createContext, ReactNode, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { api, Signal, Trade, Position, CopyJob, Stats, UserProfile } from '../lib/api';
import { useAuth } from '../lib/auth';

export interface AppState {
  profile: UserProfile | null;
  signals: Signal[];
  positions: Position[];
  trades: Trade[];
  copyJobs: CopyJob[];
  copyStats: Stats | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

const AppCtx = createContext<AppState | null>(null);

export function useApp() {
  const c = useContext(AppCtx);
  if (!c) throw new Error('useApp outside AppProvider');
  return c;
}

export function AppProvider({ children }: { children: ReactNode }) {
  const { user, isAuthenticated } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [copyJobs, setCopyJobs] = useState<CopyJob[]>([]);
  const [copyStats, setCopyStats] = useState<Stats | null>(null);
  const mounted = useRef(true);

  const fetchAll = useCallback(async () => {
    if (!isAuthenticated || !user) return;
    setLoading(true);
    setError(null);
    try {
      // Helper: silently ignore downstream service errors (502/404/503) so
      // we don't spam the console or auto-logout when backend services are
      // simply not deployed yet. Only network/auth errors propagate.
      const safeGet = async <T,>(p: Promise<T>, fallback: T): Promise<T> => {
        try {
          return await p;
        } catch (e: any) {
          const msg = String(e?.message || '');
          if (/^HTTP (401|502|503|404)/.test(msg)) {
            console.debug(`[AppState] downstream unavailable: ${msg}`);
            return fallback;
          }
          throw e;
        }
      };

      const [prof, sig, pos, tr, cj, cs] = await Promise.allSettled([
        safeGet<UserProfile | null>(api.get<UserProfile>(`/users/${user.user_id}/profile`), null),
        safeGet<{ signals: Signal[] }>(api.get<{ signals: Signal[] }>('/signals'), { signals: [] }),
        safeGet<{ positions: Position[] }>(api.get<{ positions: Position[] }>('/risk/positions'), { positions: [] }),
        safeGet<{ executions: Trade[] }>(api.get<{ executions: Trade[] }>('/executions'), { executions: [] }),
        safeGet<{ jobs: CopyJob[]; total: number }>(api.get<{ jobs: CopyJob[]; total: number }>('/copy/jobs?limit=50'), { jobs: [], total: 0 }),
        safeGet<Stats | null>(api.get<Stats>('/copy/stats'), null),
      ]);

      if (!mounted.current) return;
      if (prof.status === 'fulfilled' && prof.value) setProfile(prof.value);
      if (sig.status === 'fulfilled') setSignals(sig.value.signals);
      if (pos.status === 'fulfilled') setPositions(pos.value.positions);
      if (tr.status === 'fulfilled') setTrades(tr.value.executions);
      if (cj.status === 'fulfilled') setCopyJobs(cj.value.jobs);
      if (cs.status === 'fulfilled' && cs.value) setCopyStats(cs.value);
    } catch (e: any) {
      if (mounted.current) setError(e.message);
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, [isAuthenticated, user]);

  useEffect(() => {
    mounted.current = true;
    if (isAuthenticated) fetchAll();
    else { setLoading(false); setProfile(null); setSignals([]); setPositions([]); setTrades([]); setCopyJobs([]); setCopyStats(null); }
    return () => { mounted.current = false; };
  }, [isAuthenticated, fetchAll]);

  useEffect(() => {
    if (!isAuthenticated) return;
    const interval = setInterval(fetchAll, 15000);
    return () => clearInterval(interval);
  }, [isAuthenticated, fetchAll]);

  return (
    <AppCtx.Provider value={{ profile, signals, positions, trades, copyJobs, copyStats, loading, error, refresh: fetchAll }}>
      {children}
    </AppCtx.Provider>
  );
}
