import { useEffect, useRef, useState } from 'react';
import { RefreshCw, ExternalLink } from 'lucide-react';

/**
 * Mt5BotPage - Embebe el dashboard Streamlit v14.2 (D:\TradingBotMT5) dentro
 * del frontend TNSVT en :5180/mt5-bot.
 *
 * El iframe apunta a /mt5-bot-iframe, que Vite redirige via proxy a
 * http://localhost:8501 (Streamlit del bot nativo). Asi el usuario solo ve
 * :5180; los detalles de los puertos quedan ocultos.
 */
export function Mt5BotPage() {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [status, setStatus] = useState<'checking' | 'online' | 'offline'>('checking');

  useEffect(() => {
    // Ping al dashboard para mostrar estado
    fetch('/mt5-bot-iframe/_stcore/health', { method: 'GET' })
      .then((r) => (r.ok ? setStatus('online') : setStatus('offline')))
      .catch(() => setStatus('offline'));
  }, [reloadKey]);

  const handleReload = () => setReloadKey((k) => k + 1);
  const handleOpenExternal = () => window.open('http://localhost:8501', '_blank');

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-tnvs-border bg-tnvs-surface px-4 py-2">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-semibold text-white">🤖 MT5 Trading Bot v14.2</h2>
          <span
            className={
              'inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-medium ' +
              (status === 'online'
                ? 'bg-emerald-500/10 text-emerald-400'
                : status === 'offline'
                ? 'bg-red-500/10 text-red-400'
                : 'bg-amber-500/10 text-amber-400')
            }
            data-testid="mt5-bot-status"
          >
            <span
              className={
                'h-1.5 w-1.5 rounded-full ' +
                (status === 'online' ? 'bg-emerald-400' : status === 'offline' ? 'bg-red-400' : 'bg-amber-400')
              }
            />
            {status === 'online' ? 'Online' : status === 'offline' ? 'Offline' : 'Verificando...'}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={handleReload}
            data-testid="mt5-bot-reload"
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-tnvs-muted hover:bg-white/[0.04] hover:text-white"
            title="Recargar dashboard"
          >
            <RefreshCw className="h-3 w-3" />
            Reload
          </button>
          <button
            onClick={handleOpenExternal}
            data-testid="mt5-bot-external"
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-tnvs-muted hover:bg-white/[0.04] hover:text-white"
            title="Abrir en pestaña nueva"
          >
            <ExternalLink className="h-3 w-3" />
            Nueva pestaña
          </button>
        </div>
      </div>

      <div className="relative flex-1 bg-tnvs-void">
        {status === 'offline' ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="max-w-md rounded-lg border border-red-500/20 bg-red-500/5 p-6 text-center">
              <h3 className="text-base font-semibold text-red-400">Dashboard no disponible</h3>
              <p className="mt-2 text-sm text-tnvs-muted">
                El bot MT5 v14.2 (Streamlit en :8501) no responde. Asegurate de que
                <code className="mx-1 rounded bg-black/30 px-1.5 py-0.5 text-xs">D:\TradingBotMT5\START_BOT.bat</code>
                esté corriendo.
              </p>
              <button
                onClick={handleReload}
                className="mt-4 rounded-md bg-red-500/20 px-3 py-1.5 text-xs text-red-300 hover:bg-red-500/30"
              >
                Reintentar
              </button>
            </div>
          </div>
        ) : (
          <iframe
            key={reloadKey}
            ref={iframeRef}
            src="/mt5-bot-iframe"
            className="absolute inset-0 h-full w-full border-0"
            title="MT5 Trading Bot v14.2 - Streamlit"
            data-testid="mt5-bot-iframe"
            sandbox="allow-same-origin allow-scripts allow-forms allow-popups"
          />
        )}
      </div>
    </div>
  );
}
