import { memo, useEffect, useState } from 'react';
import { ArrowUp, ArrowDown, DollarSign, Activity, TrendingUp, TrendingDown, BarChart3 } from 'lucide-react';
import { useApp } from '../state/AppStateProvider';
import { useBridge } from '../state/BridgeProvider';
import { useLatestTicks } from '../lib/tickStream';
import { api } from '../lib/api';
import { cls, fmtUsd, fmtPct, fmtDate } from '../utils/format';

export const DashboardPage = memo(function DashboardPage() {
  const app = useApp();
  const bridge = useBridge();
  const { signals = [], positions = [], trades = [], metrics, loading = false } = app;
  const { latest: latestTicks, state: tickState } = useLatestTicks();

  const [orchestratorStats, setOrchestratorStats] = useState<{ paused: boolean; drawdown: number; open_positions: number; pending_signals: number } | null>(null);

  useEffect(() => {
    const fetchOrch = async () => {
      try {
        const s = await api.orchestrator.stats();
        setOrchestratorStats({
          paused: s.paused,
          drawdown: s.portfolio.drawdown,
          open_positions: s.portfolio.open_positions,
          pending_signals: s.pending_signals,
        });
      } catch { /* silent */ }
    };
    fetchOrch();
    const id = setInterval(fetchOrch, 10000);
    return () => clearInterval(id);
  }, []);

  const totalPnl = trades.filter(t => t.status === 'closed').reduce((s, t) => s + (t.pnl || 0), 0);
  const winTrades = trades.filter(t => t.status === 'closed' && (t.pnl || 0) > 0).length;
  const lossTrades = trades.filter(t => t.status === 'closed' && (t.pnl || 0) < 0).length;
  const totalClosed = winTrades + lossTrades;
  const winRate = totalClosed > 0 ? winTrades / totalClosed : 0;

  const recentSignals = signals.slice(-5).reverse();
  const openPos = positions.filter(p => p.status === 'open');
  const recentTrades = trades.slice(-10).reverse();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">Dashboard</h2>
        <div className="flex items-center gap-3">
          {orchestratorStats && (
            <button
              type="button"
              onClick={async () => {
                try {
                  if (orchestratorStats.paused) {
                    await api.orchestrator.resume();
                  } else {
                    await api.orchestrator.pause();
                  }
                  const s = await api.orchestrator.stats();
                  setOrchestratorStats({
                    paused: s.paused,
                    drawdown: s.portfolio.drawdown,
                    open_positions: s.portfolio.open_positions,
                    pending_signals: s.pending_signals,
                  });
                } catch { /* silent */ }
              }}
              className={cls(
                'rounded px-3 py-1 text-xs font-semibold uppercase tracking-wider transition-colors',
                orchestratorStats.paused
                  ? 'bg-green-600/20 text-green-400 hover:bg-green-600/30'
                  : 'bg-yellow-600/20 text-yellow-400 hover:bg-yellow-600/30',
              )}
            >
              {orchestratorStats.paused ? '▶ RESUME' : '⏸ PAUSE'}
            </button>
          )}
        </div>
      </div>

      {loading && <div className="text-sm text-tnvs-muted">Loading...</div>}

      <div className="grid grid-cols-4 gap-4">
        <Card data-testid="kpi-pnl"     icon={DollarSign}   label="Total P&L"          value={fmtUsd(totalPnl)} color={totalPnl >= 0 ? 'text-tnvs-win' : 'text-tnvs-loss'} />
        <Card data-testid="kpi-balance" icon={Activity}     label="MT5 Balance"        value={bridge.account ? fmtUsd(bridge.account.balance) : '-'} />
        <Card data-testid="kpi-equity"  icon={TrendingUp}   label="MT5 Equity"         value={bridge.account ? fmtUsd(bridge.account.equity) : '-'} color={(bridge.account?.equity ?? 0) >= (bridge.account?.balance ?? 0) ? 'text-tnvs-win' : 'text-tnvs-loss'} />
        <Card data-testid="kpi-winrate" icon={TrendingDown} label="Win Rate"           value={fmtPct(winRate)} color={winRate >= 0.5 ? 'text-tnvs-win' : 'text-tnvs-warn'} />
        <Card data-testid="kpi-pos"     icon={Activity}     label="Open Positions"     value={String(bridge.openPositions)} />
        <Card data-testid="kpi-dd"      icon={BarChart3}    label="Orchestrator DD"    value={orchestratorStats ? fmtPct(orchestratorStats.drawdown * 100) : '-'} color={(orchestratorStats?.drawdown ?? 0) > 0.05 ? 'text-tnvs-warn' : 'text-tnvs-win'} />
        <Card data-testid="kpi-pending" icon={Activity}     label="Pending Signals"    value={String(orchestratorStats?.pending_signals ?? 0)} />
        <Card data-testid="kpi-signals" icon={TrendingDown} label="30d Signals"        value={String(signals.length)} />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="tnvs-card">
          <h3 className="mb-3 text-sm font-semibold text-white">Open Positions</h3>
          {openPos.length === 0 ? <Empty>No open positions</Empty> : (
            <table className="tnvs-table">
              <thead><tr><th>Symbol</th><th>Side</th><th>Qty</th><th>Entry</th><th>P&L</th></tr></thead>
              <tbody>
                {openPos.slice(0, 6).map(p => (
                  <tr key={p.id}>
                    <td className="font-medium">{p.symbol}</td>
                    <td><SideBadge side={p.side} /></td>
                    <td>{p.quantity}</td>
                    <td className="font-mono">{fmtUsd(p.entry_price)}</td>
                    <td className={cls('font-mono', p.unrealized_pnl >= 0 ? 'text-tnvs-win' : 'text-tnvs-loss')}>
                      {p.unrealized_pnl >= 0 ? '+' : ''}{fmtUsd(p.unrealized_pnl)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="tnvs-card">
          <h3 className="mb-3 text-sm font-semibold text-white">Recent Signals</h3>
          {recentSignals.length === 0 ? <Empty>No signals yet</Empty> : (
            <table className="tnvs-table">
              <thead><tr><th>Symbol</th><th>Action</th><th>Price</th><th>Conf</th><th>Time</th></tr></thead>
              <tbody>
                {recentSignals.map(s => (
                  <tr key={s.id}>
                    <td className="font-medium">{s.symbol}</td>
                    <td><ActionBadge action={s.action} /></td>
                    <td className="font-mono">{fmtUsd(s.entry_price)}</td>
                    <td>{s.confidence != null ? fmtPct(s.confidence * 100) : '-'}</td>
                    <td className="text-xs text-tnvs-muted">{fmtDate(s.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="tnvs-card">
          <h3 className="mb-3 text-sm font-semibold text-white">Recent Trades</h3>
          {recentTrades.length === 0 ? <Empty>No trades yet</Empty> : (
            <table className="tnvs-table">
              <thead>
                <tr><th>Symbol</th><th>Side</th><th>Entry</th><th>P&L</th><th>Status</th><th>Time</th></tr>
              </thead>
              <tbody>
                {recentTrades.slice(0, 8).map(e => (
                  <tr key={e.id}>
                    <td className="font-medium">{e.symbol}</td>
                    <td><SideBadge side={e.side} /></td>
                    <td className="font-mono">{fmtUsd(e.entry_price)}</td>
                    <td className={cls('font-mono', (e.pnl || 0) >= 0 ? 'text-tnvs-win' : 'text-tnvs-loss')}>{(e.pnl || 0) >= 0 ? '+' : ''}{fmtUsd(e.pnl || 0)}</td>
                    <td className={cls('text-xs', e.status === 'closed' ? 'text-tnvs-win' : 'text-tnvs-warn')}>{e.status.toUpperCase()}</td>
                    <td className="text-xs text-tnvs-muted">{fmtDate(e.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="tnvs-card">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">Live Prices</h3>
            <span data-testid="dashboard-tick-state" className="text-[10px] uppercase tracking-wider text-tnvs-dim">
              {tickState === 'open' ? 'streaming' : tickState}
            </span>
          </div>
          {Object.keys(latestTicks).length === 0 ? (
            <Empty>Waiting for ticks… (start price-feed)</Empty>
          ) : (
            <table className="tnvs-table" data-testid="dashboard-ticks">
              <thead>
                <tr><th>Symbol</th><th>Bid</th><th>Ask</th><th>Last</th><th>Source</th></tr>
              </thead>
              <tbody>
                {Object.values(latestTicks)
                  .sort((a, b) => a.symbol.localeCompare(b.symbol))
                  .slice(0, 8)
                  .map((t) => (
                    <tr key={t.symbol}>
                      <td className="font-medium">{t.symbol}</td>
                      <td className="font-mono">{fmtUsd(t.bid)}</td>
                      <td className="font-mono">{fmtUsd(t.ask)}</td>
                      <td className="font-mono">{fmtUsd(t.last)}</td>
                      <td className="text-xs text-tnvs-muted">{t.source}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
});

function Card({ icon: Icon, label, value, color, 'data-testid': testId }: { icon: React.ComponentType<{ className?: string }>; label: string; value: string; color?: string; 'data-testid'?: string }) {
  return (
    <div data-testid={testId} className="tnvs-card flex items-center gap-4">
      <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-white/[0.04]">
        <Icon className={cls('h-5 w-5', color || 'text-tnvs-muted')} />
      </div>
      <div className="min-w-0">
        <div className="text-xs text-tnvs-muted">{label}</div>
        <div className={cls('truncate font-mono text-lg font-semibold', color || 'text-white')}>{value}</div>
      </div>
    </div>
  );
}

function Empty({ children }: { children: string }) {
  return <div className="py-8 text-center text-sm text-tnvs-dim">{children}</div>;
}

function ActionBadge({ action }: { action: string }) {
  const color = action.toLowerCase() === 'buy' ? 'text-tnvs-win' : action.toLowerCase() === 'sell' ? 'text-tnvs-loss' : 'text-tnvs-warn';
  const Icon = action.toLowerCase() === 'buy' ? ArrowUp : ArrowDown;
  return <span className={cls('inline-flex items-center gap-1 text-xs font-medium', color)}><Icon className="h-3 w-3" />{action.toUpperCase()}</span>;
}

function SideBadge({ side }: { side: string }) {
  const color = side?.toLowerCase() === 'buy' || side?.toLowerCase() === 'long' ? 'text-tnvs-win' : 'text-tnvs-loss';
  return <span className={cls('text-xs font-medium', color)}>{side?.toUpperCase() || '-'}</span>;
}