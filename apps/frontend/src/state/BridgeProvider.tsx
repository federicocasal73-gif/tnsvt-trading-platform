import { createContext, ReactNode, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { api, Mt5AccountSnapshot, Mt5PositionSnapshot, Metrics } from '../lib/api';

export interface Mt5AccountSummary {
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
}

export interface AggregateData {
  total_balance: number;
  total_equity: number;
  total_pnl: number;
  total_open_positions: number;
}

export interface BridgeState {
  // Cuenta activa seleccionada (null = principal)
  selectedLogin: number | null;
  // Lista de cuentas MT5 conocidas
  accounts: Mt5AccountSummary[];
  aggregate: AggregateData;
  // Snapshot de la cuenta activa (legacy/principal por default)
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
  selectAccount: (login: number | null) => void;
}

const BridgeCtx = createContext<BridgeState | null>(null);

const ACC_STORAGE_KEY = 'tnsvt-selected-account';

function readSelectedLogin(): number | null {
  try {
    const v = localStorage.getItem(ACC_STORAGE_KEY);
    if (v && /^\d+$/.test(v)) return parseInt(v, 10);
  } catch {}
  return null;
}

export function useBridge() {
  const c = useContext(BridgeCtx);
  if (!c) throw new Error('useBridge outside BridgeProvider');
  return c;
}

export function BridgeProvider({ children }: { children: ReactNode }) {
  const [accounts, setAccounts] = useState<Mt5AccountSummary[]>([]);
  const [aggregate, setAggregate] = useState<AggregateData>({
    total_balance: 0,
    total_equity: 0,
    total_pnl: 0,
    total_open_positions: 0,
  });
  const [selectedLogin, setSelectedLoginState] = useState<number | null>(readSelectedLogin);

  const [account, setAccount] = useState<Mt5AccountSnapshot | null>(null);
  const [positions, setPositions] = useState<Mt5PositionSnapshot[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [signalCopierOnline, setSignalCopierOnline] = useState(false);
  const [signalCopierData, setSignalCopierData] = useState<BridgeState['signalCopierData']>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<number>(0);
  const mounted = useRef(true);

  const selectAccount = useCallback((login: number | null) => {
    setSelectedLoginState(login);
    try {
      if (login == null) localStorage.removeItem(ACC_STORAGE_KEY);
      else localStorage.setItem(ACC_STORAGE_KEY, String(login));
    } catch {}
  }, []);

  const fetchAll = useCallback(async () => {
    setError(null);
    try {
      const accParam = selectedLogin ?? undefined;
      const results = await Promise.allSettled([
        api.bridge.account(accParam),
        api.bridge.accountPositions(accParam),
        api.bridge.metrics(),
        api.bridge.signalCopierStatus(),
        api.bridge.accounts(),
      ]);
      if (!mounted.current) return;

      if (results[0].status === 'fulfilled' && results[0].value?.ok) {
        setAccount(results[0].value.data);
      } else {
        setAccount(null);
      }

      if (results[1].status === 'fulfilled') {
        const arr = (results[1].value as any)?.data || [];
        setPositions(arr);
      }

      if (results[2].status === 'fulfilled') {
        setMetrics(results[2].value);
      }

      if (results[3].status === 'fulfilled' && (results[3].value as any)?.ok && (results[3].value as any)?.data?.connected) {
        setSignalCopierOnline(true);
        setSignalCopierData((results[3].value as any).data);
      } else {
        setSignalCopierOnline(false);
        setSignalCopierData(null);
      }

      if (results[4].status === 'fulfilled' && (results[4].value as any)?.ok) {
        setAccounts((results[4].value as any).accounts || []);
        setAggregate((results[4].value as any).aggregate || aggregate);
      }

      setLastUpdate(Date.now());
    } catch (e: any) {
      if (mounted.current) setError(e.message);
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, [selectedLogin]);

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
        selectedLogin,
        accounts,
        aggregate,
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
        selectAccount,
      }}
    >
      {children}
    </BridgeCtx.Provider>
  );
}
