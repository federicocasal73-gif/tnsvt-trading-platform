import { Metrics } from '../lib/api';
import { cls } from '../utils/format';

export function KPIGrid({ metrics }: { metrics: Metrics | null }) {
  const m = metrics;
  if (!m) return null;

  const cards = [
    { label: 'Total Trades', value: m.total, accent: '' },
    { label: 'Ejecutadas', value: m.wins + m.losses, accent: '' },
    { label: 'Bloqueadas', value: m.total - (m.wins + m.losses), accent: 'text-tnvs-warn' },
    { label: 'Hoy', value: '...', accent: 'text-tnvs-muted' },
    { label: 'Win Rate', value: `${(m.win_rate * 100).toFixed(1)}%`, accent: m.win_rate >= 0.5 ? 'text-tnvs-win' : 'text-tnvs-loss' },
    { label: 'Ganadas', value: m.wins, accent: 'text-tnvs-win' },
    { label: 'Perdidas', value: m.losses, accent: 'text-tnvs-loss' },
    { label: 'PNL Total', value: `$${m.gross_profit - m.gross_loss > 0 ? (m.gross_profit - m.gross_loss).toFixed(2) : '0.00'}`, accent: m.gross_profit - m.gross_loss >= 0 ? 'text-tnvs-win' : 'text-tnvs-loss' },
  ];

  return (
    <div className="grid grid-cols-4 gap-3">
      {cards.map((c) => (
        <div key={c.label} className="rounded-lg border border-tnvs-border bg-tnvs-surface p-3">
          <div className="text-[10px] font-medium uppercase tracking-wider text-tnvs-muted">{c.label}</div>
          <div className={cls('mt-1 font-mono text-xl font-semibold', c.accent || 'text-white')}>{c.value}</div>
        </div>
      ))}
    </div>
  );
}
