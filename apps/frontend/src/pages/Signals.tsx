import { memo, useEffect, useState } from 'react';
import { ArrowUp, ArrowDown, Zap, Filter, ChevronDown, ChevronRight, AlertTriangle, Shield, ShieldAlert, TrendingUp, Globe } from 'lucide-react';
import { api, OrchestratorPublishedSignal, HorizonScore } from '../lib/api';
import { cls, fmtUsd, fmtPct, fmtDate } from '../utils/format';

export const SignalsPage = memo(function SignalsPage() {
  const [signals, setSignals] = useState<OrchestratorPublishedSignal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

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
        <span className="text-xs text-tnvs-muted">{signals.length} signals</span>
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