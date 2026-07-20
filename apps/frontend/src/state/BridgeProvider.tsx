import { createContext, ReactNode, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { api, Mt5AccountSnapshot, Mt5PositionSnapshot, Metrics } from '../lib/api';

export interface BridgeState {
  account: Mt5AccountSnapshot | null;
  positions: Mt5PositionSnapshot[];
  openPositions: number;
  unrealizedPnl: number;
  metrics: Metrics | null;
  signalCopierOnline: boolean;
  signalCopierData: { connected: boolean; balance: number; equity: number; margin: number; profit: number; open_positions: number } | null;
  loading: boolean;
  error: string | null;
  lastUpdate: number;
  refresh: () => Promise<void>;
}

const BridgeCtx = createContext<BridgeState | null>(null);

export function useBridge() {
  const c = useContext(BridgeCtx);
  if (!c) throw new Error('useBridge outside BridgeProvider');
  return c;
}

export function BridgeProvider({ children }: { children: ReactNode }) {
  const [account, setAccount] = useState<Mt5AccountSnapshot | null>(null);
  const [positions, setPositions] = useState<Mt5PositionSnapshot[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [signalCopierOnline, setSignalCopierOnline] = useState(false);
  const [signalCopierData, setSignalCopierData] = useState<BridgeState['signalCopierData']>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<number>(0);
  const mounted = useRef(true);

  const fetchAll = useCallback(async () => {
    setError(null);
    try {
      const results = await Promise.allSettled([
        api.bridge.account(),
        api.bridge.positionsLive(),
        api.bridge.metrics(),
        api.bridge.signalCopierStatus(),
      ]);
      if (!mounted.current) return;

      if (results[0].status === 'fulfilled' && results[0].value?.ok) {
        setAccount(results[0].value.data);
      } else {
        setAccount(null);
      }

      if (results[1].status === 'fulfilled') {
        const arr = results[1].value?.data || [];
        setPositions(arr);
      }

      if (results[2].status === 'fulfilled') {
        setMetrics(results[2].value);
      }

      if (results[3].status === 'fulfilled' && results[3].value?.ok && results[3].value?.data?.connected) {
        setSignalCopierOnline(true);
        setSignalCopierData(results[3].value.data);
      } else {
        setSignalCopierOnline(false);
        setSignalCopierData(null);
      }

      setLastUpdate(Date.now());
    } catch (e: any) {
      if (mounted.current) setError(e.message);
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    fetchAll();
    const id = setInterval(fetchAll, 5000);
    return () => {
      mounted.current = false;
      clearInterval(id);
    };
  }, [fetchAll]);

  const openPositions = positions.length;
  const unrealizedPnl = positions.reduce((s, p) => s + (p.profit || 0), 0);

  return (
    <BridgeCtx.Provider
      value={{
        account,
        positions,
        openPositions,
        unrealizedPnl,
        metrics,
        signalCopierOnline,
        signalCopierData,
        loading,
        error,
        lastUpdate,
        refresh: fetchAll,
      }}
    >
      {children}
    </BridgeCtx.Provider>
  );
}
