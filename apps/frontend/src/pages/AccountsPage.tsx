import { useEffect, useState, useCallback } from 'react';
import { Plus, Trash2, Edit2, RefreshCw, Power, X, Eye, EyeOff, Wallet, CheckCircle2, XCircle } from 'lucide-react';
import { api } from '../lib/api';
import { cls, accountColor } from '../utils/format';
import { Card, Page } from '../components/common';

interface AccountRow {
  id: string;
  login: number;
  alias: string | null;
  name: string | null;
  server: string;
  broker: string;
  status: string;
  balance: number | null;
  equity: number | null;
  profit: number | null;
  open_positions: number;
  updated_at: string | null;
  copy_enabled: boolean;
}

interface Aggregate {
  total_balance: number;
  total_equity: number;
  total_pnl: number;
  total_open_positions: number;
  active_accounts: number;
}

const STATUS_BADGE: Record<string, { label: string; cls: string }> = {
  active: { label: 'Activa', cls: 'bg-tnvs-win/15 text-tnvs-win' },
  paused: { label: 'Pausada', cls: 'bg-tnvs-warn/15 text-tnvs-warn' },
  disabled: { label: 'Deshabilitada', cls: 'bg-white/[0.08] text-tnvs-muted' },
  error: { label: 'Error', cls: 'bg-tnvs-loss/15 text-tnvs-loss' },
  connected: { label: 'Conectada', cls: 'bg-tnvs-win/15 text-tnvs-win' },
};

export function AccountsPage() {
  const [accounts, setAccounts] = useState<AccountRow[]>([]);
  const [aggregate, setAggregate] = useState<Aggregate | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [revealedSecrets, setRevealedSecrets] = useState<Record<string, boolean>>({});

  const load = useCallback(async () => {
    try {
      const r = await api.accounts.list();
      setAccounts(r.accounts || []);
      setAggregate(r.aggregate || null);
      setError(null);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 10000);
    return () => clearInterval(id);
  }, [load]);

  const handleDelete = async (id: string) => {
    if (!confirm('¿Eliminar esta cuenta? Esta acción no se puede deshacer.')) return;
    try {
      await api.accounts.delete(id);
      await load();
    } catch (e: any) {
      alert(`Error: ${e.message}`);
    }
  };

  const handleToggleStatus = async (a: AccountRow) => {
    const newStatus = a.status === 'paused' ? 'active' : 'paused';
    try {
      await api.accounts.update(a.id, { status: newStatus });
      await load();
    } catch (e: any) {
      alert(`Error: ${e.message}`);
    }
  };

  const handleToggleCopy = async (a: AccountRow) => {
    try {
      await api.accounts.setCopyEnabled(a.id, !a.copy_enabled);
      await load();
    } catch (e: any) {
      alert(`Error: ${e.message}`);
    }
  };

  return (
    <Page
      title="Cuentas MT5"
      subtitle="Gestión de cuentas MT5 (multi-tenant, credenciales encriptadas AES-GCM)"
      actions={
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={load}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-white/[0.05] hover:bg-white/[0.10] text-xs"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Refrescar
          </button>
          <button
            type="button"
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-tnvs-win/20 hover:bg-tnvs-win/30 text-tnvs-win text-xs font-medium"
          >
            <Plus className="w-3.5 h-3.5" /> Agregar cuenta
          </button>
        </div>
      }
    >
      {error && (
        <div className="mb-4 px-3 py-2 rounded-md bg-tnvs-loss/10 border border-tnvs-loss/30 text-sm text-tnvs-loss">
          Error: {error}
        </div>
      )}

      {/* Aggregates */}
      {aggregate && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
          <AggregateCard label="Balance" value={aggregate.total_balance} prefix="$" color="text-tnvs-base" />
          <AggregateCard label="Equity" value={aggregate.total_equity} prefix="$" color="text-tnvs-base" />
          <AggregateCard label="P&L flotante" value={aggregate.total_pnl} prefix="$" color={aggregate.total_pnl >= 0 ? 'text-tnvs-win' : 'text-tnvs-loss'} />
          <AggregateCard label="Posiciones" value={aggregate.total_open_positions} suffix="" color="text-tnvs-base" />
          <AggregateCard label="Cuentas activas" value={aggregate.active_accounts} suffix="" color="text-tnvs-base" />
        </div>
      )}

      {/* Desglose por cuenta (Sprint 1.6) — un mini-bar por cada cuenta */}
      {accounts.length > 0 && (
        <Card header={<div className="text-sm font-semibold">Desglose por cuenta</div>} className="mb-4">
          <div className="space-y-2">
            {accounts.map((a) => {
              const bal = a.balance || 0;
              const totalBal = aggregate?.total_balance || 0;
              const pct = totalBal > 0 ? (bal / totalBal) * 100 : 0;
              const colorKey = a.id ?? a.login;
              return (
                <div key={a.id ?? a.login} className="flex items-center gap-3">
                  <div
                    className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                    style={{ backgroundColor: accountColor(colorKey) }}
                  />
                  <div className="text-xs w-32 truncate" title={a.alias ?? a.name ?? ''}>
                    {a.alias ?? a.name ?? `acc_${a.login}`}
                  </div>
                  <div className="flex-1 h-3 bg-white/[0.04] rounded overflow-hidden">
                    <div
                      className="h-full rounded transition-all"
                      style={{
                        width: `${pct}%`,
                        backgroundColor: accountColor(colorKey),
                        opacity: 0.7,
                      }}
                    />
                  </div>
                  <div className="text-xs font-mono w-24 text-right">
                    ${bal.toFixed(2)}
                  </div>
                  <div className="text-[10px] text-tnvs-muted w-12 text-right">
                    {pct.toFixed(0)}%
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {/* Tabla de cuentas */}
      <Card header={<div className="text-sm font-semibold">Cuentas configuradas</div>}>
        {loading ? (
          <div className="text-sm text-tnvs-muted">Cargando…</div>
        ) : accounts.length === 0 ? (
          <div className="text-sm text-tnvs-muted py-8 text-center">
            No hay cuentas configuradas. <button onClick={() => setShowAdd(true)} className="text-tnvs-win hover:underline">Agregar la primera</button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-tnvs-muted border-b border-white/[0.06]">
                  <th className="text-left py-2 px-2">Alias</th>
                  <th className="text-left py-2 px-2">Login</th>
                  <th className="text-left py-2 px-2">Server</th>
                  <th className="text-left py-2 px-2">Broker</th>
                  <th className="text-right py-2 px-2">Balance</th>
                  <th className="text-right py-2 px-2">Equity</th>
                  <th className="text-right py-2 px-2">P&L</th>
                  <th className="text-right py-2 px-2">Pos</th>
                  <th className="text-center py-2 px-2">Copy</th>
                  <th className="text-center py-2 px-2">Estado</th>
                  <th className="text-right py-2 px-2">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {accounts.map((a) => {
                  const badge = STATUS_BADGE[a.status] || STATUS_BADGE.disabled;
                  const colorKey = a.id ?? a.login;
                  return (
                    <tr key={a.id ?? a.login} className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                      <td className="py-2 px-2">
                        <div className="flex items-center gap-2">
                          <div
                            className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                            style={{ backgroundColor: accountColor(colorKey) }}
                            title={a.alias ?? `acc_${a.login}`}
                          />
                          <Wallet className="w-3.5 h-3.5 text-tnvs-muted" />
                          <div>
                            <div className="font-medium">{a.alias ?? `acc_${a.login}`}</div>
                            {a.name && a.name !== a.alias && (
                              <div className="text-xs text-tnvs-muted">{a.name}</div>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="py-2 px-2 font-mono text-xs">{a.login}</td>
                      <td className="py-2 px-2 text-xs text-tnvs-muted">{a.server}</td>
                      <td className="py-2 px-2 text-xs">{a.broker}</td>
                      <td className="py-2 px-2 text-right font-mono text-xs">
                        {a.balance != null ? `$${a.balance.toFixed(2)}` : '—'}
                      </td>
                      <td className="py-2 px-2 text-right font-mono text-xs">
                        {a.equity != null ? `$${a.equity.toFixed(2)}` : '—'}
                      </td>
                      <td className={cls(
                        'py-2 px-2 text-right font-mono text-xs',
                        a.profit == null ? 'text-tnvs-muted' : a.profit >= 0 ? 'text-tnvs-win' : 'text-tnvs-loss'
                      )}>
                        {a.profit != null ? `${a.profit >= 0 ? '+' : ''}$${a.profit.toFixed(2)}` : '—'}
                      </td>
                      <td className="py-2 px-2 text-right text-xs">{a.open_positions}</td>
                      <td className="py-2 px-2 text-center">
                        <button
                          type="button"
                          onClick={() => handleToggleCopy(a)}
                          data-testid={`copy-toggle-${a.id}`}
                          className={cls(
                            'inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-medium uppercase tracking-wide border transition-colors',
                            a.copy_enabled
                              ? 'bg-tnvs-win/15 text-tnvs-win border-tnvs-win/40'
                              : 'bg-white/[0.04] text-tnvs-muted border-white/[0.08] hover:border-white/[0.20]',
                          )}
                          title={a.copy_enabled ? 'Desactivar copia' : 'Activar copia'}
                        >
                          {a.copy_enabled ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                          {a.copy_enabled ? 'ON' : 'OFF'}
                        </button>
                      </td>
                      <td className="py-2 px-2 text-center">
                        <span className={cls('px-2 py-0.5 rounded text-[10px] font-medium uppercase tracking-wide', badge.cls)}>
                          {badge.label}
                        </span>
                      </td>
                      <td className="py-2 px-2">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            type="button"
                            onClick={() => setEditingId(a.id)}
                            className="p-1.5 rounded hover:bg-white/[0.08] text-tnvs-muted hover:text-tnvs-base"
                            title="Editar"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleToggleStatus(a)}
                            className={cls(
                              'p-1.5 rounded hover:bg-white/[0.08]',
                              a.status === 'paused' ? 'text-tnvs-win hover:text-tnvs-win' : 'text-tnvs-warn hover:text-tnvs-warn'
                            )}
                            title={a.status === 'paused' ? 'Activar' : 'Pausar'}
                          >
                            <Power className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDelete(a.id)}
                            className="p-1.5 rounded hover:bg-tnvs-loss/20 text-tnvs-muted hover:text-tnvs-loss"
                            title="Eliminar"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {showAdd && (
        <AddAccountModal
          onClose={() => setShowAdd(false)}
          onCreated={() => {
            setShowAdd(false);
            load();
          }}
        />
      )}

      {editingId && (
        <EditAccountModal
          accountId={editingId}
          account={accounts.find((a) => a.id === editingId)!}
          onClose={() => setEditingId(null)}
          onSaved={() => {
            setEditingId(null);
            load();
          }}
        />
      )}
    </Page>
  );
}

function AggregateCard({ label, value, prefix = '', suffix = '', color = 'text-tnvs-base' }: { label: string; value: number; prefix?: string; suffix?: string; color?: string }) {
  return (
    <div className="px-3 py-2.5 rounded-md bg-white/[0.03] border border-white/[0.05]">
      <div className="text-[10px] text-tnvs-muted uppercase tracking-wide">{label}</div>
      <div className={cls('text-lg font-semibold font-mono', color)}>
        {prefix}{value.toFixed(prefix === '$' ? 2 : 0)}{suffix}
      </div>
    </div>
  );
}

function AddAccountModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [server, setServer] = useState('');
  const [alias, setAlias] = useState('');
  const [name, setName] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.accounts.create({
        login: parseInt(login, 10),
        password,
        server,
        alias: alias || undefined,
        name: name || undefined,
      });
      onCreated();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <form onSubmit={submit} className="bg-tnvs-surface border border-white/[0.08] rounded-lg p-6 w-full max-w-md space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold">Agregar cuenta MT5</h3>
          <button type="button" onClick={onClose}><X className="w-4 h-4" /></button>
        </div>
        {error && <div className="px-3 py-2 rounded bg-tnvs-loss/10 text-tnvs-loss text-sm">{error}</div>}
        <Field label="Login (número de cuenta)" required>
          <input type="number" value={login} onChange={(e) => setLogin(e.target.value)} className="w-full px-2 py-1.5 rounded bg-white/[0.05] border border-white/[0.08] text-sm font-mono" required />
        </Field>
        <Field label="Password" required>
          <div className="relative">
            <input
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-2 py-1.5 pr-8 rounded bg-white/[0.05] border border-white/[0.08] text-sm font-mono"
              required
            />
            <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-2 top-1/2 -translate-y-1/2 text-tnvs-muted">
              {showPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
            </button>
          </div>
        </Field>
        <Field label="Server" required>
          <input type="text" value={server} onChange={(e) => setServer(e.target.value)} placeholder="ej: MetaQuotes-Demo" className="w-full px-2 py-1.5 rounded bg-white/[0.05] border border-white/[0.08] text-sm" required />
        </Field>
        <Field label="Alias">
          <input type="text" value={alias} onChange={(e) => setAlias(e.target.value)} placeholder="ej: demo_main" className="w-full px-2 py-1.5 rounded bg-white/[0.05] border border-white/[0.08] text-sm" />
        </Field>
        <Field label="Nombre">
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="ej: Demo Principal" className="w-full px-2 py-1.5 rounded bg-white/[0.05] border border-white/[0.08] text-sm" />
        </Field>
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={onClose} className="px-3 py-1.5 rounded text-xs text-tnvs-muted hover:bg-white/[0.05]">Cancelar</button>
          <button type="submit" disabled={busy} className="px-3 py-1.5 rounded bg-tnvs-win/20 hover:bg-tnvs-win/30 text-tnvs-win text-xs font-medium disabled:opacity-50">
            {busy ? 'Creando…' : 'Crear cuenta'}
          </button>
        </div>
      </form>
    </div>
  );
}

function EditAccountModal({ accountId, account, onClose, onSaved }: { accountId: string; account: AccountRow; onClose: () => void; onSaved: () => void }) {
  const [alias, setAlias] = useState(account.alias || '');
  const [name, setName] = useState(account.name || '');
  const [status, setStatus] = useState<'active' | 'paused' | 'disabled'>(
    (account.status === 'active' || account.status === 'paused' || account.status === 'disabled') ? account.status : 'active'
  );
  const [newPassword, setNewPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [tab, setTab] = useState<'info' | 'password'>('info');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.accounts.update(accountId, { alias, name, status });
      onSaved();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const changePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPassword) { setError('Password vacía'); return; }
    setBusy(true);
    setError(null);
    try {
      await api.accounts.changePassword(accountId, newPassword);
      setNewPassword('');
      alert('Password actualizada');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-tnvs-surface border border-white/[0.08] rounded-lg p-6 w-full max-w-md space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold">Editar cuenta #{account.login}</h3>
          <button type="button" onClick={onClose}><X className="w-4 h-4" /></button>
        </div>
        <div className="flex border-b border-white/[0.08]">
          <button type="button" onClick={() => setTab('info')} className={cls('px-3 py-1.5 text-xs', tab === 'info' ? 'border-b-2 border-tnvs-win text-tnvs-base' : 'text-tnvs-muted')}>
            Info
          </button>
          <button type="button" onClick={() => setTab('password')} className={cls('px-3 py-1.5 text-xs', tab === 'password' ? 'border-b-2 border-tnvs-win text-tnvs-base' : 'text-tnvs-muted')}>
            Cambiar password
          </button>
        </div>
        {error && <div className="px-3 py-2 rounded bg-tnvs-loss/10 text-tnvs-loss text-sm">{error}</div>}
        {tab === 'info' ? (
          <form onSubmit={save} className="space-y-3">
            <Field label="Alias">
              <input type="text" value={alias} onChange={(e) => setAlias(e.target.value)} className="w-full px-2 py-1.5 rounded bg-white/[0.05] border border-white/[0.08] text-sm" />
            </Field>
            <Field label="Nombre">
              <input type="text" value={name} onChange={(e) => setName(e.target.value)} className="w-full px-2 py-1.5 rounded bg-white/[0.05] border border-white/[0.08] text-sm" />
            </Field>
            <Field label="Estado">
              <select value={status} onChange={(e) => setStatus(e.target.value as any)} className="w-full px-2 py-1.5 rounded bg-white/[0.05] border border-white/[0.08] text-sm">
                <option value="active">Activa</option>
                <option value="paused">Pausada</option>
                <option value="disabled">Deshabilitada</option>
              </select>
            </Field>
            <div className="text-xs text-tnvs-muted">Server: {account.server} · Broker: {account.broker} (no editables)</div>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={onClose} className="px-3 py-1.5 rounded text-xs text-tnvs-muted hover:bg-white/[0.05]">Cancelar</button>
              <button type="submit" disabled={busy} className="px-3 py-1.5 rounded bg-tnvs-win/20 hover:bg-tnvs-win/30 text-tnvs-win text-xs font-medium disabled:opacity-50">
                {busy ? 'Guardando…' : 'Guardar'}
              </button>
            </div>
          </form>
        ) : (
          <form onSubmit={changePassword} className="space-y-3">
            <Field label="Nueva password">
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full px-2 py-1.5 pr-8 rounded bg-white/[0.05] border border-white/[0.08] text-sm font-mono"
                />
                <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-2 top-1/2 -translate-y-1/2 text-tnvs-muted">
                  {showPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                </button>
              </div>
            </Field>
            <div className="text-xs text-tnvs-muted">
              Se re-encriptará con AES-GCM. El bridge-api, mt5-connector y signal_copier podrán obtener la password descifrada vía service-to-service token.
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={onClose} className="px-3 py-1.5 rounded text-xs text-tnvs-muted hover:bg-white/[0.05]">Cancelar</button>
              <button type="submit" disabled={busy} className="px-3 py-1.5 rounded bg-tnvs-warn/20 hover:bg-tnvs-warn/30 text-tnvs-warn text-xs font-medium disabled:opacity-50">
                {busy ? 'Cambiando…' : 'Cambiar password'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-xs text-tnvs-muted block mb-1">
        {label}{required && <span className="text-tnvs-loss ml-0.5">*</span>}
      </span>
      {children}
    </label>
  );
}
