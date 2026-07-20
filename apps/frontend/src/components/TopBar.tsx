import { memo, useEffect, useState } from 'react';
import { useAuth } from '../lib/auth';
import { useBridge } from '../state/BridgeProvider';
import { useTheme, ThemeMode } from '../state/ThemeProvider';
import { cls, fmtUsd, fmtPct } from '../utils/format';
import { Activity, TrendingUp, TrendingDown, DollarSign, Shield, BarChart3, RefreshCw, Moon, Sun, BookOpen, Crown, Wallet, Layers } from 'lucide-react';

export const TopBar = memo(function TopBar() {
  const { user } = useAuth();
  const bridge = useBridge();
  const theme = useTheme();
  const {
    account,
    positions,
    aggregate,
    accounts,
    metrics,
    selectedLogin,
    selectAccount,
    loading,
    error,
    lastUpdate,
    refresh,
  } = bridge;

  const [pulse, setPulse] = useState(false);
  const [prevPnl, setPrevPnl] = useState(0);

  // Para multi-cuenta, si hay varias cuentas se ve el agregado.
  // Si hay UNA sola, se ve los datos de esa cuenta (legacy).
  const multiple = accounts.length > 1;
  const totalBalance = multiple ? aggregate.total_balance : (account?.balance ?? 0);
  const totalEquity = multiple ? aggregate.total_equity : (account?.equity ?? 0);
  const totalPnl = multiple ? aggregate.total_pnl : positions.reduce((s, p) => s + (p.profit || 0), 0);
  const totalOpen = multiple ? aggregate.total_open_positions : positions.length;

  const successRate = metrics ? Math.round(metrics.win_rate * 1000) / 10 : 0;
  const pnlPositive = totalPnl > prevPnl;
  const pnlNegative = totalPnl < prevPnl;

  useEffect(() => {
    if (totalPnl !== prevPnl && (pnlPositive || pnlNegative)) {
      setPulse(true);
      const id = setTimeout(() => setPulse(false), 600);
      setPrevPnl(totalPnl);
      return () => clearTimeout(id);
    }
  }, [totalPnl, prevPnl, pnlPositive, pnlNegative]);

  const equityColor =
    account && account.equity < account.balance
      ? 'text-tnvs-loss'
      : account && account.equity > account.balance
        ? 'text-tnvs-win'
        : 'text-white';

  // Margin level aplica solo a una cuenta, no al agregado
  const marginLevelPct = account?.margin_level ?? null;
  const marginLevelWarn = marginLevelPct !== null && marginLevelPct < 200;

  const selectedAccount = accounts.find(a => a.login === selectedLogin);

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
                  Live {multiple ? `· ${accounts.length} cuentas` : ''}
                </span>}
        </span>
      </div>

      {/* Selector de cuenta (si hay multiples) */}
      {accounts.length > 1 && (
        <AccountSelector
          accounts={accounts}
          selectedLogin={selectedLogin}
          onSelect={selectAccount}
        />
      )}

      <div className="ml-auto flex items-center gap-2">
        <KpiTop
          icon={multiple ? Layers : Wallet}
          label={multiple ? 'Bal Total' : 'Balance'}
          value={totalBalance != null ? `$${totalBalance.toLocaleString('en-US', { maximumFractionDigits: 2 })}` : '—'}
          color="text-tnvs-muted"
        />
        <KpiTop
          icon={BarChart3}
          label={multiple ? 'Equity Total' : 'Equity'}
          value={totalEquity != null ? `$${totalEquity.toLocaleString('en-US', { maximumFractionDigits: 2 })}` : '—'}
          color={multiple ? 'text-tnvs-muted' : equityColor}
        />
        {!multiple && (
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
        )}
        <KpiTop
          icon={Activity}
          label="Open Pos"
          value={String(totalOpen)}
          color={totalOpen > 0 ? 'text-tnvs-warn' : 'text-tnvs-dim'}
        />
        <KpiTop
          icon={totalPnl >= 0 ? TrendingUp : TrendingDown}
          label="Unreal P&L"
          value={
            loading
              ? '—'
              : `${totalPnl >= 0 ? '+' : ''}$${totalPnl.toFixed(2)}`
          }
          color={totalPnl > 0 ? 'text-tnvs-win' : totalPnl < 0 ? 'text-tnvs-loss' : 'text-tnvs-dim'}
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
          <div className={cls('h-1.5 w-1.5 rounded-full', accounts.length > 0 ? 'bg-tnvs-win' : 'bg-tnvs-dim')} />
          <span className="text-xs text-tnvs-muted">{user?.username || user?.email}</span>
        </div>
      </div>
    </header>
  );
});

function AccountSelector({ accounts, selectedLogin, onSelect }: {
  accounts: Array<{ login: number; alias: string; name: string }>;
  selectedLogin: number | null;
  onSelect: (login: number | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const current = accounts.find(a => a.login === selectedLogin);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className="inline-flex items-center gap-1.5 rounded-md border border-tnvs-border bg-tnvs-surface px-2.5 py-1 text-xs text-white hover:bg-tnvs-surface2"
      >
        <Layers className="h-3.5 w-3.5 text-tnvs-purple" />
        <span className="font-mono">
          {current ? `${current.alias} (${current.login})` : `Total (${accounts.length})`}
        </span>
      </button>
      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 w-64 rounded-md border border-tnvs-border bg-tnvs-surface p-1 shadow-tnvs-strong">
          <button
            onClick={() => { onSelect(null); setOpen(false); }}
            className={cls(
              'flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-xs hover:bg-white/[0.06]',
              selectedLogin == null ? 'bg-tnvs-purple/20 text-tnvs-purple' : 'text-white',
            )}
          >
            <span>📊 Total agregado</span>
            <span className="text-[10px] text-tnvs-dim">todas</span>
          </button>
          <div className="my-1 h-px bg-tnvs-border" />
          {accounts.map(a => (
            <button
              key={a.login}
              onClick={() => { onSelect(a.login); setOpen(false); }}
              className={cls(
                'flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-xs hover:bg-white/[0.06]',
                selectedLogin === a.login ? 'bg-tnvs-purple/20 text-tnvs-purple' : 'text-white',
              )}
            >
              <span className="font-mono">{a.alias}</span>
              <span className="text-[10px] text-tnvs-dim">{a.login}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

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
    { value: 'gold', icon: Crown, label: 'Gold/Black' },
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
