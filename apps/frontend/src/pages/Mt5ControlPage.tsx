import { useEffect, useState } from 'react';
import { Play, Square, Loader2, Activity, Clock } from 'lucide-react';
import { api } from '../lib/api';
import { cls } from '../utils/format';
import { Card, Page } from '../components/common';

type BotState = 'DEPLOYED' | 'STOPPED' | 'WAITING_CONFIG' | 'UNKNOWN';

interface BotStatePayload {
  status: BotState;
  updated_at?: string;
  _missing?: boolean;
  _error?: string;
}

const STATE_BADGE: Record<BotState, { label: string; cls: string }> = {
  DEPLOYED: { label: 'Desplegado', cls: 'bg-tnvs-win/15 text-tnvs-win' },
  STOPPED: { label: 'Detenido', cls: 'bg-tnvs-loss/15 text-tnvs-loss' },
  WAITING_CONFIG: { label: 'Esperando config', cls: 'bg-tnvs-warn/15 text-tnvs-warn' },
  UNKNOWN: { label: 'Sin estado', cls: 'bg-white/[0.08] text-tnvs-muted' },
};

export function Mt5ControlPage() {
  const [state, setState] = useState<BotStatePayload | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      const s = await api.bridge.controlState();
      const valid: BotState[] = ['DEPLOYED', 'STOPPED', 'WAITING_CONFIG', 'UNKNOWN'];
      const status = (valid.includes(s.status as BotState)
        ? s.status
        : 'UNKNOWN') as BotState;
      setState({ ...s, status });
      setError(null);
    } catch (e: any) {
      setError(e.message);
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 5000); // 5s polling per spec G
    return () => clearInterval(id);
  }, []);

  const handle = async (action: 'start' | 'stop' | 'wait_config') => {
    setBusy(true);
    try {
      await api.bridge.control(action);
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  if (!state) {
    return (
      <Page title="MT5 · Control" subtitle="Estado del bot y arranque/parada">
        <div className="text-sm text-tnvs-muted">Cargando…</div>
      </Page>
    );
  }

  const status = state.status;
  const badge = STATE_BADGE[status];
  const isDeployed = status === 'DEPLOYED';

  return (
    <Page
      title="MT5 · Control"
      subtitle="Estado del bot y arranque/parada manual"
      actions={
        <div className="flex items-center gap-2 text-xs">
          <span className="text-tnvs-muted">Polling 5s</span>
        </div>
      }
    >
      {error && (
        <div className="mb-4 rounded-md border border-tnvs-loss/30 bg-tnvs-loss/10 px-3 py-2 text-sm text-tnvs-loss">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_320px]">
        <Card
          header={
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-tnvs-muted" />
                Bot status
              </span>
              <span className={cls('rounded-full px-2 py-0.5 text-[10px] font-medium', badge.cls)}>
                {badge.label}
              </span>
            </div>
          }
        >
          <div className="flex flex-col items-center justify-center py-8">
            <div
              className={cls(
                'mb-3 grid h-20 w-20 place-items-center rounded-full',
                isDeployed ? 'bg-tnvs-win/15' : 'bg-tnvs-loss/10',
              )}
            >
              {isDeployed ? (
                <Play className="h-9 w-9 text-tnvs-win" />
              ) : (
                <Square className="h-9 w-9 text-tnvs-loss" />
              )}
            </div>
            <div className="text-lg font-medium text-white">
              {isDeployed ? 'Bot corriendo' : 'Bot detenido'}
            </div>
            <div className="mt-1 flex items-center gap-1.5 text-xs text-tnvs-muted">
              <Clock className="h-3 w-3" />
              {state.updated_at
                ? `Último cambio: ${new Date(state.updated_at).toLocaleString()}`
                : 'Sin timestamp'}
            </div>

            <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
              <button
                onClick={() => handle('start')}
                disabled={busy || isDeployed}
                className={cls(
                  'inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium',
                  isDeployed
                    ? 'cursor-not-allowed border border-tnvs-border bg-tnvs-void text-tnvs-muted'
                    : 'bg-tnvs-win text-tnvs-void hover:bg-tnvs-win/90',
                )}
              >
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                INICIAR PROGRAMA
              </button>
              <button
                onClick={() => handle('stop')}
                disabled={busy || !isDeployed}
                className={cls(
                  'inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium',
                  !isDeployed
                    ? 'cursor-not-allowed border border-tnvs-border bg-tnvs-void text-tnvs-muted'
                    : 'bg-tnvs-loss text-white hover:bg-tnvs-loss/90',
                )}
              >
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Square className="h-4 w-4" />}
                DETENER PROGRAMA
              </button>
            </div>
          </div>
        </Card>

        <div className="space-y-4">
          <Card header="Información">
            <div className="space-y-2 text-xs text-tnvs-muted">
              <div className="flex justify-between">
                <span>Status actual</span>
                <span className="font-mono text-white">{status}</span>
              </div>
              <div className="flex justify-between">
                <span>Último update</span>
                <span className="font-mono text-white">
                  {state.updated_at || '—'}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Persistencia</span>
                <span className="font-mono text-white">bot_state.json</span>
              </div>
            </div>
          </Card>

          <Card header="Acciones rápidas">
            <div className="space-y-2">
              <button
                onClick={() => handle('wait_config')}
                disabled={busy}
                className="w-full rounded-md border border-tnvs-border bg-tnvs-void px-3 py-2 text-left text-xs text-tnvs-muted hover:text-white disabled:opacity-40"
              >
                Forzar "Esperando config"
              </button>
              <div className="text-[10px] text-tnvs-dim">
                Mueve el bot a estado WAITING_CONFIG sin detenerlo (útil para recargar selección de canales).
              </div>
            </div>
          </Card>

          <Card header="Notas">
            <ul className="space-y-1 text-xs text-tnvs-muted">
              <li>• El bot revisa bot_state.json cada ~2s.</li>
              <li>• "Detener" no mata procesos: deja de ejecutar señales y libera sesión Telegram.</li>
              <li>• El status vuelve a WAITING_CONFIG si no hay canales seleccionados.</li>
            </ul>
          </Card>
        </div>
      </div>
    </Page>
  );
}
