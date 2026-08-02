import { memo, useEffect, useState } from 'react';
import { ArrowUp, ArrowDown, ChevronDown, ChevronRight } from 'lucide-react';
import { api, Mt5PositionSnapshot } from '../lib/api';
import { cls, fmtUsd, fmtDate } from '../utils/format';
import { TradePreviewChart } from '../components/TradePreviewChart';

interface MappedPosition {
  id: string;
  ticket: number;
  symbol: string;
  side: string;
  quantity: number;
  entry_price: number;
  current_price: number;
  stop_loss: number | null;
  take_profit: number | null;
  pnl: number;
  opened_at: string;
}

function mapSnapshot(p: Mt5PositionSnapshot): MappedPosition {
  return {
    id: String(p.ticket),
    ticket: p.ticket,
    symbol: p.symbol,
    side: p.type === 'BUY' ? 'BUY' : 'SELL',
    quantity: p.volume,
    entry_price: p.price_open,
    current_price: p.price_current,
    stop_loss: p.sl,
    take_profit: p.tp,
    pnl: p.profit,
    opened_at: p.time,
  };
}

export const PositionsPage = memo(function PositionsPage() {
  const [positions, setPositions] = useState<MappedPosition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const fetchPositions = async () => {
    try {
      const data = await api.bridge.positionsLive();
      setPositions((data.data || []).map(mapSnapshot));
      setError(null);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      if (!/^HTTP (401|502|503|404)/.test(msg)) setError(msg);
      setPositions([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPositions();
    const id = setInterval(fetchPositions, 5000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">Positions</h2>
        <span className="text-xs text-tnvs-muted">
          {loading ? 'Loading…' : `${positions.length} open`}
        </span>
      </div>
      {error && (
        <div className="text-xs text-tnvs-warn bg-tnvs-warn/10 px-3 py-2 rounded">
          {error}
        </div>
      )}

      <Section title={`Open (${positions.length})`}>
        {positions.length === 0 ? <Empty /> : (
          <table className="tnvs-table">
            <thead>
              <tr>
                <th></th>
                <th>Ticket</th>
                <th>Symbol</th>
                <th>Side</th>
                <th>Qty</th>
                <th>Entry</th>
                <th>Current</th>
                <th>SL</th>
                <th>TP</th>
                <th>P&L</th>
                <th>Opened</th>
              </tr>
            </thead>
            <tbody>
              {positions.map(p => {
                 const isExpanded = expandedId === String(p.ticket);
                const isBuy = p.side?.toLowerCase() === 'buy';
                return (
                  <>
                    <tr key={p.id}>
                      <td className="w-6">
                        <button
                          onClick={() => setExpandedId(isExpanded ? null : String(p.ticket))}
                          className="text-tnvs-dim hover:text-white"
                        >
                          {isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                        </button>
                      </td>
                      <td className="font-mono text-xs text-tnvs-muted">{String(p.ticket)}</td>
                      <td className="font-medium">{p.symbol}</td>
                      <td><SideBadge side={p.side} /></td>
                      <td className="font-mono">{p.quantity.toFixed(2)}</td>
                      <td className="font-mono">{fmtUsd(p.entry_price)}</td>
                      <td className="font-mono">{fmtUsd(p.current_price)}</td>
                      <td className="font-mono text-tnvs-dim">{p.stop_loss != null ? fmtUsd(p.stop_loss) : '-'}</td>
                      <td className="font-mono text-tnvs-dim">{p.take_profit != null ? fmtUsd(p.take_profit) : '-'}</td>
                      <td className={cls('font-mono', p.pnl >= 0 ? 'text-tnvs-win' : 'text-tnvs-loss')}>
                        {p.pnl >= 0 ? '+' : ''}{fmtUsd(p.pnl)}
                      </td>
                      <td className="text-xs text-tnvs-muted">{fmtDate(p.opened_at)}</td>
                    </tr>
                    {isExpanded && (
                      <tr>
                        <td colSpan={11} className="p-0">
                          <TradePreviewChart
                            trade={{
                              id: 0,
                              ticket: p.ticket,
                              symbol: p.symbol,
                              action: p.side,
                              volume: p.quantity,
                              open_price: p.entry_price,
                              close_price: null,
                              sl: p.stop_loss,
                              tp: p.take_profit,
                              pnl: p.pnl,
                              commission: 0,
                              swap: 0,
                              opened_at: p.opened_at,
                              closed_at: null,
                              channel_id: null,
                              channel_title: null,
                              topic_id: null,
                              status: 'open',
                              received_at: p.opened_at,
                            }}
                            inline
                          />
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
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