import { useEffect, useState } from 'react';
import { Users, DollarSign, TrendingDown, RefreshCw, Plus, Trash2, CheckCircle2, XCircle } from 'lucide-react';
import { api, AdminTenant, AdminStats, TenantPlan, TenantStatus } from '../lib/api';
import { cls } from '../utils/format';
import { Card, Empty, Page, StatCard } from '../components/common';

const PLAN_COLORS: Record<string, string> = {
  trimestral: 'bg-tnvs-purple/15 text-tnvs-purple',
  semestral: 'bg-blue-500/15 text-blue-400',
  anual: 'bg-amber-500/15 text-amber-400',
};

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-tnvs-win/15 text-tnvs-win',
  trial: 'bg-tnvs-warn/15 text-tnvs-warn',
  suspended: 'bg-tnvs-loss/15 text-tnvs-loss',
};

const PLANS: { value: TenantPlan; label: string; months: number; usd: number }[] = [
  { value: 'trimestral', label: 'Trimestral', months: 3, usd: 150 },
  { value: 'semestral', label: 'Semestral', months: 6, usd: 375 },
  { value: 'anual', label: 'Anual', months: 12, usd: 599.99 },
];

const PLAN_LABEL: Record<string, string> = {
  trimestral: 'Trimestral',
  semestral: 'Semestral',
  anual: 'Anual',
};

function fmtUsd(v: number | null | undefined): string {
  return v == null ? '—' : `$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return isNaN(d.getTime()) ? '—' : d.toLocaleDateString();
}

export function AdminPage() {
  const [tenants, setTenants] = useState<AdminTenant[]>([]);
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form de alta manual
  const [showForm, setShowForm] = useState(false);
  const [formName, setFormName] = useState('');
  const [formEmail, setFormEmail] = useState('');
  const [formPlan, setFormPlan] = useState<TenantPlan>('trimestral');
  const [formStatus, setFormStatus] = useState<TenantStatus>('active');
  const [formPrice, setFormPrice] = useState('');
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [t, s] = await Promise.all([
        api.admin.tenants(),
        api.admin.stats(),
      ]);
      setTenants(t);
      setStats(s);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName.trim()) {
      setError('El nombre es requerido.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const plan = PLANS.find(p => p.value === formPlan)!;
      const priceUsd = formPrice.trim() === '' ? undefined : parseFloat(formPrice);
      await api.admin.create({
        name: formName.trim(),
        email: formEmail.trim() || undefined,
        plan: formPlan,
        status: formStatus,
        price_usd: priceUsd && !isNaN(priceUsd) ? priceUsd : plan.usd,
      });
      setFormName('');
      setFormEmail('');
      setFormPrice('');
      setShowForm(false);
      await load();
    } catch (err: any) {
      setError(err.message || 'No se pudo dar de alta.');
    } finally {
      setSaving(false);
    }
  };

  const setStatus = async (t: AdminTenant, status: TenantStatus) => {
    try {
      await api.admin.update(t.id, { status });
      await load();
    } catch (err: any) {
      setError(err.message || 'No se pudo actualizar.');
    }
  };

  const changePlan = async (t: AdminTenant, plan: TenantPlan) => {
    try {
      await api.admin.update(t.id, { plan });
      await load();
    } catch (err: any) {
      setError(err.message || 'No se pudo cambiar el plan.');
    }
  };

  const removeTenant = async (t: AdminTenant) => {
    if (!window.confirm(`¿Eliminar definitivamente a "${t.name}"?`)) return;
    try {
      await api.admin.remove(t.id);
      await load();
    } catch (err: any) {
      setError(err.message || 'No se pudo eliminar.');
    }
  };

  return (
    <Page
      title="Admin · Suscriptores"
      subtitle="Gestión manual de suscriptores (cobro por transferencia)"
      actions={
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowForm(s => !s)}
            className="inline-flex items-center gap-1 rounded-md bg-tnvs-purple px-3 py-1.5 text-xs font-medium text-white hover:bg-tnvs-purple/80"
          >
            <Plus className="h-3 w-3" /> Alta suscriptor
          </button>
          <button
            onClick={load}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-tnvs-muted hover:bg-white/[0.04] hover:text-white"
          >
            <RefreshCw className="h-3 w-3" /> Refrescar
          </button>
        </div>
      }
    >
      {error && (
        <div className="mb-4 rounded-md border border-tnvs-loss/30 bg-tnvs-loss/10 px-3 py-2 text-sm text-tnvs-loss">
          {error}
        </div>
      )}

      {showForm && (
        <Card header="Nuevo suscriptor" className="mb-4">
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <div>
                <label className="tnvs-label" htmlFor="t-name">Nombre *</label>
                <input
                  id="t-name"
                  className="tnvs-input mt-1"
                  value={formName}
                  onChange={e => setFormName(e.target.value)}
                  placeholder="Nombre y apellido / empresa"
                  autoFocus
                />
              </div>
              <div>
                <label className="tnvs-label" htmlFor="t-email">Email</label>
                <input
                  id="t-email"
                  className="tnvs-input mt-1"
                  type="email"
                  value={formEmail}
                  onChange={e => setFormEmail(e.target.value)}
                  placeholder="cliente@mail.com"
                />
              </div>
              <div>
                <label className="tnvs-label" htmlFor="t-price">Precio USD (opcional)</label>
                <input
                  id="t-price"
                  className="tnvs-input mt-1"
                  type="number"
                  step="0.01"
                  min="0"
                  value={formPrice}
                  onChange={e => setFormPrice(e.target.value)}
                  placeholder="auto según plan"
                />
              </div>
              <div>
                <label className="tnvs-label" htmlFor="t-plan">Plan</label>
                <select
                  id="t-plan"
                  className="tnvs-input mt-1"
                  value={formPlan}
                  onChange={e => setFormPlan(e.target.value as TenantPlan)}
                >
                  {PLANS.map(p => (
                    <option key={p.value} value={p.value}>
                      {p.label} — ${p.usd} / {p.months} meses
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="tnvs-label" htmlFor="t-status">Estado</label>
                <select
                  id="t-status"
                  className="tnvs-input mt-1"
                  value={formStatus}
                  onChange={e => setFormStatus(e.target.value as TenantStatus)}
                >
                  <option value="active">Activo</option>
                  <option value="trial">Trial</option>
                  <option value="suspended">Suspendido</option>
                </select>
              </div>
            </div>
            <div className="flex items-center gap-2 pt-1">
              <button
                type="submit"
                disabled={saving}
                className="tnvs-btn-primary"
              >
                {saving ? 'Guardando…' : 'Guardar'}
              </button>
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="rounded-md px-3 py-1.5 text-xs text-tnvs-muted hover:bg-white/[0.04] hover:text-white"
              >
                Cancelar
              </button>
            </div>
          </form>
        </Card>
      )}

      {/* KPIs */}
      <div className="mb-4 grid grid-cols-4 gap-3">
        <StatCard
          label="Suscriptores totales"
          value={stats?.total_tenants ?? '—'}
          hint="incl. trial + suspended"
          icon={Users}
          accent="text-white"
        />
        <StatCard
          label="Activos"
          value={stats?.active_subscriptions ?? '—'}
          hint="status = active"
          icon={Users}
          accent="text-tnvs-win"
        />
        <StatCard
          label="MRR"
          value={stats ? `$${stats.mrr_usd.toLocaleString()}` : '—'}
          hint="Monthly Recurring Revenue USD"
          icon={DollarSign}
          accent="text-tnvs-win"
        />
        <StatCard
          label="Churn"
          value={stats ? `${stats.churn_pct.toFixed(1)}%` : '—'}
          hint="% suspendidos sobre total"
          icon={TrendingDown}
          accent="text-tnvs-loss"
        />
      </div>

      {/* Plan breakdown */}
      <div className="mb-4 grid grid-cols-2 gap-4">
        <Card header="Plan breakdown">
          {stats && stats.by_plan.length > 0 ? (
            <div className="space-y-2">
              {stats.by_plan.map(b => {
                const total = stats.total_tenants || 1;
                const pct = (b.count / total) * 100;
                const price = stats.pricing_per_plan_usd?.[b.plan] ?? 0;
                return (
                  <div key={b.plan}>
                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2">
                        <span className={cls('rounded px-2 py-0.5 font-medium uppercase', PLAN_COLORS[b.plan] || 'bg-white/10 text-tnvs-muted')}>
                          {PLAN_LABEL[b.plan] || b.plan}
                        </span>
                        <span className="text-tnvs-muted">{b.count} · ${price}/mes MRR</span>
                      </div>
                      <span className="font-mono text-tnvs-muted">{pct.toFixed(0)}%</span>
                    </div>
                    <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-tnvs-void">
                      <div
                        className={cls('h-full', b.plan === 'anual' && 'bg-amber-500',
                          b.plan === 'semestral' && 'bg-blue-500',
                          b.plan === 'trimestral' && 'bg-tnvs-purple')}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-sm text-tnvs-muted">
              {stats ? 'Sin suscriptores todavía' : 'Cargando…'}
            </div>
          )}
        </Card>

        <Card header="Cómo gestionar (cobro manual)">
          <ol className="space-y-2 text-xs text-tnvs-muted">
            <li><span className="font-medium text-white">1.</span> Cobrás la transferencia por fuera del sistema.</li>
            <li><span className="font-medium text-white">2.</span> Tocá <span className="text-tnvs-purple">Alta suscriptor</span> con nombre, plan y estado <em>activo</em>.</li>
            <li><span className="font-medium text-white">3.</span> El MRR y el plan breakdown se actualizan al instante.</li>
            <li><span className="font-medium text-white">4.</span> Para renovar: cambiá el plan o el estado; para baja: suspendé o eliminá.</li>
          </ol>
        </Card>
      </div>

      {/* Tenants table */}
      <Card header={`Suscriptores (${tenants.length})`}>
        {loading ? (
          <div className="py-8 text-center text-sm text-tnvs-muted">Cargando…</div>
          ) : tenants.length === 0 ? (
            <Empty
              title="Sin suscriptores"
              description={
                error
                  ? 'La petición falló. Reintentá más tarde.'
                  : 'Dale de alta al primer suscriptor con el botón "Alta suscriptor".'
              }
            />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-tnvs-border text-left text-[11px] uppercase tracking-wider text-tnvs-muted">
                  <th className="px-3 py-2 font-medium">Suscriptor</th>
                  <th className="px-3 py-2 font-medium">Plan</th>
                  <th className="px-3 py-2 font-medium">Estado</th>
                  <th className="px-3 py-2 font-medium text-right">Precio USD</th>
                  <th className="px-3 py-2 font-medium">Vence</th>
                  <th className="px-3 py-2 font-medium text-right">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {tenants.map(t => (
                  <tr key={t.id} className="border-b border-tnvs-border/30 hover:bg-white/[0.02]">
                    <td className="px-3 py-2.5">
                      <div className="font-medium text-white">{t.name}</div>
                      <div className="font-mono text-[10px] text-tnvs-dim">
                        {t.email || t.slug || t.id.slice(0, 8)}
                      </div>
                    </td>
                    <td className="px-3 py-2.5">
                      <select
                        value={t.plan}
                        onChange={e => changePlan(t, e.target.value as TenantPlan)}
                        className="rounded border border-tnvs-border bg-tnvs-surface px-2 py-1 text-xs text-tnvs-muted"
                      >
                        {PLANS.map(p => (
                          <option key={p.value} value={p.value}>{p.label}</option>
                        ))}
                      </select>
                    </td>
                    <td className="px-3 py-2.5">
                      <span className={cls('rounded px-2 py-0.5 text-[10px] font-medium uppercase', STATUS_COLORS[t.status] || 'bg-white/10 text-tnvs-muted')}>
                        {t.status}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-right font-mono text-tnvs-muted">{fmtUsd(t.price_usd)}</td>
                    <td className="px-3 py-2.5 font-mono text-[11px] text-tnvs-muted">{fmtDate(t.expires_at)}</td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center justify-end gap-1">
                        {t.status !== 'active' ? (
                          <button
                            onClick={() => setStatus(t, 'active')}
                            title="Activar"
                            className="rounded p-1 text-tnvs-win hover:bg-white/[0.06]"
                          >
                            <CheckCircle2 className="h-4 w-4" />
                          </button>
                        ) : (
                          <button
                            onClick={() => setStatus(t, 'suspended')}
                            title="Suspender"
                            className="rounded p-1 text-tnvs-loss hover:bg-white/[0.06]"
                          >
                            <XCircle className="h-4 w-4" />
                          </button>
                        )}
                        <button
                          onClick={() => removeTenant(t)}
                          title="Eliminar"
                          className="rounded p-1 text-tnvs-muted hover:bg-white/[0.06] hover:text-tnvs-loss"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </Page>
  );
}
