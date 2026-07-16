import { memo, useMemo, useState, useEffect } from 'react';
import { Radio, Wifi, WifiOff } from 'lucide-react';
import { useTickStream } from '../lib/tickStream';
import type { Tick } from '../lib/types';
import { cls, fmtUsd } from '../utils/format';

export const LivePage = memo(function LivePage() {
  const { ticks, state } = useTickStream({ maxTicks: 500 });

  // Latest per symbol — recompute when ticks change
  const latest = useMemo(() => {
    const map = new Map<string, Tick>();
    for (const t of ticks) {
      const prev = map.get(t.symbol);
      if (!prev || new Date(t.timestamp) > new Date(prev.timestamp)) {
        map.set(t.symbol, t);
      }
    }
    return [...map.values()].sort((a, b) => a.symbol.localeCompare(b.symbol));
  }, [ticks]);

  // Counts by source for the header
  const counts = useMemo(() => {
    const total = ticks.length;
    const symbols = latest.length;
    return { total, symbols };
  }, [ticks, latest]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-white">Live Ticks</h2>
          <ConnectionBadge state={state} />
        </div>
        <div className="flex items-center gap-4 text-xs text-tnvs-muted">
          <span data-testid="live-count">{counts.total} ticks</span>
          <span>·</span>
          <span data-testid="live-symbols">{counts.symbols} symbols</span>
        </div>
      </div>

      <div className="tnvs-card">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-white/80">Latest per symbol</h3>
          <span className="text-[10px] uppercase tracking-wider text-tnvs-dim">updates live</span>
        </div>
        {latest.length === 0 ? (
          <div className="py-8 text-center text-sm text-tnvs-dim" data-testid="live-empty">
            Waiting for ticks… (make sure price-feed is running)
          </div>
        ) : (
          <table className="tnvs-table" data-testid="live-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Bid</th>
                <th>Ask</th>
                <th>Mid</th>
                <th>Last</th>
                <th>Spread</th>
                <th>Source</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {latest.map((t) => {
                const spread = t.ask - t.bid;
                const mid = (t.bid + t.ask) / 2;
                return (
                  <tr key={t.symbol} data-testid={`live-row-${t.symbol}`}>
                    <td className="font-medium">{t.symbol}</td>
                    <td className="font-mono">{fmtUsd(t.bid)}</td>
                    <td className="font-mono">{fmtUsd(t.ask)}</td>
                    <td className="font-mono">{fmtUsd(mid)}</td>
                    <td className="font-mono">{fmtUsd(t.last)}</td>
                    <td className="font-mono text-tnvs-dim">{spread.toFixed(5)}</td>
                    <td className="text-xs text-tnvs-muted">{t.source}</td>
                    <td className="text-xs text-tnvs-muted">
                      <RelativeTime iso={t.timestamp} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <div className="tnvs-card">
        <h3 className="mb-3 text-sm font-semibold text-white/80">Raw feed (latest 50)</h3>
        {ticks.length === 0 ? (
          <div className="py-4 text-center text-xs text-tnvs-dim">No ticks received yet</div>
        ) : (
          <ul
            data-testid="live-feed"
            className="divide-y divide-tnvs-border/40 font-mono text-xs"
          >
            {ticks.slice(0, 50).map((t, i) => (
              <li key={`${t.timestamp}-${i}`} className="flex justify-between py-1.5 text-tnvs-muted">
                <span className="text-white">{t.symbol}</span>
                <span>bid={t.bid.toFixed(5)}</span>
                <span>ask={t.ask.toFixed(5)}</span>
                <span className="text-tnvs-dim">{new Date(t.timestamp).toLocaleTimeString()}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
});

function ConnectionBadge({ state }: { state: string }) {
  const tone =
    state === 'open' ? 'bg-tnvs-win/10 text-tnvs-win border-tnvs-win/30'
    : state === 'connecting' ? 'bg-tnvs-warn/10 text-tnvs-warn border-tnvs-warn/30'
    : state === 'error' ? 'bg-tnvs-loss/10 text-tnvs-loss border-tnvs-loss/30'
    : 'bg-white/[0.04] text-tnvs-muted border-tnvs-border';
  const Icon = state === 'open' ? Wifi : state === 'error' ? WifiOff : Radio;
  return (
    <span
      data-testid="live-status"
      data-state={state}
      className={cls('inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider', tone)}
    >
      <Icon className="h-3 w-3" />
      {state}
    </span>
  );
}

/**
 * Re-renders every 1s so the relative time stays fresh without re-firing
 * the tick stream.
 */
function RelativeTime({ iso }: { iso: string }) {
  const [, setNow] = useState(Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  const sec = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (sec < 1) return <>just now</>;
  if (sec < 60) return <>{sec}s ago</>;
  const min = Math.floor(sec / 60);
  if (min < 60) return <>{min}m ago</>;
  return <>{Math.floor(min / 60)}h ago</>;
}