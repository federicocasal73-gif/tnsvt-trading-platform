import { useEffect, useState } from 'react';
import { api, Metrics, LivePosition } from '../lib/api';
import { AnimatedNumber, TiltCard } from './common';
import { cls } from '../utils/format';

export function KPIGrid({ metrics }: { metrics: Metrics | null }) {
  const m = metrics;
  const [todayPnL, setTodayPnL] = useState<number | null>(null);
  const [tradesToday, setTradesToday] = useState<number>(0);
  const [maxTradesPerDay, setMaxTradesPerDay] = useState<number>(0);

  useEffect(() => {
    let mounted = true;
    const loadToday = async () => {
      try {
        const today = new Date().toISOString().slice(0, 10);
        const all: LivePosition[] = await api.bridge.trades('CLOSED');
        // Sum realized P&L of trades closed today, in account currency
        const today_pnl = all
          .filter(t => t.closed_at && t.closed_at.startsWith(today))
          .reduce((acc, t) => acc + (t.pnl || 0), 0);
        if (mounted) setTodayPnL(today_pnl);
      } catch {
        if (mounted) setTodayPnL(0);
      }
    };

    const loadDailyCount = async () => {
      try {
        const today = new Date().toISOString().slice(0, 10);
        const all = await api.bridge.trades('CLOSED');
        const openedToday = all.filter(t => t.opened_at && t.opened_at.startsWith(today)).length;
        if (mounted) setTradesToday(openedToday);
      } catch {
        if (mounted) setTradesToday(0);
      }
    };

    const loadLimits = async () => {
      try {
        const cfg: any = await api.bridge.config();
        const risk = cfg?.risk_management || {};
        const max = Number(risk.max_trades_per_day ?? 0);
        if (mounted) setMaxTradesPerDay(max);
      } catch {
        // ignore
      }
    };

    loadToday();
    loadDailyCount();
    loadLimits();
    const id = setInterval(() => { loadToday(); loadDailyCount(); loadLimits(); }, 5000);
    return () => { mounted = false; clearInterval(id); };
  }, []);

  const safeToday = todayPnL ?? 0;
  const hasLimit = maxTradesPerDay > 0;
  const tradesLabel = hasLimit
    ? `${tradesToday} / ${maxTradesPerDay} trades`
    : `${tradesToday} trades`;
  const tradesAccent = hasLimit && tradesToday >= maxTradesPerDay
    ? 'text-tnvs-warn'
    : '';

  const cards = [
    { label: 'Trades hoy', value: tradesLabel, accent: tradesAccent },
    { label: 'Total Trades', value: m ? m.total : '—', accent: '' },
    { label: 'Ejecutadas', value: m ? m.wins + m.losses : '—', accent: '' },
    { label: 'Bloqueadas', value: m ? Math.max(0, m.total - (m.wins + m.losses)) : '—', accent: 'text-tnvs-warn' },
    {
      label: 'Hoy $',
      value: todayPnL === null ? '…' : `$${safeToday.toFixed(2)}`,
      accent: safeToday >= 0 ? 'text-tnvs-win' : 'text-tnvs-loss',
    },
    { label: 'Win Rate', value: m ? `${(m.win_rate * 100).toFixed(1)}%` : '—', accent: m && m.win_rate >= 0.5 ? 'text-tnvs-win' : 'text-tnvs-loss' },
    { label: 'Ganadas', value: m ? m.wins : '—', accent: 'text-tnvs-win' },
    { label: 'Perdidas', value: m ? m.losses : '—', accent: 'text-tnvs-loss' },
  ];
  if (!m && todayPnL === null) return null;

  return (
    <div className="grid grid-cols-4 gap-3">
      {cards.map((c) => (
        <TiltCard key={c.label}>
          <div className="rounded-lg border border-tnvs-border bg-tnvs-surface p-3">
            <div className="text-[10px] font-medium uppercase tracking-wider text-tnvs-muted">{c.label}</div>
            <div className={cls('mt-1 font-mono text-xl font-semibold', c.accent || 'text-white')}>
              {typeof c.value === 'number' && c.value !== null ? (
                <AnimatedNumber value={c.value} />
              ) : (
                c.value
              )}
            </div>
          </div>
        </TiltCard>
      ))}
    </div>
  );
}
