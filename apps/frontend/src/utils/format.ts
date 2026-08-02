import type { CSSProperties } from 'react';

export function fmtUsd(v: number | null | undefined, opts?: { sign?: boolean }): string {
  if (v == null) return '$0.00';
  const s = v.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 });
  if (opts?.sign && v >= 0) return '+' + s;
  return s;
}

export function fmtPct(v: number | null | undefined, dp = 1): string {
  if (v == null) return '0.0%';
  const sign = v >= 0 ? '+' : '';
  return `${sign}${v.toFixed(dp)}%`;
}

export function fmtNum(v: number | null | undefined, dp = 0): string {
  if (v == null) return '0';
  return v.toLocaleString('en-US', { minimumFractionDigits: dp, maximumFractionDigits: dp });
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

export function fmtRelative(iso: string | null | undefined): string {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const d = Math.floor(hr / 24);
  return `${d}d ago`;
}

export function fmtTimeShort(iso: string | null | undefined): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

// ─── Color por cuenta (Sprint 1.6) ───────────────────────────────
// Hash determinístico → color HSL estable. El mismo account_id siempre
// produce el mismo color. La saturación/luminosidad fijas garantizan que
// los colores se ven bien en temas light/dark.

const ACCOUNT_COLORS = [
  'hsl(212, 70%, 55%)',  // blue
  'hsl(150, 65%, 45%)',  // green
  'hsl(28, 80%, 55%)',   // orange
  'hsl(280, 60%, 60%)',  // purple
  'hsl(350, 70%, 55%)',  // red
  'hsl(190, 70%, 45%)',  // teal
  'hsl(45, 85%, 50%)',   // yellow
  'hsl(95, 60%, 45%)',   // lime
];

export function accountColor(key: string | number | null | undefined): string {
  if (key == null || key === '') return ACCOUNT_COLORS[0];
  const s = String(key);
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = (h * 31 + s.charCodeAt(i)) >>> 0;
  }
  return ACCOUNT_COLORS[h % ACCOUNT_COLORS.length];
}

export function accountBadgeStyle(key: string | number | null | undefined): CSSProperties {
  const color = accountColor(key);
  return {
    backgroundColor: `${color.replace('hsl(', 'hsla(').replace(')', ' / 0.15)')}`,
    color,
    borderColor: `${color.replace('hsl(', 'hsla(').replace(')', ' / 0.4)')}`,
  };
}

export const fmtDate = fmtDateTime;

export function cls(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(' ');
}

export function titleCase(s: string): string {
  return s.replace(/([a-z])([A-Z])/g, '$1 $2').replace(/([A-Z]+)([A-Z][a-z])/g, '$1 $2').replace(/^./, c => c.toUpperCase());
}
