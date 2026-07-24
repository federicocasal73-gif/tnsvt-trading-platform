import { useEffect, useState } from 'react';
import { ExternalLink, RefreshCw, Wallet, TrendingUp, TrendingDown, Activity, BarChart3, DollarSign, Percent, Shield, LayoutGrid, Layers } from 'lucide-react';
import { api, Metrics, EquityPoint, ChannelAgg, SymbolAgg, CalendarDay, Mt5AccountSnapshot, Mt5PositionSnapshot } from '../lib/api';
import { useBridge } from '../state/BridgeProvider';
import { cls } from '../utils/format';
import { EquityCurve } from '../components/EquityCurve';
import { KPIGrid } from '../components/KPIGrid';
import { ChannelTable } from '../components/ChannelTable';
import { SymbolTable } from '../components/SymbolTable';
import { CalendarHeatmap } from '../components/CalendarHeatmap';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { SkeletonGrid, SkeletonTable, Skeleton } from '../components/Skeleton';
import { useAdaptivePolling } from '../hooks/useAdaptivePolling';

type Status = 'checking' | 'online' | 'offline';

function AccountCard({ label, value, sub, icon: Icon, positive, negative, warning }: {
  label: string; value: string; sub?: string; icon: React.ElementType;
  positive?: boolean; negative?: boolean; warning?: boolean;
}) {
  const color = positive ? 'text-emerald-400' : negative ? 'text-red-400' : warning ? 'text-amber-400' : 'text-white';
  return (
    <div className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-3.5">
      <div className="flex items-center gap-2 text-tnvs-muted text-xs mb-1.5">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <div className={`text-lg font-semibold tabular-nums leading-tight ${color}`}>{value}</div>
      {sub && <div className="text-[10px] text-tnvs-muted mt-0.5">{sub}</div>}
    </div>
  );
}

export function Mt5DashboardPage() {
  const bridge = useBridge();
  const { selectedLogin, accounts } = bridge;
  const [account, setAccount] = useState<Mt5AccountSnapshot | null>(null);
  const [openCount, setOpenCount] = useState<number | null>(null);
  const [positions, setPositions] = useState<Mt5PositionSnapshot[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [equity, setEquity] = useState<EquityPoint[]>([]);
  const [byChannel, setByChannel] = useState<ChannelAgg[]>([]);
  const [bySymbol, setBySymbol] = useState<SymbolAgg[]>([]);
  const [calendar, setCalendar] = useState<CalendarDay[]>([]);
  const [positionsOpen, setPositionsOpen] = useState(false);
  const [bridgeStatus, setBridgeStatus] = useState<Status>('checking');
  const [accountAvailable, setAccountAvailable] = useState(false);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<number>(0);
  const [sinceDays, setSinceDays] = useState<number>(30);

  const fetchAll = async () => {
    const acc = selectedLogin ?? undefined;
    const results = await Promise.allSettled([
      api.bridge.metrics(),
      api.bridge.equityCurve(),
      api.bridge.byChannel(undefined, sinceDays),
      api.bridge.bySymbol(undefined, sinceDays),
      api.bridge.calendar(),
      api.bridge.account(acc),
      api.bridge.positionsLive(acc),
      api.bridge.trades(undefined, sinceDays),
    ]);
    if (results[0].status === 'fulfilled') {
      setMetrics(results[0].value);
      setBridgeStatus('online');
    }
    if (results[1].status === 'fulfilled') setEquity(results[1].value);
    if (results[2].status === 'fulfilled') setByChannel(results[2].value);
    if (results[3].status === 'fulfilled') setBySymbol(results[3].value);
    if (results[4].status === 'fulfilled') setCalendar(results[4].value);
    if (results[5].status === 'fulfilled' && results[5].value.ok) {
      setAccount(results[5].value.data);
      setAccountAvailable(true);
      setBridgeStatus('online');
    } else if (results[5].status === 'fulfilled' && !results[5].value.ok) {
      setBridgeStatus('offline');
    }
    if (results[6].status === 'fulfilled') {
      setOpenCount(results[6].value.count);
      setPositions(results[6].value.data || []);
    }
    setLoading(false);
    setLastRefresh(Date.now());
  };

  useEffect(() => {
    fetchAll();
  }, [selectedLogin]);

  useAdaptivePolling(fetchAll, { intervalMs: 5000, idleIntervalMs: 30000, pauseOnHidden: true });

  const secondsAgo = lastRefresh ? Math.max(0, Math.floor((Date.now() - lastRefresh) / 1000)) : null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-white">Dashboard MT5</h2>
          <span
            className={
              'inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-medium ' +
              (bridgeStatus === 'online' ? 'bg-emerald-500/10 text-emerald-400' :
               bridgeStatus === 'offline' ? 'bg-red-500/10 text-red-400' :
               'bg-amber-500/10 text-amber-400')
            }
          >
            <span className={'h-1.5 w-1.5 rounded-full ' + (bridgeStatus === 'online' ? 'bg-emerald-400' : bridgeStatus === 'offline' ? 'bg-red-400' : 'bg-amber-400')} />
            {bridgeStatus === 'online' ? 'Online' : bridgeStatus === 'offline' ? 'Offline' : 'Verificando...'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="inline-flex items-center rounded-md border border-tnvs-border bg-tnvs-surface text-[10px] overflow-hidden">
            {[7, 30, 90].map(d => (
              <button
                key={d}
                onClick={() => setSinceDays(d)}
                className={cls(
                  'px-2 py-1 transition-colors',
                  sinceDays === d
                    ? 'bg-tnvs-purple text-white'
                    : 'text-tnvs-muted hover:text-white'
                )}
              >
                {d}d
              </button>
            ))}
          </div>
          <button
            onClick={fetchAll}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-tnvs-muted hover:bg-white/[0.04] hover:text-white"
          >
            <RefreshCw className="h-3 w-3" />
            Refrescar
            {secondsAgo !== null && (
              <span className="text-[10px] text-tnvs-dim">· {secondsAgo}s</span>
            )}
          </button>
        </div>
      </div>

      {accounts.length > 1 && (
        <div className="mb-3 flex items-center gap-2 rounded-md border border-tnvs-purple/30 bg-tnvs-purple/5 px-3 py-2 text-xs text-tnvs-muted">
          <Layers className="h-3.5 w-3.5 text-tnvs-purple" />
          <span>
            Multi-cuenta: {accounts.length} cuentas configuradas. Cambiá la cuenta activa en el TopBar (selector <code className="text-tnvs-purple">Layers</code>) para ver datos individuales.
          </span>
        </div>
      )}

      {loading ? (
        <div className="space-y-6">
          <div>
            <Skeleton className="h-3 w-32 mb-2" />
            <SkeletonGrid count={5} />
          </div>
          <div className="rounded-lg border border-tnvs-border bg-tnvs-surface p-4">
            <Skeleton className="h-32 w-full" />
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2.5">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="rounded-lg border border-tnvs-border bg-tnvs-surface p-3.5">
                <Skeleton className="h-3 w-20 mb-2" />
                <Skeleton className="h-5 w-24" />
              </div>
            ))}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <SkeletonTable rows={4} cols={5} />
            <SkeletonTable rows={4} cols={3} />
          </div>
        </div>
      ) : (
        <>
          {/* Account Snapshot */}
          {accountAvailable && account && (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Wallet className="h-4 w-4 text-tnvs-muted" />
                <span className="text-xs font-medium text-tnvs-muted uppercase tracking-wider">Cuenta</span>
                {account.server && (
                  <span className="text-[10px] text-tnvs-muted/60">{account.server} · ID {account.login}</span>
                )}
                {openCount !== null && (
                  <button
                    onClick={() => setPositionsOpen(o => !o)}
                    className="text-[10px] text-tnvs-muted/60 hover:text-tnvs-cyan"
                  >
                    · {openCount} posición(es) abierta(s) {positionsOpen ? '▾' : '▸'}
                  </button>
                )}
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2.5">
                <AccountCard icon={DollarSign} label="Balance" value={`$${(account.balance ?? 0).toLocaleString()}`} />
                <AccountCard icon={TrendingUp} label="Equity" value={`$${(account.equity ?? 0).toLocaleString()}`}
                  positive={(account.equity ?? 0) >= (account.balance ?? 0)} negative={(account.equity ?? 0) < (account.balance ?? 0)} />
                <AccountCard icon={BarChart3} label="Margen" value={`$${(account.margin ?? 0).toLocaleString()}`}
                  sub={`Libre: $${(account.margin_free ?? 0).toLocaleString()}`} />
                <AccountCard icon={Shield} label="Nivel de Margen"
                  value={account.margin_level != null ? `${account.margin_level.toFixed(2)}%` : '—'}
                  positive={account.margin_level != null && account.margin_level > 200}
                  warning={account.margin_level != null && account.margin_level <= 200 && account.margin_level > 100}
                  negative={account.margin_level != null && account.margin_level <= 100} />
                <AccountCard icon={Activity} label="Flotante" value={`$${(account.profit ?? 0) >= 0 ? '+' : ''}${(account.profit ?? 0).toFixed(2)}`}
                  positive={(account.profit ?? 0) > 0} negative={(account.profit ?? 0) < 0}
                  sub={`Apalancamiento: 1:${account.leverage ?? 0}`} />
              </div>
              {positionsOpen && positions.length > 0 && (
                <div className="mt-3 rounded-lg border border-tnvs-border bg-tnvs-void overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-tnvs-border text-tnvs-muted text-[10px] uppercase">
                          <th className="px-3 py-2 text-left">Symbol</th>
                          <th className="px-3 py-2 text-left">Tipo</th>
                          <th className="px-3 py-2 text-right">Volumen</th>
                          <th className="px-3 py-2 text-right">Entry</th>
                          <th className="px-3 py-2 text-right">Current</th>
                          <th className="px-3 py-2 text-right">SL</th>
                          <th className="px-3 py-2 text-right">TP</th>
                          <th className="px-3 py-2 text-right">Profit</th>
                        </tr>
                      </thead>
                      <tbody>
                        {positions.map(p => (
                          <tr key={p.ticket} className="border-b border-tnvs-border/40 last:border-0">
                            <td className="px-3 py-2 font-mono">{p.symbol}</td>
                            <td className={cls('px-3 py-2', p.type === 'BUY' ? 'text-tnvs-win' : 'text-tnvs-loss')}>{p.type}</td>
                            <td className="px-3 py-2 text-right font-mono">{p.volume}</td>
                            <td className="px-3 py-2 text-right font-mono">{p.price_open?.toFixed(5)}</td>
                            <td className="px-3 py-2 text-right font-mono">{p.price_current?.toFixed(5)}</td>
                            <td className="px-3 py-2 text-right font-mono text-tnvs-muted">{p.sl ?? '—'}</td>
                            <td className="px-3 py-2 text-right font-mono text-tnvs-muted">{p.tp ?? '—'}</td>
                            <td className={cls('px-3 py-2 text-right font-mono', p.profit >= 0 ? 'text-tnvs-win' : 'text-tnvs-loss')}>
                              {p.profit >= 0 ? '+' : ''}${p.profit.toFixed(2)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}

          <ErrorBoundary title="Error en Equity Curve">
            <EquityCurve data={equity} />
          </ErrorBoundary>
          <ErrorBoundary title="Error en KPIs">
            <KPIGrid metrics={metrics} />
          </ErrorBoundary>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <ErrorBoundary title="Error en Por Canal">
              <ChannelTable rows={byChannel} />
            </ErrorBoundary>
            <ErrorBoundary title="Error en Por Simbolo">
              <SymbolTable rows={bySymbol} />
            </ErrorBoundary>
          </div>
          {calendar.length > 0 && (
            <ErrorBoundary title="Error en Calendario">
              <CalendarHeatmap data={calendar} year={new Date().getFullYear()} />
            </ErrorBoundary>
          )}
        </>
      )}
    </div>
  );
}
