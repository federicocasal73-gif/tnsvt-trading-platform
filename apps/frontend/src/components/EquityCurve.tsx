import { EquityPoint } from '../lib/api';
import { Empty } from './common';

export function EquityCurve({ data }: { data: EquityPoint[] }) {
  if (!data.length) return <Empty title="Sin historial aún" description="Los trades cerrados aparecerán aquí" />;

  const W = 800, H = 240, P = 30;
  const maxE = Math.max(...data.map(d => d.equity));
  const minE = Math.min(...data.map(d => d.equity), 0);
  const range = maxE - minE || 1;

  const points = data.map((d, i) => {
    const x = P + (i / (data.length - 1 || 1)) * (W - 2 * P);
    const y = P + (1 - (d.equity - minE) / range) * (H - 2 * P);
    return `${x},${y}`;
  });

  const last = data[data.length - 1];
  const peak = Math.max(...data.map(d => d.equity));
  const maxDd = Math.max(...data.map(d => d.drawdown));

  return (
    <div className="rounded-lg border border-tnvs-border bg-tnvs-surface p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-white">Equity Curve</h3>
        <div className="flex gap-4 text-[11px]">
          <span className="text-tnvs-muted">Equity: <span className="font-mono text-tnvs-win">${last.equity.toFixed(2)}</span></span>
          <span className="text-tnvs-muted">Peak: <span className="font-mono text-white">${peak.toFixed(2)}</span></span>
          <span className="text-tnvs-muted">Max DD: <span className="font-mono text-tnvs-loss">-${maxDd.toFixed(2)}</span></span>
        </div>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" preserveAspectRatio="xMidYMid meet">
        <defs>
          <linearGradient id="eq-gradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgb(16, 185, 129)" stopOpacity="0.35" />
            <stop offset="100%" stopColor="rgb(16, 185, 129)" stopOpacity="0" />
          </linearGradient>
        </defs>
        <polyline points={points.join(' ')} fill="none" stroke="rgb(16, 185, 129)" strokeWidth="2" strokeLinejoin="round" />
        <polygon points={`${P},${H - P} ${points.join(' ')} ${W - P},${H - P}`} fill="url(#eq-gradient)" />
      </svg>
    </div>
  );
}
