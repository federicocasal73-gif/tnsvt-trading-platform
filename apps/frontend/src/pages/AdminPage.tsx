import { useEffect, useState } from 'react';
import { Users, DollarSign, TrendingDown, RefreshCw } from 'lucide-react';
import { api, AdminTenant, AdminStats } from '../lib/api';
import { cls } from '../utils/format';
import { Card, Empty, Page, StatCard } from '../components/common';

const PLAN_COLORS: Record<string, string> = {
  free: 'bg-tnvs-muted/20 text-tnvs-muted',
  starter: 'bg-blue-500/15 text-blue-400',
  pro: 'bg-tnvs-purple/15 text-tnvs-purple',
  enterprise: 'bg-amber-500/15 text-amber-400',
};

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-tnvs-win/15 text-tnvs-win',
  trial: 'bg-tnvs-warn/15 text-tnvs-warn',
  suspended: 'bg-tnvs-loss/15 text-tnvs-loss',
};

export function AdminPage() {
  const [tenants, setTenants] = useState<AdminTenant[]>([]);
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  useEffect(() => {
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, []);

  return (
    <Page
      title="Admin · Tenants & Billing"
      subtitle="MRR, churn, plan breakdown (suscripciones Stripe en vivo)"
      actions={
        <button
          onClick={load}
          className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-tnvs-muted hover:bg-white/[0.04] hover:text-white"
        >
          <RefreshCw className="h-3 w-3" /> Refrescar
        </button>
      }
    >
      {error && (
        <div className="mb-4 rounded-md border border-tnvs-loss/30 bg-tnvs-loss/10 px-3 py-2 text-sm text-tnvs-loss">
          {error}
        </div>
      )}

      {/* KPIs */}
      <div className="mb-4 grid grid-cols-4 gap-3">
        <StatCard
          label="Tenants totales"
          value={stats?.total_tenants ?? '—'}
          hint="incl. free + suspended"
          icon={Users}
          accent="text-white"
        />
        <StatCard
          label="Active subs"
          value={stats?.active_subscriptions ?? '—'}
          hint="plan != free AND status=active"
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
          hint="última corrida webhook"
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
                          {b.plan}
                        </span>
                        <span className="text-tnvs-muted">{b.count} tenants · ${price}/mo</span>
                      </div>
                      <span className="font-mono text-tnvs-muted">{pct.toFixed(0)}%</span>
                    </div>
                    <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-tnvs-void">
                      <div
                        className={cls('h-full', b.plan === 'pro' && 'bg-tnvs-purple',
                          b.plan === 'starter' && 'bg-blue-500',
                          b.plan === 'enterprise' && 'bg-amber-500',
                          b.plan === 'free' && 'bg-tnvs-muted'
                        )}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-sm text-tnvs-muted">
              {stats ? 'Sin planes registrados todavía' : 'Cargando…'}
            </div>
          )}
        </Card>

        <Card header="Webhook events (referencia)">
          <div className="space-y-2 text-xs text-tnvs-muted">
            <p>Para que MRR se actualice en vivo, configurar el webhook de Stripe:</p>
            <pre className="rounded-md bg-tnvs-void px-3 py-2 font-mono text-[11px] text-tnvs-muted">
{`POST /api/v1/auth/billing/webhook
Auth: HMAC SHA256 (header Stripe-Signature)

Eventos manejados:
  - checkout.session.completed
  - customer.subscription.{created,updated,deleted}
  - invoice.paid

Env: STRIPE_WEBHOOK_SECRET=<sk_webhook_...>`}
            </pre>
          </div>
        </Card>
      </div>

      {/* Tenants table */}
      <Card header={`Tenants (${tenants.length})`}>
        {loading ? (
          <div className="py-8 text-center text-sm text-tnvs-muted">Cargando…</div>
          ) : tenants.length === 0 ? (
            <Empty
              title="Sin tenants"
              description={
                error
                  ? 'La petición falló (ver error arriba). Requerido rol admin/super_admin/tenant_admin.'
                  : stats === null
                  ? 'Cargando…'
                  : 'No hay tenants registrados todavía.'
              }
            />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-tnvs-border text-left text-[11px] uppercase tracking-wider text-tnvs-muted">
                  <th className="px-3 py-2 font-medium">Tenant</th>
                  <th className="px-3 py-2 font-medium">Slug</th>
                  <th className="px-3 py-2 font-medium">Plan</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium text-right">Users</th>
                  <th className="px-3 py-2 font-medium text-right">Señales/día</th>
                  <th className="px-3 py-2 font-medium">Creado</th>
                </tr>
              </thead>
              <tbody>
                {tenants.map(t => (
                  <tr key={t.id} className="border-b border-tnvs-border/30 hover:bg-white/[0.02]">
                    <td className="px-3 py-2.5">
                      <div className="font-medium text-white">{t.name}</div>
                      <div className="font-mono text-[10px] text-tnvs-dim">{t.id.slice(0, 8)}…</div>
                    </td>
                    <td className="px-3 py-2.5 font-mono text-xs text-tnvs-muted">{t.slug}</td>
                    <td className="px-3 py-2.5">
                      <span className={cls('rounded px-2 py-0.5 text-[10px] font-medium uppercase', PLAN_COLORS[t.plan])}>
                        {t.plan}
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      <span className={cls('rounded px-2 py-0.5 text-[10px] font-medium uppercase', STATUS_COLORS[t.status] || 'bg-white/10 text-tnvs-muted')}>
                        {t.status}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-right font-mono text-tnvs-muted">{t.max_users}</td>
                    <td className="px-3 py-2.5 text-right font-mono text-tnvs-muted">{t.max_signals_per_day}</td>
                    <td className="px-3 py-2.5 font-mono text-[11px] text-tnvs-muted">
                      {new Date(t.created_at).toLocaleDateString()}
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
