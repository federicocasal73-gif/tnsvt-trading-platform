import { useMemo } from 'react';
import { EquityPoint } from '../lib/api';
import { cls } from '../utils/format';
import { Empty } from './common';

export function EquityCurve({ data }: { data: EquityPoint[] }) {
  if (!data.length) return <Empty title="Sin historial aún" description="Los trades cerrados aparecerán aquí" />;

  const W = 800, H = 240, P = 30;

  const { maxE, minE, range, peak, maxDd, maxDdPct, last, points, ddPoints } = useMemo(() => {
    const maxE = Math.max(...data.map(d => d.equity));
    const minE = Math.min(...data.map(d => d.equity), 0);
    const range = maxE - minE || 1;
    const peak = Math.max(...data.map(d => d.equity));
    const maxDd = Math.max(...data.map(d => d.drawdown));
    const maxDdPct = peak > 0 ? (maxDd / peak) * 100 : 0;
    const last = data[data.length - 1];

    const scaleY = (v: number) => P + (1 - (v - minE) / range) * (H - 2 * P);

    const points = data.map((d, i) => {
      const x = P + (i / (data.length - 1 || 1)) * (W - 2 * P);
      return `${x},${scaleY(d.equity)}`;
    });

    const ddPoints = data.map((d, i) => {
      const x = P + (i / (data.length - 1 || 1)) * (W - 2 * P);
      const eqY = scaleY(d.equity);
      const peakY = scaleY(peak - d.drawdown);
      return { x, eqY, peakY };
    });

    return { maxE, minE, range, peak, maxDd, maxDdPct, last, points, ddPoints };
  }, [data]);

  const peakIdx = data.findIndex(d => d.equity === peak);
  const peakX = P + (peakIdx / (data.length - 1 || 1)) * (W - 2 * P);
  const peakY = P + (1 - (peak - minE) / range) * (H - 2 * P);
  const lastX = P + ((data.length - 1) / (data.length - 1 || 1)) * (W - 2 * P);
  const lastY = P + (1 - (last.equity - minE) / range) * (H - 2 * P);

  return (
    <div className="rounded-lg border border-tnvs-border bg-tnvs-surface p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-white">Equity Curve</h3>
        <div className="flex items-center gap-4 text-[11px]">
          <span className="text-tnvs-muted">
            Equity: <span className={cls('font-mono', last.equity >= 0 ? 'text-tnvs-win' : 'text-tnvs-loss')}>
              ${last.equity.toFixed(2)}
            </span>
          </span>
          <span className="text-tnvs-muted">
            Peak: <span className="font-mono text-white">${peak.toFixed(2)}</span>
          </span>
          <span className="text-tnvs-muted">
            DD: <span className="font-mono text-tnvs-loss">-${maxDd.toFixed(2)}</span>
            <span className="text-tnvs-dim ml-0.5">({maxDdPct.toFixed(1)}%)</span>
          </span>
        </div>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" preserveAspectRatio="xMidYMid meet">
        <defs>
          <linearGradient id="eq-gradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgb(16, 185, 129)" stopOpacity="0.35" />
            <stop offset="100%" stopColor="rgb(16, 185, 129)" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="dd-gradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgb(239, 68, 68)" stopOpacity="0.3" />
            <stop offset="100%" stopColor="rgb(239, 68, 68)" stopOpacity="0" />
          </linearGradient>
        </defs>

        <polygon points={`${P},${H - P} ${points.join(' ')} ${W - P},${H - P}`} fill="url(#eq-gradient)" />

        {points.length > 1 && (
          <polygon
            points={ddPoints.map(d => `${d.x},${d.peakY}`).join(' ') + ' ' + [...ddPoints].reverse().map(d => `${d.x},${d.eqY}`).join(' ')}
            fill="url(#dd-gradient)"
          />
        )}

        {points.length > 1 && (
          <polyline points={ddPoints.map(d => `${d.x},${d.peakY}`).join(' ')} fill="none" stroke="rgb(239, 68, 68)" strokeWidth="1" strokeDasharray="4,3" opacity="0.6" />
        )}

        <polyline points={points.join(' ')} fill="none" stroke="rgb(16, 185, 129)" strokeWidth="2" strokeLinejoin="round" />

        <circle cx={lastX} cy={lastY} r="3" fill="rgb(16, 185, 129)" stroke="#0f172a" strokeWidth="1.5" />
      </svg>
    </div>
  );
}
