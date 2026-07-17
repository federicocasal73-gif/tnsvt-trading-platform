import { Link } from 'react-router-dom';
import { Activity, Bot, BarChart3, ShieldCheck, Zap, Layers } from 'lucide-react';
import { cls } from '../utils/format';

export function LandingPage() {
  return (
    <div className="min-h-screen bg-tnvs-void text-white">
      {/* Topbar */}
      <header className="border-b border-tnvs-border/40 bg-tnvs-void/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2">
            <div className="grid h-9 w-9 place-items-center rounded-lg bg-tnvs-glow shadow-tnvs-soft">
              <Activity className="h-4 w-4 text-white" />
            </div>
            <div>
              <div className="font-pixel text-[10px] uppercase tracking-[0.18em] text-white/90">TNSVT</div>
              <div className="text-xs text-tnvs-muted">Terminal Financiera Pro</div>
            </div>
          </div>
          <nav className="flex items-center gap-3">
            <Link to="/pricing" className="text-sm text-tnvs-muted hover:text-white">Pricing</Link>
            <Link to="/login" className="text-sm text-tnvs-muted hover:text-white">Sign in</Link>
            <Link
              to="/signup"
              className="rounded-md bg-tnvs-purple px-3 py-1.5 text-sm font-medium text-white hover:bg-tnvs-purple/80"
            >
              Empezar gratis
            </Link>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="mx-auto max-w-6xl px-6 py-20 text-center">
        <div className="mx-auto mb-4 inline-flex items-center gap-1.5 rounded-full border border-tnvs-border bg-tnvs-surface px-3 py-1 text-[11px] text-tnvs-muted">
          <span className="h-1.5 w-1.5 rounded-full bg-tnvs-win shadow-[0_0_8px_rgb(16,185,129)]" />
          Multi-tenant · MT5 nativo · Copy trading
        </div>
        <h1 className="mx-auto max-w-3xl text-balance text-4xl font-bold leading-tight tracking-tight md:text-6xl">
          Tu bot de Telegram, conectado a MT5.
          <br />
          <span className="bg-gradient-to-r from-tnvs-purple to-emerald-400 bg-clip-text text-transparent">
            En piloto automático.
          </span>
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-balance text-base text-tnvs-muted">
          TNSVT corre tu bot de señales favorito con integridad financiera, multi-tenant,
          AI scoring y dashboards listos para vender como SaaS.
        </p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Link
            to="/signup"
            className="rounded-lg bg-tnvs-purple px-5 py-2.5 text-sm font-medium text-white shadow-tnvs-glow hover:bg-tnvs-purple/90"
          >
            Empezar gratis
          </Link>
          <Link
            to="/pricing"
            className="rounded-lg border border-tnvs-border bg-tnvs-surface px-5 py-2.5 text-sm font-medium text-tnvs-muted hover:text-white"
          >
            Ver planes
          </Link>
        </div>
        <div className="mt-10 grid grid-cols-1 gap-3 text-left md:grid-cols-3">
          {[
            { label: 'Latencia p95', value: '< 100 ms' },
            { label: 'Uptime 30d', value: '99.95%' },
            { label: 'Tenants activos', value: '3 (beta)' },
          ].map(s => (
            <div key={s.label} className="rounded-lg border border-tnvs-border/60 bg-tnvs-surface px-4 py-3">
              <div className="text-[10px] uppercase tracking-wider text-tnvs-muted">{s.label}</div>
              <div className="mt-1 font-mono text-2xl font-semibold text-white">{s.value}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="mx-auto max-w-6xl px-6 py-16">
        <div className="mb-10 text-center">
          <h2 className="text-2xl font-semibold">Una plataforma, todo el stack</h2>
          <p className="mt-2 text-sm text-tnvs-muted">
            Lo que necesitas para operar y vender automatización de trading.
          </p>
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Feature icon={Bot} title="Bot MT5 nativo" body="Parser multi-formato, multi-cuenta, trailing-stop pip-aware, partial closes, news filter." />
          <Feature icon={BarChart3} title="Analytics en vivo" body="Equity curve, KPIs (Sharpe, Sortino, PF, drawdown) y breakdowns por canal y símbolo." />
          <Feature icon={Zap} title="Telegram en un click" body="Scan de canales y foros, checkboxes, persistencia en config.json del bot." />
          <Feature icon={ShieldCheck} title="Multi-tenant" body="Cada cliente aislado, auth JWT, rate limiting y separación de datos por tenant." />
          <Feature icon={Layers} title="Copy trading" body="Replica señales de un canal maestro a N cuentas siguiendo reglas de riesgo." />
          <Feature icon={Activity} title="Outbox persistente" body="Ni una orden se pierde aunque el bridge o el gateway estén caídos." />
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-4xl px-6 py-16 text-center">
        <div className="rounded-2xl border border-tnvs-border bg-tnvs-surface p-10 shadow-tnvs-strong">
          <h3 className="text-2xl font-semibold">Probá TNSVT hoy</h3>
          <p className="mx-auto mt-3 max-w-xl text-sm text-tnvs-muted">
            Setup en 5 minutos: creás tu tenant, escaneás tus canales, y el bot empieza a operar.
          </p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <Link
              to="/signup"
              className="rounded-lg bg-tnvs-purple px-5 py-2.5 text-sm font-medium text-white hover:bg-tnvs-purple/90"
            >
              Crear cuenta gratis
            </Link>
            <Link
              to="/login"
              className={cls(
                'rounded-lg border border-tnvs-border px-5 py-2.5 text-sm text-tnvs-muted hover:text-white'
              )}
            >
              Ya tengo cuenta
            </Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-tnvs-border/40 py-6 text-center text-xs text-tnvs-muted">
        © {new Date().getFullYear()} TNSVT · v1.0 demo build
      </footer>
    </div>
  );
}

function Feature({ icon: Icon, title, body }: { icon: React.ComponentType<{ className?: string }>; title: string; body: string }) {
  return (
    <div className="rounded-lg border border-tnvs-border/60 bg-tnvs-surface p-5">
      <div className="grid h-10 w-10 place-items-center rounded-lg bg-tnvs-glow/60">
        <Icon className="h-5 w-5 text-tnvs-purple" />
      </div>
      <h4 className="mt-3 text-sm font-medium text-white">{title}</h4>
      <p className="mt-1 text-xs leading-relaxed text-tnvs-muted">{body}</p>
    </div>
  );
}
