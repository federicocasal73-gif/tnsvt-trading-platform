import { useEffect, useState } from 'react';
import { Save, RotateCcw, AlertTriangle, CheckCircle2, Activity, Zap, Wifi, WifiOff } from 'lucide-react';
import { api, BotConfig } from '../lib/api';
import { useBridge } from '../state/BridgeProvider';
import { cls } from '../utils/format';
import { Card, Page, Switch, NumberInput, PercentInput } from '../components/common';

type Toast = { kind: 'ok' | 'err'; msg: string } | null;

const DEFAULTS = {
  lot_mode: 'FIXED' as 'FIXED' | 'PERCENTAGE',
  lot_size: 0.01,
  lot_percentage: 0.5,
  deviation: 20,
  symbol_suffix: '',
  active_daily_profit: false,
  daily_profit_target: 2.0,
  active_daily_loss: false,
  daily_loss_limit: 2.0,
  active_weekly_profit: false,
  weekly_profit: 5.0,
  active_weekly_loss: false,
  weekly_loss: 5.0,
  active_monthly_profit: false,
  monthly_profit: 15.0,
  active_monthly_loss: false,
  monthly_loss: 10.0,
};

export function Mt5SettingsPage() {
  const bridge = useBridge();
  const [cfg, setCfg] = useState<BotConfig | null>(null);
  const [draft, setDraft] = useState<BotConfig | null>(null);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);
  const [dirty, setDirty] = useState(false);

  const load = async () => {
    try {
      const c = await api.bridge.config();
      setCfg(c);
      setDraft(c);
      setDirty(false);
    } catch (e: any) {
      setToast({ kind: 'err', msg: e.message });
    }
  };

  useEffect(() => {
    load();
  }, []);

  const update = (patch: Partial<BotConfig>) => {
    setDraft(d => (d ? { ...d, ...patch } : d));
    setDirty(true);
  };

  const updateRisk = (patch: Record<string, unknown>) => {
    setDraft(d => (d ? { ...d, risk_management: { ...(d.risk_management || {}), ...patch } as any } : d));
    setDirty(true);
  };

  const handleSave = async () => {
    if (!draft) return;
    setSaving(true);
    setToast(null);
    try {
      const patch: Record<string, unknown> = {
        lot_mode: draft.lot_mode || DEFAULTS.lot_mode,
        lot_size: draft.lot_size ?? DEFAULTS.lot_size,
        lot_percentage: draft.lot_percentage ?? DEFAULTS.lot_percentage,
        deviation: draft.deviation ?? DEFAULTS.deviation,
        symbol_suffix: draft.symbol_suffix ?? DEFAULTS.symbol_suffix,
        risk_management: draft.risk_management,
        trailing_stop: (draft as any).trailing_stop || { enabled: false, step_pips: 30, start_pips: 20 },
      };
      const res = await api.bridge.updateConfig(patch);
      setToast({ kind: 'ok', msg: `Guardado: ${res.updated_keys.join(', ')}` });
      setDirty(false);
      await load();
    } catch (e: any) {
      setToast({ kind: 'err', msg: e.message });
    } finally {
      setSaving(false);
    }
    setTimeout(() => setToast(null), 4000);
  };

  const handleReset = () => {
    setDraft(cfg);
    setDirty(false);
  };

  if (!draft) {
    return (
      <Page title="MT5 · Settings" subtitle="Configuración de operativa y riesgo">
        <div className="text-sm text-tnvs-muted">Cargando…</div>
      </Page>
    );
  }

  const risk = (draft.risk_management || {}) as any;
  const safeNum = (v: any, fb: number) => (typeof v === 'number' ? v : fb);

  const trailing = (draft as any).trailing_stop || { enabled: false, step_pips: 30, start_pips: 20 };
  const mt5Online = bridge.openPositions > 0 || !!bridge.account;
  const trailingActive = !!trailing.enabled;

  return (
    <Page
      title="MT5 · Settings"
      subtitle="Modo de lote, riesgo y operativa"
      actions={
        <div className="flex items-center gap-2">
          <button
            onClick={handleReset}
            disabled={!dirty || saving}
            className="inline-flex items-center gap-1.5 rounded-md border border-tnvs-border bg-tnvs-surface px-3 py-1.5 text-xs text-tnvs-muted hover:text-white disabled:opacity-40"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Reset
          </button>
          <button
            onClick={handleSave}
            disabled={!dirty || saving}
            className="inline-flex items-center gap-1.5 rounded-md bg-tnvs-purple px-3 py-1.5 text-xs font-medium text-white hover:bg-tnvs-purple/80 disabled:opacity-40"
          >
            <Save className="h-3.5 w-3.5" />
            {saving ? 'Guardando…' : 'Guardar'}
          </button>
        </div>
      }
    >
      {toast && (
        <div
          className={cls(
            'mb-4 inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs',
            toast.kind === 'ok'
              ? 'border-tnvs-win/40 bg-tnvs-win/10 text-tnvs-win'
              : 'border-tnvs-loss/40 bg-tnvs-loss/10 text-tnvs-loss',
          )}
        >
          {toast.kind === 'ok' ? <CheckCircle2 className="h-3.5 w-3.5" /> : <AlertTriangle className="h-3.5 w-3.5" />}
          {toast.msg}
        </div>
      )}

      {/* Banner de estado MT5 + Trailing */}
      <div className="mb-4 grid grid-cols-3 gap-3">
        <div
          className={cls(
            'flex items-center gap-2.5 rounded-lg border bg-tnvs-surface px-3 py-2',
            mt5Online ? 'border-tnvs-win/40' : 'border-tnvs-loss/40',
          )}
        >
          {mt5Online ? <Wifi className="h-4 w-4 text-tnvs-win" /> : <WifiOff className="h-4 w-4 text-tnvs-loss" />}
          <div className="text-xs">
            <div className={mt5Online ? 'text-tnvs-win' : 'text-tnvs-loss'}>MT5 {mt5Online ? 'Conectado' : 'Desconectado'}</div>
            <div className="text-tnvs-muted">
              {bridge.account ? `Balance $${bridge.account.balance.toLocaleString()}` : 'sin snapshot'}
            </div>
          </div>
        </div>

        <div
          className={cls(
            'flex items-center gap-2.5 rounded-lg border bg-tnvs-surface px-3 py-2',
            trailingActive ? 'border-tnvs-purple/40' : 'border-tnvs-border',
          )}
        >
          <Zap className={cls('h-4 w-4', trailingActive ? 'text-tnvs-purple' : 'text-tnvs-dim')} />
          <div className="text-xs">
            <div className={trailingActive ? 'text-tnvs-purple' : 'text-tnvs-muted'}>
              Trailing {trailingActive ? 'ACTIVO' : 'apagado'}
            </div>
            <div className="text-tnvs-muted">
              {trailingActive
                ? `start=${trailing.start_pips} pips · step=${trailing.step_pips} pips`
                : 'mueve SL a favor cuando hay ganancia'}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2.5 rounded-lg border border-tnvs-border bg-tnvs-surface px-3 py-2">
          <Activity className="h-4 w-4 text-tnvs-cyan" />
          <div className="text-xs">
            <div className="text-tnvs-cyan">Posiciones abiertas: {bridge.openPositions}</div>
            <div className="text-tnvs-muted">
              P&L flotante:{' '}
              <span className={cls('font-mono', bridge.unrealizedPnl > 0 ? 'text-tnvs-win' : bridge.unrealizedPnl < 0 ? 'text-tnvs-loss' : 'text-tnvs-muted')}>
                {bridge.unrealizedPnl >= 0 ? '+' : ''}${bridge.unrealizedPnl.toFixed(2)}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card header="Broker / Operativa">
          <div className="space-y-4">
            <div>
              <div className="text-xs font-medium text-tnvs-muted">Modo de lote</div>
              <div className="mt-2 flex gap-2">
                {(['FIXED', 'PERCENTAGE'] as const).map(mode => (
                  <button
                    key={mode}
                    onClick={() => update({ lot_mode: mode })}
                    className={cls(
                      'rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                      draft.lot_mode === mode
                        ? 'bg-tnvs-purple text-white'
                        : 'border border-tnvs-border bg-tnvs-void text-tnvs-muted hover:text-white',
                    )}
                  >
                    {mode === 'FIXED' ? 'Lote Fijo' : 'Riesgo Dinámico %'}
                  </button>
                ))}
              </div>
            </div>

            {draft.lot_mode === 'FIXED' ? (
              <div>
                <div className="text-xs font-medium text-tnvs-muted">Tamaño lote fijo</div>
                <div className="mt-2">
                  <NumberInput
                    value={safeNum(draft.lot_size, DEFAULTS.lot_size)}
                    onChange={v => update({ lot_size: v })}
                    min={0.01}
                    step={0.01}
                  />
                </div>
              </div>
            ) : (
              <div>
                <div className="text-xs font-medium text-tnvs-muted">% riesgo por operación</div>
                <div className="mt-2 flex items-center gap-2">
                  <PercentInput
                    value={safeNum(draft.lot_percentage, DEFAULTS.lot_percentage) / 100}
                    onChange={v => {
                      const pct = Math.round(v * 10000) / 100;
                      const clamped = Math.max(0.01, Math.min(10.0, pct));
                      update({ lot_percentage: clamped });
                    }}
                    step={0.0025}
                    min={0.01}
                    max={10.0}
                  />
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => {
                        const cur = safeNum(draft.lot_percentage, DEFAULTS.lot_percentage);
                        update({ lot_percentage: Math.max(0.01, Math.round((cur - 0.25) * 100) / 100) });
                      }}
                      className="rounded border border-tnvs-border bg-tnvs-void px-1.5 py-0.5 text-xs text-tnvs-muted hover:text-white"
                      title="-0.25%"
                    >
                      −0.25
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        const cur = safeNum(draft.lot_percentage, DEFAULTS.lot_percentage);
                        update({ lot_percentage: Math.min(10.0, Math.round((cur + 0.25) * 100) / 100) });
                      }}
                      className="rounded border border-tnvs-border bg-tnvs-void px-1.5 py-0.5 text-xs text-tnvs-muted hover:text-white"
                      title="+0.25%"
                    >
                      +0.25
                    </button>
                    <button
                      type="button"
                      onClick={() => update({ lot_percentage: 0.5 })}
                      className="rounded border border-tnvs-border bg-tnvs-void px-1.5 py-0.5 text-xs text-tnvs-muted hover:text-white"
                      title="Set 0.5%"
                    >
                      0.5%
                    </button>
                    <button
                      type="button"
                      onClick={() => update({ lot_percentage: 1.0 })}
                      className="rounded border border-tnvs-border bg-tnvs-void px-1.5 py-0.5 text-xs text-tnvs-muted hover:text-white"
                      title="Set 1.0%"
                    >
                      1.0%
                    </button>
                  </div>
                </div>
              </div>
            )}

            <div>
              <div className="text-xs font-medium text-tnvs-muted">Desviación máxima (pips)</div>
              <div className="mt-2">
                <NumberInput
                  value={safeNum(draft.deviation, DEFAULTS.deviation)}
                  onChange={v => update({ deviation: v })}
                  min={1}
                  step={5}
                />
              </div>
            </div>

            <div>
              <div className="text-xs font-medium text-tnvs-muted">Symbol suffix (vacío = auto-detect)</div>
              <div className="mt-2">
                <input
                  value={draft.symbol_suffix || ''}
                  onChange={e => update({ symbol_suffix: e.target.value })}
                  placeholder=".pro, .ecn, ..."
                  className="tnvs-input w-48 font-mono text-sm"
                />
              </div>
            </div>
          </div>
        </Card>

        <Card header="Risk Management">
          <div className="space-y-3">
            <div className="grid grid-cols-3 gap-4">
              <RiskColumn
                title="Diaria"
                activeProfit={risk.active_daily_profit}
                targetProfit={safeNum(risk.daily_profit_target, DEFAULTS.daily_profit_target)}
                activeLoss={risk.active_daily_loss}
                limitLoss={safeNum(risk.daily_loss_limit, DEFAULTS.daily_loss_limit)}
                onToggleProfit={(v) => updateRisk({ active_daily_profit: v })}
                onChangeProfit={(v) => updateRisk({ daily_profit_target: v })}
                onToggleLoss={(v) => updateRisk({ active_daily_loss: v })}
                onChangeLoss={(v) => updateRisk({ daily_loss_limit: v })}
              />
              <RiskColumn
                title="Semanal"
                activeProfit={risk.active_weekly_profit}
                targetProfit={safeNum(risk.weekly_profit, DEFAULTS.weekly_profit)}
                activeLoss={risk.active_weekly_loss}
                limitLoss={safeNum(risk.weekly_loss, DEFAULTS.weekly_loss)}
                onToggleProfit={(v) => updateRisk({ active_weekly_profit: v })}
                onChangeProfit={(v) => updateRisk({ weekly_profit: v })}
                onToggleLoss={(v) => updateRisk({ active_weekly_loss: v })}
                onChangeLoss={(v) => updateRisk({ weekly_loss: v })}
              />
              <RiskColumn
                title="Mensual"
                activeProfit={risk.active_monthly_profit}
                targetProfit={safeNum(risk.monthly_profit, DEFAULTS.monthly_profit)}
                activeLoss={risk.active_monthly_loss}
                limitLoss={safeNum(risk.monthly_loss, DEFAULTS.monthly_loss)}
                onToggleProfit={(v) => updateRisk({ active_monthly_profit: v })}
                onChangeProfit={(v) => updateRisk({ monthly_profit: v })}
                onToggleLoss={(v) => updateRisk({ active_monthly_loss: v })}
                onChangeLoss={(v) => updateRisk({ monthly_loss: v })}
              />
            </div>
          </div>
        </Card>

        <Card header="Trailing Stop (Phase 1)">
          {(() => {
            const trailing = (draft as any).trailing_stop || { enabled: false, step_pips: 30, start_pips: 20 };
            const updateTrailing = (patch: any) => {
              setDraft((d) => d ? { ...d, trailing_stop: { ...(d as any).trailing_stop, ...patch } } as any : d);
              setDirty(true);
            };
            return (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm text-white">Activar Trailing Stop</div>
                    <div className="text-xs text-tnvs-muted">Mueve el SL hacia el precio cuando va a favor. Protege ganancias.</div>
                  </div>
                  <Switch
                    checked={!!trailing.enabled}
                    onChange={(v) => updateTrailing({ enabled: v })}
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className={cls('rounded-md bg-tnvs-void p-3', !trailing.enabled && 'opacity-40 pointer-events-none')}>
                    <div className="text-[10px] uppercase tracking-wider text-tnvs-muted mb-1">Trailing Start</div>
                    <NumberInput
                      value={safeNum(trailing.start_pips, 20)}
                      onChange={(v) => updateTrailing({ start_pips: v })}
                      min={1}
                      step={5}
                      suffix="pips"
                    />
                    <div className="text-[10px] text-tnvs-dim mt-1">
                      El SL empieza a moverse cuando la ganancia llega a este nivel
                    </div>
                  </div>
                  <div className={cls('rounded-md bg-tnvs-void p-3', !trailing.enabled && 'opacity-40 pointer-events-none')}>
                    <div className="text-[10px] uppercase tracking-wider text-tnvs-muted mb-1">Trailing Step</div>
                    <NumberInput
                      value={safeNum(trailing.step_pips, 30)}
                      onChange={(v) => updateTrailing({ step_pips: v })}
                      min={1}
                      step={5}
                      suffix="pips"
                    />
                    <div className="text-[10px] text-tnvs-dim mt-1">
                      Cuántos pips mantiene el SL detrás del precio
                    </div>
                  </div>
                </div>
              </div>
            );
          })()}
        </Card>

        <Card header="Conexión (solo lectura)" className="lg:col-span-2">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <ReadRow label="API ID" value={cfg?.api_id ? `${cfg.api_id.slice(0, 4)}…` : '—'} />
            <ReadRow label="API Hash" value={cfg?.api_hash ? `${cfg.api_hash.slice(0, 6)}…` : '—'} />
            <ReadRow label="Bridge URL" value={cfg?.bridge_url || '—'} mono />
            <ReadRow
              label="Canales configurados"
              value={`${(cfg?.channels_data || []).length} seleccionados`}
            />
          </div>
          <div className="mt-3 text-xs text-tnvs-dim">
            Para reconfigurar Telegram, usá <span className="font-medium text-tnvs-muted">MT5 Channels</span>.
          </div>
        </Card>
      </div>
    </Page>
  );
}

function RiskColumn({
  title, activeProfit, targetProfit, activeLoss, limitLoss,
  onToggleProfit, onChangeProfit, onToggleLoss, onChangeLoss,
}: {
  title: string;
  activeProfit: boolean;
  targetProfit: number;
  activeLoss: boolean;
  limitLoss: number;
  onToggleProfit: (v: boolean) => void;
  onChangeProfit: (v: number) => void;
  onToggleLoss: (v: boolean) => void;
  onChangeLoss: (v: number) => void;
}) {
  return (
    <div>
      <div className="text-xs font-medium uppercase tracking-wider text-tnvs-muted">{title}</div>
      <div className="mt-3 space-y-3">
        <div className="rounded-md bg-tnvs-void p-3">
          <Switch
            checked={activeProfit}
            onChange={onToggleProfit}
            label="Meta profit"
          />
          <div className={cls('mt-2', !activeProfit && 'opacity-40 pointer-events-none')}>
            <NumberInput
              value={targetProfit}
              onChange={onChangeProfit}
              min={0}
              step={0.5}
              suffix="%"
              prefix="Target"
            />
          </div>
        </div>
        <div className="rounded-md bg-tnvs-void p-3">
          <Switch
            checked={activeLoss}
            onChange={onToggleLoss}
            label="Límite loss"
          />
          <div className={cls('mt-2', !activeLoss && 'opacity-40 pointer-events-none')}>
            <NumberInput
              value={limitLoss}
              onChange={onChangeLoss}
              min={0}
              step={0.5}
              suffix="%"
              prefix="Límite"
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function ReadRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between rounded bg-tnvs-void px-3 py-2">
      <span className="text-xs text-tnvs-muted">{label}</span>
      <span className={cls('text-sm text-white', mono && 'font-mono')}>{value}</span>
    </div>
  );
}
