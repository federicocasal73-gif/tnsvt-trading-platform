import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { CheckCircle2, ChevronRight, ChevronLeft, Loader2 } from 'lucide-react';
import { cls } from '../utils/format';

type Step = 1 | 2 | 3;

interface FormData {
  email: string;
  password: string;
  full_name: string;
  tenant_name: string;
  slug: string;
}

const DEFAULTS: FormData = {
  email: '',
  password: '',
  full_name: '',
  tenant_name: '',
  slug: '',
};

export function SignupWizard() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>(1);
  const [data, setData] = useState<FormData>(DEFAULTS);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const update = (patch: Partial<FormData>) => setData(d => ({ ...d, ...patch }));

  const next = () => {
    setError(null);
    if (step === 1) {
      if (!data.email.includes('@') || data.password.length < 8) {
        setError('Email válido y contraseña con 8+ caracteres requeridos.');
        return;
      }
    }
    if (step === 2) {
      if (!data.tenant_name.trim()) {
        setError('Elegí un nombre para tu tenant.');
        return;
      }
      const slug = data.slug || data.tenant_name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      if (!/^[a-z0-9-]{3,30}$/.test(slug)) {
        setError('Slug debe tener 3-30 chars, solo a-z, 0-9 y guiones.');
        return;
      }
      update({ slug });
    }
    setStep((s) => Math.min(3, (s + 1)) as Step);
  };

  const back = () => setStep((s) => Math.max(1, (s - 1)) as Step);

  const submit = async () => {
    setError(null);
    setSubmitting(true);
    try {
      // El backend real register multi-tenant no existe aún (vía auth-service
      // Go). En demo, simula 1.5s y manda a /login con un mensaje.
      await new Promise(r => setTimeout(r, 1500));
      navigate('/login?welcome=1', { replace: true });
    } catch (e: any) {
      setError(e.message || 'No se pudo crear la cuenta.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-tnvs-radial bg-tnvs-void px-4 py-10">
      <div className="w-full max-w-md rounded-2xl border border-tnvs-border bg-tnvs-surface p-8 shadow-tnvs-strong">
        <StepIndicator step={step} />

        <div className="mt-6 space-y-4">
          {step === 1 && (
            <>
              <h2 className="text-lg font-semibold text-white">Tu cuenta</h2>
              <Field label="Email">
                <input
                  className="tnvs-input"
                  type="email"
                  value={data.email}
                  onChange={e => update({ email: e.target.value })}
                  placeholder="vos@ejemplo.com"
                  autoFocus
                />
              </Field>
              <Field label="Contraseña" hint="Mínimo 8 caracteres">
                <input
                  className="tnvs-input"
                  type="password"
                  value={data.password}
                  onChange={e => update({ password: e.target.value })}
                  placeholder="••••••••"
                />
              </Field>
              <Field label="Nombre completo" hint="Opcional">
                <input
                  className="tnvs-input"
                  type="text"
                  value={data.full_name}
                  onChange={e => update({ full_name: e.target.value })}
                  placeholder="Juan Pérez"
                />
              </Field>
            </>
          )}

          {step === 2 && (
            <>
              <h2 className="text-lg font-semibold text-white">Tu workspace</h2>
              <Field label="Nombre del tenant">
                <input
                  className="tnvs-input"
                  type="text"
                  value={data.tenant_name}
                  onChange={e => update({ tenant_name: e.target.value, slug: '' })}
                  placeholder="Trading Hub"
                  autoFocus
                />
              </Field>
              <Field label="URL slug" hint={data.slug ? `${data.slug}.tnsvt.app` : 'Generado del nombre'}>
                <input
                  className="tnvs-input font-mono"
                  type="text"
                  value={data.slug}
                  onChange={e => update({ slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '') })}
                  placeholder="trading-hub"
                />
              </Field>
            </>
          )}

          {step === 3 && (
            <>
              <div className="flex flex-col items-center text-center">
                <div className="grid h-12 w-12 place-items-center rounded-full bg-tnvs-win/15">
                  <CheckCircle2 className="h-6 w-6 text-tnvs-win" />
                </div>
                <h2 className="mt-4 text-lg font-semibold text-white">Todo listo</h2>
                <p className="mt-2 text-sm text-tnvs-muted">
                  Vas a crear una cuenta con email <span className="font-mono text-white">{data.email}</span> y
                  el tenant <span className="font-mono text-white">{data.slug || data.tenant_name}</span>.
                </p>
              </div>
              <SummaryRow label="Email" value={data.email} />
              <SummaryRow label="Tenant" value={data.tenant_name} mono />
              <SummaryRow label="Slug" value={data.slug || data.tenant_name.toLowerCase()} mono />
            </>
          )}

          {error && (
            <div className="rounded-md border border-tnvs-loss/30 bg-tnvs-loss/10 px-3 py-2 text-xs text-tnvs-loss">
              {error}
            </div>
          )}
        </div>

        <div className="mt-6 flex items-center justify-between">
          <button
            onClick={back}
            disabled={step === 1 || submitting}
            className="inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-xs text-tnvs-muted hover:text-white disabled:opacity-40"
          >
            <ChevronLeft className="h-3.5 w-3.5" /> Atrás
          </button>
          {step < 3 ? (
            <button
              onClick={next}
              className="inline-flex items-center gap-1 rounded-md bg-tnvs-purple px-4 py-1.5 text-sm font-medium text-white hover:bg-tnvs-purple/90"
            >
              Siguiente <ChevronRight className="h-3.5 w-3.5" />
            </button>
          ) : (
            <button
              onClick={submit}
              disabled={submitting}
              className="inline-flex items-center gap-1 rounded-md bg-tnvs-win px-4 py-1.5 text-sm font-medium text-tnvs-void hover:bg-tnvs-win/90 disabled:opacity-50"
            >
              {submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
              {submitting ? 'Creando…' : 'Crear cuenta'}
            </button>
          )}
        </div>

        <div className="mt-6 border-t border-tnvs-border/40 pt-4 text-center text-xs text-tnvs-muted">
          ¿Ya tenés cuenta?{' '}
          <Link to="/login" className="text-tnvs-purple hover:underline">
            Iniciar sesión
          </Link>
        </div>
      </div>
    </div>
  );
}

function StepIndicator({ step }: { step: Step }) {
  const steps = ['Cuenta', 'Workspace', 'Confirmar'] as const;
  return (
    <div className="flex items-center gap-2">
      {steps.map((label, i) => {
        const idx = i + 1;
        const active = idx === step;
        const done = idx < step;
        return (
          <div key={label} className="flex flex-1 items-center gap-2">
            <div
              className={cls(
                'grid h-6 w-6 place-items-center rounded-full text-[10px] font-medium',
                done && 'bg-tnvs-win text-tnvs-void',
                active && 'bg-tnvs-purple text-white',
                !done && !active && 'bg-tnvs-void text-tnvs-muted',
              )}
            >
              {done ? <CheckCircle2 className="h-3.5 w-3.5" /> : idx}
            </div>
            <span className={cls('text-[11px]', active ? 'text-white' : 'text-tnvs-muted')}>
              {label}
            </span>
            {i < steps.length - 1 && (
              <div className={cls('h-px flex-1', done ? 'bg-tnvs-win/40' : 'bg-tnvs-border/60')} />
            )}
          </div>
        );
      })}
    </div>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="tnvs-label">{label}</label>
      {children}
      {hint && <p className="mt-1 text-[10px] text-tnvs-dim">{hint}</p>}
    </div>
  );
}

function SummaryRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between rounded-md bg-tnvs-void px-3 py-2 text-sm">
      <span className="text-tnvs-muted">{label}</span>
      <span className={cls('text-white', mono && 'font-mono text-xs')}>{value}</span>
    </div>
  );
}
