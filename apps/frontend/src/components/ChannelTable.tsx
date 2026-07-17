import { ChannelAgg } from '../lib/api';
import { cls } from '../utils/format';

export function ChannelTable({ rows }: { rows: ChannelAgg[] }) {
  if (!rows.length) return null;

  const maxPnl = Math.max(...rows.map(r => Math.abs(r.pnl)), 1);

  return (
    <div className="rounded-lg border border-tnvs-border bg-tnvs-surface">
      <div className="border-b border-tnvs-border px-4 py-3 text-sm font-medium text-white">Por Canal</div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-tnvs-border text-left text-[11px] uppercase tracking-wider text-tnvs-muted">
              <th className="px-4 py-2 font-medium">Canal</th>
              <th className="px-4 py-2 font-medium text-right">Trades</th>
              <th className="px-4 py-2 font-medium text-right">Wins</th>
              <th className="px-4 py-2 font-medium text-right">PNL</th>
              <th className="px-4 py-2 font-medium text-right">Win Rate</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.channel_id ?? 0} className="border-b border-tnvs-border/50 last:border-0 hover:bg-white/[0.02]">
                <td className="px-4 py-2.5 text-white">{r.channel_title}</td>
                <td className="px-4 py-2.5 text-right font-mono text-tnvs-muted">{r.trades}</td>
                <td className="px-4 py-2.5 text-right font-mono text-tnvs-win">{r.wins}</td>
                <td className={cls('px-4 py-2.5 text-right font-mono', r.pnl >= 0 ? 'text-tnvs-win' : 'text-tnvs-loss')}>
                  ${r.pnl.toFixed(2)}
                </td>
                <td className="px-4 py-2.5 text-right font-mono text-tnvs-muted">{(r.win_rate * 100).toFixed(1)}%</td>
                <td className="px-4 py-2.5">
                  <div className="h-1.5 w-24 rounded-full bg-white/[0.08]">
                    <div
                      className="h-full rounded-full bg-tnvs-win transition-all"
                      style={{ width: `${(Math.abs(r.pnl) / maxPnl) * 100}%` }}
                    />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
