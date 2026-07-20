import { memo, useEffect, useState } from 'react';
import { useAuth } from '../lib/auth';
import { useBridge } from '../state/BridgeProvider';
import { useTheme, ThemeMode } from '../state/ThemeProvider';
import { cls, fmtUsd, fmtPct } from '../utils/format';
import { Activity, TrendingUp, TrendingDown, DollarSign, Shield, BarChart3, RefreshCw, Moon, Sun, BookOpen, Monitor } from 'lucide-react';

export const TopBar = memo(function TopBar() {
  const { user } = useAuth();
  const bridge = useBridge();
  const theme = useTheme();
  const { account, positions, metrics, loading, error, lastUpdate, refresh } = bridge;

  const [pulse, setPulse] = useState(false);
  const [prevPnl, setPrevPnl] = useState(0);

  const openPnl = positions.reduce((s, p) => s + (p.profit || 0), 0);
  const openCount = positions.length;
  const successRate = metrics ? Math.round(metrics.win_rate * 1000) / 10 : 0;
  const pnlPositive = openPnl > prevPnl;
  const pnlNegative = openPnl < prevPnl;

  useEffect(() => {
    if (openPnl !== prevPnl && (pnlPositive || pnlNegative)) {
      setPulse(true);
      const id = setTimeout(() => setPulse(false), 600);
      setPrevPnl(openPnl);
      return () => clearTimeout(id);
    }
  }, [openPnl, prevPnl, pnlPositive, pnlNegative]);

  const balanceColor =
    account && account.equity < account.balance
      ? 'text-tnvs-loss'
      : account && account.equity > account.balance
        ? 'text-tnvs-win'
        : 'text-white';

  const marginLevelPct = account?.margin_level ?? null;
  const marginLevelWarn = marginLevelPct !== null && marginLevelPct < 200;

  return (
    <header className="z-20 flex items-center gap-3 border-b border-tnvs-border bg-tnvs-void/70 px-4 py-2 backdrop-blur">
      <div className="flex items-baseline gap-2">
        <h1 className="text-base font-semibold text-white">Terminal Financiera</h1>
        <span className="text-[10px] text-tnvs-muted">
          ·{' '}
          {loading
            ? 'Cargando...'
            : error
              ? <span className="text-tnvs-loss">offline</span>
              : <span className="inline-flex items-center gap-1">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-tnvs-win" />
                  Live
                </span>}
        </span>
      </div>

      <div className="ml-auto flex items-center gap-2">
        <KpiTop
          icon={DollarSign}
          label="Balance"
          value={account ? `$${account.balance.toLocaleString('en-US', { maximumFractionDigits: 2 })}` : '—'}
          color="text-tnvs-muted"
        />
        <KpiTop
          icon={BarChart3}
          label="Equity"
          value={account ? `$${account.equity.toLocaleString('en-US', { maximumFractionDigits: 2 })}` : '—'}
          color={balanceColor}
        />
        <KpiTop
          icon={Shield}
          label="Margin Lvl"
          value={
            marginLevelPct === null
              ? '—'
              : `${marginLevelPct.toFixed(2)}%`
          }
          color={marginLevelWarn ? 'text-tnvs-loss' : 'text-tnvs-win'}
          warn={marginLevelWarn}
        />
        <KpiTop
          icon={Activity}
          label="Open Pos"
          value={String(openCount)}
          color={openCount > 0 ? 'text-tnvs-warn' : 'text-tnvs-dim'}
        />
        <KpiTop
          icon={openPnl >= 0 ? TrendingUp : TrendingDown}
          label="Unreal P&L"
          value={
            loading
              ? '—'
              : `${openPnl >= 0 ? '+' : ''}$${openPnl.toFixed(2)}`
          }
          color={openPnl > 0 ? 'text-tnvs-win' : openPnl < 0 ? 'text-tnvs-loss' : 'text-tnvs-dim'}
          pulse={pulse}
          pulsePos={pnlPositive}
        />
        <KpiTop
          icon={TrendingUp}
          label="Win Rate"
          value={metrics ? `${successRate.toFixed(1)}%` : '—'}
          color={
            successRate >= 60
              ? 'text-tnvs-win'
              : successRate >= 40
                ? 'text-tnvs-warn'
                : successRate > 0
                  ? 'text-tnvs-loss'
                  : 'text-tnvs-dim'
          }
        />

        <button
          onClick={refresh}
          title={lastUpdate ? `Actualizado ${new Date(lastUpdate).toLocaleTimeString()}` : ''}
          className="ml-1 inline-flex items-center justify-center rounded-md p-1 text-tnvs-muted hover:bg-white/[0.04] hover:text-white"
        >
          <RefreshCw className="h-3.5 w-3.5" />
        </button>

        <ThemeToggle theme={theme} />

        <div className="flex items-center gap-2 rounded-lg border border-tnvs-border bg-tnvs-surface px-2.5 py-1">
          <div className={cls('h-1.5 w-1.5 rounded-full', account ? 'bg-tnvs-win' : 'bg-tnvs-dim')} />
          <span className="text-xs text-tnvs-muted">{user?.username || user?.email}</span>
        </div>
      </div>
    </header>
  );
});

function KpiTop({
  icon: Icon,
  label,
  value,
  color,
  warn,
  pulse,
  pulsePos,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  color?: string;
  warn?: boolean;
  pulse?: boolean;
  pulsePos?: boolean;
}) {
  return (
    <div
      className={cls(
        'flex flex-col gap-0.5 rounded-md border px-2.5 py-1 transition-colors',
        warn ? 'border-tnvs-loss/40 bg-tnvs-loss/5' : 'border-tnvs-border bg-tnvs-surface/50',
        pulse && pulsePos && 'ring-1 ring-tnvs-win',
        pulse && !pulsePos && 'ring-1 ring-tnvs-loss',
      )}
    >
      <div className="flex items-center gap-1 text-[9px] font-medium uppercase tracking-wider text-tnvs-muted">
        <Icon className="h-2.5 w-2.5" />
        {label}
      </div>
      <span className={cls('font-mono text-xs font-medium leading-tight tabular-nums', color)}>{value}</span>
    </div>
  );
}

function ThemeToggle({ theme }: { theme: ReturnType<typeof useTheme> }) {
  const options: { value: ThemeMode; icon: React.ElementType; label: string }[] = [
    { value: 'dark', icon: Moon, label: 'Oscuro' },
    { value: 'light', icon: Sun, label: 'Claro' },
    { value: 'sepia', icon: BookOpen, label: 'Sepia' },
    { value: 'auto', icon: Monitor, label: 'Auto' },
  ];
  return (
    <div className="inline-flex items-center gap-0.5 rounded-md border border-tnvs-border bg-tnvs-surface/50 p-0.5">
      {options.map(o => {
        const Icon = o.icon;
        const active = theme.theme === o.value;
        return (
          <button
            key={o.value}
            onClick={() => theme.setTheme(o.value)}
            title={o.label}
            className={cls(
              'inline-flex items-center justify-center rounded p-1.5 transition-colors',
              active
                ? 'bg-tnvs-purple text-white'
                : 'text-tnvs-muted hover:bg-white/[0.06] hover:text-white',
            )}
          >
            <Icon className="h-3.5 w-3.5" />
          </button>
        );
      })}
    </div>
  );
}
