# Roadmap de Mejoras - TNSVT V2 Architecture

## Prioridad ALTA (impacto alto, esfuerzo bajo-medio)

| # | Idea | Descripcion |
|---|------|-------------|
| 1 | **Spread Gate** | Rechazar ordenes cuando el spread > umbral configurable. Evita entradas en spreads extremos que destruyen equity. |
| 2 | **Trade Map Compaction** | Limpiar entries de tickets cerrados y >7 dias en cada startup y periodicamente. Previene memory leak. |
| 3 | **ErrorBoundary en Frontend** | Sin esto, cualquier crash en un componente tumba toda la app. Cada widget necesita su propio boundary con boton "Recargar". |
| 4 | **Skeleton Loaders** | Reemplazar "Cargando..." generico con skeletons animados que matcheen la forma de cada tarjeta. |
| 5 | **Pending Signal TTL** | Senales pendientes sin respuesta expiran en 10 min. Evita estados colgados para siempre. |
| 6 | **Persistir Partial Close Configs** | Serializar `partial_configs` a JSON. Al reiniciar no se pierden los niveles de scale-out y el monitor puede retomar cierres parciales. |

---

## Prioridad MEDIA (impacto bueno, esfuerzo mayor)

| # | Idea | Descripcion |
|---|------|-------------|
| 7 | **WebSocket Real-Time** | `WebSocket /ws/events` en bridge. Elimina polling de 5s — trades/blocked se ven instantaneamente. |
| 8 | **Circuit Breaker en API Layer** | Despues de 3 fallos consecutivos a un endpoint, pausar 30s y mostrar "unavailable". Evita cascadas de errores. |
| 9 | **Polling Adaptativo** | Reducir a 30s tras 60s de inactividad. Pausar cuando el tab esta hidden (Page Visibility API). |
| 10 | **Date Range Selector** | Filtro 7d/30d/90d/custom en byChannel/bySymbol/calendar. Actualmente fijo en 30 dias. |
| 11 | **Equity Curve Interactiva** | Tooltip SVG al hover mostrando equity/drawdown/fecha. Mini-selectores de rango 1W/1M/3M/ALL. |
| 12 | **Pending Signals por canal+simbolo** | `pending_signals[f"{chat_name}:{symbol}"]` en vez de solo `chat_name`. Permite multiples simbolos pendientes del mismo canal. |
| 13 | **Margin Level Thresholds** | Warning amber <200%, rojo <150% con toast notification. Actualmente solo rojo <=100%. |
| 14 | **Tabla de Posiciones Abiertas** | Seccion collapsible bajo account cards con: ticket, simbolo, tipo, volumen, entry, SL, TP, profit. |
| 15 | **Reset Semanal/Mensual de Risk State** | `weekly_pnl` se resetea el lunes, `monthly_pnl` el dia 1. Actualmente solo daily reset. |

---

## Prioridad BAJA (mucho esfuerzo, beneficio marginal)

| # | Idea | Descripcion |
|---|------|-------------|
| 16 | **Graceful MT5 Reconnect** | Exponential backoff en `executor.connect()` en vez de fail once. |
| 17 | **Structured Channel Registry** | Config map `{chat_id: {title, is_forum, topics[]}}` en vez de substring matching. |
| 18 | **Telethon Reconnection Handler** | Auto-reconnect si la conexion Telegram se cae. |
| 19 | **Dead-Letter Queue para Outbox** | Events en PENDING >10 retries van a `outbox_dlq`. Endpoint `GET /outbox/dlq`. |
| 20 | **Trade History List** | Lista scrollable de ultimos 20 trades clickeable para ver detalle (entry, SL, TP, P&L, commission, swap). |
| 21 | **Signal Replay Mode** | Flag CLI para re-ejecutar senales historicas desde DB (backtesting o recovery). |
| 22 | **Enforcar BRIDGE_API_KEY** | Middleware que valide `X-Bridge-Key` en todas las rutas `/api/v1/bridge/*`. |
| 23 | **Rate Limiting por Tenant** | slowapi: 100 req/min por `X-Tenant-Id`. Evita que un tenant sature el bridge. |
| 24 | **Export CSV en ChannelTable/SymbolTable** | Boton de download que exporta los datos visibles como CSV. |
| 25 | **Bot Token Telegram Usage** | O usar `BOT_TOKEN` con Bot API mode, o remover la property de settings.py (actualmente existe pero no se usa). |

---

## Issues Conocidos (no son mejoras, pero estan)

| # | Issue | Estado |
|---|-------|--------|
| A | 404s en `AppStateProvider` para endpoints V1 legacy (`/signals`, `/risk/positions`, etc) | Harmless — `safeGet` los atrapa y usa fallback. Pre-existente. |
| B | `correlation_guard` en UI no persiste — el `config.json` no tiene la key, usa env var default | Pre-existente. |
| C | Boton "Guardar" en Scale-Out se resetea si el backend no responde con `scale_out` | **FIXED** — renombrado campo `scaleout` → `scale_out` en `ConfigUpdate` Pydantic. |
| D | Multiples procesos `signal_copier/main.py` corriendo simultaneamente | Limpiar PIDs huerfanos antes de iniciar nuevo proceso. |

---

*Generado: 2026-07-24*
