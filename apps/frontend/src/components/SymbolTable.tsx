import { SymbolAgg } from '../lib/api';
import { cls } from '../utils/format';

export function SymbolTable({ rows }: { rows: SymbolAgg[] }) {
  if (!rows.length) return null;

  return (
    <div className="rounded-lg border border-tnvs-border bg-tnvs-surface">
      <div className="border-b border-tnvs-border px-4 py-3 text-sm font-medium text-white">Por Símbolo</div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-tnvs-border text-left text-[11px] uppercase tracking-wider text-tnvs-muted">
              <th className="px-4 py-2 font-medium">Símbolo</th>
              <th className="px-4 py-2 font-medium text-right">Trades</th>
              <th className="px-4 py-2 font-medium text-right">PNL</th>
              <th className="px-4 py-2 font-medium" />
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.symbol} className="border-b border-tnvs-border/50 last:border-0 hover:bg-white/[0.02]">
                <td className="flex items-center gap-2 px-4 py-2.5 font-mono text-white">
                  {r.symbol}
                  {r.best && <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 text-[10px] text-emerald-400">Mejor</span>}
                  {r.worst && <span className="rounded bg-red-500/20 px-1.5 py-0.5 text-[10px] text-red-400">Peor</span>}
                </td>
                <td className="px-4 py-2.5 text-right font-mono text-tnvs-muted">{r.trades}</td>
                <td className={cls('px-4 py-2.5 text-right font-mono', r.pnl >= 0 ? 'text-tnvs-win' : 'text-tnvs-loss')}>
                  ${r.pnl.toFixed(2)}
                </td>
                <td className="px-4 py-2.5">
                  <div className="flex gap-2">
                    <span className="text-[10px] text-tnvs-dim">trades: {r.trades}</span>
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
