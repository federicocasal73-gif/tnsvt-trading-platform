import { useEffect, useMemo, useState } from 'react';
import { Search, RefreshCw, Save, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { api, BotConfig, ChannelProfile, ChannelSelection, ScanResult } from '../lib/api';
import { cls } from '../utils/format';
import { Empty, Card, Page } from '../components/common';

type Toast = { kind: 'ok' | 'err'; msg: string } | null;

function key(sel: ChannelSelection) {
  return `${sel.id}_${sel.topic_id ?? 'None'}`;
}

function parseKey(k: string): ChannelSelection {
  const [idStr, topicStr] = k.split('_');
  return {
    id: parseInt(idStr, 10),
    name: '',
    topic_id: topicStr === 'None' ? null : parseInt(topicStr, 10),
  };
}

export function Mt5ChannelsPage() {
  const [cfg, setCfg] = useState<BotConfig | null>(null);
  const [scan, setScan] = useState<ScanResult | null>(null);
  const [scanning, setScanning] = useState(false);
  const [saving, setSaving] = useState(false);
  const [filter, setFilter] = useState('');
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [toast, setToast] = useState<Toast>(null);

  const loadConfig = async () => {
    try {
      const c = await api.bridge.config();
      setCfg(c);
      const saved = (c.channels_data || []).map(s => key(s));
      setSelected(new Set(saved));
    } catch (e: any) {
      setToast({ kind: 'err', msg: `Error cargando config: ${e.message}` });
    }
  };

  const loadScan = async () => {
    try {
      const r = await api.bridge.scanResult();
      setScan(r);
    } catch {
      // silent
    }
  };

  useEffect(() => {
    loadConfig();
    loadScan();
  }, []);

  // Polling automático cuando hay scan pendiente
  useEffect(() => {
    if (!scanning) return;
    const id = setInterval(async () => {
      const r = await api.bridge.scanResult();
      setScan(r);
      if (r.status !== 'PENDING') {
        setScanning(false);
      }
    }, 1500);
    return () => clearInterval(id);
  }, [scanning]);

  const handleScan = async () => {
    try {
      setScanning(true);
      await api.bridge.triggerScan();
      setToast({ kind: 'ok', msg: 'Scan iniciado. Esperando resultado…' });
      setTimeout(() => setToast(null), 4000);
    } catch (e: any) {
      setScanning(false);
      setToast({ kind: 'err', msg: e.message });
    }
  };

  const toggle = (k: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });
  };

  const handleSave = async () => {
    if (!cfg || !scan?.data) {
      setToast({ kind: 'err', msg: 'Necesitás escanear primero' });
      return;
    }
    setSaving(true);
    try {
      const byKey = new Map<string, string>();
      for (const ch of scan.data) {
        byKey.set(key({ id: ch.id, name: ch.name, topic_id: null }), ch.name);
        for (const t of ch.topics || []) {
          byKey.set(
            key({ id: ch.id, name: `${ch.name} > ${t.title}`, topic_id: t.id }),
            `${ch.name} > ${t.title}`,
          );
        }
      }

      const channels_data: ChannelSelection[] = [];
      for (const k of selected) {
        const sel = parseKey(k);
        sel.name = byKey.get(k) || `Channel ${sel.id}`;
        channels_data.push(sel);
      }

      const res = await api.bridge.updateConfig({ channels_data });
      setToast({
        kind: 'ok',
        msg: `Guardado: ${res.updated_keys.length} campo(s) — ${channels_data.length} canal(es)`,
      });
      setTimeout(() => setToast(null), 4000);
      await loadConfig();
    } catch (e: any) {
      setToast({ kind: 'err', msg: e.message });
    } finally {
      setSaving(false);
    }
  };

  const channels = scan?.data || [];
  const filteredChannels = useMemo(() => {
    if (!filter.trim()) return channels;
    const f = filter.toLowerCase();
    return channels.filter(ch =>
      ch.name.toLowerCase().includes(f) ||
      (ch.topics || []).some(t => t.title.toLowerCase().includes(f)),
    );
  }, [channels, filter]);

  const channelSummary = useMemo(() => {
    const total = channels.length;
    const forums = channels.filter(c => c.is_forum).length;
    const topics = channels.reduce((n, c) => n + (c.topics?.length || 0), 0);
    return { total, forums, topics };
  }, [channels]);

  return (
    <Page
      title="MT5 · Telegram Channels"
      subtitle="Escaneá tus canales y elegí cuáles monitorear"
      actions={
        <div className="flex items-center gap-2">
          <button
            onClick={handleScan}
            disabled={scanning}
            className="inline-flex items-center gap-1.5 rounded-md bg-tnvs-purple px-3 py-1.5 text-xs font-medium text-white hover:bg-tnvs-purple/80 disabled:opacity-50"
          >
            <RefreshCw className={cls('h-3.5 w-3.5', scanning && 'animate-spin')} />
            {scanning ? 'Escaneando…' : 'Escanear canales'}
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !scan?.data}
            className="inline-flex items-center gap-1.5 rounded-md bg-tnvs-win px-3 py-1.5 text-xs font-medium text-tnvs-void hover:bg-tnvs-win/80 disabled:opacity-50"
          >
            <Save className="h-3.5 w-3.5" />
            {saving ? 'Guardando…' : `Guardar (${selected.size})`}
          </button>
        </div>
      }
    >
      {toast && (
        <div
          className={cls(
            'mb-4 inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs',
            toast.kind === 'ok'
              ? 'border-tnvs-win/40 bg-tnvs-win/10 text-tnvs-win'
              : 'border-tnvs-loss/40 bg-tnvs-loss/10 text-tnvs-loss',
          )}
        >
          {toast.kind === 'ok' ? <CheckCircle2 className="h-3.5 w-3.5" /> : <AlertTriangle className="h-3.5 w-3.5" />}
          {toast.msg}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_280px]">
        <div className="space-y-4">
          {/* Status del scan */}
          <Card
            header={
              <div className="flex items-center justify-between">
                <span>Canales detectados</span>
                {scan && (
                  <span
                    className={cls(
                      'rounded-full px-2 py-0.5 text-[10px] font-medium',
                      scan.status === 'OK' && 'bg-tnvs-win/15 text-tnvs-win',
                      scan.status === 'PENDING' && 'bg-tnvs-warn/15 text-tnvs-warn',
                      scan.status === 'ERROR' && 'bg-tnvs-loss/15 text-tnvs-loss',
                      scan.status === 'NO_SCAN' && 'bg-white/[0.08] text-tnvs-muted',
                    )}
                  >
                    {scan.status}
                  </span>
                )}
              </div>
            }
          >
            {!scan ? (
              <div className="text-sm text-tnvs-muted">Cargando…</div>
            ) : scan.status === 'NO_SCAN' ? (
              <Empty
                title="Sin resultados de scan"
                description="Tocá 'Escanear canales' para listar los canales de tu Telegram"
              />
            ) : scan.status === 'PENDING' ? (
              <div className="flex items-center gap-3 text-sm text-tnvs-warn">
                <RefreshCw className="h-4 w-4 animate-spin" />
                El bot está escaneando tus canales y foros…
              </div>
            ) : scan.status === 'ERROR' ? (
              <div className="rounded-md border border-tnvs-loss/30 bg-tnvs-loss/10 p-3 text-sm text-tnvs-loss">
                <div className="font-medium">No se pudo escanear</div>
                <div className="mt-1 text-xs text-tnvs-loss/80">{scan.error}</div>
              </div>
            ) : (
              <>
                <div className="mb-4 grid grid-cols-3 gap-3">
                  <div className="rounded-md bg-tnvs-void px-3 py-2">
                    <div className="text-[10px] uppercase tracking-wider text-tnvs-muted">Total canales</div>
                    <div className="mt-1 font-mono text-xl font-semibold text-white">
                      {channelSummary.total}
                    </div>
                  </div>
                  <div className="rounded-md bg-tnvs-void px-3 py-2">
                    <div className="text-[10px] uppercase tracking-wider text-tnvs-muted">Foros</div>
                    <div className="mt-1 font-mono text-xl font-semibold text-white">
                      {channelSummary.forums}
                    </div>
                  </div>
                  <div className="rounded-md bg-tnvs-void px-3 py-2">
                    <div className="text-[10px] uppercase tracking-wider text-tnvs-muted">Sub-canales</div>
                    <div className="mt-1 font-mono text-xl font-semibold text-white">
                      {channelSummary.topics}
                    </div>
                  </div>
                </div>

                <div className="relative mb-3">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-tnvs-muted" />
                  <input
                    value={filter}
                    onChange={e => setFilter(e.target.value)}
                    placeholder="Filtrar canales o temas…"
                    className="tnvs-input w-full pl-9"
                  />
                </div>

                <div className="max-h-[60vh] space-y-2 overflow-y-auto pr-1">
                  {filteredChannels.length === 0 ? (
                    <div className="py-8 text-center text-sm text-tnvs-muted">
                      Sin coincidencias con "{filter}"
                    </div>
                  ) : (
                    filteredChannels.map(ch => (
                      <ChannelRow
                        key={ch.id}
                        channel={ch}
                        selectedKeys={selected}
                        onToggle={toggle}
                      />
                    ))
                  )}
                </div>
              </>
            )}
          </Card>
        </div>

        {/* Sidebar resumen */}
        <div className="space-y-4">
          <Card header="Selección actual">
            <div className="text-3xl font-mono font-semibold text-white">
              {selected.size}
            </div>
            <div className="text-xs text-tnvs-dim">
              canales / sub-canales marcados
            </div>
            {selected.size > 0 && (
              <div className="mt-3 max-h-40 space-y-1 overflow-y-auto text-xs">
                {Array.from(selected).map(k => {
                  const sel = parseKey(k);
                  return (
                    <div
                      key={k}
                      className="flex items-center justify-between rounded bg-tnvs-void px-2 py-1 font-mono text-tnvs-muted"
                    >
                      <span>{sel.id}{sel.topic_id != null ? `·t${sel.topic_id}` : ''}</span>
                      <button
                        onClick={() => toggle(k)}
                        className="text-tnvs-loss hover:text-tnvs-loss/80"
                        title="Quitar"
                      >
                        ×
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>

          {cfg?.risk_management && (
            <Card header="Risk management (resumen)">
              <RiskRow label="Daily Profit" v={cfg.risk_management.daily_profit_target} on={cfg.risk_management.active_daily_profit} />
              <RiskRow label="Daily Loss" v={cfg.risk_management.daily_loss_limit} on={cfg.risk_management.active_daily_loss} />
              <RiskRow label="Weekly Profit" v={cfg.risk_management.weekly_profit} on={cfg.risk_management.active_weekly_profit} />
              <RiskRow label="Weekly Loss" v={cfg.risk_management.weekly_loss} on={cfg.risk_management.active_weekly_loss} />
              <RiskRow label="Monthly Profit" v={cfg.risk_management.monthly_profit} on={cfg.risk_management.active_monthly_profit} />
              <RiskRow label="Monthly Loss" v={cfg.risk_management.monthly_loss} on={cfg.risk_management.active_monthly_loss} />
              <div className="mt-3 text-[10px] text-tnvs-dim">
                Editar en Mt5Settings (Bloque F)
              </div>
            </Card>
          )}
        </div>
      </div>
    </Page>
  );
}

function ChannelRow({
  channel,
  selectedKeys,
  onToggle,
}: {
  channel: ChannelProfile;
  selectedKeys: Set<string>;
  onToggle: (k: string) => void;
}) {
  const mainKey = key({ id: channel.id, name: channel.name, topic_id: null });
  const isMainSelected = selectedKeys.has(mainKey);

  return (
    <div className="rounded-md border border-tnvs-border/60 bg-tnvs-void">
      <label className="flex cursor-pointer items-center gap-3 px-3 py-2">
        <input
          type="checkbox"
          checked={isMainSelected}
          onChange={() => onToggle(mainKey)}
          className="h-4 w-4 rounded border-tnvs-border bg-tnvs-surface accent-tnvs-purple"
        />
        <span className="text-sm text-white">{channel.name}</span>
        <span className="ml-auto text-[10px] text-tnvs-dim">
          {channel.is_forum ? `${(channel.topics || []).length} temas` : 'chat'}
        </span>
      </label>

      {channel.is_forum && (channel.topics || []).length > 0 && (
        <div className="space-y-1 border-t border-tnvs-border/40 px-3 py-2">
          {(channel.topics || []).map(t => {
            const tk = key({
              id: channel.id,
              name: `${channel.name} > ${t.title}`,
              topic_id: t.id,
            });
            const checked = selectedKeys.has(tk);
            return (
              <label
                key={t.id}
                className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 hover:bg-white/[0.03]"
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => onToggle(tk)}
                  className="h-3.5 w-3.5 rounded border-tnvs-border bg-tnvs-surface accent-tnvs-purple"
                />
                <span className="text-xs text-tnvs-muted">{t.title}</span>
              </label>
            );
          })}
        </div>
      )}
    </div>
  );
}

function RiskRow({ label, v, on }: { label: string; v: number; on: boolean }) {
  return (
    <div className="flex items-center justify-between border-b border-tnvs-border/30 py-1.5 text-xs last:border-0">
      <span className="text-tnvs-muted">{label}</span>
      <span className="flex items-center gap-2 font-mono">
        {on ? (
          <span className="rounded bg-tnvs-win/15 px-1 text-tnvs-win">ON</span>
        ) : (
          <span className="rounded bg-white/[0.05] px-1 text-tnvs-dim">off</span>
        )}
        <span className="text-white">{v}%</span>
      </span>
    </div>
  );
}
