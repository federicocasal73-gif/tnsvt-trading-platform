import { memo, useState } from 'react';
import { useAuth } from '../lib/auth';
import { useApp } from '../state/AppStateProvider';
import { cls } from '../utils/format';

export const SettingsPage = memo(function SettingsPage() {
  const { user } = useAuth();
  const { profile } = useApp();
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(user?.user_id || '');
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* ignore */ }
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
        <h3 className="mb-3 text-sm font-semibold text-white/80">API Access</h3>
        <p className="mb-3 text-xs text-tnvs-muted">Use your JWT token for API authentication.</p>
        <button
          onClick={handleCopy}
          className={cls(
            'rounded-lg border px-4 py-2 text-xs font-medium transition-colors',
            copied
              ? 'border-tnvs-win/40 bg-tnvs-win/10 text-tnvs-win'
              : 'border-tnvs-border bg-tnvs-void text-tnvs-muted hover:border-tnvs-glow/30 hover:text-white',
          )}
        >
          {copied ? 'Copied Token!' : 'Copy JWT Token'}
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
