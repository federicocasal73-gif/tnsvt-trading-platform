import { createContext, ReactNode, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { api, Signal, Trade, Position, Metrics } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useBridge } from './BridgeProvider';

export interface AppState {
  profile: { user_id: string; tenant_id: string; full_name: string; avatar_url?: string; timezone: string; language: string } | null;
  signals: Signal[];
  positions: Position[];
  trades: Trade[];
  metrics: Metrics | null;
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

function normalizeSignal(s: any): Signal {
  const ts = s.published_at ? new Date(s.published_at * 1000).toISOString() : new Date().toISOString();
  return {
    id: s.id ?? `${s.symbol}-${s.published_at}`,
    symbol: s.symbol,
    action: s.action,
    lot_size: s.lot_size ?? 0,
    entry_price: 0,
    stop_loss: s.stop_loss ?? 0,
    take_profit: s.take_profits?.[0] ?? 0,
    confidence: s.confidence ?? 0,
    source: 'orchestrator',
    status: s.filtered_out ? 'filtered' : 'open',
    created_at: ts,
  };
}

function normalizePosition(p: any): Position {
  return {
    id: String(p.ticket),
    symbol: p.symbol,
    side: p.type === 'BUY' ? 'buy' : 'sell',
    quantity: p.volume,
    entry_price: p.price_open,
    current_price: p.price_current,
    stop_loss: p.sl ?? 0,
    take_profit: p.tp ?? 0,
    unrealized_pnl: p.profit,
    status: 'open',
    created_at: p.time,
  };
}

function normalizeTrade(t: any): Trade {
  return {
    id: String(t.id),
    symbol: t.symbol,
    side: t.action === 'BUY' ? 'buy' : 'sell',
    quantity: t.volume,
    entry_price: t.open_price,
    stop_loss: t.sl ?? 0,
    take_profit: t.tp ?? 0,
    status: t.status === 'OPEN' ? 'open' : 'closed',
    ticket: String(t.ticket),
    pnl: t.pnl,
    created_at: t.opened_at,
    closed_at: t.closed_at,
  };
}

export function AppProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  // Reutilizar data de BridgeProvider (no re-fetchear lo mismo)
  const bridge = useBridge();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [profile, setProfile] = useState<AppState['profile']>(null);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const mounted = useRef(true);
  // Track si BridgeProvider ya cargo data para evitar fetch duplicado
  const bridgeReady = useRef(false);

  const fetchAll = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError(null);
    try {
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

      const profileData = {
        user_id: user.user_id,
        tenant_id: user.tenant_id,
        full_name: user.username || user.email || '',
        email: user.email,
        username: user.username,
        role: user.role,
        timezone: 'UTC',
        language: 'es',
      };

      // Solo pedimos lo que BridgeProvider NO tiene: signals (viene de orchestrator)
      // y metrics (BridgeProvider tiene uno tambien, lo podriamos reutilizar pero
      // por simplicidad lo dejamos). LivePositions y trades los sincronizamos desde
      // BridgeContext via useEffect abajo.
      const results = await Promise.allSettled([
        Promise.resolve(profileData),
        safeGet<{ items: any[] }>(api.orchestrator.signals(50), { items: [] }),
        safeGet<Metrics | null>(api.bridge.metrics(), null),
      ]);

      if (!mounted.current) return;

      setProfile(profileData);
      setSignals((results[1].status === 'fulfilled' ? results[1].value.items : []).map(normalizeSignal));
      setMetrics(results[2].status === 'fulfilled' ? results[2].value : null);
      bridgeReady.current = true;
    } catch (e: any) {
      if (mounted.current) setError(e.message);
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, [user]);

  // Sincronizar positions y trades desde BridgeContext (sin refetch)
  useEffect(() => {
    if (!bridgeReady.current) return;
    setPositions(bridge.positions.map(normalizePosition));
    setTrades([]);  // BridgeProvider no expone trades; vaciamos
  }, [bridge.positions, bridge.lastUpdate]);

  useEffect(() => {
    mounted.current = true;
    if (user) fetchAll();
    else { setLoading(false); setProfile(null); setSignals([]); setPositions([]); setTrades([]); setMetrics(null); }
    return () => { mounted.current = false; };
  }, [user, fetchAll]);

  // Polling cada 60s (era 15s). signals del orchestrator no necesitan refresh de 15s.
  useEffect(() => {
    if (!user) return;
    const interval = setInterval(fetchAll, 60000);
    return () => clearInterval(interval);
  }, [user, fetchAll]);

  return (
    <AppCtx.Provider value={{ profile, signals, positions, trades, metrics, loading, error, refresh: fetchAll }}>
      {children}
    </AppCtx.Provider>
  );
}