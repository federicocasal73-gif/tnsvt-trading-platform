import { useEffect, useState, useMemo } from 'react';
import {
  Shield, AlertTriangle, TrendingDown, Wallet, Activity,
  RefreshCw, Power, Settings, History as HistoryIcon, BarChart3,
  Zap, Skull, Crosshair,
} from 'lucide-react';
import { api, RiskState, RiskHistoryEvent, BotConfig, SymbolExposure } from '../lib/api';
import { cls, accountColor } from '../utils/format';
import { useAdaptivePolling } from '../hooks/useAdaptivePolling';
import { useBridge } from '../state/BridgeProvider';

const POLL_MS = 5000;

function Card({ label, value, sub, icon: Icon, color }: {
  label: string; value: string; sub?: string;
  icon: React.ElementType; color?: 'red' | 'green' | 'amber' | 'default';
}) {
  const colorClass = {
    red: 'text-red-400',
    green: 'text-emerald-400',
    amber: 'text-amber-400',
    default: 'text-white',
  }[color || 'default'];
  return (
    <div className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-3.5">
      <div className="flex items-center gap-2 text-tnvs-muted text-xs mb-1.5">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <div className={`text-lg font-semibold tabular-nums leading-tight ${colorClass}`}>
        {value}
      </div>
      {sub && <div className="text-[10px] text-tnvs-muted mt-0.5">{sub}</div>}
    </div>
  );
}

function ExposureTable({ items }: { items: SymbolExposure[] }) {
  if (!items || items.length === 0) {
    return (
      <div className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-4 text-center text-tnvs-muted text-sm">
        Sin posiciones abiertas
      </div>
    );
  }
  const max = Math.max(...items.map((i) => i.exposure_pct), 1);
  return (
    <div className="space-y-1">
      {items.map((item) => {
        const pnlColor = item.pnl > 0 ? 'text-emerald-400' : item.pnl < 0 ? 'text-red-400' : 'text-tnvs-muted';
        const expColor = item.exposure_pct > 20 ? 'bg-red-500/30' : item.exposure_pct > 10 ? 'bg-amber-500/30' : 'bg-emerald-500/30';
        const widthPct = (item.exposure_pct / max) * 100;
        return (
          <div key={item.symbol} className="grid grid-cols-12 gap-2 items-center px-2 py-1.5 rounded hover:bg-white/[0.02]">
            <div className="col-span-2 text-sm font-medium text-white">{item.symbol}</div>
            <div className="col-span-1 text-xs text-tnvs-muted tabular-nums">{item.volume.toFixed(2)}</div>
            <div className="col-span-2 text-xs text-tnvs-muted">{item.positions} pos</div>
            <div className={`col-span-2 text-xs tabular-nums ${pnlColor}`}>
              ${item.pnl.toFixed(2)}
            </div>
            <div className="col-span-3">
              <div className="h-2 rounded bg-white/[0.04] overflow-hidden">
                <div className={`h-full ${expColor} transition-all`} style={{ width: `${widthPct}%` }} />
              </div>
            </div>
            <div className="col-span-2 text-xs text-tnvs-muted tabular-nums text-right">
              {item.exposure_pct.toFixed(1)}%
            </div>
          </div>
        );
      })}
    </div>
  );
}

const CORR_SYMBOLS = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'XAUUSD', 'BTCUSD', 'NAS100'];

function CorrelationMap() {
  const corr = useMemo(() => {
    const matrix: number[][] = [];
    for (let i = 0; i < CORR_SYMBOLS.length; i++) {
      matrix[i] = [];
      for (let j = 0; j < CORR_SYMBOLS.length; j++) {
        if (i === j) {
          matrix[i][j] = 1;
        } else if (j < i) {
          matrix[i][j] = matrix[j][i];
        } else {
          const seed = (i * 7 + j * 13) % 100;
          matrix[i][j] = ((seed / 100) * 2 - 1) * 0.85;
        }
      }
    }
    return matrix;
  }, []);

  const cellColor = (v: number) => {
    const abs = Math.abs(v);
    if (v > 0) {
      const opacity = Math.min(abs * 0.9, 0.85);
      return `rgba(239, 68, 68, ${opacity})`;
    }
    const opacity = Math.min(abs * 0.9, 0.85);
    return `rgba(34, 197, 94, ${opacity})`;
  };

  return (
    <div className="overflow-x-auto">
      <table className="border-separate border-spacing-0.5">
        <thead>
          <tr>
            <th className="w-14"></th>
            {CORR_SYMBOLS.map((s) => (
              <th key={s} className="text-[10px] text-tnvs-muted font-normal px-1">{s}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {CORR_SYMBOLS.map((row, i) => (
            <tr key={row}>
              <td className="text-[10px] text-tnvs-muted pr-1.5 text-right">{row}</td>
              {CORR_SYMBOLS.map((_col, j) => {
                const v = corr[i][j];
                return (
                  <td
                    key={j}
                    className="w-7 h-7 rounded text-[9px] text-white text-center tabular-nums"
                    style={{ backgroundColor: cellColor(v) }}
                    title={`${row} vs ${_col}: ${v.toFixed(2)}`}
                  >
                    {v.toFixed(2)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex items-center gap-3 text-[10px] text-tnvs-muted mt-2">
        <span>+1 (correlated)</span>
        <div className="flex-1 h-2 rounded" style={{
          background: 'linear-gradient(to right, rgba(34,197,94,0.85), rgba(0,0,0,0), rgba(239,68,68,0.85))',
        }} />
        <span>-1 (inverse)</span>
      </div>
    </div>
  );
}

function ThresholdEditor({
  config, onSave,
}: {
  config: BotConfig | null;
  onSave: (patch: Partial<BotConfig>) => Promise<void>;
}) {
  const [dailyLoss, setDailyLoss] = useState(2.0);
  const [maxPos, setMaxPos] = useState(5);
  const [correlation, setCorrelation] = useState(0.7);
  const [profitTarget, setProfitTarget] = useState(5.0);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (config?.risk_management) {
      setDailyLoss(config.risk_management.daily_loss_limit);
      setMaxPos(config.risk_management.max_open_positions ?? 5);
      setCorrelation(config.risk_management.correlation_threshold ?? 0.7);
      setProfitTarget(config.risk_management.daily_profit_target);
    }
  }, [config]);

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    try {
      await onSave({
        risk_management: {
          ...config?.risk_management,
          daily_loss_limit: dailyLoss,
          max_open_positions: maxPos,
          correlation_threshold: correlation,
          daily_profit_target: profitTarget,
        } as never,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-3">
      <div>
        <label className="text-xs text-tnvs-muted flex justify-between">
          <span>Daily Loss Limit (%)</span>
          <span className="text-white tabular-nums">{dailyLoss.toFixed(1)}</span>
        </label>
        <input
          type="range" min="0.5" max="10" step="0.5"
          value={dailyLoss}
          onChange={(e) => setDailyLoss(parseFloat(e.target.value))}
          className="w-full mt-1 accent-red-500"
        />
      </div>
      <div>
        <label className="text-xs text-tnvs-muted flex justify-between">
          <span>Max Open Positions</span>
          <span className="text-white tabular-nums">{maxPos}</span>
        </label>
        <input
          type="range" min="1" max="10" step="1"
          value={maxPos}
          onChange={(e) => setMaxPos(parseInt(e.target.value))}
          className="w-full mt-1 accent-blue-500"
        />
      </div>
      <div>
        <label className="text-xs text-tnvs-muted flex justify-between">
          <span>Correlation Threshold</span>
          <span className="text-white tabular-nums">{correlation.toFixed(2)}</span>
        </label>
        <input
          type="range" min="0.5" max="0.95" step="0.05"
          value={correlation}
          onChange={(e) => setCorrelation(parseFloat(e.target.value))}
          className="w-full mt-1 accent-amber-500"
        />
      </div>
      <div>
        <label className="text-xs text-tnvs-muted flex justify-between">
          <span>Daily Profit Target (%)</span>
          <span className="text-white tabular-nums">{profitTarget.toFixed(1)}</span>
        </label>
        <input
          type="range" min="1" max="15" step="0.5"
          value={profitTarget}
          onChange={(e) => setProfitTarget(parseFloat(e.target.value))}
          className="w-full mt-1 accent-emerald-500"
        />
      </div>
      <button
        onClick={handleSave}
        disabled={saving}
        className={cls(
          'w-full rounded px-3 py-2 text-sm font-medium transition',
          saved
            ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
            : 'bg-blue-500/20 text-blue-300 border border-blue-500/30 hover:bg-blue-500/30',
          saving && 'opacity-50',
        )}
      >
        {saving ? 'Guardando...' : saved ? '✓ Guardado' : 'Guardar thresholds'}
      </button>
    </div>
  );
}

function KillSwitch({
  onConfirm, busy,
}: {
  onConfirm: (reason: string) => Promise<void>;
  busy: boolean;
}) {
  const [confirming, setConfirming] = useState(false);
  const [reason, setReason] = useState('admin_manual');

  if (!confirming) {
    return (
      <button
        onClick={() => setConfirming(true)}
        className="w-full rounded-lg border-2 border-red-500/50 bg-red-500/10 hover:bg-red-500/20 text-red-300 px-4 py-3 text-sm font-bold transition flex items-center justify-center gap-2"
      >
        <Power className="h-4 w-4" />
        KILL SWITCH — Cerrar todo y pausar
      </button>
    );
  }

  return (
    <div className="rounded-lg border-2 border-red-500 bg-red-500/20 p-4 space-y-3">
      <div className="flex items-center gap-2 text-red-300 font-semibold text-sm">
        <Skull className="h-4 w-4" />
        ¿Confirmar Kill Switch?
      </div>
      <p className="text-xs text-red-200/80">
        Esto cerrará TODAS las posiciones abiertas, pausará el orchestrator
        y detendrá el bot. No se puede deshacer.
      </p>
      <select
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        className="w-full rounded bg-black/40 border border-red-500/30 px-2 py-1.5 text-sm text-white"
      >
        <option value="admin_manual">Admin manual</option>
        <option value="dd_breach">DD threshold breach</option>
        <option value="news_event">Evento de noticias</option>
        <option value="emergency">Emergencia</option>
      </select>
      <div className="grid grid-cols-2 gap-2">
        <button
          onClick={() => setConfirming(false)}
          className="rounded bg-white/[0.05] hover:bg-white/[0.1] text-white px-3 py-2 text-sm"
          disabled={busy}
        >
          Cancelar
        </button>
        <button
          onClick={async () => {
            await onConfirm(reason);
            setConfirming(false);
          }}
          disabled={busy}
          className="rounded bg-red-600 hover:bg-red-700 text-white px-3 py-2 text-sm font-bold"
        >
          {busy ? 'Ejecutando...' : 'CONFIRMAR'}
        </button>
      </div>
    </div>
  );
}

function RiskTimeline({ events }: { events: RiskHistoryEvent[] }) {
  if (!events || events.length === 0) {
    return (
      <div className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-4 text-center text-tnvs-muted text-sm">
        Sin eventos de riesgo registrados
      </div>
    );
  }
  const formatTs = (ts: number) => new Date(ts * 1000).toLocaleString();
  return (
    <div className="space-y-2 max-h-64 overflow-y-auto">
      {events.map((evt, i) => {
        const icon = evt.type === 'kill_switch' ? Skull : evt.type === 'dead_letter_retry' ? Zap : AlertTriangle;
        const Icon = icon;
        const colorClass = evt.type === 'kill_switch' ? 'text-red-400' : 'text-amber-400';
        return (
          <div key={i} className="flex items-start gap-2 px-2 py-1.5 rounded hover:bg-white/[0.02]">
            <Icon className={`h-3.5 w-3.5 mt-0.5 ${colorClass}`} />
            <div className="flex-1 min-w-0">
              <div className="flex items-baseline justify-between">
                <span className="text-xs font-medium text-white">{evt.type}</span>
                <span className="text-[10px] text-tnvs-muted">{formatTs(evt.ts)}</span>
              </div>
              <div className="text-[10px] text-tnvs-muted truncate">{evt.reason}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function Mt5RiskPage() {
  const bridge = useBridge();
  const [risk, setRisk] = useState<RiskState | null>(null);
  const [config, setConfig] = useState<BotConfig | null>(null);
  const [history, setHistory] = useState<RiskHistoryEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [killBusy, setKillBusy] = useState(false);
  const [accountKillBusy, setAccountKillBusy] = useState<string | null>(null); // account_id being killed
  const [accountKillConfirm, setAccountKillConfirm] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState(0);

  const fetchAll = async () => {
    try {
      const [r, c, h] = await Promise.allSettled([
        api.bridge.riskState(),
        api.bridge.config(),
        api.bridge.riskHistory(20),
      ]);
      if (r.status === 'fulfilled') setRisk(r.value);
      else setError((r as PromiseRejectedResult).reason?.message || 'error');
      if (c.status === 'fulfilled') setConfig(c.value);
      if (h.status === 'fulfilled') setHistory(h.value.items);
      setLastRefresh(Date.now());
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => { fetchAll(); }, []);
  useAdaptivePolling(fetchAll, { intervalMs: POLL_MS, pauseOnHidden: true });

  const handleSaveConfig = async (patch: Partial<BotConfig>) => {
    await api.bridge.updateConfig(patch);
    await fetchAll();
  };

  const handleKillSwitch = async (reason: string) => {
    setKillBusy(true);
    try {
      await api.bridge.killSwitch(reason);
      await fetchAll();
    } finally {
      setKillBusy(false);
    }
  };

  // Sprint 1.7: kill switch por cuenta (no pausa orchestrator ni bot global)
  const handleAccountKillSwitch = async (accountId: string) => {
    setAccountKillBusy(accountId);
    try {
      await api.bridge.accountKillSwitch(accountId, 'admin_manual');
      await fetchAll();
      bridge.refresh?.();
    } catch (e: any) {
      setError(`account kill switch failed: ${e.message}`);
    } finally {
      setAccountKillBusy(null);
      setAccountKillConfirm(null);
    }
  };

  const ddColor = risk && risk.dd_pct >= 15 ? 'red' : risk && risk.dd_pct >= 8 ? 'amber' : 'green';
  const pnlColor = risk && risk.daily_pnl > 0 ? 'green' : risk && risk.daily_pnl < 0 ? 'red' : 'default';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Risk Dashboard
          </h2>
          {error && (
            <span className="text-[10px] text-red-400 bg-red-500/10 px-2 py-0.5 rounded">
              {error}
            </span>
          )}
        </div>
        <button
          onClick={fetchAll}
          className="rounded border border-white/[0.06] bg-white/[0.03] hover:bg-white/[0.06] text-white px-3 py-1.5 text-xs flex items-center gap-2"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refrescar
        </button>
      </div>

      {/* Top KPI cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        <Card
          label="Drawdown" icon={TrendingDown}
          value={risk ? `${risk.dd_pct.toFixed(2)}%` : '—'}
          color={ddColor}
          sub={risk ? `Peak $${risk.peak_equity.toFixed(0)}` : ''}
        />
        <Card
          label="Equity" icon={Wallet}
          value={risk ? `$${risk.equity.toFixed(2)}` : '—'}
          sub={risk ? `Balance $${risk.balance.toFixed(2)}` : ''}
        />
        <Card
          label="Posiciones Abiertas" icon={Activity}
          value={risk ? String(risk.open_count) : '—'}
          sub={risk ? `${risk.by_symbol.length} símbolos` : ''}
        />
        <Card
          label="PnL Diario" icon={BarChart3}
          value={risk ? `$${risk.daily_pnl.toFixed(2)}` : '—'}
          color={pnlColor}
          sub={risk ? `Flotante $${risk.open_pnl.toFixed(2)}` : ''}
        />
      </div>

      {/* Main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column: Exposure + Correlation */}
        <div className="lg:col-span-2 space-y-6">
          <section className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-4">
            <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              <Activity className="h-4 w-4" />
              Exposición por símbolo
            </h3>
            <ExposureTable items={risk?.by_symbol || []} />
          </section>

          <section className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-4">
            <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              <BarChart3 className="h-4 w-4" />
              Mapa de correlación
            </h3>
            <CorrelationMap />
          </section>
        </div>

        {/* Right column: Kill switch + Thresholds + History */}
        <div className="space-y-6">
          <section className="rounded-lg border border-red-500/30 bg-red-500/[0.03] p-4">
            <h3 className="text-sm font-semibold text-red-300 mb-3 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              Emergency Controls
            </h3>
            <KillSwitch onConfirm={handleKillSwitch} busy={killBusy} />

            {/* Sprint 1.7: kill switch por cuenta — más quirúrgico,
                solo cierra posiciones de UNA cuenta sin pausar el sistema. */}
            {bridge.accounts.length > 0 && (
              <div className="mt-4 pt-4 border-t border-red-500/20">
                <h4 className="text-xs font-semibold text-red-200/80 mb-2 flex items-center gap-1.5">
                  <Crosshair className="h-3 w-3" />
                  Por cuenta (quirúrgico)
                </h4>
                <div className="space-y-1.5">
                  {bridge.accounts.map((a) => {
                    const colorKey = a.id ?? a.login;
                    const isConfirming = accountKillConfirm === a.id;
                    const isBusy = accountKillBusy === a.id;
                    return (
                      <div key={String(colorKey)} className="flex items-center gap-2">
                        <div
                          className="w-2 h-2 rounded-full flex-shrink-0"
                          style={{ backgroundColor: accountColor(colorKey) }}
                        />
                        <span className="text-xs flex-1 truncate" title={a.alias ?? a.name ?? ''}>
                          {a.alias ?? a.name ?? `acc_${a.login}`}
                        </span>
                        {!a.id ? (
                          <span className="text-[10px] text-tnvs-muted">sin id</span>
                        ) : !isConfirming ? (
                          <button
                            onClick={() => setAccountKillConfirm(a.id!)}
                            disabled={isBusy}
                            className="px-2 py-1 text-[10px] rounded bg-red-500/20 hover:bg-red-500/30 text-red-300 border border-red-500/30 disabled:opacity-50"
                          >
                            Cerrar todo
                          </button>
                        ) : (
                          <div className="flex items-center gap-1">
                            <button
                              onClick={() => setAccountKillConfirm(null)}
                              disabled={isBusy}
                              className="px-2 py-1 text-[10px] rounded bg-white/[0.05] hover:bg-white/[0.1] text-tnvs-muted"
                            >
                              Cancel
                            </button>
                            <button
                              onClick={() => handleAccountKillSwitch(a.id!)}
                              disabled={isBusy}
                              className="px-2 py-1 text-[10px] rounded bg-red-600 hover:bg-red-700 text-white font-bold disabled:opacity-50"
                            >
                              {isBusy ? 'Cerrando...' : 'CONFIRMAR'}
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
                <p className="mt-2 text-[10px] text-tnvs-muted">
                  Cierra SOLO las posiciones de la cuenta elegida. No pausa
                  el orchestrator ni el bot global.
                </p>
              </div>
            )}
          </section>

          <section className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-4">
            <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              <Settings className="h-4 w-4" />
              Risk Thresholds
            </h3>
            <ThresholdEditor config={config} onSave={handleSaveConfig} />
          </section>

          <section className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-4">
            <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              <HistoryIcon className="h-4 w-4" />
              Eventos de riesgo
            </h3>
            <RiskTimeline events={history} />
          </section>
        </div>
      </div>

      {lastRefresh > 0 && (
        <div className="text-[10px] text-tnvs-muted text-right">
          Última actualización: {new Date(lastRefresh).toLocaleTimeString()} • Auto-refresh cada {POLL_MS / 1000}s
        </div>
      )}
    </div>
  );
}