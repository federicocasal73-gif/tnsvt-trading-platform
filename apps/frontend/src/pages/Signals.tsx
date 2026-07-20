import { memo } from 'react';
import { ArrowUp, ArrowDown } from 'lucide-react';
import { useApp } from '../state/AppStateProvider';
import { cls, fmtUsd, fmtPct, fmtDate } from '../utils/format';

export const SignalsPage = memo(function SignalsPage() {
  const { signals, loading } = useApp();
  const sorted = [...signals].reverse();

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-white">Signals</h2>
      {loading && <div className="text-sm text-tnvs-muted">Loading...</div>}

      <div className="tnvs-card">
        {sorted.length === 0 ? (
          <div className="py-8 text-center text-sm text-tnvs-dim">No signals received yet</div>
        ) : (
          <table className="tnvs-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Symbol</th>
                <th>Action</th>
                <th>Lot Size</th>
                <th>Entry</th>
                <th>SL</th>
                <th>TP</th>
                <th>Confidence</th>
                <th>Source</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map(s => (
                <tr key={s.id}>
                  <td className="text-xs text-tnvs-muted">{fmtDate(s.created_at)}</td>
                  <td className="font-medium">{s.symbol}</td>
                  <td><ActionBadge action={s.action} /></td>
                  <td>{s.lot_size}</td>
                  <td className="font-mono">{fmtUsd(s.entry_price)}</td>
                  <td className="font-mono text-tnvs-loss">{fmtUsd(s.stop_loss)}</td>
                  <td className="font-mono text-tnvs-win">{fmtUsd(s.take_profit)}</td>
                  <td>{s.confidence != null ? fmtPct(s.confidence * 100) : '-'}</td>
                  <td className="text-xs text-tnvs-muted">{s.source || '-'}</td>
                  <td><StatusBadge status={s.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
});

function ActionBadge({ action }: { action: string }) {
  const isBuy = action.toLowerCase() === 'buy';
  const color = isBuy ? 'text-tnvs-win' : action.toLowerCase() === 'sell' ? 'text-tnvs-loss' : 'text-tnvs-warn';
  const Icon = isBuy ? ArrowUp : ArrowDown;
  return (
    <span className={cls('inline-flex items-center gap-1 text-xs font-medium', color)}>
      <Icon className="h-3 w-3" />{action.toUpperCase()}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    pending: 'text-tnvs-warn', executing: 'text-blue-400', completed: 'text-tnvs-win',
    failed: 'text-tnvs-loss', ignored: 'text-tnvs-dim',
  };
  return <span className={cls('text-xs', colors[status] || 'text-tnvs-muted')}>{status.toUpperCase()}</span>;
}
