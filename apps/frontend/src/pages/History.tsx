import { memo } from 'react';
import { useApp } from '../state/AppStateProvider';
import { cls, fmtUsd, fmtDate } from '../utils/format';

export const HistoryPage = memo(function HistoryPage() {
  const { trades, loading } = useApp();
  const closed = trades.filter(t => t.status === 'closed').reverse();

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-white">Trade History</h2>
      {loading && <div className="text-sm text-tnvs-muted">Loading...</div>}

      <div className="tnvs-card">
        {closed.length === 0 ? (
          <div className="py-8 text-center text-sm text-tnvs-dim">No closed trades yet</div>
        ) : (
          <table className="tnvs-table">
            <thead>
              <tr>
                <th>Opened</th>
                <th>Closed</th>
                <th>Symbol</th>
                <th>Side</th>
                <th>Qty</th>
                <th>Entry</th>
                <th>P&L</th>
                <th>Ticket</th>
              </tr>
            </thead>
            <tbody>
              {closed.map(t => (
                <tr key={t.id}>
                  <td className="text-xs text-tnvs-muted">{fmtDate(t.created_at)}</td>
                  <td className="text-xs text-tnvs-muted">{t.closed_at ? fmtDate(t.closed_at) : '-'}</td>
                  <td className="font-medium">{t.symbol}</td>
                  <td><SideBadge side={t.side} /></td>
                  <td>{t.quantity}</td>
                  <td className="font-mono">{fmtUsd(t.entry_price)}</td>
                  <td className={cls('font-mono', (t.pnl || 0) >= 0 ? 'text-tnvs-win' : 'text-tnvs-loss')}>
                    {(t.pnl || 0) >= 0 ? '+' : ''}{fmtUsd(t.pnl || 0)}
                  </td>
                  <td className="font-mono text-xs text-tnvs-dim">{t.ticket || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
});

function SideBadge({ side }: { side: string }) {
  const color = side?.toLowerCase() === 'buy' || side?.toLowerCase() === 'long' ? 'text-tnvs-win' : 'text-tnvs-loss';
  return <span className={cls('text-xs font-medium', color)}>{side?.toUpperCase() || '-'}</span>;
}
