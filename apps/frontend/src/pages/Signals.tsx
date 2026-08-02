import { memo, useEffect, useState } from 'react';
import { ArrowUp, ArrowDown, Zap, Filter, ChevronDown, ChevronRight, AlertTriangle, Shield, ShieldAlert, TrendingUp, Globe, Plus, X } from 'lucide-react';
import { api, OrchestratorPublishedSignal, HorizonScore } from '../lib/api';
import { cls, fmtUsd, fmtPct, fmtDate } from '../utils/format';
import { useBridge } from '../state/BridgeProvider';

export const SignalsPage = memo(function SignalsPage() {
  const bridge = useBridge();
  const [signals, setSignals] = useState<OrchestratorPublishedSignal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [showManual, setShowManual] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitOk, setSubmitOk] = useState<string | null>(null);

  // Form state
  const [mSymbol, setMSymbol] = useState('');
  const [mAction, setMAction] = useState<'BUY' | 'SELL'>('BUY');
  const [mEntry, setMEntry] = useState('');
  const [mSL, setMSL] = useState('');
  const [mTPs, setMTPs] = useState(''); // CSV
  const [mLotSize, setMLotSize] = useState('0.01');
  const [mLotMode, setMLotMode] = useState<'fixed' | 'risk_based'>('fixed');
  const [mRiskPct, setMRiskPct] = useState('1.0');
  const [mComment, setMComment] = useState('');
  const [mAccountId, setMAccountId] = useState('');

  const fetchAll = async () => {
    try {
      const data = await api.orchestrator.signals(50);
      setSignals(data.items);
      setError(null);
    } catch (e: any) {
      const msg = String(e?.message || '');
      if (!/^HTTP (401|404|502|503)/.test(msg)) setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, 5000);
    return () => clearInterval(id);
  }, []);

  const submitManual = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setSubmitError(null);
    setSubmitOk(null);
    try {
      const tps = mTPs
        .split(',')
        .map((s) => s.trim())
        .filter((s) => s.length > 0)
        .map((s) => parseFloat(s));
      if (tps.some((n) => Number.isNaN(n))) {
        throw new Error('Take profits inválidos (deben ser números separados por coma)');
      }
      const sl = parseFloat(mSL);
      if (Number.isNaN(sl) || sl <= 0) {
        throw new Error('Stop Loss debe ser un número positivo');
      }
      const payload: any = {
        symbol: mSymbol.toUpperCase(),
        action: mAction,
        stop_loss: sl,
        take_profits: tps,
        lot_mode: mLotMode,
        comment: mComment || `manual from ${bridge.selectedLogin ? 'login ' + bridge.selectedLogin : 'web UI'}`,
      };
      const ep = parseFloat(mEntry);
      if (!Number.isNaN(ep) && ep > 0) payload.entry_price = ep;
      if (mLotMode === 'fixed') {
        const ls = parseFloat(mLotSize);
        if (!Number.isNaN(ls) && ls > 0) payload.lot_size = ls;
      } else {
        const rp = parseFloat(mRiskPct);
        if (!Number.isNaN(rp) && rp > 0) payload.risk_percent = rp;
      }
      if (mAccountId) payload.account_id = mAccountId;

      const result = await api.signals.manual(payload);
      setSubmitOk(`✓ Señal creada: ${result.id || ''} ${result.symbol} ${result.action}`);
      // Reset form (mantener account_id)
      setMSymbol('');
      setMEntry('');
      setMSL('');
      setMTPs('');
      setMComment('');
      // Refrescar lista después de 1s
      setTimeout(() => fetchAll(), 1000);
      setTimeout(() => setShowManual(false), 2500);
    } catch (e: any) {
      setSubmitError(e.message || String(e));
    } finally {
      setSubmitting(false);
    }
  };

  const sorted = [...signals].sort((a, b) => {
    const ta = a.published_at ?? 0;
    const tb = b.published_at ?? 0;
    return tb - ta;
  });

  function toggleExpand(id: string) {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">Signals</h2>
        <div className="flex items-center gap-3">
          <span className="text-xs text-tnvs-muted">{signals.length} signals</span>
          <button
            type="button"
            onClick={() => setShowManual(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-tnvs-win/20 hover:bg-tnvs-win/30 text-tnvs-win text-xs font-medium"
          >
            <Plus className="w-3.5 h-3.5" /> Crear señal
          </button>
        </div>
      </div>
      {loading && <div className="text-sm text-tnvs-muted">Loading…</div>}
      {error && (
        <div className="text-xs text-tnvs-warn bg-tnvs-warn/10 px-3 py-2 rounded">
          {error}
        </div>
      )}

      <div className="tnvs-card">
        {sorted.length === 0 ? (
          <div className="py-8 text-center text-sm text-tnvs-dim">No signals received yet</div>
        ) : (
          <table className="tnvs-table">
            <thead>
              <tr>
                <th className="w-6" />
                <th>Time</th>
                <th>Symbol</th>
                <th>Action</th>
                <th>Bias</th>
                <th>Horizons</th>
                <th>Macro</th>
                <th>Lot</th>
                <th>SL</th>
                <th>TP</th>
                <th>Conf</th>
                <th>RR</th>
                <th>Risk</th>
                <th>Filter</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map(s => {
                const rowId = `${s.id ?? `${s.symbol}-${s.published_at}`}`;
                const isExpanded = expanded.has(rowId);
                const riskLevel = s.filtered_out ? 'critical' : s.confidence != null && s.confidence >= 0.7 ? 'low' : s.confidence != null && s.confidence >= 0.5 ? 'medium' : 'high';
                return (
                  <tr key={rowId} className={cls(s.filtered_out && 'opacity-50', 'cursor-pointer')} onClick={() => toggleExpand(rowId)}>
                    <td>
                      {isExpanded ? <ChevronDown className="h-3 w-3 text-tnvs-muted" /> : <ChevronRight className="h-3 w-3 text-tnvs-muted" />}
                    </td>
                    <td className="text-xs text-tnvs-muted whitespace-nowrap">{fmtDate(s.published_at ? new Date(s.published_at * 1000).toISOString() : new Date().toISOString())}</td>
                    <td className="font-medium">{s.symbol}</td>
                    <td><ActionBadge action={s.action} /></td>
                    <td>
                      <div className="flex items-center gap-1">
                        <BiasBadge bias={s.bias} />
                        {s.master_score != null && (
                          <span className="text-[10px] text-tnvs-dim tabular-nums">
                            {s.master_score.toFixed(0)}
                          </span>
                        )}
                      </div>
                    </td>
                    <td><HorizonGrid scores={s.horizon_scores} /></td>
                    <td><MacroBadge riskOff={s.macro_risk_off} reasons={s.macro_reasons} /></td>
                    <td className="font-mono">{s.lot_size != null ? s.lot_size.toFixed(2) : '-'}</td>
                    <td className="font-mono text-tnvs-loss">{s.stop_loss != null ? fmtUsd(s.stop_loss) : '-'}</td>
                    <td className="font-mono text-tnvs-win">
                      {s.take_profits && s.take_profits.length > 0 ? fmtUsd(s.take_profits[0]) : '-'}
                    </td>
                    <td>{confidenceBar(s.confidence)}</td>
                    <td className="font-mono text-xs text-tnvs-muted">{s.rr_ratio != null ? s.rr_ratio.toFixed(2) : '-'}</td>
                    <td>
                      {riskBadge(riskLevel)}
                    </td>
                    <td>
                      {s.filtered_out ? (
                        <span className="text-xs text-tnvs-loss">filtered</span>
                      ) : s.lot_multiplier && s.lot_multiplier > 1 ? (
                        <span className="text-xs text-tnvs-win inline-flex items-center gap-1">
                          <Zap className="h-3 w-3" /> boosted
                        </span>
                      ) : s.lot_multiplier && s.lot_multiplier < 1 ? (
                        <span className="text-xs text-tnvs-warn">reduced</span>
                      ) : (
                        <span className="text-xs text-tnvs-dim">-</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {signals.filter(s => {
        const rowId = `${s.id ?? `${s.symbol}-${s.published_at}`}`;
        return expanded.has(rowId);
      }).length > 0 && (
        <div className="space-y-2">
          {signals.filter(s => {
            const rowId = `${s.id ?? `${s.symbol}-${s.published_at}`}`;
            return expanded.has(rowId);
          }).map(s => {
            const rowId = `${s.id ?? `${s.symbol}-${s.published_at}`}`;
            return (
              <div key={`detail-${rowId}`} className="tnvs-card text-sm">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  {s.reasons && s.reasons.length > 0 && (
                    <div className="col-span-full">
                      <span className="text-xs text-tnvs-muted block mb-1">Reasons</span>
                      <div className="flex flex-wrap gap-1">
                        {s.reasons.map((r, i) => (
                          <span key={i} className="text-xs bg-tnvs-bg px-1.5 py-0.5 rounded text-tnvs-dim">{r}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {s.macro_reasons && s.macro_reasons.length > 0 && (
                    <div className="col-span-full">
                      <span className="text-xs text-tnvs-muted block mb-1">Macro Risk</span>
                      <div className="flex flex-wrap gap-1">
                        {s.macro_reasons.map((r, i) => (
                          <span key={i} className="text-xs bg-red-500/10 text-red-300 px-1.5 py-0.5 rounded">{r}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {s.horizon_scores && Object.keys(s.horizon_scores).length > 0 && (
                    <div className="col-span-full">
                      <span className="text-xs text-tnvs-muted block mb-1">Multi-Horizon Detail</span>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                        {Object.entries(s.horizon_scores).map(([tf, h]) => (
                          <div key={tf} className="bg-tnvs-bg rounded p-2">
                            <div className="flex items-center justify-between">
                              <span className="text-[10px] text-tnvs-dim">{tf}</span>
                              <BiasBadge bias={h.bias} />
                            </div>
                            <div className="text-sm font-mono mt-1">{h.score.toFixed(1)}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {s.atr != null && (
                    <div>
                      <span className="text-xs text-tnvs-muted block">ATR</span>
                      <span className="font-mono">{s.atr.toFixed(2)}</span>
                    </div>
                  )}
                  {s.correlation_count != null && (
                    <div>
                      <span className="text-xs text-tnvs-muted block">Correlated</span>
                      <span className="font-mono text-tnvs-win inline-flex items-center gap-1">
                        <TrendingUp className="h-3 w-3" /> {s.correlation_count}
                      </span>
                    </div>
                  )}
                  {s.lot_multiplier != null && (
                    <div>
                      <span className="text-xs text-tnvs-muted block">Lot Multiplier</span>
                      <span className="font-mono">{s.lot_multiplier.toFixed(2)}x</span>
                    </div>
                  )}
                  {s.take_profits && s.take_profits.length > 1 && (
                    <div className="col-span-full">
                      <span className="text-xs text-tnvs-muted block mb-1">All TP Levels</span>
                      <div className="flex flex-wrap gap-2">
                        {s.take_profits.map((tp, i) => (
                          <span key={i} className="font-mono text-xs text-tnvs-win">TP{i + 1}: {fmtUsd(tp)}</span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {signals.length > 0 && (
        <div className="tnvs-card">
          <h3 className="mb-3 text-sm font-semibold text-white/80 flex items-center gap-2">
            <Filter className="h-4 w-4" />
            Orchestrator Stats
          </h3>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <Stat label="Filtered" value={signals.filter(s => s.filtered_out).length} color="text-tnvs-loss" />
            <Stat label="Boosted (corr)" value={signals.filter(s => s.lot_multiplier && s.lot_multiplier > 1).length} color="text-tnvs-win" />
            <Stat label="Reduced (corr)" value={signals.filter(s => s.lot_multiplier && s.lot_multiplier < 1 && !s.filtered_out).length} color="text-tnvs-warn" />
          </div>
        </div>
      )}

      {submitOk && (
        <div className="px-3 py-2 rounded bg-tnvs-win/10 border border-tnvs-win/30 text-sm text-tnvs-win">
          {submitOk}
        </div>
      )}

      {showManual && (
        <CreateSignalModal
          onClose={() => setShowManual(false)}
          onSuccess={() => { fetchAll(); setSubmitOk('✓ Señal creada'); setTimeout(() => setSubmitOk(null), 4000); }}
        />
      )}
    </div>
  );
});

function Stat({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-xs text-tnvs-muted">{label}</span>
      <span className={cls('text-lg font-semibold', color ?? 'text-white')}>{value}</span>
    </div>
  );
}

function riskBadge(level?: string) {
  switch (level?.toLowerCase()) {
    case 'low': return <span className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded bg-green-500/20 text-green-300">Low</span>;
    case 'medium': return <span className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-300">Medium</span>;
    case 'high': return <span className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded bg-orange-500/20 text-orange-300">High</span>;
    case 'critical': return <span className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded bg-red-500/20 text-red-300">Critical</span>;
    default: return <span className="text-xs text-tnvs-dim">-</span>;
  }
}

function confidenceBar(conf?: number) {
  if (conf == null) return null;
  const pct = Math.round(conf * 100);
  const color = pct >= 80 ? 'bg-green-500' : pct >= 60 ? 'bg-yellow-500' : pct >= 40 ? 'bg-orange-500' : 'bg-red-500';
  return (
    <div className="flex items-center gap-1.5">
      <div className="w-16 h-1.5 bg-tnvs-border rounded-full overflow-hidden">
        <div className={cls('h-full rounded-full transition-all', color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono">{pct}%</span>
    </div>
  );
}

function ActionBadge({ action }: { action: string }) {
  const isBuy = action.toLowerCase() === 'buy';
  const color = isBuy ? 'text-tnvs-win' : action.toLowerCase() === 'sell' ? 'text-tnvs-loss' : 'text-tnvs-warn';
  const Icon = isBuy ? ArrowUp : ArrowDown;
  return <span className={cls('inline-flex items-center gap-1 text-xs font-medium', color)}><Icon className="h-3 w-3" />{action.toUpperCase()}</span>;
}

function BiasBadge({ bias }: { bias?: string }) {
  if (!bias) return null;
  const cfg: Record<string, { color: string; bg: string }> = {
    BULLISH: { color: 'text-emerald-300', bg: 'bg-emerald-500/20' },
    BEARISH: { color: 'text-red-300', bg: 'bg-red-500/20' },
    NEUTRAL: { color: 'text-tnvs-muted', bg: 'bg-white/[0.06]' },
  };
  const c = cfg[bias] || cfg.NEUTRAL;
  return (
    <span className={cls('inline-flex items-center text-[10px] font-semibold px-1.5 py-0.5 rounded', c.bg, c.color)}>
      {bias}
    </span>
  );
}

function HorizonCell({ h }: { h?: HorizonScore }) {
  if (!h) return <span className="text-[10px] text-tnvs-dim">-</span>;
  const biasColor =
    h.bias === 'BULLISH' ? 'text-emerald-300' :
    h.bias === 'BEARISH' ? 'text-red-300' : 'text-tnvs-muted';
  const barColor =
    h.score >= 65 ? 'bg-emerald-500' :
    h.score >= 50 ? 'bg-emerald-300' :
    h.score >= 35 ? 'bg-red-300' : 'bg-red-500';
  return (
    <div className="flex flex-col gap-0.5 min-w-[60px]">
      <div className="flex items-center justify-between gap-1">
        <span className="text-[9px] text-tnvs-dim">{h.timeframe}</span>
        <span className={cls('text-[9px] font-semibold', biasColor)}>
          {h.score.toFixed(0)}
        </span>
      </div>
      <div className="h-1 w-full bg-tnvs-border rounded-full overflow-hidden">
        <div className={cls('h-full rounded-full transition-all', barColor)} style={{ width: `${h.score}%` }} />
      </div>
    </div>
  );
}

function HorizonGrid({ scores }: { scores?: Record<string, HorizonScore> }) {
  if (!scores || Object.keys(scores).length === 0) {
    return <span className="text-[10px] text-tnvs-dim">-</span>;
  }
  const order = ['M5', 'H1', 'H4', 'D1'];
  const tfs = order.filter((t) => scores[t]);
  return (
    <div className="flex gap-2">
      {tfs.map((tf) => (
        <HorizonCell key={tf} h={scores[tf]} />
      ))}
    </div>
  );
}

function MacroBadge({ riskOff, reasons }: { riskOff?: boolean; reasons?: string[] }) {
  if (!riskOff) {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300">
        <Globe className="h-3 w-3" />
        Macro OK
      </span>
    );
  }
  return (
    <span
      className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-red-500/20 text-red-300"
      title={reasons?.join(' • ') || 'Risk-off'}
    >
      <AlertTriangle className="h-3 w-3" />
      Risk-off
    </span>
  );
}

// Sprint 2.2: modal "Crear señal" — trader la usa para inyectar ideas propias.
function CreateSignalModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  // Hooks locales para evitar tocar el padre
  const bridge = useBridge();
  const [symbol, setSymbol] = useState('');
  const [action, setAction] = useState<'BUY' | 'SELL'>('BUY');
  const [entry, setEntry] = useState('');
  const [sl, setSL] = useState('');
  const [tps, setTPs] = useState('');
  const [lotSize, setLotSize] = useState('0.01');
  const [lotMode, setLotMode] = useState<'fixed' | 'risk_based'>('fixed');
  const [riskPct, setRiskPct] = useState('1.0');
  const [comment, setComment] = useState('');
  const [accountId, setAccountId] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const tpsArr = tps
        .split(',')
        .map((s) => s.trim())
        .filter((s) => s.length > 0)
        .map((s) => parseFloat(s));
      if (tpsArr.length === 0) throw new Error('Al menos un Take Profit es requerido');
      if (tpsArr.some((n) => Number.isNaN(n))) throw new Error('TPs inválidos');
      const slNum = parseFloat(sl);
      if (Number.isNaN(slNum) || slNum <= 0) throw new Error('Stop Loss inválido');
      if (!symbol.trim()) throw new Error('Símbolo requerido');

      const payload: any = {
        symbol: symbol.toUpperCase(),
        action,
        stop_loss: slNum,
        take_profits: tpsArr,
        lot_mode: lotMode,
        comment: comment || `manual desde UI`,
      };
      const ep = parseFloat(entry);
      if (!Number.isNaN(ep) && ep > 0) payload.entry_price = ep;
      if (lotMode === 'fixed') {
        const ls = parseFloat(lotSize);
        if (!Number.isNaN(ls) && ls > 0) payload.lot_size = ls;
      } else {
        const rp = parseFloat(riskPct);
        if (!Number.isNaN(rp) && rp > 0) payload.risk_percent = rp;
      }
      if (accountId) payload.account_id = accountId;
      else if (bridge.selectedLogin) {
        // intentar matchear account_id a partir de selectedLogin
        const a = bridge.accounts.find((acc) => acc.login === bridge.selectedLogin);
        if (a?.id) payload.account_id = a.id;
      }

      const result = await api.signals.manual(payload);
      alert(`✓ Señal creada: ${result.id?.substring(0, 8) || ''} ${result.symbol} ${result.action}`);
      onSuccess();
      onClose();
    } catch (e: any) {
      setError(e.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <form onSubmit={submit} className="bg-tnvs-surface border border-white/[0.08] rounded-lg p-6 w-full max-w-md space-y-3 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Zap className="w-4 h-4 text-tnvs-win" /> Crear señal manual
          </h3>
          <button type="button" onClick={onClose}><X className="w-4 h-4" /></button>
        </div>
        <p className="text-xs text-tnvs-muted">
          Crea una señal que pasa por validación de formato, dedup, risk-engine y execution-engine.
          Mismo pipeline que señales de Telegram.
        </p>
        {error && <div className="px-3 py-2 rounded bg-tnvs-loss/10 border border-tnvs-loss/30 text-sm text-tnvs-loss">{error}</div>}

        <div className="grid grid-cols-3 gap-2">
          <label className="block col-span-2">
            <span className="text-xs text-tnvs-muted block mb-1">Símbolo *</span>
            <input
              type="text"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              placeholder="XAUUSD, EURUSD, BTCUSD…"
              className="w-full px-2 py-1.5 rounded bg-white/[0.05] border border-white/[0.08] text-sm font-mono"
              required
            />
          </label>
          <label className="block">
            <span className="text-xs text-tnvs-muted block mb-1">Acción *</span>
            <select
              value={action}
              onChange={(e) => setAction(e.target.value as 'BUY' | 'SELL')}
              className="w-full px-2 py-1.5 rounded bg-white/[0.05] border border-white/[0.08] text-sm"
            >
              <option value="BUY">BUY</option>
              <option value="SELL">SELL</option>
            </select>
          </label>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <label className="block">
            <span className="text-xs text-tnvs-muted block mb-1">Entry price (opcional)</span>
            <input
              type="number"
              step="0.00001"
              value={entry}
              onChange={(e) => setEntry(e.target.value)}
              placeholder="ej: 2030.50"
              className="w-full px-2 py-1.5 rounded bg-white/[0.05] border border-white/[0.08] text-sm font-mono"
            />
          </label>
          <label className="block">
            <span className="text-xs text-tnvs-muted block mb-1">Stop Loss *</span>
            <input
              type="number"
              step="0.00001"
              value={sl}
              onChange={(e) => setSL(e.target.value)}
              placeholder="ej: 2025.00"
              className="w-full px-2 py-1.5 rounded bg-white/[0.05] border border-white/[0.08] text-sm font-mono"
              required
            />
          </label>
        </div>

        <label className="block">
          <span className="text-xs text-tnvs-muted block mb-1">Take Profits (separar por coma) *</span>
          <input
            type="text"
            value={tps}
            onChange={(e) => setTPs(e.target.value)}
            placeholder="ej: 2035.00, 2040.00, 2045.00"
            className="w-full px-2 py-1.5 rounded bg-white/[0.05] border border-white/[0.08] text-sm font-mono"
            required
          />
        </label>

        <div className="grid grid-cols-3 gap-2">
          <label className="block">
            <span className="text-xs text-tnvs-muted block mb-1">Lot mode</span>
            <select
              value={lotMode}
              onChange={(e) => setLotMode(e.target.value as 'fixed' | 'risk_based')}
              className="w-full px-2 py-1.5 rounded bg-white/[0.05] border border-white/[0.08] text-sm"
            >
              <option value="fixed">fixed</option>
              <option value="risk_based">% riesgo</option>
            </select>
          </label>
          {lotMode === 'fixed' ? (
            <label className="block col-span-2">
              <span className="text-xs text-tnvs-muted block mb-1">Lot size</span>
              <input
                type="number"
                step="0.01"
                value={lotSize}
                onChange={(e) => setLotSize(e.target.value)}
                className="w-full px-2 py-1.5 rounded bg-white/[0.05] border border-white/[0.08] text-sm font-mono"
              />
            </label>
          ) : (
            <label className="block col-span-2">
              <span className="text-xs text-tnvs-muted block mb-1">Risk %</span>
              <input
                type="number"
                step="0.1"
                value={riskPct}
                onChange={(e) => setRiskPct(e.target.value)}
                className="w-full px-2 py-1.5 rounded bg-white/[0.05] border border-white/[0.08] text-sm font-mono"
              />
            </label>
          )}
        </div>

        {bridge.accounts.length > 0 && (
          <label className="block">
            <span className="text-xs text-tnvs-muted block mb-1">Cuenta (opcional)</span>
            <select
              value={accountId}
              onChange={(e) => setAccountId(e.target.value)}
              className="w-full px-2 py-1.5 rounded bg-white/[0.05] border border-white/[0.08] text-sm"
            >
              <option value="">(usar default)</option>
              {bridge.accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.alias || a.name} ({a.login})
                </option>
              ))}
            </select>
          </label>
        )}

        <label className="block">
          <span className="text-xs text-tnvs-muted block mb-1">Comentario (opcional)</span>
          <input
            type="text"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="ej: setup H1, pullback a 50% fib"
            className="w-full px-2 py-1.5 rounded bg-white/[0.05] border border-white/[0.08] text-sm"
          />
        </label>

        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={onClose} className="px-3 py-1.5 rounded text-xs text-tnvs-muted hover:bg-white/[0.05]">
            Cancelar
          </button>
          <button
            type="submit"
            disabled={busy}
            className="px-3 py-1.5 rounded bg-tnvs-win/20 hover:bg-tnvs-win/30 text-tnvs-win text-xs font-medium disabled:opacity-50"
          >
            {busy ? 'Creando…' : 'Crear señal'}
          </button>
        </div>
      </form>
    </div>
  );
}