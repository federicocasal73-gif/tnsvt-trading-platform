import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, X } from 'lucide-react';
import { cls } from '../utils/format';

interface Plan {
  name: string;
  price: string;
  period: string;
  blurb: string;
  highlight?: boolean;
  ctaLabel: string;
  features: { ok: boolean; label: string }[];
}

const PLANS: Plan[] = [
  {
    name: 'Free',
    price: '$0',
    period: 'forever',
    blurb: 'Para probar la plataforma con una cuenta demo.',
    ctaLabel: 'Empezar gratis',
    features: [
      { ok: true, label: '1 cuenta MT5' },
      { ok: true, label: '100 señales/día' },
      { ok: true, label: '1 canal Telegram' },
      { ok: true, label: 'Dashboard analytics' },
      { ok: false, label: 'Copy trading' },
      { ok: false, label: 'AI scoring' },
      { ok: false, label: 'Soporte prioritario' },
    ],
  },
  {
    name: 'Starter',
    price: '$29',
    period: '/mes',
    blurb: 'Para traders retail que operan en serio.',
    highlight: true,
    ctaLabel: 'Elegir Starter',
    features: [
      { ok: true, label: '5 cuentas MT5' },
      { ok: true, label: '1.000 señales/día' },
      { ok: true, label: '10 canales Telegram' },
      { ok: true, label: 'Dashboard analytics + export' },
      { ok: true, label: 'Copy trading (hasta 3 grupos)' },
      { ok: false, label: 'AI scoring' },
      { ok: false, label: 'Soporte prioritario' },
    ],
  },
  {
    name: 'Pro',
    price: '$99',
    period: '/mes',
    blurb: 'Para operadores con volumen o desks.',
    ctaLabel: 'Elegir Pro',
    features: [
      { ok: true, label: 'Cuentas MT5 ilimitadas' },
      { ok: true, label: 'Señales ilimitadas' },
      { ok: true, label: 'Canales Telegram ilimitados' },
      { ok: true, label: 'Analytics avanzado + alertas' },
      { ok: true, label: 'Copy trading ilimitado' },
      { ok: true, label: 'AI scoring (Gemini)' },
      { ok: true, label: 'Soporte prioritario 24/7' },
    ],
  },
];

export function PricingPage() {
  const [annual, setAnnual] = useState(false);
  return (
    <div className="min-h-screen bg-tnvs-void text-white">
      <header className="border-b border-tnvs-border/40">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link to="/landing" className="font-pixel text-[10px] uppercase tracking-[0.18em] text-white/90">
            TNSVT
          </Link>
          <Link to="/login" className="text-sm text-tnvs-muted hover:text-white">Sign in</Link>
        </div>
      </header>

      <section className="mx-auto max-w-6xl px-6 py-16 text-center">
        <h1 className="text-3xl font-semibold md:text-4xl">Planes simples, sin sorpresas</h1>
        <p className="mx-auto mt-3 max-w-2xl text-sm text-tnvs-muted">
          Empezás gratis, escalás cuando estés operando en serio. Cancelás cuando quieras.
        </p>
        <div className="mt-6 inline-flex items-center gap-3 rounded-full border border-tnvs-border bg-tnvs-surface px-3 py-1.5 text-xs">
          <button
            onClick={() => setAnnual(false)}
            className={cls('rounded-full px-3 py-1', !annual ? 'bg-tnvs-purple text-white' : 'text-tnvs-muted')}
          >
            Mensual
          </button>
          <button
            onClick={() => setAnnual(true)}
            className={cls('rounded-full px-3 py-1', annual ? 'bg-tnvs-purple text-white' : 'text-tnvs-muted')}
          >
            Anual <span className="ml-1 text-tnvs-win">-20%</span>
          </button>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl grid-cols-1 gap-5 px-6 pb-16 md:grid-cols-3">
        {PLANS.map(p => (
          <PlanCard key={p.name} plan={p} annual={annual} />
        ))}
      </section>

      <section className="mx-auto max-w-3xl px-6 pb-20 text-center">
        <h3 className="text-base font-medium text-white">¿Necesitás algo custom?</h3>
        <p className="mt-2 text-sm text-tnvs-muted">
          Tenemos un plan Enterprise con instancias dedicadas, SLA y soporte white-glove.
        </p>
        <Link
          to="/landing"
          className="mt-4 inline-block text-sm text-tnvs-purple hover:underline"
        >
          ← Volver al landing
        </Link>
      </section>
    </div>
  );
}

function PlanCard({ plan, annual }: { plan: Plan; annual: boolean }) {
  const price = annual && plan.price.startsWith('$')
    ? `$${Math.round(parseInt(plan.price.replace('$', '')) * 0.8)}`
    : plan.price;
  const period = annual && plan.period === '/mes' ? '/mes facturado anual' : plan.period;

  return (
    <div
      className={cls(
        'flex flex-col rounded-2xl border p-6',
        plan.highlight
          ? 'border-tnvs-purple bg-gradient-to-b from-tnvs-purple/10 to-tnvs-surface shadow-tnvs-glow'
          : 'border-tnvs-border bg-tnvs-surface',
      )}
    >
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold text-white">{plan.name}</h3>
        {plan.highlight && (
          <span className="rounded-full bg-tnvs-purple/30 px-2 py-0.5 text-[10px] font-medium text-white">
            Popular
          </span>
        )}
      </div>
      <p className="mt-1 text-xs text-tnvs-muted">{plan.blurb}</p>

      <div className="mt-5 flex items-baseline gap-1">
        <span className="font-mono text-3xl font-bold text-white">{price}</span>
        <span className="text-sm text-tnvs-muted">{period}</span>
      </div>

      <ul className="mt-5 space-y-2 text-sm">
        {plan.features.map(f => (
          <li key={f.label} className="flex items-center gap-2">
            {f.ok ? (
              <Check className="h-4 w-4 text-tnvs-win" />
            ) : (
              <X className="h-4 w-4 text-tnvs-dim" />
            )}
            <span className={cls(f.ok ? 'text-white' : 'text-tnvs-dim line-through')}>
              {f.label}
            </span>
          </li>
        ))}
      </ul>

      <Link
        to="/signup"
        className={cls(
          'mt-6 inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium transition-colors',
          plan.highlight
            ? 'bg-tnvs-purple text-white hover:bg-tnvs-purple/90'
            : 'border border-tnvs-border bg-tnvs-void text-white hover:border-tnvs-purple/60',
        )}
      >
        {plan.ctaLabel}
      </Link>
    </div>
  );
}
