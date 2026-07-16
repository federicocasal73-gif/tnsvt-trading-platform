import { useState } from 'react';
import { useAuth } from '../lib/auth';
import { cls } from '../utils/format';

export function LoginPage() {
  const { login, loading, error } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    if (!email || !password) { setLocalError('Email and password required'); return; }
    try {
      await login(email, password);
    } catch (err: any) {
      setLocalError(err.message);
    }
  };

  return (
    <div className="flex h-screen w-full items-center justify-center bg-tnvs-radial bg-tnvs-void">
      <div className="w-[400px] rounded-xl border border-tnvs-border bg-tnvs-surface p-8 shadow-tnvs-strong">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-xl bg-tnvs-glow shadow-tnvs-glow">
            <span className="text-2xl font-bold text-white">T</span>
          </div>
          <h1 className="text-xl font-semibold text-white">TNSVT Terminal</h1>
          <p className="mt-1 text-sm text-tnvs-muted">Sign in to your account</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="tnvs-label">Email</label>
            <input className="tnvs-input mt-1" type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" autoFocus />
          </div>
          <div>
            <label className="tnvs-label">Password</label>
            <input className="tnvs-input mt-1" type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" />
          </div>

          {(localError || error) && (
            <div className="rounded-lg border border-tnvs-loss/30 bg-tnvs-loss/10 px-3 py-2 text-sm text-tnvs-loss">
              {localError || error}
            </div>
          )}

          <button type="submit" disabled={loading} className="tnvs-btn-primary w-full">
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        <div className="mt-6 border-t border-tnvs-border pt-4 text-center">
          <p className="text-xs text-tnvs-dim">TNSVT V2 · Terminal Financiera Pro</p>
        </div>
      </div>
    </div>
  );
}
