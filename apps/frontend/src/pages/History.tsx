import { memo, useEffect, useState } from 'react';
import { ArrowUp, ArrowDown, CheckCircle2, XCircle, Clock, ChevronLeft, ChevronRight } from 'lucide-react';
import { api, LivePosition } from '../lib/api';
import { cls, fmtUsd, fmtDate } from '../utils/format';

type DateRange = '24h' | '7d' | '30d' | 'all';

export const HistoryPage = memo(function HistoryPage() {
  const [trades, setTrades] = useState<LivePosition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [dateRange, setDateRange] = useState<DateRange>('7d');
  const [page, setPage] = useState(0);
  const pageSize = 20;

  const fetchAll = async () => {
    try {
      const params = new URLSearchParams({ limit: String(pageSize), offset: String(page * pageSize) });
      if (statusFilter !== 'all') params.set('status', statusFilter);

      const [tradeData] = await Promise.all([
        api.bridge.trades(statusFilter === 'all' ? undefined : statusFilter),
      ]);
      setTrades(tradeData ?? []);
      setError(null);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      if (!/^HTTP (401|404|502|503)/.test(msg)) setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAll();
  }, [page, statusFilter]);

  useEffect(() => {
    const id = setInterval(fetchAll, 15000);
    return () => clearInterval(id);
  }, [page, statusFilter]);

  const total = trades.length;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const pageStart = page * pageSize + 1;
  const pageEnd = Math.min((page + 1) * pageSize, total);

  function filterByDate(t: LivePosition): boolean {
    if (dateRange === 'all') return true;
    const cutoff = Date.now() - (
      dateRange === '24h' ? 86400000 :
      dateRange === '7d' ? 604800000 :
      2592000000
    );
    return new Date(t.opened_at).getTime() >= cutoff;
  }

  const filtered = trades.filter(filterByDate);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">Trade History</h2>
        <span className="text-xs text-tnvs-muted">{loading ? 'Loading…' : `${total} total`}</span>
      </div>

      {error && (
        <div className="text-xs text-tnvs-warn bg-tnvs-warn/10 px-3 py-2 rounded">{error}</div>
      )}

      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2 text-xs">
          <FilterButton active={statusFilter === 'all'} onClick={() => { setStatusFilter('all'); setPage(0); }}>All</FilterButton>
          <FilterButton active={statusFilter === 'OPEN'} onClick={() => { setStatusFilter('OPEN'); setPage(0); }}>Open</FilterButton>
          <FilterButton active={statusFilter === 'CLOSED'} onClick={() => { setStatusFilter('CLOSED'); setPage(0); }}>Closed</FilterButton>
        </div>
        <div className="flex items-center gap-2 text-xs">
          {(['24h', '7d', '30d', 'all'] as DateRange[]).map(r => (
            <FilterButton key={r} active={dateRange === r} onClick={() => setDateRange(r)}>
              {r === 'all' ? 'All time' : r}
            </FilterButton>
          ))}
        </div>
      </div>

      <div className="tnvs-card">
        {filtered.length === 0 ? (
          <div className="py-8 text-center text-sm text-tnvs-dim">No trades yet</div>
        ) : (
          <table className="tnvs-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Symbol</th>
                <th>Side</th>
                <th>Qty</th>
                <th>Entry</th>
                <th>Close</th>
                <th>SL</th>
                <th>TP</th>
                <th>P&L</th>
                <th>Commission</th>
                <th>Swap</th>
                <th>Status</th>
                <th>Ticket</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(e => {
                const pnl = e.pnl ?? 0;
                return (
                  <tr key={e.id}>
                    <td className="text-xs text-tnvs-muted whitespace-nowrap">{fmtDate(e.opened_at)}</td>
                    <td className="font-medium">{e.symbol}</td>
                    <td><SideBadge side={e.action} /></td>
                    <td className="font-mono">{e.volume.toFixed(2)}</td>
                    <td className="font-mono text-xs">{fmtUsd(e.open_price)}</td>
                    <td className="font-mono text-xs">{e.close_price != null ? fmtUsd(e.close_price) : '-'}</td>
                    <td className="font-mono text-xs text-tnvs-muted">{e.sl != null ? fmtUsd(e.sl) : '-'}</td>
                    <td className="font-mono text-xs text-tnvs-muted">{e.tp != null ? fmtUsd(e.tp) : '-'}</td>
                    <td className={cls('font-mono text-xs', pnl >= 0 ? 'text-tnvs-win' : 'text-tnvs-loss')}>
                      {pnl >= 0 ? '+' : ''}{fmtUsd(pnl)}
                    </td>
                    <td className="font-mono text-xs text-tnvs-muted">{e.commission != null ? fmtUsd(e.commission) : '-'}</td>
                    <td className="font-mono text-xs text-tnvs-muted">{e.swap != null ? fmtUsd(e.swap) : '-'}</td>
                    <td><StatusBadge status={e.status} /></td>
                    <td className="font-mono text-xs text-tnvs-dim">{e.ticket}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}

        {total > pageSize && (
          <div className="flex items-center justify-between pt-3 border-t border-tnvs-border mt-3">
            <span className="text-xs text-tnvs-muted">{pageStart}–{pageEnd} of {total}</span>
            <div className="flex items-center gap-1">
              <button
                disabled={page === 0}
                onClick={() => setPage(p => p - 1)}
                className="p-1 rounded text-tnvs-muted hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
                const start = Math.max(0, Math.min(page - 2, totalPages - 5));
                const p = start + i;
                if (p >= totalPages) return null;
                return (
                  <button
                    key={p}
                    onClick={() => setPage(p)}
                    className={cls(
                      'px-2 py-0.5 text-xs rounded',
                      p === page ? 'bg-tnvs-accent/20 text-white' : 'text-tnvs-muted hover:text-white'
                    )}
                  >
                    {p + 1}
                  </button>
                );
              })}
              <button
                disabled={page >= totalPages - 1}
                onClick={() => setPage(p => p + 1)}
                className="p-1 rounded text-tnvs-muted hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
});

function FilterButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={cls(
        'px-2 py-1 rounded border text-xs transition-colors',
        active
          ? 'bg-tnvs-accent/20 border-tnvs-accent text-white'
          : 'bg-tnvs-bg border-tnvs-border text-tnvs-muted hover:text-white'
      )}
    >
      {children}
    </button>
  );
}

function SideBadge({ side }: { side: string }) {
  const isBuy = side?.toLowerCase() === 'buy' || side?.toLowerCase() === 'long';
  const color = isBuy ? 'text-tnvs-win' : 'text-tnvs-loss';
  return (
    <span className={cls('inline-flex items-center gap-1 text-xs font-medium', color)}>
      {isBuy ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />}
      {side?.toUpperCase() || '-'}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const s = status?.toLowerCase();
  const color = s === 'closed' ? 'text-tnvs-win' : s === 'open' ? 'text-tnvs-warn' : 'text-tnvs-muted';
  return <span className={cls('inline-flex items-center gap-1 text-xs font-medium', color)}>{status?.toUpperCase() || '-'}</span>;
}