import { useEffect, useState, useCallback } from 'react';
import { Plus, Trash2, Edit2, RefreshCw, Users, Briefcase, Activity, ChevronRight, Copy, Power, XCircle, CheckCircle2 } from 'lucide-react';
import { api } from '../lib/api';
import { cls } from '../utils/format';
import { Card, Page } from '../components/common';

type Tab = 'replicators' | 'groups' | 'accounts' | 'jobs' | 'stats';

export function CopyTradingPage() {
  const [tab, setTab] = useState<Tab>('replicators');
  const [groups, setGroups] = useState<any[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);
  const [stats, setStats] = useState<any | null>(null);
  const [replicators, setReplicators] = useState<any[]>([]);
  const [replicatorLive, setReplicatorLive] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showGroupModal, setShowGroupModal] = useState(false);
  const [editingGroup, setEditingGroup] = useState<any | null>(null);
  const [showAccountModal, setShowAccountModal] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const g = await api.copy.listGroups();
      setGroups(g.groups || []);
      if (!selectedGroupId && g.groups && g.groups.length > 0) {
        setSelectedGroupId(g.groups[0].id);
      }
      if (selectedGroupId) {
        const a = await api.copy.listAccounts(selectedGroupId);
        setAccounts(a.accounts || []);
      } else {
        setAccounts([]);
      }
      if (tab === 'replicators') {
        try {
          const r = await api.accounts.listReplicators();
          setReplicators(r.accounts || []);
          try {
            const live = await api.bridgeReplicators.list();
            const map: Record<string, any> = {};
            for (const a of (live as any).accounts || []) map[a.login] = a;
            setReplicatorLive(map);
          } catch {
            // bridge no responde, seguimos sin live data
          }
        } catch (e: any) {
          setError(e.message);
        }
      }
      if (tab === 'jobs') {
        const j = await api.copy.listJobs(50);
        setJobs(j.jobs || []);
      }
      if (tab === 'stats') {
        const s = await api.copy.getStats();
        setStats(s);
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [selectedGroupId, tab]);

  useEffect(() => { load(); }, [load]);

  const toggleCopy = async (a: any) => {
    try {
      await api.accounts.setCopyEnabled(a.id, !a.copy_enabled);
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  };

  return (
    <Page
      title="Copy Trading"
      subtitle="Grupos, cuentas destino, jobs y estadísticas (Go service :8005)"
      actions={
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={load}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-white/[0.05] hover:bg-white/[0.10] text-xs disabled:opacity-50"
          >
            <RefreshCw className={cls('w-3.5 h-3.5', loading && 'animate-spin')} /> Refrescar
          </button>
          {tab === 'groups' && (
            <button
              type="button"
              onClick={() => { setEditingGroup(null); setShowGroupModal(true); }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-tnvs-win/20 hover:bg-tnvs-win/30 text-tnvs-win text-xs font-medium"
            >
              <Plus className="w-3.5 h-3.5" /> Nuevo grupo
            </button>
          )}
          {tab === 'accounts' && selectedGroupId && (
            <button
              type="button"
              onClick={() => setShowAccountModal(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-tnvs-win/20 hover:bg-tnvs-win/30 text-tnvs-win text-xs font-medium"
            >
              <Plus className="w-3.5 h-3.5" /> Agregar cuenta
            </button>
          )}
        </div>
      }
    >
      {error && (
        <div className="mb-4 px-3 py-2 rounded-md bg-tnvs-loss/10 border border-tnvs-loss/30 text-sm text-tnvs-loss">
          Error: {error}
        </div>
      )}

      <div className="flex border-b border-white/[0.08] mb-4">
        {(['replicators', 'groups', 'accounts', 'jobs', 'stats'] as Tab[]).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={cls(
              'px-4 py-2 text-xs uppercase tracking-wider',
              tab === t ? 'border-b-2 border-tnvs-win text-tnvs-base' : 'text-tnvs-muted hover:text-tnvs-base'
            )}
          >
            {t === 'replicators' && <><Copy className="inline w-3.5 h-3.5 mr-1.5" />Replicators</>}
            {t === 'groups' && <><Users className="inline w-3.5 h-3.5 mr-1.5" />Grupos (avanzado)</>}
            {t === 'accounts' && <><Briefcase className="inline w-3.5 h-3.5 mr-1.5" />Cuentas (avanzado)</>}
            {t === 'jobs' && <><Activity className="inline w-3.5 h-3.5 mr-1.5" />Jobs</>}
            {t === 'stats' && <><Activity className="inline w-3.5 h-3.5 mr-1.5" />Estadísticas</>}
          </button>
        ))}
      </div>

      {tab === 'replicators' && (
        <ReplicatorsTab
          replicators={replicators}
          live={replicatorLive}
          onToggle={toggleCopy}
        />
      )}

      {tab === 'groups' && (
        <GroupsTab
          groups={groups}
          onEdit={(g) => { setEditingGroup(g); setShowGroupModal(true); }}
          onDelete={async (id) => {
            if (!confirm('¿Eliminar este grupo?')) return;
            await api.copy.deleteGroup(id);
            await load();
          }}
          onSelect={(id) => { setSelectedGroupId(id); setTab('accounts'); }}
        />
      )}

      {tab === 'accounts' && (
        <AccountsTab
          groupId={selectedGroupId}
          groups={groups}
          accounts={accounts}
          onSelectGroup={setSelectedGroupId}
        />
      )}

      {tab === 'jobs' && <JobsTab jobs={jobs} />}

      {tab === 'stats' && <StatsTab stats={stats} />}

      {showGroupModal && (
        <GroupModal
          group={editingGroup}
          onClose={() => { setShowGroupModal(false); setEditingGroup(null); }}
          onSaved={() => { setShowGroupModal(false); setEditingGroup(null); load(); }}
        />
      )}

      {showAccountModal && selectedGroupId && (
        <AccountModal
          groupId={selectedGroupId}
          onClose={() => setShowAccountModal(false)}
          onSaved={() => { setShowAccountModal(false); load(); }}
        />
      )}
    </Page>
  );
}

function GroupsTab({ groups, onEdit, onDelete, onSelect }: { groups: any[]; onEdit: (g: any) => void; onDelete: (id: string) => void; onSelect: (id: string) => void }) {
  if (groups.length === 0) {
    return (
      <Card>
        <div className="text-sm text-tnvs-muted py-8 text-center">
          No hay grupos. Creá uno con el botón "Nuevo grupo".
        </div>
      </Card>
    );
  }
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {groups.map((g) => (
        <Card key={g.id}>
          <div className="flex items-start justify-between mb-2">
            <div>
              <div className="font-semibold">{g.name}</div>
              {g.description && <div className="text-xs text-tnvs-muted mt-1">{g.description}</div>}
            </div>
            <div className="flex items-center gap-1">
              <button onClick={() => onEdit(g)} className="p-1.5 rounded hover:bg-white/[0.08] text-tnvs-muted hover:text-tnvs-base" title="Editar">
                <Edit2 className="w-3.5 h-3.5" />
              </button>
              <button onClick={() => onDelete(g.id)} className="p-1.5 rounded hover:bg-tnvs-loss/20 text-tnvs-muted hover:text-tnvs-loss" title="Eliminar">
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
          <div className="flex items-center gap-4 text-xs text-tnvs-muted">
            <span>Cuentas: <span className="text-tnvs-base font-mono">{g.total_accounts || 0}</span></span>
            <span>Success: <span className="text-tnvs-base font-mono">{(g.success_rate || 0).toFixed(1)}%</span></span>
          </div>
          <button
            onClick={() => onSelect(g.id)}
            className="mt-3 flex items-center gap-1 text-xs text-tnvs-win hover:underline"
          >
            Ver cuentas <ChevronRight className="w-3 h-3" />
          </button>
        </Card>
      ))}
    </div>
  );
}

function AccountsTab({ groupId, groups, accounts, onSelectGroup }: { groupId: string | null; groups: any[]; accounts: any[]; onSelectGroup: (id: string) => void }) {
  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <span className="text-xs text-tnvs-muted">Grupo:</span>
        <select
          value={groupId || ''}
          onChange={(e) => onSelectGroup(e.target.value)}
          className="px-2 py-1.5 rounded bg-white/[0.05] border border-white/[0.08] text-sm"
        >
          {groups.length === 0 ? (
            <option value="">— sin grupos —</option>
          ) : groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
        </select>
      </div>
      {!groupId ? (
        <Card><div className="text-sm text-tnvs-muted py-4 text-center">Seleccioná un grupo para ver sus cuentas.</div></Card>
      ) : accounts.length === 0 ? (
        <Card><div className="text-sm text-tnvs-muted py-4 text-center">Este grupo no tiene cuentas todavía.</div></Card>
      ) : (
        <Card>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-tnvs-muted border-b border-white/[0.06]">
                <th className="text-left py-2 px-2">Nombre</th>
                <th className="text-left py-2 px-2">Login</th>
                <th className="text-left py-2 px-2">Broker</th>
                <th className="text-left py-2 px-2">Lot mode</th>
                <th className="text-right py-2 px-2">Lot</th>
                <th className="text-right py-2 px-2">Mult</th>
                <th className="text-right py-2 px-2">Risk%</th>
                <th className="text-center py-2 px-2">Invertir</th>
                <th className="text-center py-2 px-2">Activa</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((a) => (
                <tr key={a.id} className="border-b border-white/[0.04]">
                  <td className="py-2 px-2 font-medium">{a.name}</td>
                  <td className="py-2 px-2 font-mono text-xs">{a.account_id}</td>
                  <td className="py-2 px-2 text-xs">{a.broker}</td>
                  <td className="py-2 px-2 text-xs">{a.lot_mode}</td>
                  <td className="py-2 px-2 text-right font-mono text-xs">{a.lot_size}</td>
                  <td className="py-2 px-2 text-right font-mono text-xs">{a.lot_multiplier}</td>
                  <td className="py-2 px-2 text-right font-mono text-xs">{a.risk_percent}</td>
                  <td className="py-2 px-2 text-center">{a.invert_side ? '🔄' : '—'}</td>
                  <td className="py-2 px-2 text-center">
                    <span className={cls('px-2 py-0.5 rounded text-[10px] uppercase', a.enabled ? 'bg-tnvs-win/15 text-tnvs-win' : 'bg-white/[0.08] text-tnvs-muted')}>
                      {a.enabled ? 'Sí' : 'No'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}

function JobsTab({ jobs }: { jobs: any[] }) {
  if (jobs.length === 0) {
    return <Card><div className="text-sm text-tnvs-muted py-8 text-center">Sin jobs todavía.</div></Card>;
  }
  return (
    <Card>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-tnvs-muted border-b border-white/[0.06]">
            <th className="text-left py-2 px-2">Signal</th>
            <th className="text-left py-2 px-2">Symbol</th>
            <th className="text-left py-2 px-2">Action</th>
            <th className="text-left py-2 px-2">Account</th>
            <th className="text-right py-2 px-2">Lot</th>
            <th className="text-center py-2 px-2">Status</th>
            <th className="text-left py-2 px-2">Created</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((j) => (
            <tr key={j.id} className="border-b border-white/[0.04]">
              <td className="py-2 px-2 font-mono text-xs">{j.signal_id?.substring(0, 8) || '—'}</td>
              <td className="py-2 px-2 font-medium">{j.symbol || j.applied_symbol}</td>
              <td className="py-2 px-2 text-xs">{j.action || j.applied_side}</td>
              <td className="py-2 px-2 font-mono text-xs">{j.account_id?.substring(0, 8) || '—'}</td>
              <td className="py-2 px-2 text-right font-mono text-xs">{j.applied_lot_size}</td>
              <td className="py-2 px-2 text-center">
                <span className={cls('px-2 py-0.5 rounded text-[10px] uppercase', j.status === 'success' ? 'bg-tnvs-win/15 text-tnvs-win' : j.status === 'failed' ? 'bg-tnvs-loss/15 text-tnvs-loss' : 'bg-white/[0.08] text-tnvs-muted')}>
                  {j.status}
                </span>
              </td>
              <td className="py-2 px-2 text-xs text-tnvs-muted">{j.created_at ? new Date(j.created_at).toLocaleString() : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

function StatsTab({ stats }: { stats: any }) {
  if (!stats) return <Card><div className="text-sm text-tnvs-muted py-8 text-center">Cargando…</div></Card>;
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      <StatBox label="Total jobs" value={stats.total_jobs || 0} />
      <StatBox label="Exitosos" value={stats.successful_jobs || 0} color="text-tnvs-win" />
      <StatBox label="Fallidos" value={stats.failed_jobs || 0} color="text-tnvs-loss" />
      <StatBox label="Success rate" value={`${(stats.success_rate || 0).toFixed(1)}%`} color="text-tnvs-base" />
    </div>
  );
}

function StatBox({ label, value, color = 'text-tnvs-base' }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="px-3 py-3 rounded-md bg-white/[0.03] border border-white/[0.05]">
      <div className="text-[10px] text-tnvs-muted uppercase tracking-wide">{label}</div>
      <div className={cls('text-2xl font-semibold font-mono', color)}>{value}</div>
    </div>
  );
}

function GroupModal({ group, onClose, onSaved }: { group: any | null; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState(group?.name || '');
  const [description, setDescription] = useState(group?.description || '');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      if (group) {
        await api.copy.updateGroup(group.id, { name, description });
      } else {
        await api.copy.createGroup({ name, description });
      }
      onSaved();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <form onSubmit={submit} className="bg-tnvs-surface border border-white/[0.08] rounded-lg p-6 w-full max-w-md space-y-3">
        <h3 className="text-lg font-semibold">{group ? 'Editar grupo' : 'Nuevo grupo'}</h3>
        {err && <div className="px-3 py-2 rounded bg-tnvs-loss/10 text-tnvs-loss text-sm">{err}</div>}
        <label className="block">
          <span className="text-xs text-tnvs-muted block mb-1">Nombre *</span>
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} className="w-full px-2 py-1.5 rounded bg-white/[0.05] border border-white/[0.08] text-sm" required />
        </label>
        <label className="block">
          <span className="text-xs text-tnvs-muted block mb-1">Descripción</span>
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} className="w-full px-2 py-1.5 rounded bg-white/[0.05] border border-white/[0.08] text-sm" />
        </label>
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={onClose} className="px-3 py-1.5 rounded text-xs text-tnvs-muted hover:bg-white/[0.05]">Cancelar</button>
          <button type="submit" disabled={busy} className="px-3 py-1.5 rounded bg-tnvs-win/20 hover:bg-tnvs-win/30 text-tnvs-win text-xs font-medium disabled:opacity-50">
            {busy ? 'Guardando…' : 'Guardar'}
          </button>
        </div>
      </form>
    </div>
  );
}

function AccountModal({ groupId, onClose, onSaved }: { groupId: string; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState('');
  const [accountId, setAccountId] = useState('');
  const [broker, setBroker] = useState('mt5');
  const [lotMode, setLotMode] = useState<'fixed' | 'proportional' | 'risk_based'>('fixed');
  const [lotSize, setLotSize] = useState('0.01');
  const [lotMult, setLotMult] = useState('1.0');
  const [riskPct, setRiskPct] = useState('1.0');
  const [invert, setInvert] = useState(false);
  const [enabled, setEnabled] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await api.copy.createAccount(groupId, {
        name,
        account_id: accountId,
        broker,
        lot_mode: lotMode,
        lot_size: parseFloat(lotSize),
        lot_multiplier: parseFloat(lotMult),
        risk_percent: parseFloat(riskPct),
        invert_side: invert,
        enabled,
      });
      onSaved();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <form onSubmit={submit} className="bg-tnvs-surface border border-white/[0.08] rounded-lg p-6 w-full max-w-md space-y-3 max-h-[90vh] overflow-y-auto">
        <h3 className="text-lg font-semibold">Agregar cuenta al grupo</h3>
        {err && <div className="px-3 py-2 rounded bg-tnvs-loss/10 text-tnvs-loss text-sm">{err}</div>}
        <Field label="Nombre *" >
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} required className="w-full px-2 py-1.5 rounded bg-white/[0.05] border border-white/[0.08] text-sm" />
        </Field>
        <Field label="MT5 Login *">
          <input type="text" value={accountId} onChange={(e) => setAccountId(e.target.value)} required className="w-full px-2 py-1.5 rounded bg-white/[0.05] border border-white/[0.08] text-sm font-mono" />
        </Field>
        <Field label="Broker">
          <select value={broker} onChange={(e) => setBroker(e.target.value)} className="w-full px-2 py-1.5 rounded bg-white/[0.05] border border-white/[0.08] text-sm">
            <option value="mt5">mt5</option>
            <option value="ctrader">ctrader</option>
          </select>
        </Field>
        <Field label="Lot mode">
          <select value={lotMode} onChange={(e) => setLotMode(e.target.value as any)} className="w-full px-2 py-1.5 rounded bg-white/[0.05] border border-white/[0.08] text-sm">
            <option value="fixed">fixed</option>
            <option value="proportional">proportional</option>
            <option value="risk_based">risk_based</option>
          </select>
        </Field>
        <div className="grid grid-cols-3 gap-2">
          <Field label="Lot size"><input type="number" step="0.01" value={lotSize} onChange={(e) => setLotSize(e.target.value)} className="w-full px-2 py-1.5 rounded bg-white/[0.05] border border-white/[0.08] text-sm font-mono" /></Field>
          <Field label="Multiplier"><input type="number" step="0.1" value={lotMult} onChange={(e) => setLotMult(e.target.value)} className="w-full px-2 py-1.5 rounded bg-white/[0.05] border border-white/[0.08] text-sm font-mono" /></Field>
          <Field label="Risk %"><input type="number" step="0.1" value={riskPct} onChange={(e) => setRiskPct(e.target.value)} className="w-full px-2 py-1.5 rounded bg-white/[0.05] border border-white/[0.08] text-sm font-mono" /></Field>
        </div>
        <div className="flex gap-3 text-xs">
          <label className="flex items-center gap-1.5"><input type="checkbox" checked={invert} onChange={(e) => setInvert(e.target.checked)} /> Invertir side</label>
          <label className="flex items-center gap-1.5"><input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} /> Activa</label>
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={onClose} className="px-3 py-1.5 rounded text-xs text-tnvs-muted hover:bg-white/[0.05]">Cancelar</button>
          <button type="submit" disabled={busy} className="px-3 py-1.5 rounded bg-tnvs-win/20 hover:bg-tnvs-win/30 text-tnvs-win text-xs font-medium disabled:opacity-50">
            {busy ? 'Creando…' : 'Crear'}
          </button>
        </div>
      </form>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-xs text-tnvs-muted block mb-1">{label}</span>
      {children}
    </label>
  );
}

function ReplicatorsTab({ replicators, live, onToggle }: { replicators: any[]; live: Record<string, any>; onToggle: (a: any) => Promise<void> }) {
  return (
    <Card header={
      <div>
        <div className="text-sm font-medium">Replicators (cuentas con copy_enabled=true)</div>
        <div className="text-xs text-tnvs-muted mt-0.5">Modo basico: solo las cuentas marcadas aqui replican las senales del EA. Para filtros avanzados y grupos, usa el tab 'Grupos'.</div>
      </div>
    }>
      {replicators.length === 0 ? (
        <div className="text-sm text-tnvs-muted py-8 text-center">
          No hay cuentas marcadas para copy. Marca cuentas en <strong>Cuentas MT5</strong> con el toggle "Copy".
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-tnvs-muted border-b border-white/[0.06]">
                <th className="text-left py-2 px-2">Alias</th>
                <th className="text-left py-2 px-2">Login</th>
                <th className="text-left py-2 px-2">Server</th>
                <th className="text-right py-2 px-2">Balance</th>
                <th className="text-right py-2 px-2">Equity</th>
                <th className="text-right py-2 px-2">P&L</th>
                <th className="text-right py-2 px-2">Pos</th>
                <th className="text-center py-2 px-2">Accion</th>
              </tr>
            </thead>
            <tbody>
              {replicators.map((a: any) => {
                const liveData = live[a.login];
                return (
                  <tr key={a.id} className="border-b border-white/[0.04]">
                    <td className="py-2 px-2 font-medium">{a.alias ?? `acc_${a.login}`}</td>
                    <td className="py-2 px-2 font-mono text-xs">{a.login}</td>
                    <td className="py-2 px-2 text-xs text-tnvs-muted">{a.server}</td>
                    <td className="py-2 px-2 text-right font-mono text-xs">
                      {liveData?.balance != null ? `$${Number(liveData.balance).toFixed(2)}` : a.balance != null ? `$${Number(a.balance).toFixed(2)}` : '—'}
                    </td>
                    <td className="py-2 px-2 text-right font-mono text-xs">
                      {liveData?.equity != null ? `$${Number(liveData.equity).toFixed(2)}` : a.equity != null ? `$${Number(a.equity).toFixed(2)}` : '—'}
                    </td>
                    <td className={cls('py-2 px-2 text-right font-mono text-xs', liveData?.profit == null ? 'text-tnvs-muted' : liveData.profit >= 0 ? 'text-tnvs-win' : 'text-tnvs-loss')}>
                      {liveData?.profit != null ? `${liveData.profit >= 0 ? '+' : ''}$${Number(liveData.profit).toFixed(2)}` : '—'}
                    </td>
                    <td className="py-2 px-2 text-right text-xs">{a.open_positions ?? liveData?.open_positions ?? 0}</td>
                    <td className="py-2 px-2 text-center">
                      <button
                        type="button"
                        onClick={() => onToggle(a)}
                        data-testid={`copy-replicator-toggle-${a.id}`}
                        className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-medium uppercase tracking-wide border bg-tnvs-loss/15 text-tnvs-loss border-tnvs-loss/40 hover:bg-tnvs-loss/25"
                        title="Desactivar copia"
                      >
                        <XCircle className="w-3 h-3" />
                        OFF
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
