import { useEffect, useState } from 'react';
import { ExternalLink, RefreshCw } from 'lucide-react';
import { api, Metrics, EquityPoint, ChannelAgg, SymbolAgg, CalendarDay } from '../lib/api';
import { EquityCurve } from '../components/EquityCurve';
import { KPIGrid } from '../components/KPIGrid';
import { ChannelTable } from '../components/ChannelTable';
import { SymbolTable } from '../components/SymbolTable';
import { CalendarHeatmap } from '../components/CalendarHeatmap';

type Status = 'checking' | 'online' | 'offline';

export function Mt5DashboardPage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [equity, setEquity] = useState<EquityPoint[]>([]);
  const [byChannel, setByChannel] = useState<ChannelAgg[]>([]);
  const [bySymbol, setBySymbol] = useState<SymbolAgg[]>([]);
  const [calendar, setCalendar] = useState<CalendarDay[]>([]);
  const [status, setStatus] = useState<Status>('checking');
  const [loading, setLoading] = useState(true);

  const fetchAll = async () => {
    try {
      const [m, e, c, s, cal] = await Promise.all([
        api.bridge.metrics(),
        api.bridge.equityCurve(),
        api.bridge.byChannel(),
        api.bridge.bySymbol(),
        api.bridge.calendar(),
      ]);
      setMetrics(m); setEquity(e); setByChannel(c); setBySymbol(s); setCalendar(cal);
      setStatus('online');
    } catch {
      setStatus('offline');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, 30000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-white">Dashboard MT5</h2>
          <span
            className={
              'inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-medium ' +
              (status === 'online' ? 'bg-emerald-500/10 text-emerald-400' :
               status === 'offline' ? 'bg-red-500/10 text-red-400' :
               'bg-amber-500/10 text-amber-400')
            }
          >
            <span className={'h-1.5 w-1.5 rounded-full ' + (status === 'online' ? 'bg-emerald-400' : status === 'offline' ? 'bg-red-400' : 'bg-amber-400')} />
            {status === 'online' ? 'Online' : status === 'offline' ? 'Offline' : 'Verificando...'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <a
            href="http://localhost:8501"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-tnvs-muted hover:bg-white/[0.04] hover:text-white"
          >
            <ExternalLink className="h-3 w-3" />
            Modo clásico
          </a>
          <button
            onClick={fetchAll}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-tnvs-muted hover:bg-white/[0.04] hover:text-white"
          >
            <RefreshCw className="h-3 w-3" />
            Refrescar
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20 text-sm text-tnvs-muted">Cargando...</div>
      ) : (
        <>
          <EquityCurve data={equity} />
          <KPIGrid metrics={metrics} />
          <div className="grid grid-cols-2 gap-4">
            <ChannelTable rows={byChannel} />
            <SymbolTable rows={bySymbol} />
          </div>
          {calendar.length > 0 && (
            <CalendarHeatmap data={calendar} year={new Date().getFullYear()} />
          )}
        </>
      )}
    </div>
  );
}
