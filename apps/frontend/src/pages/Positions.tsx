import { memo } from 'react';
import { ArrowUp, ArrowDown } from 'lucide-react';
import { useApp } from '../state/AppStateProvider';
import { cls, fmtUsd, fmtPct, fmtDate } from '../utils/format';

export const PositionsPage = memo(function PositionsPage() {
  const { positions, loading } = useApp();
  const open = positions.filter(p => p.status === 'open');
  const closed = positions.filter(p => p.status !== 'open');

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-white">Positions</h2>
      {loading && <div className="text-sm text-tnvs-muted">Loading...</div>}

      <Section title={`Open (${open.length})`}>
        {open.length === 0 ? <Empty /> : (
          <table className="tnvs-table">
            <thead><tr><th>Symbol</th><th>Side</th><th>Qty</th><th>Entry</th><th>Current</th><th>SL</th><th>TP</th><th>P&L</th><th>Opened</th></tr></thead>
            <tbody>
              {open.map(p => (
                <tr key={p.id}>
                  <td className="font-medium">{p.symbol}</td>
                  <td><SideBadge side={p.side} /></td>
                  <td>{p.quantity}</td>
                  <td className="font-mono">{fmtUsd(p.entry_price)}</td>
                  <td className="font-mono">{fmtUsd(p.current_price)}</td>
                  <td className="font-mono text-tnvs-dim">{fmtUsd(p.stop_loss)}</td>
                  <td className="font-mono text-tnvs-dim">{p.take_profit ? fmtUsd(p.take_profit) : '-'}</td>
                  <td className={cls('font-mono', (p.unrealized_pnl || 0) >= 0 ? 'text-tnvs-win' : 'text-tnvs-loss')}>
                    {(p.unrealized_pnl || 0) >= 0 ? '+' : ''}{fmtUsd(p.unrealized_pnl)}
                  </td>
                  <td className="text-xs text-tnvs-muted">{fmtDate(p.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>

      <Section title={`Closed (${closed.length})`}>
        {closed.length === 0 ? <Empty /> : (
          <table className="tnvs-table">
            <thead><tr><th>Symbol</th><th>Side</th><th>Qty</th><th>Entry</th><th>P&L</th><th>Status</th><th>Closed</th></tr></thead>
            <tbody>
              {closed.slice().reverse().map(p => (
                <tr key={p.id}>
                  <td className="font-medium">{p.symbol}</td>
                  <td><SideBadge side={p.side} /></td>
                  <td>{p.quantity}</td>
                  <td className="font-mono">{fmtUsd(p.entry_price)}</td>
                  <td className={cls('font-mono', (p.unrealized_pnl || 0) >= 0 ? 'text-tnvs-win' : 'text-tnvs-loss')}>
                    {(p.unrealized_pnl || 0) >= 0 ? '+' : ''}{fmtUsd(p.unrealized_pnl)}
                  </td>
                  <td><StatusBadge status={p.status} /></td>
                  <td className="text-xs text-tnvs-muted">{p.closed_at ? fmtDate(p.closed_at) : '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>
    </div>
  );
});

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="tnvs-card">
      <h3 className="mb-3 text-sm font-semibold text-white/80">{title}</h3>
      {children}
    </div>
  );
}

function Empty() {
  return <div className="py-6 text-center text-sm text-tnvs-dim">No positions</div>;
}

function SideBadge({ side }: { side: string }) {
  const isBuy = side?.toLowerCase() === 'buy' || side?.toLowerCase() === 'long';
  return (
    <span className={cls('inline-flex items-center gap-1 text-xs font-medium', isBuy ? 'text-tnvs-win' : 'text-tnvs-loss')}>
      {isBuy ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />}
      {side?.toUpperCase() || '-'}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = { closed: 'text-tnvs-dim', open: 'text-tnvs-win', pending: 'text-tnvs-warn' };
  return <span className={cls('text-xs', colors[status] || 'text-tnvs-muted')}>{status.toUpperCase()}</span>;
}
