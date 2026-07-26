# Spec: Fase 2 — Dense Trade History con Inline Expand

**Fecha:** 2026-07-25
**Feature:** Inline expand en Mt5PositionsPage con mini chart + detail panel

## Resumen

Al hacer click en una fila de la tabla de Mt5PositionsPage, se expande inline debajo de la fila con un mini chart M5 y un panel de detalle del trade. Sin backend nuevo — todo se computa desde `LivePosition` + `GET /bridge/trades/{ticket}/candles`.

## Comportamiento

- **Click en fila**: toggle expand. Si la fila ya está expandida, se cierra. Si se clickea otra fila, se cierra la anterior y se abre la nueva.
- **Transición**: slide down suave (max-height transition, ~200ms).
- **Datos**: se cargan lazy al expandir (candles via `api.bridge.tradeCandles(ticket)`).
- **Hover preview**: sigue funcionando independientemente del expand.

## Layout del Expand

Dos columnas dentro de la fila expandida:

| Columna izquierda (chart) | Columna derecha (detail) |
|---|---|
| Mini chart M5 (reusa `TradePreviewChart` pero inline, no fixed) | Duration: `2h 15m` |
| Mismo dark theme, entry/SL/TP markers | Entry: `1.08500` → Close: `1.08750` |
| 400×180, sin handleScroll ni handleScale | SL: `1.08000` · TP: `1.09000` |
| | P&L: `+$15.50` con badge WIN/LOSS/BE |
| | Commission: `$0.00` · Swap: `$0.00` |
| | Canal: `@canal_test` |
| | Abierto: `20/07 14:40` · Cerrado: `20/07 14:40` |

## Implementación

### Mt5PositionsPage.tsx

- Nuevo estado `expandedTicket: number | null`
- `handleRowClick(ticket)` → toggle expand, fetch candles
- Renderizar expanded row como `<tr>` adicional después de la fila clickeada, con `colSpan={columns.length}`
- Content: flex row con chart a la izquierda + detail panel a la derecha
- Detail panel: duración calculada `(closed_at - opened_at)`, badge resultado, comisión/swap, precios

### TradePreviewChart.tsx

- Agregar prop `inline?: boolean` que:
  - Si `true`: no renderiza header (symbol/M5/close button), no es fixed, tamaño 400×180
  - Si `false`/default: comportamiento actual (popover con header + close button)

### Caching

- El cache `_previewCache` ya existe — se reusa para el expand
- Al expandir, verificar cache primero; si miss, fetch via `api.bridge.tradeCandles`

## No incluye (para después)

- Timeline de ejecución (entrada → salida con timestamps)
- Partial closes / scale-out levels
- Contexto SMC (FVG, Order Block)
- Selector de timeframe

## Estados

| Estado | Qué se muestra |
|--------|---------------|
| **Cargando** | Skeleton: barra gris animada del alto del expand |
| **Sin velas** | Detail panel igual, chart placeholder "Sin velas" |
| **Trade abierto** | Duration en vivo, chart con velas hasta ahora |
| **Trade cerrado** | Duration fija, chart con entry→close |
| **Error fetch** | Detail panel igual, chart placeholder "Error al cargar" |