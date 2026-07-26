# Fase 2 — Inline Expand Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add click-to-expand inline rows in Mt5PositionsPage showing mini M5 chart + detail panel

**Architecture:** Frontend-only. Click row → toggle expanded `<tr>` with `colSpan` containing chart (reuses TradePreviewChart with `inline` prop) + detail panel (duration, prices, SL/TP, P&L badge, commission/swap).

**Tech Stack:** React 18, TypeScript, lightweight-charts v5

## Global Constraints

- No new backend endpoints
- Reuse `_previewCache` and `api.bridge.tradeCandles()`
- Hover preview must continue working independently
- TradePreviewChart must support both popover mode (existing) and inline mode (new)

---

### Task 1: Add `inline` prop to TradePreviewChart

**Files:**
- Modify: `apps/frontend/src/components/TradePreviewChart.tsx`

**Interfaces:**
- Consumes: existing `Props` (trade, candles?, onClose?)
- Produces: Props extended with `inline?: boolean`

- [ ] **Step 1: Add `inline` prop and conditional rendering**

Edit `TradePreviewChart.tsx` to add `inline` prop. When true: no header bar, no close button, size 400×180, no fixed positioning.

```tsx
interface Props {
  trade: LivePosition;
  candles?: BridgeCandle[];
  onClose?: () => void;
  inline?: boolean;
}
```

In the JSX, wrap the header in a conditional:

```tsx
{!inline && (
  <div className="flex items-center justify-between border-b border-tnvs-border px-3 py-2">
    <span className="text-xs font-medium text-white">
      {symbol} · M5
      <span className="ml-2 text-tnvs-dim">Preview</span>
    </span>
    {onClose && (
      <button onClick={onClose} className="text-tnvs-dim hover:text-white text-xs">✕</button>
    )}
  </div>
)}
```

Wrap the info bar (BUY/SELL, Entry, SL, TP) the same way — only show when not inline (the parent tr will show its own detail panel):

```tsx
{!inline && (
  <div className="flex items-center gap-2 border-b border-tnvs-border/30 px-3 py-1.5 text-[10px] text-tnvs-dim font-mono">
    ...
  </div>
)}
```

Change the container height based on inline:

```tsx
<div ref={containerRef} className={inline ? 'h-[180px] w-[400px]' : 'h-[240px]'} />
```

And remove the outer border/padding when inline — use a `className` that changes:

```tsx
<div className={cls(inline ? '' : 'relative rounded-lg border border-tnvs-border bg-tnvs-surface shadow-tnvs-strong')}>
```

- [ ] **Step 2: Run TypeScript check**

```bash
cd apps/frontend && npx tsc -b --noEmit
```
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add apps/frontend/src/components/TradePreviewChart.tsx
git commit -m "feat: add inline prop to TradePreviewChart for inline expand mode"
```

### Task 2: Add inline expand to Mt5PositionsPage

**Files:**
- Modify: `apps/frontend/src/pages/Mt5PositionsPage.tsx`

**Interfaces:**
- Consumes: `TradePreviewChart` with `inline` prop, `_previewCache`, `_previewFetch`, `api.bridge.tradeCandles()`
- Produces: expanded row with chart + detail panel on row click

- [ ] **Step 1: Add state and click handler**

Add new state variables after existing state declarations (~line 194-198):

```tsx
const [expandedTicket, setExpandedTicket] = useState<number | null>(null);
const [expandedCandles, setExpandedCandles] = useState<BridgeCandle[] | null>(null);
const [expandedLoading, setExpandedLoading] = useState(false);
```

Add click handler before the return statement (~line 232):

```tsx
const handleRowClick = useCallback(async (ticket: number) => {
  if (expandedTicket === ticket) {
    setExpandedTicket(null);
    setExpandedCandles(null);
    return;
  }
  setExpandedTicket(ticket);
  setExpandedCandles(null);
  setExpandedLoading(true);
  const cached = _previewCache.get(ticket);
  if (cached) {
    setExpandedCandles(cached);
    setExpandedLoading(false);
    return;
  }
  try {
    const res = await api.bridge.tradeCandles(ticket);
    if (res.ok && res.candles?.length > 0) {
      _previewCache.set(ticket, res.candles);
      setExpandedCandles(res.candles);
    }
  } catch { /* noop */ }
  setExpandedLoading(false);
}, [expandedTicket]);
```

- [ ] **Step 2: Add onClick to table rows**

Add `onClick` and cursor style to each `<tr>` in the map:

```tsx
<tr key={t.ticket || i} className={cls(
  'border-b border-tnvs-border/30 hover:bg-white/[0.02] cursor-pointer',
  t.status === 'OPEN' && 'bg-tnvs-win/[0.02]',
  hoveredTrade?.ticket === t.ticket && 'bg-white/[0.04]',
  expandedTicket === t.ticket && 'bg-white/[0.06]',
)}
  onMouseEnter={(ev) => handleRowEnter(t, ev)}
  onMouseLeave={handleRowLeave}
  onClick={() => handleRowClick(t.ticket)}
>
```

- [ ] **Step 3: Add expanded row after each trade row**

After the closing `</tr>` of the mapped row, add:

```tsx
{expandedTicket === t.ticket && (
  <tr className="border-b border-tnvs-border/30">
    <td colSpan={11} className="px-4 py-3">
      {expandedLoading ? (
        <div className="flex items-center gap-3">
          <div className="h-[180px] w-[400px] animate-pulse rounded bg-white/[0.04]" />
          <div className="flex-1 space-y-2">
            <div className="h-4 w-24 animate-pulse rounded bg-white/[0.04]" />
            <div className="h-4 w-32 animate-pulse rounded bg-white/[0.04]" />
            <div className="h-4 w-20 animate-pulse rounded bg-white/[0.04]" />
          </div>
        </div>
      ) : (
        <div className="flex gap-4">
          <TradePreviewChart trade={t} candles={expandedCandles ?? undefined} inline />
          <div className="flex-1 space-y-2 text-xs font-mono text-tnvs-muted">
            <div className="flex items-center gap-2">
              <span className={cls('rounded px-1.5 py-0.5 text-[10px] font-medium',
                t.pnl > 0 ? 'bg-emerald-500/15 text-emerald-400' :
                t.pnl < 0 ? 'bg-red-500/15 text-red-400' :
                'bg-white/[0.08] text-tnvs-muted'
              )}>
                {t.pnl > 0 ? 'WIN' : t.pnl < 0 ? 'LOSS' : 'BE'}
              </span>
              <span className={t.pnl > 0 ? 'text-tnvs-win' : t.pnl < 0 ? 'text-tnvs-loss' : 'text-tnvs-muted'}>
                {t.pnl > 0 ? '+' : ''}${t.pnl.toFixed(2)}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
              <span>Duration: <span className="text-white">{_formatDuration(t.opened_at, t.closed_at)}</span></span>
              <span>Entry: <span className="text-white">{t.open_price.toFixed(5)}</span></span>
              <span>Close: <span className="text-white">{t.close_price != null ? t.close_price.toFixed(5) : '—'}</span></span>
              <span>SL: <span className="text-red-400">{t.sl ?? '—'}</span></span>
              <span>TP: <span className="text-green-400">{t.tp ?? '—'}</span></span>
              <span>Commission: <span className="text-white">${t.commission.toFixed(2)}</span></span>
              <span>Swap: <span className="text-white">${t.swap.toFixed(2)}</span></span>
              <span>Canal: <span className="text-white">{t.channel_title || 'Directo'}</span></span>
            </div>
            <div className="text-[10px] text-tnvs-dim">
              Abierto: {new Date(t.opened_at).toLocaleString('es-AR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
              {t.closed_at && <> · Cerrado: {new Date(t.closed_at).toLocaleString('es-AR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}</>}
            </div>
          </div>
        </div>
      )}
    </td>
  </tr>
)}
```

- [ ] **Step 4: Add the _formatDuration helper**

Add this function at module level (near `_previewFetch`, ~line 9):

```tsx
function _formatDuration(opened_at: string, closed_at: string | null): string {
  if (!closed_at) return 'Abierto';
  const start = new Date(opened_at).getTime();
  const end = new Date(closed_at).getTime();
  const diff = end - start;
  if (diff < 0) return '—';
  const hours = Math.floor(diff / 3600000);
  const minutes = Math.floor((diff % 3600000) / 60000);
  const seconds = Math.floor((diff % 60000) / 1000);
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}
```

- [ ] **Step 5: Run TypeScript check**

```bash
cd apps/frontend && npx tsc -b --noEmit
```
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add apps/frontend/src/pages/Mt5PositionsPage.tsx
git commit -m "feat: inline expand rows with chart + detail panel in Mt5PositionsPage"
```