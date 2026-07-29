import { memo, useEffect, useState } from 'react';
import {
  Activity, ArrowUp, ArrowDown, Minus, Globe, Newspaper,
  TrendingUp, TrendingDown, AlertCircle, CheckCircle2, XCircle,
  RefreshCw, BarChart3,
} from 'lucide-react';
import {
  api, MacroIndicator, MacroMarketState, MacroMarketTag,
  MacroCalendarEvent, MacroLiquidity,
} from '../lib/api';
import { cls } from '../utils/format';

// ─── Helpers ────────────────────────────────────────────────────────

function directionIcon(d: MacroIndicator['direction']) {
  if (d === 'up') return ArrowUp;
  if (d === 'down') return ArrowDown;
  return Minus;
}

function directionColor(d: MacroIndicator['direction']) {
  if (d === 'up') return 'text-emerald-300';
  if (d === 'down') return 'text-red-300';
  return 'text-tnvs-muted';
}

function forecastBadge(vs: MacroIndicator['vs_forecast']) {
  if (vs === 'beat') return {
    icon: CheckCircle2, color: 'text-emerald-300', bg: 'bg-emerald-500/15', label: 'Beat',
  };
  if (vs === 'miss') return {
    icon: XCircle, color: 'text-red-300', bg: 'bg-red-500/15', label: 'Miss',
  };
  if (vs === 'in-line') return {
    icon: Minus, color: 'text-amber-300', bg: 'bg-amber-500/15', label: 'In-line',
  };
  return {
    icon: AlertCircle, color: 'text-tnvs-muted', bg: 'bg-white/[0.06]', label: 'N/D',
  };
}

// ─── Sub-components ─────────────────────────────────────────────────

function IndicatorCard({ ind }: { ind: MacroIndicator }) {
  const DirIcon = directionIcon(ind.direction);
  const dirColor = directionColor(ind.direction);
  const fb = forecastBadge(ind.vs_forecast);
  const FbIcon = fb.icon;

  return (
    <div className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-3">
      <div className="flex items-start justify-between mb-1">
        <span className="text-xs font-semibold text-white">{ind.key}</span>
        <DirIcon className={cls('h-4 w-4', dirColor)} />
      </div>
      <div className="text-[10px] text-tnvs-muted mb-1.5 line-clamp-1">{ind.name}</div>
      <div className="space-y-1 text-[10px] tabular-nums">
        <div className="flex justify-between">
          <span className="text-tnvs-muted">Anterior</span>
          <span className="text-tnvs-dim">{ind.previous}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-tnvs-muted">Actual</span>
          <span className={cls('font-semibold', dirColor)}>{ind.actual}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-tnvs-muted">Estimado</span>
          <span className="text-tnvs-dim">{ind.forecast}</span>
        </div>
      </div>
      <div className={cls('mt-2 inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded', fb.bg, fb.color)}>
        <FbIcon className="h-3 w-3" />
        {fb.label}
      </div>
    </div>
  );
}

function MarketTagPill({ tag }: { tag: MacroMarketTag }) {
  const cfg: Record<string, { bg: string; text: string }> = {
    Fuerte: { bg: 'bg-emerald-500/20', text: 'text-emerald-300' },
    Estable: { bg: 'bg-blue-500/20', text: 'text-blue-300' },
    Debil: { bg: 'bg-red-500/20', text: 'text-red-300' },
    Alto: { bg: 'bg-red-500/20', text: 'text-red-300' },
    Medio: { bg: 'bg-amber-500/20', text: 'text-amber-300' },
    Bajo: { bg: 'bg-emerald-500/20', text: 'text-emerald-300' },
    Normal: { bg: 'bg-emerald-500/20', text: 'text-emerald-300' },
    Alto_2: { bg: 'bg-red-500/20', text: 'text-red-300' },
    Alta: { bg: 'bg-red-500/20', text: 'text-red-300' },
    Media: { bg: 'bg-amber-500/20', text: 'text-amber-300' },
    Baja: { bg: 'bg-emerald-500/20', text: 'text-emerald-300' },
    Alcista: { bg: 'bg-emerald-500/20', text: 'text-emerald-300' },
    Lateral: { bg: 'bg-amber-500/20', text: 'text-amber-300' },
    Bajista: { bg: 'bg-red-500/20', text: 'text-red-300' },
    Desconocido: { bg: 'bg-white/[0.06]', text: 'text-tnvs-muted' },
  };
  const c = cfg[tag.label] || cfg.Desconocido;
  return (
    <span className={cls('inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-1 rounded', c.bg, c.text)}>
      <span className="text-tnvs-muted">{tag.tag}:</span>
      <span>{tag.label}</span>
      {tag.value != null && <span className="text-tnvs-dim">({tag.value})</span>}
    </span>
  );
}

function RadarEventCard({ evt }: { evt: MacroCalendarEvent }) {
  const isHigh = evt.impact === 'High';
  const isMed = evt.impact === 'Medium';
  const flagColor = isHigh
    ? 'bg-red-500/20 text-red-300 border-red-500/30'
    : isMed
    ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
    : 'bg-blue-500/15 text-blue-300 border-blue-500/20';
  const impactBadge = isHigh ? 'Alto' : isMed ? 'Medio' : 'Bajo';

  // Detectar keywords para "Cómo reacciona el oro"
  const lowerName = evt.event.toLowerCase();
  let reaction = '';
  let reactionColor = 'text-tnvs-muted';
  if (lowerName.includes('fomc') || lowerName.includes('fed') || lowerName.includes('rate')) {
    reaction = 'FED mueve todo: hawkish → USD+ oro-, dovish → USD- oro+';
    reactionColor = 'text-blue-300';
  } else if (lowerName.includes('cpi') || lowerName.includes('inflation') || lowerName.includes('ppi')) {
    reaction = 'Inflacion alta → USD+ (FED hawkish) + oro+';
    reactionColor = 'text-amber-300';
  } else if (lowerName.includes('nonfarm') || lowerName.includes('nfp') || lowerName.includes('payroll')) {
    reaction = 'Empleo fuerte → USD+; debil → USD- (FED dovish)';
    reactionColor = 'text-purple-300';
  } else if (lowerName.includes('gdp')) {
    reaction = 'GDP fuerte → USD+; debil → USD-';
    reactionColor = 'text-emerald-300';
  }

  return (
    <div className={cls('rounded-lg border p-3', flagColor)}>
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center text-[10px] font-mono bg-white/[0.06] px-1.5 py-0.5 rounded">
            {evt.currency}
          </span>
          <span className="inline-flex items-center text-[10px] font-semibold px-1.5 py-0.5 rounded bg-white/[0.06]">
            {impactBadge}
          </span>
          {evt.time && (
            <span className="text-[10px] text-tnvs-muted">{evt.time} ART</span>
          )}
        </div>
      </div>
      <h4 className="text-sm font-semibold text-white leading-snug mb-1.5">
        {evt.event}
      </h4>
      {evt.date && (
        <div className="text-[10px] text-tnvs-muted mb-1">{evt.date}</div>
      )}
      {(evt.forecast || evt.previous) && (
        <div className="flex gap-3 text-[10px] tabular-nums mb-1.5">
          {evt.previous && (
            <span><span className="text-tnvs-muted">Prev:</span> {evt.previous}</span>
          )}
          {evt.forecast && (
            <span><span className="text-tnvs-muted">Est:</span> {evt.forecast}</span>
          )}
        </div>
      )}
      {reaction && (
        <div className={cls('text-[10px] mt-1.5 pt-1.5 border-t border-white/[0.06]', reactionColor)}>
          <span className="text-tnvs-muted">Reaccion oro:</span> {reaction}
        </div>
      )}
    </div>
  );
}

// ─── Main page ──────────────────────────────────────────────────────

export const MacroPage = memo(function MacroPage() {
  const [indicators, setIndicators] = useState<MacroIndicator[]>([]);
  const [marketState, setMarketState] = useState<MacroMarketState | null>(null);
  const [events, setEvents] = useState<MacroCalendarEvent[]>([]);
  const [liquidity, setLiquidity] = useState<MacroLiquidity | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchAll = async () => {
    try {
      const [ind, ms, rad, liq] = await Promise.allSettled([
        api.macro.indicators(),
        api.macro.marketState(),
        api.macro.radar(7),
        api.macro.liquidity(),
      ]);
      if (ind.status === 'fulfilled') setIndicators(ind.value.items);
      if (ms.status === 'fulfilled') setMarketState(ms.value);
      if (rad.status === 'fulfilled') setEvents(rad.value.events);
      if (liq.status === 'fulfilled') setLiquidity(liq.value);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, 60000);
    return () => clearInterval(id);
  }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    try { await fetchAll(); } finally { setRefreshing(false); }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Globe className="h-5 w-5" />
            Macro Dashboard
          </h2>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="rounded border border-white/[0.06] bg-white/[0.03] hover:bg-white/[0.06] text-white px-3 py-1.5 text-xs flex items-center gap-2 disabled:opacity-50"
        >
          <RefreshCw className={cls('h-3.5 w-3.5', refreshing && 'animate-spin')} />
          {refreshing ? 'Actualizando…' : 'Refrescar'}
        </button>
      </div>

      {/* Estado del Mercado — tags */}
      <section className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-4">
        <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
          <Activity className="h-4 w-4" />
          Estado del Mercado
        </h3>
        {marketState && marketState.tags.length > 0 ? (
          <>
            <div className="flex flex-wrap gap-2 mb-3">
              {marketState.tags.map((t, i) => (
                <MarketTagPill key={i} tag={t} />
              ))}
            </div>
            {marketState.narrative && (
              <p className="text-xs text-tnvs-muted leading-relaxed border-t border-white/[0.04] pt-3">
                {marketState.narrative}
              </p>
            )}
          </>
        ) : (
          <div className="text-xs text-tnvs-muted">Sin tags cargados.</div>
        )}
      </section>

      {/* Pulso Macro — 6 indicator cards */}
      <section className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-4">
        <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
          <BarChart3 className="h-4 w-4" />
          Pulso Macro — Datos vs Previo
        </h3>
        {indicators.length > 0 ? (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            {indicators.map((ind) => (
              <IndicatorCard key={ind.key} ind={ind} />
            ))}
          </div>
        ) : (
          <div className="text-xs text-tnvs-muted">Sin indicadores cargados.</div>
        )}
      </section>

      {/* Liquidity */}
      {liquidity && (
        <section className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-4">
          <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
            <TrendingUp className="h-4 w-4" />
            Liquidez (TGA / RRP)
          </h3>
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="rounded bg-white/[0.02] p-3">
              <span className="text-tnvs-muted block mb-1">TGA (Tesoro)</span>
              <span className="text-lg font-mono tabular-nums text-white">
                {liquidity.tga_billion != null ? `$${liquidity.tga_billion.toFixed(1)}B` : '—'}
              </span>
              {liquidity.tga_billion != null && liquidity.tga_billion > 700 && (
                <div className="text-[10px] text-red-300 mt-1">⚠️ TGA elevado (drenaje de liquidez)</div>
              )}
            </div>
            <div className="rounded bg-white/[0.02] p-3">
              <span className="text-tnvs-muted block mb-1">RRP (Reverse Repo)</span>
              <span className="text-lg font-mono tabular-nums text-white">
                {liquidity.rrp_billion != null ? `$${liquidity.rrp_billion.toFixed(1)}B` : '—'}
              </span>
              {liquidity.rrp_billion != null && liquidity.rrp_billion < 300 && (
                <div className="text-[10px] text-amber-300 mt-1">⚠️ RRP bajo (liquidez reducida)</div>
              )}
            </div>
          </div>
        </section>
      )}

      {/* Radar Macro — upcoming events */}
      <section className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-4">
        <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
          <Newspaper className="h-4 w-4" />
          Radar Macro — Próximos eventos
        </h3>
        {events.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {events.slice(0, 12).map((evt, i) => (
              <RadarEventCard key={i} evt={evt} />
            ))}
          </div>
        ) : (
          <div className="text-xs text-tnvs-muted">Sin eventos próximos.</div>
        )}
      </section>
    </div>
  );
});