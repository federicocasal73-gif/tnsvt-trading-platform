import { useEffect, useMemo, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { api, LivePosition } from '../lib/api';
import { cls } from '../utils/format';
import { Empty } from '../components/common';

type Tab = 'OPEN' | 'CLOSED' | 'ALL';
const TABS: { key: Tab; label: string }[] = [
  { key: 'OPEN', label: 'Open' },
  { key: 'CLOSED', label: 'Closed' },
  { key: 'ALL', label: 'All' },
];

type SortDir = 'asc' | 'desc';
type SortKey = 'symbol' | 'action' | 'pnl' | 'opened_at' | 'closed_at' | 'channel_title';

export function Mt5PositionsPage() {
  const [tab, setTab] = useState<Tab>('OPEN');
  const [trades, setTrades] = useState<LivePosition[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortKey, setSortKey] = useState<SortKey>('opened_at');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [filterSymbol, setFilterSymbol] = useState('');
  const [filterChannel, setFilterChannel] = useState('');

  const fetchData = async () => {
    try {
      const data = await api.bridge.trades(tab === 'ALL' ? undefined : tab);
      setTrades(data);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    fetchData();
    const id = setInterval(fetchData, 30000);
    return () => clearInterval(id);
  }, [tab]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('desc'); }
  };

  const filtered = useMemo(() => {
    let result = [...trades];
    if (filterSymbol) result = result.filter(t => t.symbol.toLowerCase().includes(filterSymbol.toLowerCase()));
    if (filterChannel) result = result.filter(t => (t.channel_title || '').toLowerCase().includes(filterChannel.toLowerCase()));
    result.sort((a, b) => {
      const aV = a[sortKey] ?? '';
      const bV = b[sortKey] ?? '';
      const cmp = typeof aV === 'number' ? (aV as number) - (bV as number) : String(aV).localeCompare(String(bV));
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return result;
  }, [trades, filterSymbol, filterChannel, sortKey, sortDir]);

  const uniqueSymbols = useMemo(() => [...new Set(trades.map(t => t.symbol))].sort(), [trades]);
  const uniqueChannels = useMemo(() => [...new Set(trades.map(t => t.channel_title).filter(Boolean))].sort(), [trades]);

  const SortIcon = ({ k }: { k: SortKey }) => {
    if (sortKey !== k) return <span className="ml-1 text-tnvs-dim">↕</span>;
    return <span className="ml-1">{sortDir === 'asc' ? '↑' : '↓'}</span>;
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-tnvs-border px-6 py-4">
        <h2 className="text-lg font-semibold text-white">MT5 Positions</h2>
        <button onClick={fetchData} className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-tnvs-muted hover:bg-white/[0.04] hover:text-white">
          <RefreshCw className="h-3 w-3" /> Refrescar
        </button>
      </div>

      <div className="flex items-center gap-4 border-b border-tnvs-border bg-tnvs-surface/50 px-6 py-2">
        {TABS.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={cls(
              'rounded-md px-3 py-1 text-xs font-medium transition-colors',
              tab === t.key ? 'bg-white/[0.08] text-white' : 'text-tnvs-muted hover:text-white'
            )}
          >
            {t.label}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-3">
          <select value={filterSymbol} onChange={e => setFilterSymbol(e.target.value)}
            className="rounded border border-tnvs-border bg-tnvs-surface px-2 py-1 text-xs text-tnvs-muted outline-none">
            <option value="">Todos los símbolos</option>
            {uniqueSymbols.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <select value={filterChannel} onChange={e => setFilterChannel(e.target.value)}
            className="rounded border border-tnvs-border bg-tnvs-surface px-2 py-1 text-xs text-tnvs-muted outline-none">
            <option value="">Todos los canales</option>
            {uniqueChannels.map(c => <option key={c} value={c!}>{c}</option>)}
          </select>
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        {loading ? (
          <div className="flex items-center justify-center py-20 text-sm text-tnvs-muted">Cargando...</div>
        ) : filtered.length === 0 ? (
          <Empty title="Sin posiciones" description="No hay trades para esta vista" />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="sticky top-0 border-b border-tnvs-border bg-tnvs-void text-left text-[11px] uppercase tracking-wider text-tnvs-muted">
                <th className="cursor-pointer px-4 py-2.5 font-medium hover:text-white" onClick={() => handleSort('symbol')}>
                  Symbol <SortIcon k="symbol" />
                </th>
                <th className="cursor-pointer px-4 py-2.5 font-medium hover:text-white" onClick={() => handleSort('action')}>
                  Side <SortIcon k="action" />
                </th>
                <th className="px-4 py-2.5 font-medium text-right">Volume</th>
                <th className="px-4 py-2.5 font-medium text-right">Open</th>
                <th className="px-4 py-2.5 font-medium text-right">Close</th>
                <th className="cursor-pointer px-4 py-2.5 font-medium text-right hover:text-white" onClick={() => handleSort('pnl')}>
                  P&L <SortIcon k="pnl" />
                </th>
                <th className="cursor-pointer px-4 py-2.5 font-medium hover:text-white" onClick={() => handleSort('channel_title')}>
                  Channel <SortIcon k="channel_title" />
                </th>
                <th className="cursor-pointer px-4 py-2.5 font-medium hover:text-white" onClick={() => handleSort('opened_at')}>
                  Opened <SortIcon k="opened_at" />
                </th>
                <th className="cursor-pointer px-4 py-2.5 font-medium hover:text-white" onClick={() => handleSort('closed_at')}>
                  Closed <SortIcon k="closed_at" />
                </th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((t, i) => (
                <tr key={t.ticket || i} className="border-b border-tnvs-border/30 hover:bg-white/[0.02]">
                  <td className="px-4 py-2.5 font-mono text-white">{t.symbol}</td>
                  <td className="px-4 py-2.5">
                    <span className={cls('rounded px-1.5 py-0.5 text-[10px] font-medium', t.action === 'BUY' ? 'bg-emerald-500/15 text-emerald-400' : 'bg-red-500/15 text-red-400')}>
                      {t.action}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-tnvs-muted">{t.volume.toFixed(2)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-tnvs-muted">{t.open_price.toFixed(5)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-tnvs-muted">{t.close_price != null ? t.close_price.toFixed(5) : '—'}</td>
                  <td className={cls('px-4 py-2.5 text-right font-mono', t.pnl > 0 ? 'text-tnvs-win' : t.pnl < 0 ? 'text-tnvs-loss' : 'text-tnvs-muted')}>
                    {t.pnl > 0 ? '+' : ''}${t.pnl.toFixed(2)}
                  </td>
                  <td className="px-4 py-2.5 text-tnvs-muted">{t.channel_title || '—'}</td>
                  <td className="px-4 py-2.5 font-mono text-[11px] text-tnvs-muted">{new Date(t.opened_at).toLocaleDateString()}</td>
                  <td className="px-4 py-2.5 font-mono text-[11px] text-tnvs-muted">{t.closed_at ? new Date(t.closed_at).toLocaleDateString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
