import { memo } from 'react';
import { useAuth } from '../lib/auth';
import { useApp } from '../state/AppStateProvider';
import { cls, fmtUsd, fmtPct } from '../utils/format';

export const TopBar = memo(function TopBar() {
  const { user } = useAuth();
  const { positions, copyStats, loading } = useApp();

  const openPnl = positions.reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0);
  const openCount = positions.filter(p => p.status === 'open').length;
  const successRate = copyStats?.success_rate || 0;

  return (
    <header className="z-20 flex items-center gap-4 border-b border-tnvs-border bg-tnvs-void/70 px-6 py-3 backdrop-blur">
      <div className="flex items-baseline gap-2">
        <h1 className="text-lg font-semibold text-white">Terminal Financiera</h1>
        <span className="text-xs text-tnvs-muted">· {loading ? 'Loading...' : 'Live'}</span>
      </div>

      <div className="ml-auto flex items-center gap-4">
        <Stat label="Open Positions" value={String(openCount)} />
        <Stat label="Unrealized P&L" value={fmtUsd(openPnl)} color={openPnl >= 0 ? 'text-tnvs-win' : 'text-tnvs-loss'} />
        <Stat label="Success Rate" value={fmtPct(successRate)} color={successRate >= 50 ? 'text-tnvs-win' : 'text-tnvs-warn'} />

        <div className="flex items-center gap-2 rounded-lg border border-tnvs-border bg-tnvs-surface px-3 py-1.5">
          <div className="h-2 w-2 rounded-full bg-tnvs-win" />
          <span className="text-xs text-tnvs-muted">{user?.username || user?.email}</span>
        </div>
      </div>
    </header>
  );
});

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex flex-col items-end leading-tight">
      <span className="text-[10px] uppercase tracking-wider text-tnvs-muted">{label}</span>
      <span className={cls('font-mono text-sm', color || 'text-white')}>{value}</span>
    </div>
  );
}
