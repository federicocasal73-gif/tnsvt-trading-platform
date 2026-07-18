import { useMemo } from 'react';
import { CalendarDay } from '../lib/api';
import { cls } from '../utils/format';
import { Empty } from './common';

const DAY_NAMES = ['', 'Mon', '', 'Wed', '', 'Fri', ''];

function pnlLevel(pnl: number, maxAbs: number): number {
  if (maxAbs === 0) return 0;
  const ratio = Math.abs(pnl) / maxAbs;
  if (pnl > 0) {
    if (ratio > 0.8) return 4;
    if (ratio > 0.5) return 3;
    if (ratio > 0.2) return 2;
    return 1;
  }
  if (pnl < 0) {
    if (ratio > 0.8) return -4;
    if (ratio > 0.5) return -3;
    if (ratio > 0.2) return -2;
    return -1;
  }
  return 0;
}

function levelColor(level: number): string {
  switch (level) {
    case 4:  return 'bg-tnvs-win';
    case 3:  return 'bg-tnvs-win/60';
    case 2:  return 'bg-tnvs-win/40';
    case 1:  return 'bg-tnvs-win/20';
    case -1: return 'bg-tnvs-loss/20';
    case -2: return 'bg-tnvs-loss/40';
    case -3: return 'bg-tnvs-loss/60';
    case -4: return 'bg-tnvs-loss';
    default: return 'bg-white/[0.04]';
  }
}

export function CalendarHeatmap({ data, year }: { data: CalendarDay[]; year: number }) {
  const maxAbs = useMemo(() => {
    if (!data.length) return 0;
    return Math.max(...data.map(d => Math.abs(d.pnl)), 1);
  }, [data]);

  const byDate = useMemo(() => {
    const m = new Map<string, CalendarDay>();
    for (const d of data) m.set(d.date, d);
    return m;
  }, [data]);

  const weeks = useMemo(() => {
    const start = new Date(year, 0, 1);
    const end = new Date(year, 11, 31);
    const w: { date: Date; day: CalendarDay | null }[][] = [];
    let cur: { date: Date; day: CalendarDay | null }[] = [];

    // Pad to Monday
    const pad = (start.getDay() + 6) % 7;
    for (let p = 0; p < pad; p++) cur.push({ date: new Date(0), day: null });

    for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
      const key = d.toISOString().slice(0, 10);
      const day = byDate.get(key) || null;
      cur.push({ date: new Date(d), day });
      if (cur.length === 7) {
        w.push(cur);
        cur = [];
      }
    }
    if (cur.length) w.push(cur);
    return w;
  }, [year, byDate]);

  if (!data.length) return <Empty title="Sin datos" description="No hay trades cerrados este año" />;

  const totalPnl = data.reduce((s, d) => s + d.pnl, 0);
  const winDays = data.filter(d => d.pnl > 0).length;
  const lossDays = data.filter(d => d.pnl < 0).length;

  return (
    <div className="rounded-lg border border-tnvs-border bg-tnvs-surface p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-white">Calendar · {year}</h3>
        <div className="flex items-center gap-3 text-[11px]">
          <span className="text-tnvs-muted">
            <span className="text-tnvs-win">{winDays}d</span> / <span className="text-tnvs-loss">{lossDays}d</span>
          </span>
          <span className={cls('font-mono', totalPnl >= 0 ? 'text-tnvs-win' : 'text-tnvs-loss')}>
            ${totalPnl >= 0 ? '+' : ''}{totalPnl.toFixed(0)}
          </span>
        </div>
      </div>
      <div className="overflow-x-auto">
        <div className="flex gap-1" style={{ minWidth: 720 }}>
          {weeks.map((week, wi) => (
            <div key={wi} className="flex flex-col gap-0.5">
              {week.map((cell, di) => {
                if (!cell.day) return <div key={di} className="h-3 w-3" />;
                const level = pnlLevel(cell.day.pnl, maxAbs);
                return (
                  <div
                    key={di}
                    className={cls('h-3 w-3 rounded-sm cursor-pointer', levelColor(level))}
                    title={`${cell.date.toISOString().slice(0, 10)}: $${cell.day.pnl.toFixed(2)} (${cell.day.trades} trades)`}
                  />
                );
              })}
            </div>
          ))}
        </div>
      </div>
      <div className="mt-3 flex items-center gap-1.5 text-[10px] text-tnvs-dim">
        <span>Less</span>
        <div className="h-3 w-3 rounded-sm bg-white/[0.04]" />
        <div className="h-3 w-3 rounded-sm bg-tnvs-win/20" />
        <div className="h-3 w-3 rounded-sm bg-tnvs-win/40" />
        <div className="h-3 w-3 rounded-sm bg-tnvs-win/60" />
        <div className="h-3 w-3 rounded-sm bg-tnvs-win" />
        <div className="h-3 w-3 rounded-sm bg-tnvs-loss/20" />
        <div className="h-3 w-3 rounded-sm bg-tnvs-loss/40" />
        <div className="h-3 w-3 rounded-sm bg-tnvs-loss/60" />
        <div className="h-3 w-3 rounded-sm bg-tnvs-loss" />
        <span>More</span>
      </div>
    </div>
  );
}
