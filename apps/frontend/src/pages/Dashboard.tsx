import { memo } from 'react';
import { ArrowUp, ArrowDown, DollarSign, Activity, TrendingUp, TrendingDown } from 'lucide-react';
import { useApp } from '../state/AppStateProvider';
import { cls, fmtUsd, fmtPct, fmtDate } from '../utils/format';

export const DashboardPage = memo(function DashboardPage() {
  const { signals, positions, trades, copyJobs, copyStats, loading } = useApp();

  const totalPnl = trades.filter(t => t.status === 'closed').reduce((s, t) => s + (t.pnl || 0), 0);
  const winTrades = trades.filter(t => t.status === 'closed' && (t.pnl || 0) > 0).length;
  const lossTrades = trades.filter(t => t.status === 'closed' && (t.pnl || 0) < 0).length;
  const totalClosed = winTrades + lossTrades;
  const winRate = totalClosed > 0 ? winTrades / totalClosed : 0;

  const recentSignals = signals.slice(-5).reverse();
  const openPos = positions.filter(p => p.status === 'open');
  const recentJobs = copyJobs.slice(0, 10);

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-white">Dashboard</h2>

      {loading && <div className="text-sm text-tnvs-muted">Loading...</div>}

      <div className="grid grid-cols-4 gap-4">
        <Card icon={DollarSign} label="Total P&L" value={fmtUsd(totalPnl)} color={totalPnl >= 0 ? 'text-tnvs-win' : 'text-tnvs-loss'} />
        <Card icon={TrendingUp} label="Win Rate" value={fmtPct(winRate)} color={winRate >= 0.5 ? 'text-tnvs-win' : 'text-tnvs-warn'} />
        <Card icon={Activity} label="Open Positions" value={String(openPos.length)} />
        <Card icon={TrendingDown} label="30d Signals" value={String(signals.length)} />
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
                    <td>{s.confidence != null ? fmtPct(s.confidence / 100) : '-'}</td>
                    <td className="text-xs text-tnvs-muted">{fmtDate(s.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div className="tnvs-card">
        <h3 className="mb-3 text-sm font-semibold text-white">Latest Copy Jobs</h3>
        {recentJobs.length === 0 ? <Empty>No copy jobs yet</Empty> : (
          <table className="tnvs-table">
            <thead><tr><th>Symbol</th><th>Action</th><th>Status</th><th>Side</th><th>Lot</th><th>Time</th></tr></thead>
            <tbody>
              {recentJobs.map(j => (
                <tr key={j.id}>
                  <td className="font-medium">{j.symbol}</td>
                  <td><ActionBadge action={j.action} /></td>
                  <td><StatusBadge status={j.status} /></td>
                  <td><SideBadge side={j.applied_side} /></td>
                  <td>{j.applied_lot_size}</td>
                  <td className="text-xs text-tnvs-muted">{fmtDate(j.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
});

function Card({ icon: Icon, label, value, color }: { icon: React.ComponentType<{ className?: string }>; label: string; value: string; color?: string }) {
  return (
    <div className="tnvs-card flex items-center gap-4">
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

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = { completed: 'text-tnvs-win', pending: 'text-tnvs-warn', failed: 'text-tnvs-loss', executing: 'text-blue-400', skipped: 'text-tnvs-dim' };
  return <span className={cls('text-xs font-medium', colors[status] || 'text-tnvs-muted')}>{status.toUpperCase()}</span>;
}
