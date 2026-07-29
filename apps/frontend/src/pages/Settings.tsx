import { memo, useState } from 'react';
import { useAuth } from '../lib/auth';
import { useApp } from '../state/AppStateProvider';
import { api } from '../lib/api';
import { cls } from '../utils/format';

export const SettingsPage = memo(function SettingsPage() {
  const { user, refreshProfile } = useAuth();
  const { profile } = useApp();
  const [copied, setCopied] = useState(false);
  const [showPwd, setShowPwd] = useState(false);
  const [currentPwd, setCurrentPwd] = useState('');
  const [newPwd, setNewPwd] = useState('');
  const [pwdError, setPwdError] = useState<string | null>(null);
  const [pwdSuccess, setPwdSuccess] = useState<string | null>(null);
  const [pwdBusy, setPwdBusy] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(user?.user_id || '');
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* ignore */ }
  };

  const handleChangePassword = async () => {
    setPwdError(null);
    setPwdSuccess(null);
    if (newPwd.length < 12) {
      setPwdError('La contraseña nueva debe tener 12+ chars con mayúscula, minúscula y número.');
      return;
    }
    setPwdBusy(true);
    try {
      await api.auth.changePassword(currentPwd, newPwd);
      setPwdSuccess('Contraseña cambiada. Iniciá sesión nuevamente.');
      setCurrentPwd('');
      setNewPwd('');
      setShowPwd(false);
      // Forzar re-login para renovar tokens
      setTimeout(() => {
        localStorage.removeItem('tnsvt_token');
        localStorage.removeItem('tnsvt_refresh');
        window.location.href = '/login';
      }, 1500);
    } catch (e: any) {
      const msg = String(e?.message || '');
      if (msg.includes('401') || msg.toLowerCase().includes('current password')) {
        setPwdError('La contraseña actual es incorrecta.');
      } else if (msg.toLowerCase().includes('weak')) {
        setPwdError('La contraseña nueva no cumple las reglas de seguridad.');
      } else {
        setPwdError(msg || 'No se pudo cambiar la contraseña.');
      }
    } finally {
      setPwdBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h2 className="text-lg font-semibold text-white">Settings</h2>

      <div className="tnvs-card space-y-4">
        <h3 className="text-sm font-semibold text-white/80">Account</h3>
        <Row label="User ID"><span className="font-mono text-xs text-tnvs-muted">{user?.user_id}</span></Row>
        <Row label="Email"><span className="text-sm text-white">{user?.email}</span></Row>
        <Row label="Username"><span className="text-sm text-white">{user?.username}</span></Row>
        <Row label="Role"><span className="text-xs font-medium text-tnvs-dim uppercase">{user?.role}</span></Row>
        <Row label="Tenant ID"><span className="font-mono text-xs text-tnvs-muted">{user?.tenant_id}</span></Row>
        {profile && (
          <>
            <Row label="Full Name"><span className="text-sm text-white">{profile.full_name}</span></Row>
            <Row label="Timezone"><span className="text-sm text-white">{profile.timezone}</span></Row>
            <Row label="Language"><span className="text-sm text-white">{profile.language}</span></Row>
          </>
        )}
      </div>

      <div className="tnvs-card">
        <h3 className="mb-3 text-sm font-semibold text-white/80">Cambiar contraseña</h3>
        {!showPwd ? (
          <button
            onClick={() => setShowPwd(true)}
            className="rounded-lg border border-tnvs-border bg-tnvs-void px-4 py-2 text-xs font-medium text-tnvs-muted hover:border-tnvs-glow/30 hover:text-white"
          >
            Cambiar contraseña
          </button>
        ) : (
          <div className="space-y-3">
            <div>
              <label className="tnvs-label" htmlFor="current-pwd">Contraseña actual</label>
              <input
                id="current-pwd"
                className="tnvs-input mt-1"
                type="password"
                value={currentPwd}
                onChange={e => setCurrentPwd(e.target.value)}
                autoFocus
              />
            </div>
            <div>
              <label className="tnvs-label" htmlFor="new-pwd">Nueva contraseña</label>
              <input
                id="new-pwd"
                className="tnvs-input mt-1"
                type="password"
                value={newPwd}
                onChange={e => setNewPwd(e.target.value)}
                placeholder="Mínimo 12 chars, mayúscula, minúscula y número"
              />
            </div>
            {pwdError && (
              <div className="rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
                {pwdError}
              </div>
            )}
            {pwdSuccess && (
              <div className="rounded border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-300">
                {pwdSuccess}
              </div>
            )}
            <div className="flex gap-2">
              <button
                onClick={handleChangePassword}
                disabled={pwdBusy || !currentPwd || !newPwd}
                className="rounded-lg bg-tnvs-purple px-4 py-2 text-xs font-medium text-white hover:bg-tnvs-purple/90 disabled:opacity-50"
              >
                {pwdBusy ? 'Cambiando…' : 'Cambiar'}
              </button>
              <button
                onClick={() => { setShowPwd(false); setCurrentPwd(''); setNewPwd(''); setPwdError(null); }}
                className="rounded-lg border border-tnvs-border bg-tnvs-void px-4 py-2 text-xs text-tnvs-muted hover:text-white"
              >
                Cancelar
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="tnvs-card">
        <h3 className="mb-3 text-sm font-semibold text-white/80">API Access</h3>
        <p className="mb-3 text-xs text-tnvs-muted">Usa tu JWT token para autenticación API.</p>
        <button
          onClick={handleCopy}
          className={cls(
            'rounded-lg border px-4 py-2 text-xs font-medium transition-colors',
            copied
              ? 'border-tnvs-win/40 bg-tnvs-win/10 text-tnvs-win'
              : 'border-tnvs-border bg-tnvs-void text-tnvs-muted hover:border-tnvs-glow/30 hover:text-white',
          )}
        >
          {copied ? '¡Token copiado!' : 'Copiar JWT Token'}
        </button>
        <button
          onClick={refreshProfile}
          className="ml-2 rounded-lg border border-tnvs-border bg-tnvs-void px-4 py-2 text-xs text-tnvs-muted hover:text-white"
        >
          Refrescar perfil
        </button>
      </div>
    </div>
  );
});

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-tnvs-border/50 pb-2 last:border-0">
      <span className="text-xs text-tnvs-muted">{label}</span>
      <div>{children}</div>
    </div>
  );
}