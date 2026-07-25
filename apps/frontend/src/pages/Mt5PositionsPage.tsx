import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { MessageCircle, RefreshCw, Terminal } from 'lucide-react';
import { api, BridgeCandle, LivePosition, Mt5PositionSnapshot } from '../lib/api';
import { useBridge } from '../state/BridgeProvider';
import { cls } from '../utils/format';
import { Empty } from '../components/common';
import { TradePreviewChart } from '../components/TradePreviewChart';

const _previewCache = new Map<number, BridgeCandle[]>();

function _formatDuration(opened_at: string, closed_at: string | null): string {
  if (!closed_at) return 'Abierto';
  const start = new Date(opened_at).getTime();
  const end = new Date(closed_at).getTime();
  const diff = end - start;
  if (diff < 0) return '—';
  const hours = Math.floor(diff / 3600000);
  const minutes = Math.floor((diff % 3600000) / 60000);
  const seconds = Math.floor((diff % 60000) / 1000);
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

async function _previewFetch(trade: LivePosition): Promise<BridgeCandle[] | null> {
  const cached = _previewCache.get(trade.ticket);
  if (cached) return cached;

  const openedAt = new Date(trade.opened_at);
  const from = new Date(openedAt.getTime() - 30 * 60 * 1000).toISOString();
  const to = trade.closed_at
    ? new Date(new Date(trade.closed_at).getTime() + 5 * 60 * 1000).toISOString()
    : new Date(Date.now() + 5 * 60 * 1000).toISOString();

  try {
    const res = await api.bridge.candles(trade.symbol, 'M5', from, to, 100);
    if (res.ok && res.candles?.length > 0) {
      _previewCache.set(trade.ticket, res.candles);
      return res.candles;
    }
  } catch { /* fallback */ }
  return null;
}

type Tab = 'OPEN' | 'CLOSED' | 'ALL';
const TABS: { key: Tab; label: string }[] = [
  { key: 'OPEN', label: 'Open' },
  { key: 'CLOSED', label: 'Closed' },
  { key: 'ALL', label: 'All' },
];

const POLL_MS: Record<Tab, number> = { OPEN: 2000, CLOSED: 30000, ALL: 30000 };

type SortDir = 'asc' | 'desc';
type SortKey = 'symbol' | 'action' | 'pnl' | 'opened_at' | 'closed_at' | 'channel_title';

export function Mt5PositionsPage() {
  const bridge = useBridge();
  const { selectedLogin } = bridge;
  const [tab, setTab] = useState<Tab>('OPEN');
  const [trades, setTrades] = useState<LivePosition[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<number>(0);
  const [pulse, setPulse] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>('opened_at');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [filterSymbol, setFilterSymbol] = useState('');
  const [filterChannel, setFilterChannel] = useState('');
  const tabsRef = useRef<HTMLDivElement>(null!);
  const pillRef = useRef<HTMLSpanElement>(null!);
  const movePill = useCallback((animate: boolean) => {
    const bar = tabsRef.current;
    const pill = pillRef.current;
    if (!bar || !pill) return;
    const active = bar.querySelector<HTMLButtonElement>('[aria-selected="true"]');
    if (!active) return;
    if (animate) {
      pill.style.transform = `translateX(${active.offsetLeft}px)`;
      pill.style.width = `${active.offsetWidth}px`;
    } else {
      pill.style.transition = 'none';
      pill.style.transform = `translateX(${active.offsetLeft}px)`;
      pill.style.width = `${active.offsetWidth}px`;
      void pill.offsetWidth;
      pill.style.transition = '';
    }
  }, []);
  useEffect(() => { movePill(false); }, [movePill]);
  useEffect(() => { movePill(true); }, [tab, movePill]);
  useEffect(() => {
    const onResize = () => movePill(false);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [movePill]);

  const fetchData = useCallback(async () => {
    try {
      const acc = selectedLogin ?? undefined;
      const [tradesResult, liveResult] = await Promise.allSettled([
        api.bridge.trades(undefined, 30),
        api.bridge.accountPositions(acc),
      ]);

      let merged: LivePosition[] = [];

      if (tradesResult.status === 'fulfilled') {
        merged = tradesResult.value;
      }

      if (liveResult.status === 'fulfilled' && liveResult.value?.ok) {
        const livePositions = (liveResult.value.data as Mt5PositionSnapshot[]) || [];
        const existingTickets = new Set(merged.map(t => t.ticket));
        for (const lp of livePositions) {
          if (!existingTickets.has(lp.ticket)) {
            const openedAt = typeof lp.time === 'number'
              ? new Date(lp.time * 1000).toISOString()
              : lp.time;
            merged.push({
              id: lp.ticket,
              ticket: lp.ticket,
              symbol: lp.symbol,
              action: lp.type,
              volume: lp.volume,
              open_price: lp.price_open,
              close_price: null,
              sl: lp.sl,
              tp: lp.tp,
              pnl: lp.profit,
              commission: lp.commission ?? 0,
              swap: lp.swap ?? 0,
              opened_at: openedAt,
              closed_at: null,
              channel_id: null,
              channel_title: null,
              topic_id: null,
              status: 'OPEN',
              received_at: openedAt,
            });
          }
        }
      }

      void acc;
      // Filtrar por tab despues del merge
      const filtered = tab === 'OPEN' ? merged.filter(t => t.status === 'OPEN')
        : tab === 'CLOSED' ? merged.filter(t => t.status === 'CLOSED')
        : merged;

      setTrades(prev => {
        if (JSON.stringify(prev) !== JSON.stringify(filtered)) {
          setPulse(true);
          setTimeout(() => setPulse(false), 300);
          return filtered;
        }
        return prev;
      });
      setLastUpdate(Date.now());
    } catch {
    } finally {
      setLoading(false);
    }
  }, [tab, selectedLogin]);

  useEffect(() => {
    setLoading(true);
    fetchData();
    const id = setInterval(fetchData, POLL_MS[tab]);
    return () => clearInterval(id);
  }, [fetchData, tab]);

  const tabSum = useMemo(() => {
    const open = trades.filter(t => t.status === 'OPEN').length;
    const closed = trades.filter(t => t.status === 'CLOSED').length;
    return { open, closed, total: trades.length };
  }, [trades]);

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

  const openPositions = trades.filter(t => t.status === 'OPEN');
  const totalRealized = trades.filter(t => t.status === 'CLOSED').reduce((s, t) => s + (t.pnl || 0), 0);
  const totalUnrealized = openPositions.reduce((s, t) => s + (t.pnl || 0), 0);

  const [hoveredTrade, setHoveredTrade] = useState<LivePosition | null>(null);
  const [previewPos, setPreviewPos] = useState<{ top: number; left: number } | null>(null);
  const [previewCandles, setPreviewCandles] = useState<BridgeCandle[] | null>(null);
  const hoverTimer = useRef<ReturnType<typeof setTimeout>>();
  const leaveTimer = useRef<ReturnType<typeof setTimeout>>();
  const previewRef = useRef<HTMLDivElement>(null);

  const [expandedTicket, setExpandedTicket] = useState<number | null>(null);
  const [expandedCandles, setExpandedCandles] = useState<BridgeCandle[] | null>(null);
  const [expandedLoading, setExpandedLoading] = useState(false);

  const handleRowEnter = useCallback((trade: LivePosition, ev: React.MouseEvent) => {
    clearTimeout(leaveTimer.current);
    clearTimeout(hoverTimer.current);
    hoverTimer.current = setTimeout(async () => {
      const rect = (ev.currentTarget as HTMLElement).getBoundingClientRect();
      setPreviewPos({ top: rect.top, left: rect.right + 8 });
      setHoveredTrade(trade);
      const candles = await _previewFetch(trade);
      setPreviewCandles(candles);
    }, 150);
  }, []);

  const handleRowLeave = useCallback(() => {
    clearTimeout(hoverTimer.current);
    clearTimeout(leaveTimer.current);
    leaveTimer.current = setTimeout(() => {
      setHoveredTrade(null);
      setPreviewPos(null);
      setPreviewCandles(null);
    }, 200);
  }, []);

  const handlePreviewEnter = useCallback(() => {
    clearTimeout(leaveTimer.current);
  }, []);

  const handlePreviewLeave = useCallback(() => {
    setHoveredTrade(null);
    setPreviewPos(null);
    setPreviewCandles(null);
  }, []);

  const handleRowClick = useCallback(async (ticket: number) => {
    if (expandedTicket === ticket) {
      setExpandedTicket(null);
      setExpandedCandles(null);
      return;
    }
    setExpandedTicket(ticket);
    setExpandedCandles(null);
    setExpandedLoading(true);
    const cached = _previewCache.get(ticket);
    if (cached) {
      setExpandedCandles(cached);
      setExpandedLoading(false);
      return;
    }
    try {
      const res = await api.bridge.tradeCandles(ticket);
      if (res.ok && res.candles?.length > 0) {
        _previewCache.set(ticket, res.candles);
        setExpandedCandles(res.candles);
      }
    } catch { /* noop */ }
    setExpandedLoading(false);
  }, [expandedTicket]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-tnvs-border px-6 py-4">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-white">MT5 Positions</h2>
          <span className={cls('h-2 w-2 rounded-full', pulse ? 'bg-tnvs-win animate-ping' : 'bg-tnvs-win/60')} />
          {tab === 'OPEN' && (
            <span className="text-[11px] text-tnvs-dim font-mono">
              polling 2s · {openPositions.length} open · ${totalUnrealized > 0 ? '+' : ''}{totalUnrealized.toFixed(2)} unrealized
            </span>
          )}
          {tab === 'CLOSED' && (
            <span className="text-[11px] text-tnvs-dim font-mono">
              ${totalRealized > 0 ? '+' : ''}{totalRealized.toFixed(2)} realized
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {lastUpdate > 0 && (
            <span className="text-[10px] text-tnvs-dim font-mono">
              {new Date(lastUpdate).toLocaleTimeString()}
            </span>
          )}
          <button onClick={fetchData} className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-tnvs-muted hover:bg-white/[0.04] hover:text-white">
            <RefreshCw className="h-3 w-3" /> Refrescar
          </button>
        </div>
      </div>

      <div className="flex items-center border-b border-tnvs-border bg-tnvs-surface/50 px-6 py-2">
        <div ref={tabsRef} className="t-tabs" role="tablist">
          <span ref={pillRef} className="t-tabs-pill" aria-hidden="true" />
          {TABS.map(t => (
            <button key={t.key} role="tab" aria-selected={tab === t.key} onClick={() => setTab(t.key)}
              className="t-tab"
            >
              {t.label}
              {t.key === 'OPEN' && tabSum.open > 0 && (
                <span className="ml-1.5 rounded-full bg-tnvs-purple/20 px-1.5 py-0.5 text-[10px] text-tnvs-purple">{tabSum.open}</span>
              )}
              {t.key === 'CLOSED' && tabSum.closed > 0 && (
                <span className="ml-1.5 rounded-full bg-white/[0.08] px-1.5 py-0.5 text-[10px] text-tnvs-muted">{tabSum.closed}</span>
              )}
            </button>
          ))}
        </div>
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
          <Empty title="Sin posiciones" description="No hay trades para esta vista" action={
              <div className="mt-4 w-full border-t border-tnvs-border/30 pt-4">
                <p className="mb-2 text-[10px] uppercase tracking-wider text-tnvs-dim">Últimas señales reales recibidas</p>
                <div className="space-y-1.5 text-[11px] font-mono text-tnvs-muted">
                  <div className="flex items-center gap-2">
                    <span className="w-32 text-tnvs-dim">2026-07-24 13:43</span>
                    <span className="w-16 text-emerald-400">BUY</span>
                    <span className="w-20 text-white">XAUUSD</span>
                    <span className="text-tnvs-dim">XAU LIQUIDITY PRIVADO</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-32 text-tnvs-dim">2026-07-23 23:44</span>
                    <span className="w-16 text-red-400">SELL</span>
                    <span className="w-20 text-white">NZDCHF</span>
                    <span className="text-tnvs-dim">SL:94.904 TP:94.392</span>
                    <span className="text-tnvs-dim">INVESTMENTH VIP</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-32 text-tnvs-dim">2026-07-23 12:30</span>
                    <span className="w-16 text-emerald-400">BUY</span>
                    <span className="w-20 text-white">XAUUSD</span>
                    <span className="text-tnvs-dim">SL:4039.0 TP:4079.0</span>
                    <span className="text-tnvs-dim">XAU LIQUIDITY PRIVADO</span>
                  </div>
                </div>
              </div>
            } />
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
                <th className="px-4 py-2.5 font-medium text-right">SL</th>
                <th className="px-4 py-2.5 font-medium text-right">TP</th>
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
                <React.Fragment key={t.ticket || i}>
                <tr key={t.ticket || i} className={cls(
                  'border-b border-tnvs-border/30 hover:bg-white/[0.02] cursor-pointer',
                  t.status === 'OPEN' && 'bg-tnvs-win/[0.02]',
                  hoveredTrade?.ticket === t.ticket && 'bg-white/[0.04]',
                  expandedTicket === t.ticket && 'bg-white/[0.06]',
                )}
                  onMouseEnter={(ev) => handleRowEnter(t, ev)}
                  onMouseLeave={handleRowLeave}
                  onClick={() => handleRowClick(t.ticket)}
                >
                  <td className="px-4 py-2.5 font-mono text-white">{t.symbol}</td>
                  <td className="px-4 py-2.5">
                    <span className={cls('rounded px-1.5 py-0.5 text-[10px] font-medium', t.action === 'BUY' ? 'bg-emerald-500/15 text-emerald-400' : 'bg-red-500/15 text-red-400')}>
                      {t.action}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-tnvs-muted">{t.volume.toFixed(2)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-tnvs-muted">{t.open_price.toFixed(5)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-tnvs-muted">{t.close_price != null ? t.close_price.toFixed(5) : '—'}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-[11px] text-tnvs-dim">{t.sl ?? '—'}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-[11px] text-tnvs-dim">{t.tp ?? '—'}</td>
                  <td className={cls('px-4 py-2.5 text-right font-mono', t.pnl > 0 ? 'text-tnvs-win' : t.pnl < 0 ? 'text-tnvs-loss' : 'text-tnvs-muted')}>
                    {t.pnl > 0 ? '+' : ''}${t.pnl.toFixed(2)}
                  </td>
                  <td className="px-4 py-2.5">
                    {t.channel_title ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-blue-500/10 px-2 py-0.5 text-xs text-blue-400">
                        <MessageCircle className="h-3 w-3" />
                        {t.channel_title}
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-full bg-white/[0.05] px-2 py-0.5 text-xs text-tnvs-muted">
                        <Terminal className="h-3 w-3" />
                        Directo
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-[11px] text-tnvs-muted">
                    {new Date(t.opened_at).toLocaleString('es-AR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-[11px] text-tnvs-muted">
                    {t.closed_at ? new Date(t.closed_at).toLocaleString('es-AR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—'}
                  </td>
                </tr>
                {expandedTicket === t.ticket && (
                  <tr className="border-b border-tnvs-border/30">
                    <td colSpan={11} className="px-4 py-3">
                      {expandedLoading ? (
                        <div className="flex items-center gap-3">
                          <div className="h-[180px] w-[400px] animate-pulse rounded bg-white/[0.04]" />
                          <div className="flex-1 space-y-2">
                            <div className="h-4 w-24 animate-pulse rounded bg-white/[0.04]" />
                            <div className="h-4 w-32 animate-pulse rounded bg-white/[0.04]" />
                            <div className="h-4 w-20 animate-pulse rounded bg-white/[0.04]" />
                          </div>
                        </div>
                      ) : (
                        <div className="flex gap-4">
                          <TradePreviewChart trade={t} candles={expandedCandles ?? undefined} inline />
                          <div className="flex-1 space-y-2 text-xs font-mono text-tnvs-muted">
                            <div className="flex items-center gap-2">
                              <span className={cls('rounded px-1.5 py-0.5 text-[10px] font-medium',
                                t.pnl > 0 ? 'bg-emerald-500/15 text-emerald-400' :
                                t.pnl < 0 ? 'bg-red-500/15 text-red-400' :
                                'bg-white/[0.08] text-tnvs-muted'
                              )}>
                                {t.pnl > 0 ? 'WIN' : t.pnl < 0 ? 'LOSS' : 'BE'}
                              </span>
                              <span className={t.pnl > 0 ? 'text-tnvs-win' : t.pnl < 0 ? 'text-tnvs-loss' : 'text-tnvs-muted'}>
                                {t.pnl > 0 ? '+' : ''}${t.pnl.toFixed(2)}
                              </span>
                            </div>
                            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                              <span>Duration: <span className="text-white">{_formatDuration(t.opened_at, t.closed_at)}</span></span>
                              <span>Entry: <span className="text-white">{t.open_price.toFixed(5)}</span></span>
                              <span>Close: <span className="text-white">{t.close_price != null ? t.close_price.toFixed(5) : '\u2014'}</span></span>
                              <span>SL: <span className="text-red-400">{t.sl ?? '\u2014'}</span></span>
                              <span>TP: <span className="text-green-400">{t.tp ?? '\u2014'}</span></span>
                              <span>Commission: <span className="text-white">${t.commission.toFixed(2)}</span></span>
                              <span>Swap: <span className="text-white">${t.swap.toFixed(2)}</span></span>
                              <span>Canal: <span className="text-white">{t.channel_title || 'Directo'}</span></span>
                            </div>
                            <div className="text-[10px] text-tnvs-dim">
                              Abierto: {new Date(t.opened_at).toLocaleString('es-AR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
                              {t.closed_at && <> · Cerrado: {new Date(t.closed_at).toLocaleString('es-AR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}</>}
                            </div>
                          </div>
                        </div>
                      )}
                    </td>
                  </tr>
                )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        )}
        {hoveredTrade && previewPos && (
          <div
            ref={previewRef}
            onMouseEnter={handlePreviewEnter}
            onMouseLeave={handlePreviewLeave}
            className="fixed z-50"
            style={{ top: previewPos.top, left: previewPos.left }}
          >
            <TradePreviewChart trade={hoveredTrade} candles={previewCandles ?? undefined} onClose={handlePreviewLeave} />
          </div>
        )}
      </div>
    </div>
  );
}
