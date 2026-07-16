import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../lib/auth';

export function LoginPage() {
  const { login, loading, error, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);

  // If we already have a valid token, skip the login form.
  useEffect(() => {
    if (isAuthenticated) navigate('/', { replace: true });
  }, [isAuthenticated, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    if (!email || !password) {
      setLocalError('Email and password required');
      return;
    }
    try {
      await login(email, password);
      navigate('/', { replace: true });
    } catch (err: any) {
      setLocalError(err.message);
    }
  };

  return (
    <div className="flex h-screen w-full items-center justify-center bg-tnvs-radial bg-tnvs-void">
      <div
        data-testid="login-card"
        className="w-[400px] rounded-xl border border-tnvs-border bg-tnvs-surface p-8 shadow-tnvs-strong"
      >
        <div className="mb-6 text-center">
          <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-xl bg-tnvs-glow shadow-tnvs-glow">
            <span className="text-2xl font-bold text-white">T</span>
          </div>
          <h1 className="text-xl font-semibold text-white">TNSVT Terminal</h1>
          <p className="mt-1 text-sm text-tnvs-muted">Sign in to your account</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="tnvs-label" htmlFor="login-email">Email</label>
            <input
              id="login-email"
              data-testid="login-email"
              className="tnvs-input mt-1"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoFocus
            />
          </div>
          <div>
            <label className="tnvs-label" htmlFor="login-password">Password</label>
            <input
              id="login-password"
              data-testid="login-password"
              className="tnvs-input mt-1"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>

          {(localError || error) && (
            <div
              data-testid="login-error"
              className="rounded-lg border border-tnvs-loss/30 bg-tnvs-loss/10 px-3 py-2 text-sm text-tnvs-loss"
            >
              {localError || error}
            </div>
          )}

          <button
            type="submit"
            data-testid="login-submit"
            disabled={loading}
            className="tnvs-btn-primary w-full"
          >
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