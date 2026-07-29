import { memo, useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Activity, ArrowUp, ArrowDown, Target, Shield, TrendingUp,
  TrendingDown, AlertTriangle, BarChart3, Newspaper, RefreshCw,
  ChevronLeft, Globe,
} from 'lucide-react';
import { api, SymbolAnalysis, HorizonScore } from '../lib/api';
import { cls } from '../utils/format';

// ─── Helpers ──────────────────────────────────────────────────────

function biasColor(bias: string | undefined) {
  if (bias === 'BULLISH') return 'text-emerald-300';
  if (bias === 'BEARISH') return 'text-red-300';
  return 'text-amber-300';
}

function biasBg(bias: string | undefined) {
  if (bias === 'BULLISH') return 'bg-emerald-500/20';
  if (bias === 'BEARISH') return 'bg-red-500/20';
  return 'bg-amber-500/20';
}

function barColor(score: number) {
  if (score >= 65) return 'bg-emerald-500';
  if (score >= 50) return 'bg-emerald-300';
  if (score >= 35) return 'bg-amber-300';
  return 'bg-red-500';
}

// ─── Sub-components ───────────────────────────────────────────────

function VeredictoHeader({ a }: { a: SymbolAnalysis }) {
  return (
    <section className="rounded-xl border border-white/[0.06] bg-white/[0.03] p-6">
      <div className="flex items-start justify-between gap-6">
        <div className="flex-1">
          <div className="text-[10px] uppercase tracking-widest text-tnvs-muted mb-2">
            Veredicto del Día · Mesa Institucional
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">
            <span className={cls('font-bold', biasColor(a.master_bias))}>{a.symbol}</span>
            {' '}— {a.master_bias === 'BULLISH' ? 'Alcista' : a.master_bias === 'BEARISH' ? 'Bajista' : 'Neutral'}{' '}
            <span className="text-tnvs-muted font-normal text-xl">
              ({a.master_score?.toFixed(0)}/100)
            </span>
          </h1>
          <p className="text-sm text-tnvs-muted leading-relaxed max-w-3xl">{a.narrative}</p>
        </div>
        <ScoreCircle score={a.master_score || 50} bias={a.master_bias || 'NEUTRAL'} />
      </div>

      {a.macro?.risk_off && (
        <div className="mt-4 rounded border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs">
          <span className="font-semibold text-amber-300">⚠️ Risk-off macro:</span>
          <span className="text-tnvs-muted ml-1">
            {(a.macro?.reasons || []).join(' • ')}
          </span>
        </div>
      )}
    </section>
  );
}

function ScoreCircle({ score, bias }: { score: number; bias: string }) {
  const color = biasColor(bias);
  const radius = 50;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const label = bias === 'BULLISH' ? 'BULLISH' : bias === 'BEARISH' ? 'BEARISH' : 'NEUTRAL';

  return (
    <div className="flex flex-col items-center">
      <svg width={140} height={140} className="-rotate-90">
        <circle cx={70} cy={70} r={radius} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth={10} />
        <circle
          cx={70} cy={70} r={radius}
          fill="none"
          stroke={bias === 'BULLISH' ? '#10b981' : bias === 'BEARISH' ? '#ef4444' : '#f59e0b'}
          strokeWidth={10}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-500"
        />
      </svg>
      <div className="-mt-24 flex flex-col items-center">
        <span className={cls('text-3xl font-bold tabular-nums', color)}>{score.toFixed(0)}</span>
        <span className={cls('text-[10px] uppercase tracking-widest mt-1', color)}>{label}</span>
      </div>
    </div>
  );
}

function HorizonGrid({ horizons }: { horizons: Record<string, HorizonScore> }) {
  const order = ['M5', 'H1', 'H4', 'D1'];
  const tfs = order.filter((t) => horizons[t]);
  if (tfs.length === 0) {
    return <div className="text-xs text-tnvs-muted">Sin datos multi-horizonte</div>;
  }
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {tfs.map((tf) => {
        const h = horizons[tf];
        return (
          <div key={tf} className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-mono text-tnvs-muted">{tf}</span>
              <span className={cls('text-[10px] font-semibold', biasColor(h.bias))}>
                {h.bias}
              </span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className={cls('text-2xl font-bold tabular-nums', biasColor(h.bias))}>
                {h.score.toFixed(0)}
              </span>
              <span className="text-[10px] text-tnvs-muted">/100</span>
            </div>
            <div className="h-1.5 w-full bg-white/[0.04] rounded-full overflow-hidden mt-2">
              <div
                className={cls('h-full rounded-full transition-all', barColor(h.score))}
                style={{ width: `${h.score}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Drivers({ drivers }: { drivers: any[] }) {
  if (!drivers || drivers.length === 0) {
    return <div className="text-xs text-tnvs-muted">Sin drivers</div>;
  }
  return (
    <div className="space-y-2">
      {drivers.map((d, i) => {
        const Icon = d.status === 'aligned' ? TrendingUp : d.status === 'divergent' ? TrendingDown : Activity;
        const color = d.status === 'aligned' ? 'text-emerald-300' : d.status === 'divergent' ? 'text-red-300' : 'text-amber-300';
        return (
          <div key={i} className="flex items-start gap-3 px-3 py-2 rounded bg-white/[0.02]">
            <Icon className={cls('h-4 w-4 mt-0.5', color)} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-white">{d.name}</span>
                <span className={cls('text-[10px]', color)}>
                  ({d.status})
                </span>
              </div>
              <p className="text-[10px] text-tnvs-muted mt-0.5">{d.detail}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function PriceRange({ pr }: { pr: any }) {
  if (!pr || pr.current == null) {
    return <div className="text-xs text-tnvs-muted">Sin datos</div>;
  }
  const pos = pr.cara_pct ?? 50;
  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between">
        <div>
          <span className="text-[10px] text-tnvs-muted">Precio actual:</span>
          <span className="ml-2 text-lg font-mono font-bold text-white">
            {pr.current?.toFixed(2)}
          </span>
        </div>
        <span className={cls(
          'text-[10px] px-2 py-0.5 rounded',
          pr.zone === 'barata' ? 'bg-emerald-500/20 text-emerald-300' :
          pr.zone === 'cara' ? 'bg-red-500/20 text-red-300' :
          'bg-amber-500/20 text-amber-300'
        )}>
          Zona {pr.zone}
        </span>
      </div>

      <div className="relative h-3 w-full bg-white/[0.04] rounded-full overflow-visible">
        <div className="absolute inset-y-0 left-0 right-0 rounded-full overflow-hidden">
          <div className="h-full bg-gradient-to-r from-emerald-500/30 via-amber-500/30 to-red-500/30" />
        </div>
        <div
          className="absolute -top-1 h-5 w-1 bg-white rounded shadow"
          style={{ left: `calc(${pos}% - 2px)` }}
        />
      </div>
      <div className="flex justify-between text-[10px] text-tnvs-muted">
        <span>${pr.low?.toFixed(2)}</span>
        <span>Fair ${pr.midpoint?.toFixed(2)}</span>
        <span>${pr.high?.toFixed(2)}</span>
      </div>
    </div>
  );
}

function PlaybookCard({ pb, color }: { pb: any; color: string }) {
  if (!pb) return null;
  const Icon = pb.horizon === 'D1' ? Target : Activity;
  return (
    <div className={cls('rounded-lg border p-4', color)}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-tnvs-muted" />
          <span className="text-[10px] uppercase tracking-wider text-tnvs-muted">{pb.horizon}</span>
        </div>
        <span className="text-xs font-semibold text-white">{pb.title}</span>
      </div>

      <p className="text-xs text-white mb-3">{pb.action}</p>

      {pb.entry != null && (
        <div className="grid grid-cols-2 gap-2 text-[10px] mb-2">
          <div className="bg-black/20 rounded px-2 py-1">
            <span className="text-tnvs-muted">Entry:</span>
            <span className="ml-1 font-mono text-white">{pb.entry?.toFixed(2)}</span>
          </div>
          <div className="bg-black/20 rounded px-2 py-1">
            <span className="text-tnvs-muted">Stop:</span>
            <span className="ml-1 font-mono text-red-300">{pb.stop?.toFixed(2)}</span>
          </div>
          <div className="bg-black/20 rounded px-2 py-1">
            <span className="text-tnvs-muted">TP1:</span>
            <span className="ml-1 font-mono text-emerald-300">{pb.tp1?.toFixed(2)}</span>
          </div>
          {pb.tp2 != null && (
            <div className="bg-black/20 rounded px-2 py-1">
              <span className="text-tnvs-muted">TP2:</span>
              <span className="ml-1 font-mono text-emerald-300">{pb.tp2?.toFixed(2)}</span>
            </div>
          )}
        </div>
      )}

      {pb.zone && (
        <p className="text-[10px] text-tnvs-muted mt-2">
          <span className="font-semibold text-tnvs-dim">Zona:</span> {pb.zone}
        </p>
      )}
      {pb.invalidation && (
        <p className="text-[10px] text-tnvs-muted mt-1">
          <span className="font-semibold text-tnvs-dim">Invalidación:</span> {pb.invalidation}
        </p>
      )}
      {pb.reglas && (
        <p className="text-[10px] text-tnvs-muted mt-1 italic">{pb.reglas}</p>
      )}

      {pb.size_pct != null && pb.size_pct > 0 && (
        <div className="mt-3 pt-2 border-t border-white/[0.06] text-[10px] text-tnvs-muted">
          Tamaño sugerido: <span className="text-white font-semibold">{(pb.size_pct * 100).toFixed(0)}%</span> de la cuenta
        </div>
      )}
    </div>
  );
}

function Divergences({ divs }: { divs: any[] }) {
  if (!divs || divs.length === 0) {
    return <div className="text-xs text-tnvs-muted">Sin divergencias relevantes</div>;
  }
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
      {divs.map((d, i) => (
        <div key={i} className="rounded border border-white/[0.06] bg-white/[0.03] p-3">
          <div className="text-[10px] text-tnvs-muted uppercase tracking-wider mb-1">
            {d.timeframe}
          </div>
          <div className={cls('text-lg font-bold tabular-nums', d.score > 0 ? 'text-emerald-300' : 'text-red-300')}>
            {d.score > 0 ? '+' : ''}{d.score}
          </div>
          <div className="text-[10px] text-tnvs-muted mt-1">{d.detail}</div>
        </div>
      ))}
    </div>
  );
}

function MacroPanel({ macro }: { macro: any }) {
  if (!macro) return null;
  const color = macro.risk_off ? 'text-amber-300' : 'text-emerald-300';
  const bg = macro.risk_off ? 'bg-amber-500/15 border-amber-500/30' : 'bg-emerald-500/15 border-emerald-500/30';
  return (
    <div className={cls('rounded border px-3 py-2 text-xs flex items-center justify-between', bg, color)}>
      <div className="flex items-center gap-2">
        <Globe className="h-3.5 w-3.5" />
        <span>
          <span className="font-semibold">Riesgo macro:</span>{' '}
          {macro.risk_off ? 'ON' : 'OFF'}
        </span>
      </div>
      <span className="text-[10px] text-tnvs-muted">
        conf ×{macro.confidence_multiplier?.toFixed(2)} · lot ×{macro.lot_multiplier?.toFixed(2)}
      </span>
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────

export const AnalysisPage = memo(function AnalysisPage() {
  const { symbol = 'XAUUSD' } = useParams<{ symbol: string }>();
  const [analysis, setAnalysis] = useState<SymbolAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAll = async () => {
    try {
      const data = await api.orchestrator.analysis(symbol);
      setAnalysis(data);
      setError(null);
    } catch (e: any) {
      setError(e?.message || 'Error cargando análisis');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    fetchAll();
    const id = setInterval(fetchAll, 60000);
    return () => clearInterval(id);
  }, [symbol]);

  if (loading && !analysis) {
    return (
      <div className="flex items-center justify-center h-64 text-tnvs-muted text-sm">
        Cargando análisis de {symbol}…
      </div>
    );
  }

  if (error || !analysis) {
    return (
      <div className="space-y-4">
        <Link to="/" className="inline-flex items-center gap-1 text-xs text-tnvs-muted hover:text-white">
          <ChevronLeft className="h-3 w-3" /> Volver
        </Link>
        <div className="rounded border border-red-500/30 bg-red-500/10 px-4 py-3 text-xs text-red-300">
          ⚠️ {error || 'No se pudo cargar el análisis. Verificá que orchestrator (:8060) esté corriendo.'}
        </div>
      </div>
    );
  }

  const biasColorCard =
    analysis.master_bias === 'BULLISH' ? 'border-emerald-500/30' :
    analysis.master_bias === 'BEARISH' ? 'border-red-500/30' : 'border-amber-500/30';

  return (
    <div className="space-y-6">
      {/* Header with back button + refresh */}
      <div className="flex items-center justify-between">
        <Link to="/" className="inline-flex items-center gap-1 text-xs text-tnvs-muted hover:text-white">
          <ChevronLeft className="h-3 w-3" /> Volver al dashboard
        </Link>
        <button
          onClick={fetchAll}
          disabled={loading}
          className="rounded border border-white/[0.06] bg-white/[0.03] hover:bg-white/[0.06] text-white px-3 py-1.5 text-xs flex items-center gap-2 disabled:opacity-50"
        >
          <RefreshCw className={cls('h-3.5 w-3.5', loading && 'animate-spin')} />
          {loading ? 'Actualizando…' : 'Refrescar'}
        </button>
      </div>

      {/* Veredicto */}
      <VeredictoHeader a={analysis} />

      {/* Macro risk */}
      <MacroPanel macro={analysis.macro} />

      {/* Multi-horizonte */}
      <section className="rounded-xl border border-white/[0.06] bg-white/[0.03] p-4">
        <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
          <BarChart3 className="h-4 w-4" />
          Lectura Multi-Horizonte
        </h3>
        <HorizonGrid horizons={analysis.horizons || {}} />
      </section>

      {/* Two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Drivers */}
        <section className="rounded-xl border border-white/[0.06] bg-white/[0.03] p-4">
          <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
            <Activity className="h-4 w-4" />
            Drivers de apoyo
          </h3>
          <Drivers drivers={analysis.drivers || []} />
        </section>

        {/* Price range */}
        <section className="rounded-xl border border-white/[0.06] bg-white/[0.03] p-4">
          <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
            <Target className="h-4 w-4" />
            ¿Dónde está el precio en su rango?
          </h3>
          <PriceRange pr={analysis.price_range} />
        </section>
      </div>

      {/* Playbooks */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section>
          <h3 className="text-xs uppercase tracking-wider text-tnvs-muted mb-2">
            Playbook Diario · Swing / Posición
          </h3>
          <PlaybookCard
            pb={analysis.playbook_daily}
            color={cls('bg-amber-500/5', biasColorCard)}
          />
        </section>
        <section>
          <h3 className="text-xs uppercase tracking-wider text-tnvs-muted mb-2">
            Playbook Intradía · ¿Qué hacer hoy?
          </h3>
          <PlaybookCard
            pb={analysis.playbook_intraday}
            color={cls('bg-blue-500/5', biasColorCard)}
          />
        </section>
      </div>

      {/* Divergences */}
      <section className="rounded-xl border border-white/[0.06] bg-white/[0.03] p-4">
        <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
          <Newspaper className="h-4 w-4" />
          Divergencias entre horizontes
        </h3>
        <Divergences divs={analysis.divergences || []} />
      </section>
    </div>
  );
});