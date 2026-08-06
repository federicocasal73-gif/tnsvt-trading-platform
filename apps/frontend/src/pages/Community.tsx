import { memo, useEffect, useState } from 'react';
import {
  Activity, Bell, BellOff, Calendar, CheckCircle2, ClipboardList,
  Plus, RefreshCw, Vote, Users,
} from 'lucide-react';
import {
  api, CommunitySurvey, CommunityEvent,
} from '../lib/api';
import { cls } from '../utils/format';

// ─── Helpers ────────────────────────────────────────────────────────

function impactBadge(impact: number) {
  if (impact >= 3) return { label: 'Alto', bg: 'bg-red-500/20', text: 'text-red-300', border: 'border-red-500/30' };
  if (impact === 2) return { label: 'Medio', bg: 'bg-amber-500/20', text: 'text-amber-300', border: 'border-amber-500/30' };
  return { label: 'Bajo', bg: 'bg-blue-500/15', text: 'text-blue-300', border: 'border-blue-500/20' };
}

function formatDt(dt: string | null): string {
  if (!dt) return '—';
  try {
    return new Date(dt).toLocaleString('es-AR', {
      day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return dt;
  }
}

function eventReaction(indicator: string): string | null {
  const l = indicator.toLowerCase();
  if (l.includes('fomc') || l.includes('fed') || l.includes('rate')) return 'FED: hawkish → USD+ / oro-, dovish → USD- / oro+';
  if (l.includes('cpi') || l.includes('inflation') || l.includes('ppi')) return 'Inflación alta → USD+ y oro+';
  if (l.includes('nonfarm') || l.includes('nfp') || l.includes('payroll')) return 'Empleo fuerte → USD+; débil → USD-';
  if (l.includes('gdp')) return 'GDP fuerte → USD+; débil → USD-';
  if (l.includes('retail')) return 'Ventas fuertes → USD+';
  return null;
}

// ─── Sub-componentes ────────────────────────────────────────────────

function EventCard({ evt, onToggle }: { evt: CommunityEvent; onToggle: (e: CommunityEvent) => void }) {
  const ib = impactBadge(evt.impact);
  const reaction = eventReaction(evt.indicator);
  return (
    <div className={cls('rounded-lg border p-3', ib.border)}>
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-2 flex-wrap">
          {evt.currency && (
            <span className="inline-flex text-[10px] font-mono bg-white/[0.06] px-1.5 py-0.5 rounded">{evt.currency}</span>
          )}
          <span className={cls('inline-flex items-center text-[10px] font-semibold px-1.5 py-0.5 rounded', ib.bg, ib.text)}>
            {ib.label}
          </span>
          {evt.notified_actual === 1 && (
            <span className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300">
              <CheckCircle2 className="h-3 w-3" /> Publicado
            </span>
          )}
        </div>
        <button
          onClick={() => onToggle(evt)}
          title={evt.notify_enabled ? 'Desactivar alerta' : 'Activar alerta'}
          className={cls(
            'inline-flex h-6 w-6 items-center justify-center rounded border transition-colors',
            evt.notify_enabled
              ? 'border-white/[0.08] bg-white/[0.05] text-emerald-300 hover:bg-white/[0.1]'
              : 'border-white/[0.06] bg-transparent text-tnvs-muted hover:bg-white/[0.05]',
          )}
        >
          {evt.notify_enabled ? <Bell className="h-3.5 w-3.5" /> : <BellOff className="h-3.5 w-3.5" />}
        </button>
      </div>
      <h4 className="text-sm font-semibold text-white leading-snug mb-1.5">{evt.indicator}</h4>
      <div className="text-[10px] text-tnvs-muted mb-1.5">{formatDt(evt.announcement_dt)}</div>
      <div className="grid grid-cols-3 gap-2 text-[10px] tabular-nums mb-1.5">
        <div>
          <div className="text-tnvs-muted">Anterior</div>
          <div className="text-tnvs-dim">{evt.previous || '—'}</div>
        </div>
        <div>
          <div className="text-tnvs-muted">Estimado</div>
          <div className="text-tnvs-dim">{evt.forecast || '—'}</div>
        </div>
        <div>
          <div className="text-tnvs-muted">Real</div>
          <div className={cls('font-semibold', evt.actual ? 'text-emerald-300' : 'text-tnvs-dim')}>
            {evt.actual || '…'}
          </div>
        </div>
      </div>
      {reaction && (
        <div className="text-[10px] pt-1.5 border-t border-white/[0.06] text-tnvs-muted">
          💡 {reaction}
        </div>
      )}
    </div>
  );
}

function SurveyCard({ survey, onClose }: { survey: CommunitySurvey; onClose: (s: CommunitySurvey) => void }) {
  const total = (survey.votes ?? []).reduce((acc, v) => acc + v.count, 0);
  const counts = new Map<number, number>((survey.votes ?? []).map(v => [v.option_selected, v.count]));
  return (
    <div className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-3">
      <div className="flex items-start justify-between gap-2 mb-2">
        <h4 className="text-sm font-semibold text-white leading-snug">{survey.title}</h4>
        <div className="flex items-center gap-2 shrink-0">
          <span className="inline-flex items-center gap-1 text-[10px] text-tnvs-muted">
            <Users className="h-3 w-3" /> {total}
          </span>
          <span className={cls(
            'inline-flex items-center text-[10px] px-1.5 py-0.5 rounded',
            survey.is_active === 1 ? 'bg-emerald-500/15 text-emerald-300' : 'bg-white/[0.06] text-tnvs-muted',
          )}>
            {survey.is_active === 1 ? 'Activa' : 'Cerrada'}
          </span>
        </div>
      </div>
      <div className="space-y-1.5 mb-3">
        {survey.options.map((opt, idx) => {
          const c = counts.get(idx) || 0;
          const pct = total > 0 ? Math.round((c / total) * 100) : 0;
          return (
            <div key={idx}>
              <div className="flex justify-between text-[10px] mb-0.5">
                <span className="text-tnvs-dim">{opt}</span>
                <span className="text-tnvs-muted tabular-nums">{c} · {pct}%</span>
              </div>
              <div className="h-1.5 rounded bg-white/[0.05] overflow-hidden">
                <div
                  className="h-full rounded bg-tnvs-purple/70"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
      {survey.is_active === 1 && (
        <button
          onClick={() => onClose(survey)}
          className="rounded border border-white/[0.06] bg-white/[0.03] hover:bg-white/[0.06] text-tnvs-muted hover:text-white px-2 py-1 text-[10px]"
        >
          Cerrar encuesta
        </button>
      )}
    </div>
  );
}

// ─── Main page ──────────────────────────────────────────────────────

type Tab = 'calendar' | 'surveys' | 'pending';

export const CommunityPage = memo(function CommunityPage() {
  const [tab, setTab] = useState<Tab>('calendar');
  const [events, setEvents] = useState<CommunityEvent[]>([]);
  const [surveys, setSurveys] = useState<CommunitySurvey[]>([]);
  const [pending, setPending] = useState<CommunityEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Modal crear encuesta
  const [showCreate, setShowCreate] = useState(false);
  const [title, setTitle] = useState('');
  const [options, setOptions] = useState(['', '', '', '']);

  const fetchAll = async () => {
    try {
      const [ev, su, pe] = await Promise.allSettled([
        api.community.events({ days: 7 }),
        api.community.surveys(),
        api.community.pendingActual(),
      ]);
      if (ev.status === 'fulfilled') setEvents(ev.value.events);
      if (su.status === 'fulfilled') setSurveys(su.value.surveys);
      if (pe.status === 'fulfilled') setPending(pe.value.events);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
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
    setError(null);
    try { await fetchAll(); } finally { setRefreshing(false); }
  };

  const handleToggleNotify = async (evt: CommunityEvent) => {
    try {
      await api.community.setEventNotify(evt.id, evt.notify_enabled !== 1);
      await fetchAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const handleCloseSurvey = async (s: CommunitySurvey) => {
    try {
      await api.community.closeSurvey(s.id);
      await fetchAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const handleCreateSurvey = async () => {
    const cleanOpts = options.map(o => o.trim()).filter(Boolean);
    if (!title.trim() || cleanOpts.length < 2) {
      setError('Título y al menos 2 opciones son requeridos.');
      return;
    }
    try {
      await api.community.createSurvey({ title: title.trim(), options: cleanOpts });
      setShowCreate(false);
      setTitle('');
      setOptions(['', '', '', '']);
      await fetchAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const tabs: { id: Tab; label: string; icon: typeof Calendar }[] = [
    { id: 'calendar', label: 'Calendario', icon: Calendar },
    { id: 'surveys', label: 'Encuestas', icon: ClipboardList },
    { id: 'pending', label: 'Dato Publicado', icon: Activity },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Vote className="h-5 w-5" />
            Comunidad
          </h2>
        </div>
        <div className="flex items-center gap-2">
          {tab === 'surveys' && (
            <button
              onClick={() => setShowCreate(true)}
              className="rounded border border-white/[0.08] bg-white/[0.04] hover:bg-white/[0.08] text-white px-3 py-1.5 text-xs flex items-center gap-2"
            >
              <Plus className="h-3.5 w-3.5" /> Nueva encuesta
            </button>
          )}
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="rounded border border-white/[0.06] bg-white/[0.03] hover:bg-white/[0.06] text-white px-3 py-1.5 text-xs flex items-center gap-2 disabled:opacity-50"
          >
            <RefreshCw className={cls('h-3.5 w-3.5', refreshing && 'animate-spin')} />
            {refreshing ? 'Actualizando…' : 'Refrescar'}
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-white/[0.06]">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={cls(
              'flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 -mb-px transition-colors',
              tab === id
                ? 'border-tnvs-purple text-white'
                : 'border-transparent text-tnvs-muted hover:text-white',
            )}
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
            {id === 'pending' && pending.length > 0 && (
              <span className="ml-1 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500/20 px-1 text-[9px] text-red-300">
                {pending.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-sm text-tnvs-muted">Cargando…</div>
      ) : (
        <>
          {tab === 'calendar' && (
            <div className="space-y-4">
              <div className="text-xs text-tnvs-muted">
                Eventos económicos persistidos por el bot. Toggle para habilitar/deshabilitar alertas.
              </div>
              {events.length === 0 ? (
                <div className="text-sm text-tnvs-muted">Sin eventos registrados aún.</div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                  {events.map(evt => (
                    <EventCard key={evt.id} evt={evt} onToggle={handleToggleNotify} />
                  ))}
                </div>
              )}
            </div>
          )}

          {tab === 'surveys' && (
            <div className="space-y-4">
              {surveys.length === 0 ? (
                <div className="text-sm text-tnvs-muted">Sin encuestas registradas.</div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                  {surveys.map(s => (
                    <SurveyCard key={s.id} survey={s} onClose={handleCloseSurvey} />
                  ))}
                </div>
              )}
            </div>
          )}

          {tab === 'pending' && (
            <div className="space-y-4">
              <div className="text-xs text-tnvs-muted">
                Eventos con alerta previa enviada, sin dato real aún (ventana 2h). El bot publica “Anterior → Estimado → Real” cuando el dato sale.
              </div>
              {pending.length === 0 ? (
                <div className="text-sm text-tnvs-muted">Nada pendiente de dato real.</div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                  {pending.map(evt => (
                    <EventCard key={evt.id} evt={evt} onToggle={handleToggleNotify} />
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* Modal crear encuesta */}
      {showCreate && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4">
          <div className="w-full max-w-md rounded-xl border border-white/[0.08] bg-tnvs-void p-5 shadow-2xl">
            <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
              <ClipboardList className="h-4 w-4" /> Nueva encuesta
            </h3>
            <label className="block text-[10px] text-tnvs-muted mb-1">Título</label>
            <input
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="¿Cómo ves XAUUSD esta semana?"
              className="w-full rounded border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-white placeholder:text-tnvs-muted/50 focus:outline-none focus:border-tnvs-purple/60 mb-3"
            />
            <label className="block text-[10px] text-tnvs-muted mb-1">Opciones</label>
            <div className="space-y-2 mb-4">
              {options.map((o, i) => (
                <input
                  key={i}
                  value={o}
                  onChange={e => {
                    const next = [...options];
                    next[i] = e.target.value;
                    setOptions(next);
                  }}
                  placeholder={`Opción ${i + 1}`}
                  className="w-full rounded border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-white placeholder:text-tnvs-muted/50 focus:outline-none focus:border-tnvs-purple/60"
                />
              ))}
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowCreate(false)}
                className="rounded border border-white/[0.06] bg-white/[0.03] hover:bg-white/[0.06] text-tnvs-muted px-3 py-1.5 text-xs"
              >
                Cancelar
              </button>
              <button
                onClick={handleCreateSurvey}
                className="rounded bg-tnvs-purple/90 hover:bg-tnvs-purple text-white px-3 py-1.5 text-xs font-medium"
              >
                Crear
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
});
