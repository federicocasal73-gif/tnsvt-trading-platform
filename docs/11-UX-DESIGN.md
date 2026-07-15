# UX-DESIGN.md — Diseño de Experiencia de Usuario

**Proyecto:** TNSVT V2 — Plataforma SaaS de Trading  
**Versión:** 2.0.0  
**Última Actualización:** 2026-07-14  
**Estado:** Documento de Arquitectura — Fase de Diseño  

---

## Tabla de Contenidos

1. [Filosofía de Diseño](#1-filosofía-de-diseño)
2. [Sistema de Design Tokens](#2-sistema-de-design-tokens)
3. [Panel Ejecutivo](#3-panel-ejecutivo)
4. [Panel de Trader](#4-panel-de-trader)
5. [Panel de Administración](#5-panel-de-administración)
6. [Panel de Desarrollador](#6-panel-de-desarrollador)
7. [Panel de Soporte](#7-panel-de-soporte)
8. [Estrategia de Actualizaciones en Tiempo Real](#8-estrategia-de-actualizaciones-en-tiempo-real)
9. [Biblioteca de Componentes](#9-biblioteca-de-componentes)
10. [Diseño Responsive](#10-diseño-responsive)
11. [Sistema de Temas](#11-sistema-de-temas)
12. [Tauri Desktop App](#12-tauri-desktop-app)
13. [Accesibilidad](#13-accesibilidad)
14. [Rendimiento de UI](#14-rendimiento-de-ui)
15. [Internacionalización](#15-internacionalización)

---

## 1. Filosofía de Diseño

### 1.1 Principios Fundamentales

La interfaz de TNSVT V2 está diseñada para profesionales del trading que necesitan
acceso rápido, preciso y confiable a información financiera crítica. Cada pixel
está optimizado para la toma de decisiones.

| Principio | Descripción | Ejemplo |
|-----------|-------------|---------|
| **Información > Decoración** | Los datos son la estrella, no el UI chrome | Gráficos ocupan 70% del viewport |
| **Velocidad > Hermosura** | Un chart que carga en 200ms vale más que uno perfecto en 2s | Skeleton loading, optimistic updates |
| **Consistencia > Novedad** | Patrones reconocibles reducen el tiempo de aprendizaje | Misma posición de P&L en todos los views |
| **Control > Automatización** | El trader quiere sentir que tiene el control | Toggle para cada automatización, override manual |
| **Profesional > Consumer** | No es una app de redes sociales, es una herramienta de trabajo | Tipografía densa, información compacta |

### 1.2 Wireframe Global

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ┌──┐  TNSVT V2                              🔍 Buscar  🔔 3  👤 Juan P.  │
│  │≡ │  ─────────────────────────────────────────────────────────────────────│
│  └──┘                                                                       │
│  ┌──────────┬───────────────────────────────────────────────────────────┐   │
│  │          │                                                           │   │
│  │  NAV     │                    CONTENIDO PRINCIPAL                    │   │
│  │          │                                                           │   │
│  │ 📊 Exec  │  ┌─────────────────────────────────────────────────────┐ │   │
│  │ 📈 Trade │  │                                                     │ │   │
│  │ ⚙ Admin  │  │  [Panel activo según selección del usuario]         │ │   │
│  │ 💻 Dev   │  │                                                     │ │   │
│  │ 🎧 Supp  │  │  Cada panel tiene su propio layout y componentes    │ │   │
│  │          │  │                                                     │ │   │
│  │ ─────── │  └─────────────────────────────────────────────────────┘ │   │
│  │          │                                                           │   │
│  │ 📊 42%   │  ┌─────────────────────────────────────────────────────┐ │   │
│  │ 🟢 Online│  │  STATUS BAR                                         │ │   │
│  │ ⚡ 23ms  │  │  Latencia: 23ms │ Broker: MT5 Conectado │ Sync: OK │ │   │
│  │          │  └─────────────────────────────────────────────────────┘ │   │
│  └──────────┴───────────────────────────────────────────────────────────┘   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Sistema de Design Tokens

### 2.1 Paleta de Colores

```css
/* ═══════════════════════════════════════════════════════════════
   TNSVT V2 — Design Tokens
   Trading-focused dark theme (default)
   ═══════════════════════════════════════════════════════════════ */

:root {
  /* ── Background Layers ── */
  --bg-primary:      #0a0e17;     /* Fondo principal (más oscuro) */
  --bg-secondary:    #111827;     /* Paneles, cards */
  --bg-tertiary:     #1a2235;     /* Hover states, elevated elements */
  --bg-quaternary:   #243049;     /* Tooltips, dropdowns */

  /* ── Surface Colors ── */
  --surface-card:    #151d2e;     /* Cards principales */
  --surface-input:   #0d1321;     /* Inputs, campos de texto */
  --surface-modal:   #1a2235cc;   /* Modales (con transparencia) */
  --surface-overlay: #00000080;   /* Overlays */

  /* ── Text Colors ── */
  --text-primary:    #e8edf5;     /* Texto principal */
  --text-secondary:  #8892a4;     /* Texto secundario, labels */
  --text-tertiary:   #5a6478;     /* Texto deshabilitado, hints */
  --text-inverse:    #0a0e17;     /* Texto sobre fondos claros */

  /* ── Trading Colors ── */
  --color-profit:    #00d68f;     /* Ganancias, posiciones long en profit */
  --color-loss:      #ff4757;     /* Pérdidas, posiciones en loss */
  --color-neutral:   #8892a4;     /* Sin cambio */
  --color-warning:   #ffb347;     /* Advertencias, drawdown moderado */
  --color-danger:    #ff4757;     /* Peligro, drawdown crítico */

  /* ── Accent Colors ── */
  --accent-primary:  #3b82f6;     /* Botones primarios, links */
  --accent-hover:    #2563eb;     /* Hover de primario */
  --accent-muted:    #1e40af33;   /* Background de badges */

  /* ── Chart Colors ── */
  --chart-candle-up:   #00d68f;   /* Vela alcista */
  --chart-candle-down: #ff4757;   /* Vela bajista */
  --chart-volume-up:   #00d68f4d; /* Volumen alcista */
  --chart-volume-down: #ff47574d; /* Volumen bajista */
  --chart-grid:        #1a2235;   /* Grid lines */
  --chart-crosshair:   #8892a4;   /* Crosshair */
  --chart-ma-20:       #f59e0b;   /* MA 20 períodos */
  --chart-ma-50:       #3b82f6;   /* MA 50 períodos */
  --chart-ma-200:      #8b5cf6;   /* MA 200 períodos */
  --chart-bb:          #6366f120; /* Bollinger Bands fill */
  --chart-ema-9:       #22d3ee;   /* EMA 9 */

  /* ── Border Colors ── */
  --border-subtle:   #1a2235;     /* Bordes sutiles */
  --border-default:  #243049;     /* Bordes estándar */
  --border-strong:   #374151;     /* Bordes destacados */
  --border-focus:    #3b82f6;     /* Focus ring */

  /* ── Shadows ── */
  --shadow-sm:  0 1px 2px 0 #00000040;
  --shadow-md:  0 4px 6px -1px #00000040, 0 2px 4px -2px #00000040;
  --shadow-lg:  0 10px 15px -3px #00000040, 0 4px 6px -4px #00000040;
  --shadow-xl:  0 20px 25px -5px #00000040, 0 8px 10px -6px #00000040;

  /* ── Typography ── */
  --font-sans:  'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-mono:  'JetBrains Mono', 'Fira Code', monospace;
  --font-data:  'Tabular Nums', var(--font-mono);

  /* ── Spacing Scale (4px base) ── */
  --space-1:  4px;
  --space-2:  8px;
  --space-3:  12px;
  --space-4:  16px;
  --space-5:  20px;
  --space-6:  24px;
  --space-8:  32px;
  --space-10: 40px;
  --space-12: 48px;

  /* ── Border Radius ── */
  --radius-sm:  4px;
  --radius-md:  6px;
  --radius-lg:  8px;
  --radius-xl:  12px;
  --radius-full: 9999px;

  /* ── Z-Index Scale ── */
  --z-base:      1;
  --z-dropdown:  10;
  --z-sticky:    20;
  --z-overlay:   30;
  --z-modal:     40;
  --z-toast:     50;
  --z-tooltip:   60;
}
```

### 2.2 Tipografía

| Elemento | Font | Size | Weight | Line Height | Uso |
|----------|------|------|--------|-------------|-----|
| H1 | Inter | 28px | 700 | 36px | Títulos de página |
| H2 | Inter | 22px | 600 | 28px | Secciones |
| H3 | Inter | 18px | 600 | 24px | Sub-secciones |
| Body | Inter | 14px | 400 | 20px | Texto general |
| Body Small | Inter | 12px | 400 | 16px | Labels, captions |
| Data Large | JetBrains Mono | 24px | 600 | 32px | Precio principal |
| Data Medium | JetBrains Mono | 16px | 500 | 24px | P&L, métricas |
| Data Small | JetBrains Mono | 12px | 400 | 16px | Tablas de datos |
| Mono | JetBrains Mono | 12px | 400 | 16px | Códigos, logs |

### 2.3 Iconografía

Se utiliza el set **Lucide Icons** (consistente con shadcn/ui):

| Categoría | Iconos Principales | Uso |
|-----------|-------------------|-----|
| Navegación | `LayoutDashboard`, `TrendingUp`, `Settings` | Sidebar items |
| Trading | `ArrowUpRight`, `ArrowDownRight`, `Minus` | Dirección de trades |
| Estados | `Circle` (colored), `AlertTriangle`, `Check` | Status indicators |
| Acciones | `Play`, `Pause`, `RotateCcw`, `Trash2` | Botones de acción |
| Datos | `BarChart3`, `Activity`, `Zap` | Métricas y charts |

---

## 3. Panel Ejecutivo

### 3.1 Wireframe

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  PANEL EJECUTIVO — Resumen del Portfolio                                     │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  HEADER: "Bienvenido, Juan"     Fecha: 14 Jul 2026  [Hoy] [7D] [30D] │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │
│  │ Balance      │ │ P&L Hoy     │ │ P&L Mensual │ │ Win Rate    │          │
│  │ $125,430.50 │ │ +$1,234.50  │ │ +$8,920.30  │ │ 62.3%       │          │
│  │ ▲ +2.1%     │ │ ▲ +1.2%     │ │ ▲ +7.7%     │ │ ▲ +3.1%     │          │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘          │
│                                                                              │
│  ┌─────────────────────────────────────┐ ┌──────────────────────────────┐  │
│  │                                     │ │                              │  │
│  │  GRÁFICO DE P&L ACUMULADO           │ │  DISTRIBUCIÓN POR BROKER     │  │
│  │                                     │ │                              │  │
│  │  $                                │ │  ┌──────────────────────┐    │  │
│  │  │        ╱╲    ╱╲   ╱╲           │ │  │   ◉ MT5       45%   │    │  │
│  │  │   ╱╲  ╱  ╲  ╱  ╲ ╱  ╲  ╱╲    │ │  │   ◉ cTrader   25%   │    │  │
│  │  │  ╱  ╲╱    ╲╱    ╲╱    ╲╱  ╲  │ │  │   ◉ Binance   20%   │    │  │
│  │  │ ╱                              │ │  │   ◉ IBKR      10%   │    │  │
│  │  │╱                               │ │  └──────────────────────┘    │  │
│  │  └────────────────────────────→    │ │                              │  │
│  │   Jun 1    Jun 15    Jul 1  Jul 14│ │  ┌──────────────────────┐    │  │
│  │                                     │ │  │   Por Instrumento    │    │  │
│  │  [Línea] [Area] [Candle]           │ │  │   EURUSD   35%       │    │  │
│  │                                     │ │  │   XAUUSD   25%       │    │  │
│  │                                     │ │  │   GBPUSD   20%       │    │  │
│  │                                     │ │  │   BTCUSD   15%       │    │  │
│  │                                     │ │  │   Otros     5%       │    │  │
│  └─────────────────────────────────────┘ │  └──────────────────────┘    │  │
│                                          └──────────────────────────────┘  │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  ESTRATEGIAS ACTIVAS                                                 │  │
│  │                                                                       │  │
│  │  ┌─────────────┬──────────┬────────┬────────┬────────┬───────────┐  │  │
│  │  │ Estrategia  │ Brokers  │ Trades │ Win R. │ P&L    │ Estado    │  │  │
│  │  ├─────────────┼──────────┼────────┼────────┼────────┼───────────┤  │  │
│  │  │ Trend EUR   │ MT5      │ 23     │ 65.2%  │ +$890  │ 🟢 Activa │  │  │
│  │  │ Mean Rev    │ cTrader  │ 45     │ 58.3%  │ +$420  │ 🟢 Activa │  │  │
│  │  │ Gold Scalp  │ MT5      │ 67     │ 61.2%  │ +$1,230│ 🟢 Activa │  │  │
│  │  │ BTC Swing   │ Binance  │ 8      │ 50.0%  │ -$120  │ 🟡 Pausada │  │  │
│  │  └─────────────┴──────────┴────────┴────────┴────────┴───────────┘  │  │
│  │                                                                       │  │
│  │  [+ Nueva Estrategia]                                                 │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌─────────────────────────────────────┐ ┌──────────────────────────────┐  │
│  │  ÚLTIMOS TRADES                     │ │  ALERTAS RECIENTES           │  │
│  │                                     │ │                              │  │
│  │  ✅ BUY EURUSD +$45.20  10:23     │ │  ⚠ Drawdown 3.2% (Gold)     │  │
│  │  ✅ SELL GBPUSD +$23.10  10:15    │ │  📊 Regime: Ranging (EURUSD) │  │
│  │  ❌ BUY XAUUSD -$32.00  10:01    │ │  🤖 Score: 82 (BUY signal)   │  │
│  │  ✅ SELL BTCUSD +$156.40  09:45  │ │  ⚡ Anomaly: Volume spike    │  │
│  │  ✅ BUY EURUSD +$67.30  09:30    │ │  📈 Overtrading risk: low    │  │
│  │                                     │ │                              │  │
│  │  [Ver Historial Completo →]         │ │  [Ver Todas las Alertas →]   │  │
│  └─────────────────────────────────────┘ └──────────────────────────────┘  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Componentes del Panel Ejecutivo

| Componente | Datos | Actualización | Fuente |
|------------|-------|---------------|--------|
| Balance Card | Balance total, cambio % | Cada 5s | Trading Core |
| P&L Chart | P&L acumulado diario | Cada 1s (tick) | Trading Core |
| Broker Distribution | % por broker | Cada 30s | Portfolio Aggregator |
| Active Strategies | Tabla de estrategias | Cada 10s | Strategy Engine |
| Recent Trades | Últimos 5 trades | Tiempo real (NATS) | Trade Stream |
| Alerts Feed | Alertas recientes | Tiempo real (SSE) | Alert Service |

### 3.3 Métricas Clave del Dashboard

```typescript
interface ExecutiveMetrics {
  balance: {
    total: number;
    change_24h: number;
    change_24h_pct: number;
    currency: string;
  };
  pnl: {
    today: number;
    today_pct: number;
    week: number;
    month: number;
    year: number;
    max_drawdown: number;
    max_drawdown_pct: number;
  };
  trading: {
    total_trades_today: number;
    win_rate: number;
    profit_factor: number;
    sharpe_ratio: number;
    avg_trade_duration: string;
  };
  risk: {
    portfolio_heat: number;
    margin_used_pct: number;
    free_margin: number;
    max_positions: number;
    active_positions: number;
  };
}
```

---

## 4. Panel de Trader

### 4.1 Wireframe

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  PANEL DE TRADER — Vista de Operaciones en Tiempo Real                       │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ TOOLBAR: [EURUSD ▼] [M1] [M5] [M15] [H1] [H4] [D1] [W1]  │ 📊 📐 ⚙ │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌──────────────────────────────────────────────┐ ┌──────────────────────┐  │
│  │                                              │ │                      │  │
│  │  ┌────────────────────────────────────────┐  │ │  POSICIONES ACTIVAS  │  │
│  │  │                                        │  │ │                      │  │
│  │  │                                        │  │ │  BUY EURUSD 1.0 lot  │  │
│  │  │         CHART PRINCIPAL                 │  │ │  Entry: 1.0850      │  │
│  │  │         (TradingView Lightweight)       │  │ │  Current: 1.0872    │  │
│  │  │                                        │  │ │  P&L: +$220.00 🟢   │  │
│  │  │  Candlesticks + Volume + Indicadores   │  │ │  SL: 1.0820 TP:1.0950│  │
│  │  │                                        │  │ │  [Close] [Modify]   │  │
│  │  │  Indicadores:                          │  │ │─────────────────────│  │
│  │  │  • MA 20 (amarillo)                    │  │ │  SELL GBPUSD 0.5 lot│  │
│  │  │  • MA 50 (azul)                        │  │ │  Entry: 1.2750      │  │
│  │  │  • Bollinger Bands (violeta)           │  │ │  Current: 1.2735    │  │
│  │  │  • RSI (panel inferior)                │  │ │  P&L: +$75.00 🟢    │  │
│  │  │  • Volume (panel inferior)             │  │ │  SL: 1.2800 TP:1.2650│  │
│  │  │                                        │  │ │  [Close] [Modify]   │  │
│  │  │                                        │  │ │─────────────────────│  │
│  │  │                                        │  │ │  BUY XAUUSD 0.1 lot │  │
│  │  │  ─────────────────────────────         │  │ │  Entry: 2,420.50    │  │
│  │  │  RSI: 62.3  │  ATR: 0.0015            │  │ │  Current: 2,418.30  │  │
│  │  └────────────────────────────────────────┘  │ │  P&L: -$22.00 🔴    │  │
│  │                                              │ │  SL: 2,400 TP:2,450 │  │
│  │  ┌────────────────────────────────────────┐  │ │  [Close] [Modify]   │  │
│  │  │  ORDER ENTRY                           │  │ │                      │  │
│  │  │                                        │  │ │  Total P&L: +$273.00│  │
│  │  │  Tipo: [BUY ▼]  Volumen: [1.0]        │  │ │  Margin: 12.3%      │  │
│  │  │  SL: [1.0820]  TP: [1.0950]           │  │ │                      │  │
│  │  │  Trailing: [20 pips ▼]                 │  │ └──────────────────────┘  │
│  │  │                                        │  │                           │
│  │  │  [🔴 SELL]  [🟢 BUY]  [⚡ MARKET]     │  │ ┌──────────────────────┐  │
│  │  │                                        │  │ │  AI SIGNAL FEED      │  │
│  │  └────────────────────────────────────────┘  │ │                      │  │
│  │                                              │ │  10:23 🟢 Score: 82  │  │
│  │  ┌────────────────────────────────────────┐  │ │  BUY EURUSD          │  │
│  │  │  RISK PANEL                            │  │ │  Regime: TRENDING_UP │  │
│  │  │                                        │  │ │  Conf: 87%           │  │
│  │  │  ┌──────────┬──────────┬──────────┐   │  │ │  [Execute] [Details] │  │
│  │  │  │ Drawdown │ Margin   │ Heat     │   │  │ │──────────────────────│  │
│  │  │  │ -3.2%    │ 12.3%    │ 42%      │   │  │ │ 10:15 🟡 Score: 55  │  │
│  │  │  │ █████░░░ │ █░░░░░░░ │ ████░░░░ │   │  │ │  SELL GBPUSD         │  │
│  │  │  └──────────┴──────────┴──────────┘   │  │ │  Regime: RANGING     │  │
│  │  │                                        │  │ │  Conf: 60%           │  │
│  │  │  [⏸ PAUSAR TODO]  [❌ CERRAR TODO]    │  │ │  [Execute] [Details] │  │
│  │  └────────────────────────────────────────┘  │ │──────────────────────│  │
│  │                                              │ │ 09:45 🔴 Score: 23  │  │
│  └──────────────────────────────────────────────┘ │  REJECTED            │  │
│                                                   │  BUY XAUUSD          │  │
│                                                   │  Anomaly detected    │  │
│                                                   │  [Why?]              │  │
│                                                   └──────────────────────┘  │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ TRADE HISTORY ──────────────────────────────────────────────────────  │ │
│  │                                                                       │ │
│  │  ┌──────┬────┬───────┬────────┬────────┬────────┬────────┬────────┐ │ │
│  │  │ Hora │Act │ Instrument│ Entry │ Exit   │ P&L    │ Dur.   │ Score  │ │ │
│  │  ├──────┼────┼───────┼────────┼────────┼────────┼────────┼────────┤ │ │
│  │  │ 10:23│BUY │ EURUSD │1.0850  │1.0872  │+$220   │ 45min  │ 82     │ │ │
│  │  │ 10:15│SELL│ GBPUSD │1.2750  │1.2735  │+$75    │ 30min  │ 55     │ │ │
│  │  │ 10:01│BUY │ XAUUSD │2420.50 │2418.30 │-$220   │ 15min  │ 34     │ │ │
│  │  └──────┴────┴───────┴────────┴────────┴────────┴────────┴────────┘ │ │
│  │                                                                       │ │
│  │  [Exportar CSV] [Filtros ▼] [Paginación: 1-25 de 342]               │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Panel de Trader — Especificaciones

| Sección | Tamaño Mínimo | Responsive | Datos en Tiempo Real |
|---------|---------------|------------|---------------------|
| Chart | 60% width, 400px height | Colapsa debajo en mobile | Sí (WebSocket) |
| Positions Panel | 300px width | Bottom sheet en mobile | Sí (NATS → SSE) |
| Order Entry | 300px width | Full width en mobile | No (on-demand) |
| Risk Panel | 200px height | Inline en mobile | Sí (cada 5s) |
| AI Signal Feed | 280px width | Drawer en mobile | Sí (NATS → SSE) |
| Trade History | Full width bottom | Scrollable table | No (polling 10s) |

### 4.3 Keyboard Shortcuts (Trader Panel)

| Atajo | Acción | Modificable |
|-------|--------|-------------|
| `Ctrl + B` | Abrir orden BUY | Sí |
| `Ctrl + S` | Abrir orden SELL | Sí |
| `Ctrl + K` | Cambiar instrumento | Sí |
| `Ctrl + 1-6` | Cambiar timeframe | Sí |
| `Ctrl + L` | Toggle positions panel | No |
| `Ctrl + T` | Toggle AI signals | No |
| `Ctrl + P` | Toggle risk panel | No |
| `Escape` | Cerrar panel activo | No |
| `Space` | Toggle chart crosshair | No |
| `Delete` | Cerrar posición seleccionada | Sí (requiere confirmación) |

---

## 5. Panel de Administración

### 5.1 Wireframe

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  PANEL DE ADMINISTRACIÓN — Gestión del Sistema                               │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────┬────────────────────────────────────────────────────────────┐  │
│  │          │                                                            │  │
│  │  SUBNAV  │  CONTENIDO (cambia según sub-sección)                     │  │
│  │          │                                                            │  │
│  │ 👥 Users │  ┌────────────────────────────────────────────────────┐   │  │
│  │ 🏢 Tenants│  │ Usuarios: 487 activos / 512 total                 │   │  │
│  │ 💳 Billing│  │                                                    │   │  │
│  │ 🖥 System │  │ Buscar: [___________________] [Filtro ▼] [Exportar]│   │  │
│  │ 📊 Health │  │                                                    │   │  │
│  │ 🔒 Audit  │  │ ┌────┬──────────┬────────┬────────┬────────┬────┐ │   │  │
│  │          │  │ │ #  │ Nombre   │ Email  │ Plan   │ Status │Act.│ │   │  │
│  │          │  │ ├────┼──────────┼────────┼────────┼────────┼────┤ │   │  │
│  │          │  │ │ 1  │ Juan P.  │ jp@... │ Pro    │ 🟢 Act │ 12 │ │   │  │
│  │          │  │ │ 2  │ María L. │ ml@... │ Entepr │ 🟢 Act │  8 │ │   │  │
│  │          │  │ │ 3  │ Carlos R │ cr@... │ Basic  │ 🟡 Sus │  3 │ │   │  │
│  │          │  │ │ 4  │ Ana M.   │ am@... │ Pro    │ 🔴 Ban │  0 │ │   │  │
│  │          │  │ └────┴──────────┴────────┴────────┴────────┴────┘ │   │  │
│  │          │  │                                                    │   │  │
│  │          │  │ [← 1 2 3 ... 10 →]  Mostrando 1-25 de 487        │   │  │
│  │          │  └────────────────────────────────────────────────────┘   │  │
│  │          │                                                            │  │
│  └──────────┴────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  SYSTEM HEALTH (si se selecciona "System Health")                    │  │
│  │                                                                       │  │
│  │  ┌──────────────┬──────────────┬──────────────┬──────────────┐      │  │
│  │  │ API Gateway   │ Trading Core │ AI Core      │ Database     │      │  │
│  │  │ 🟢 Healthy    │ 🟢 Healthy   │ 🟡 Degraded  │ 🟢 Healthy   │      │  │
│  │  │ CPU: 34%      │ CPU: 56%     │ GPU: 87%     │ CPU: 12%     │      │  │
│  │  │ RAM: 2.1 GB   │ RAM: 4.3 GB  │ RAM: 28 GB   │ Conn: 45/100 │      │  │
│  │  │ Uptime: 14d   │ Uptime: 14d  │ Uptime: 2d   │ Uptime: 30d  │      │  │
│  │  │ Lat: 23ms     │ Lat: 8ms     │ Lat: 48ms    │ Lat: 2ms     │      │  │
│  │  └──────────────┴──────────────┴──────────────┴──────────────┘      │  │
│  │                                                                       │  │
│  │  ┌──────────────┬──────────────┬──────────────┬──────────────┐      │  │
│  │  │ NATS          │ Redis        │ Ollama       │ Traefik      │      │  │
│  │  │ 🟢 Healthy    │ 🟢 Healthy   │ 🟢 Healthy   │ 🟢 Healthy   │      │  │
│  │  │ Msg/s: 12.4K  │ Mem: 1.2 GB  │ Models: 4    │ Req/s: 8.2K │      │  │
│  │  │ Queue: 0      │ Hit: 94%     │ GPU: 67%     │ Active: 234  │      │  │
│  │  └──────────────┴──────────────┴──────────────┴──────────────┘      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Funcionalidades de Admin

| Sección | Funcionalidades | Permisos Requeridos |
|---------|----------------|---------------------|
| **Users** | CRUD usuarios, asignar roles, suspender/activar, reset password | `admin:users:*` |
| **Tenants** | Gestionar planes, límites, facturación, configuración | `admin:tenants:*` |
| **Billing** | Ver suscripciones, procesar pagos, generar facturas | `admin:billing:read` |
| **System Health** | Status de servicios, métricas, logs en vivo | `admin:system:read` |
| **Audit** | Logs de actividad, exportar para compliance | `admin:audit:read` |
| **Configuration** | Parámetros globales, feature flags, maintenance mode | `admin:config:*` |

---

## 6. Panel de Desarrollador

### 6.1 Wireframe

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  PANEL DE DESARROLLADOR — API y Monitoreo                                    │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────┬────────────────────────────────────────────────────────────┐  │
│  │          │                                                            │  │
│  │  SUBNAV  │  ┌────────────────────────────────────────────────────┐   │  │
│  │          │  │ API DOCUMENTATION (OpenAPI / Swagger)               │   │  │
│  │ 📚 API   │  │                                                    │   │  │
│  │ 📋 Logs  │  │  GET  /api/v2/portfolio          [200]  23ms      │   │  │
│  │ 🖥 Status │  │  GET  /api/v2/positions           [200]  18ms      │   │  │
│  │ 🚀 Deploy│  │  POST /api/v2/orders              [201]  45ms      │   │  │
│  │ 🔑 Keys  │  │  GET  /api/v2/signals             [200]  12ms      │   │  │
│  │          │  │  GET  /api/v2/ai/insights          [200]  890ms     │   │  │
│  │          │  │  WS   /ws/market/{instrument}     [101]  5ms       │   │  │
│  │          │  │                                                    │   │  │
│  │          │  │  [Try it out] [Download OpenAPI spec]              │   │  │
│  │          │  └────────────────────────────────────────────────────┘   │  │
│  │          │                                                            │  │
│  │          │  ┌────────────────────────────────────────────────────┐   │  │
│  │          │  │ LIVE LOGS (últimas 100 entradas)                   │   │  │
│  │          │  │                                                    │   │  │
│  │          │  │ 10:23:45 INFO  api-gateway   GET /api/v2/portfolio │   │  │
│  │          │  │ 10:23:45 INFO  trading-core  Position update       │   │  │
│  │          │  │ 10:23:46 DEBUG ai-core        Signal scored: 82    │   │  │
│  │          │  │ 10:23:46 INFO  trading-core  Order executed: #4521 │   │  │
│  │          │  │ 10:23:47 WARN  ai-core        High GPU usage 87%   │   │  │
│  │          │  │ 10:23:48 INFO  nats           Message published    │   │  │
│  │          │  │                                                    │   │  │
│  │          │  │ [▶️ Follow] [🔍 Filter] [📥 Export] [⏸ Pause]      │   │  │
│  │          │  └────────────────────────────────────────────────────┘   │  │
│  └──────────┴────────────────────────────────────────────────────────────┘  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Endpoints Monitoreados

| Endpoint | Latencia Objetivo | SLA Uptime | Rate Limit |
|----------|-------------------|------------|------------|
| `GET /api/v2/portfolio` | < 50ms p99 | 99.95% | 100 req/s |
| `GET /api/v2/positions` | < 30ms p99 | 99.99% | 100 req/s |
| `POST /api/v2/orders` | < 100ms p99 | 99.99% | 50 req/s |
| `GET /api/v2/signals` | < 20ms p99 | 99.95% | 200 req/s |
| `GET /api/v2/ai/insights` | < 2s p99 | 99.5% | 10 req/s |
| `WS /ws/market/*` | < 10ms | 99.99% | 1 conn/user |

---

## 7. Panel de Soporte

### 7.1 Wireframe

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  PANEL DE SOPORTE — Atención al Cliente                                      │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────┬────────────────────────────────────────────────────────────┐  │
│  │          │                                                            │  │
│  │  SUBNAV  │  TICKETS ACTIVOS: 23  │  RESUELTOS HOY: 12  │  SLA: 94% │  │
│  │          │                                                            │  │
│  │ 🎫 Tickets│  ┌────────────────────────────────────────────────────┐   │  │
│  │ 📢 Alerts │  │ Filtrar: [Todos ▼] [Hoy] [Esta Semana] [Exportar] │   │  │
│  │ 📚 KB    │  │                                                    │   │  │
│  │          │  │ ┌────┬──────┬─────────┬─────────┬────────┬───────┐ │   │  │
│  │          │  │ │ #  │User  │ Asunto  │Prioridad│Estado  │Tiempo │ │   │  │
│  │          │  │ ├────┼──────┼─────────┼─────────┼────────┼───────┤ │   │  │
│  │          │  │ │ 487│Juan P│ No abre │ 🔴 Alta │ Abierto│ 15min │ │   │  │
│  │          │  │ │ 486│María L│ Login   │ 🟡 Med  │ En prog│ 32min │ │   │  │
│  │          │  │ │ 485│Carlos│ Balance │ 🟢 Baja │ Resuelto│ 2h   │ │   │  │
│  │          │  │ └────┴──────┴─────────┴─────────┴────────┴───────┘ │   │  │
│  │          │  └────────────────────────────────────────────────────┘   │  │
│  │          │                                                            │  │
│  │          │  ┌────────────────────────────────────────────────────┐   │  │
│  │          │  │ SYSTEM ALERTS                                      │   │  │
│  │          │  │                                                    │   │  │
│  │          │  │ 🔴 AI Core GPU > 95% (desde hace 5 min)           │   │  │
│  │          │  │ 🟡 3 usuarios con login failures > 5              │   │  │
│  │          │  │ 🟡 Broker MT5 latency > 200ms (últimos 10 min)    │   │  │
│  │          │  │ 🟢 Backup completado exitosamente (02:00 UTC)      │   │  │
│  │          │  │ 🟢 SSL certificate renewal: 28 días restantes      │   │  │
│  │          │  └────────────────────────────────────────────────────┘   │  │
│  └──────────┴────────────────────────────────────────────────────────────┘  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Estrategia de Actualizaciones en Tiempo Real

### 8.1 Arquitectura de Comunicación

```
┌──────────────────────────────────────────────────────────────────────────────┐
│              REAL-TIME UPDATE ARCHITECTURE                                     │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    NATS     ┌──────────────┐     SSE      ┌────────────┐ │
│  │ Trading Core │───────────→ │ API Gateway  │────────────→ │ Browser    │ │
│  │ (events)     │            │ (transforms) │              │ (UI React) │ │
│  └──────────────┘            └──────────────┘              └────────────┘ │
│                                                                              │
│  Canales de Comunicación:                                                    │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Protocolo: Server-Sent Events (SSE) — unidireccional, server→client  │ │
│  │                                                                        │ │
│  │ Rutas SSE:                                                            │ │
│  │ GET /api/v2/sse/portfolio/{tenant_id}                                │ │
│  │   → balance, pnl, margin updates (cada 5s)                           │ │
│  │                                                                        │ │
│  │ GET /api/v2/sse/positions/{tenant_id}                                │ │
│  │   → open positions, P&L changes (cada 1s)                            │ │
│  │                                                                        │ │
│  │ GET /api/v2/sse/signals/{tenant_id}                                  │ │
│  │   → AI signal scores, trade executions (tiempo real)                 │ │
│  │                                                                        │ │
│  │ GET /api/v2/sse/market/{instrument}                                  │ │
│  │   → OHLCV updates, order book changes (tiempo real)                  │ │
│  │                                                                        │ │
│  │ GET /api/v2/sse/alerts/{tenant_id}                                   │ │
│  │   → system alerts, overtrading warnings, anomalies (tiempo real)     │ │
│  │                                                                        │ │
│  │ Reconnection: auto-reconnect con exponential backoff (1s, 2s, 4s...)  │ │
│  │ Heartbeat: cada 30s para mantener conexión viva                       │ │
│  │ Buffer: Últimos 50 eventos para reconexión                           │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ WebSocket — Bidireccional (solo para chart en tiempo real)            │ │
│  │                                                                        │ │
│  │ WS /ws/market/{instrument}                                            │ │
│  │   → Client envía: subscribe, unsubscribe, timeframe_change           │ │
│  │   → Server envía: tick, ohlcv, orderbook, trade                      │ │
│  │                                                                        │ │
│  │ Usado exclusivamente para el chart de trading                         │ │
│  │ y datos de mercado de alta frecuencia                                 │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Estrategia de Reactividad en el Frontend

```typescript
// Zustand store con suscripciones SSE
interface TradingStore {
  // Estado
  positions: Position[];
  signals: Signal[];
  balance: Balance;
  alerts: Alert[];
  
  // Conexiones
  sseConnections: Map<string, EventSource>;
  wsConnection: WebSocket | null;
  
  // Acciones
  connectSSE: (channel: string) => void;
  disconnectSSE: (channel: string) => void;
  connectWS: (instrument: string) => void;
  
  // Optimistic updates
  optimisticUpdate: (action: OrderAction) => void;
  rollbackOptimistic: (transactionId: string) => void;
}

// Batch updates para evitar re-renders excesivos
const BATCH_INTERVAL = 100; // ms

function useSSEBatch(channel: string) {
  const buffer = useRef<Event[]>([]);
  
  useEffect(() => {
    const eventSource = new EventSource(`/api/v2/sse/${channel}`);
    
    eventSource.onmessage = (event) => {
      buffer.current.push(JSON.parse(event.data));
    };
    
    // Flush buffer cada 100ms para agrupar updates
    const interval = setInterval(() => {
      if (buffer.current.length > 0) {
        useStore.getState().batchUpdate(channel, buffer.current);
        buffer.current = [];
      }
    }, BATCH_INTERVAL);
    
    return () => {
      clearInterval(interval);
      eventSource.close();
    };
  }, [channel]);
}
```

---

## 9. Biblioteca de Componentes

### 9.1 Stack Tecnológico

| Capa | Tecnología | Versión |
|------|-----------|---------|
| Framework | Next.js (App Router) | 14+ |
| UI Library | React | 18+ |
| Componentes Base | shadcn/ui | Latest |
| Estilos | Tailwind CSS | 3.4+ |
| State Management | Zustand | 4+ |
| Charts | Lightweight Charts (TradingView) | 4+ |
| Tables | TanStack Table | 8+ |
| Forms | React Hook Form + Zod | Latest |
| Animations | Framer Motion | 11+ |
| Icons | Lucide React | Latest |

### 9.2 Componentes Custom de Trading

| Componente | Descripción | Props Principales |
|------------|-------------|-------------------|
| `<CandlestickChart>` | Chart de velas con indicadores | `data`, `indicators[]`, `timeframe` |
| `<OrderBook>` | Libro de órdenes bid/ask | `bids[]`, `asks[]`, `depth` |
| `<PositionCard>` | Tarjeta de posición abierta | `position`, `onClose`, `onModify` |
| `<SignalFeed>` | Feed de señales AI en tiempo real | `signals[]`, `onExecute` |
| `<PnLChart>` | Gráfico de P&L acumulado | `data[]`, `period`, `breakdown` |
| `<RiskGauge>` | Indicador de riesgo visual | `level`, `drawdown`, `heat` |
| `<OrderEntry>` | Formulario de nueva orden | `instrument`, `onSubmit` |
| `<RegimeIndicator>` | Badge de régimen de mercado | `regime`, `confidence` |
| `<ScoreBadge>` | Badge de score AI | `score`, `action` |
| `<SpreadDisplay>` | Display de spread actual | `spread`, `pctChange` |
| `<TickerBar>` | Barra de precios en vivo | `instruments[]` |
| `<HeatMap>` | Mapa de calor de mercados | `data[][]`, `colorScale` |

### 9.3 Componente de Ejemplo: PositionCard

```tsx
// src/components/trading/PositionCard.tsx
"use client";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface PositionCardProps {
  symbol: string;
  type: "BUY" | "SELL";
  volume: number;
  entryPrice: number;
  currentPrice: number;
  pnl: number;
  pnlPct: number;
  stopLoss?: number;
  takeProfit?: number;
  duration: string;
  onClose: () => void;
  onModify: () => void;
}

export function PositionCard({
  symbol, type, volume, entryPrice, currentPrice,
  pnl, pnlPct, stopLoss, takeProfit, duration,
  onClose, onModify,
}: PositionCardProps) {
  const isProfit = pnl >= 0;

  return (
    <Card className="p-3 border-border-subtle bg-surface-card">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Badge variant={type === "BUY" ? "profit" : "loss"}>
            {type}
          </Badge>
          <span className="font-mono font-semibold text-text-primary">
            {symbol}
          </span>
          <span className="text-text-secondary text-xs">
            {volume} lot
          </span>
        </div>
        <span className="text-text-tertiary text-xs">{duration}</span>
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs font-mono">
        <div>
          <span className="text-text-secondary">Entry</span>
          <span className="text-text-primary ml-2">{entryPrice}</span>
        </div>
        <div>
          <span className="text-text-secondary">Current</span>
          <span className="text-text-primary ml-2">{currentPrice}</span>
        </div>
      </div>

      <div className="mt-2 flex items-center justify-between">
        <span
          className={cn(
            "text-lg font-mono font-bold",
            isProfit ? "text-color-profit" : "text-color-loss"
          )}
        >
          {isProfit ? "+" : ""}${pnl.toFixed(2)}
          <span className="text-xs ml-1">
            ({isProfit ? "+" : ""}{pnlPct.toFixed(2)}%)
          </span>
        </span>
      </div>

      <div className="mt-3 flex gap-2">
        <Button variant="destructive" size="sm" onClick={onClose}>
          Cerrar
        </Button>
        <Button variant="outline" size="sm" onClick={onModify}>
          Modificar
        </Button>
      </div>
    </Card>
  );
}
```

---

## 10. Diseño Responsive

### 10.1 Breakpoints

| Breakpoint | Ancho | Layout | Uso |
|------------|-------|--------|-----|
| `xs` | < 640px | Mobile portrait | Funcionalidad mínima, notifications |
| `sm` | 640-767px | Mobile landscape | Dashboard básico |
| `md` | 768-1023px | Tablet portrait | Panel ejecutivo completo |
| `lg` | 1024-1279px | Tablet landscape | Trader panel funcional |
| `xl` | 1280-1535px | Desktop | Vista completa |
| `2xl` | ≥ 1536px | Desktop wide | Multi-panel layout |

### 10.2 Estrategia por Panel

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    RESPONSIVE LAYOUT STRATEGY                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  MOBILE (< 768px)                                                           │
│  ┌──────────────────────┐                                                   │
│  │ ☰  TNSVT   🔔 👤    │  ← Header colapsado                               │
│  ├──────────────────────┤                                                   │
│  │                      │                                                   │
│  │  ┌────────────────┐  │  ← Dashboard: cards apilados                      │
│  │  │ Balance Card   │  │                                                   │
│  │  └────────────────┘  │                                                   │
│  │  ┌────────────────┐  │                                                   │
│  │  │ P&L Card       │  │                                                   │
│  │  └────────────────┘  │                                                   │
│  │  ┌────────────────┐  │                                                   │
│  │  │ Positions      │  │  ← Posiciones: scroll horizontal                  │
│  │  │ [← →] scroll   │  │                                                   │
│  │  └────────────────┘  │                                                   │
│  │                      │                                                   │
│  │  Bottom Nav Bar      │  ← Navegación inferior                            │
│  │  [📊][📈][⚙][💻][🎧]│                                                   │
│  └──────────────────────┘                                                   │
│                                                                              │
│  TABLET (768-1023px)                                                        │
│  ┌────────────────────────────────┐                                         │
│  │  TNSVT          🔔 3  👤 Juan │                                         │
│  ├──────┬─────────────────────────┤                                         │
│  │ Nav  │  ┌──────────┬────────┐ │  ← Dos columnas                          │
│  │      │  │ Chart    │ Trades │ │                                         │
│  │ 📊   │  │ (60%)    │ (40%)  │ │                                         │
│  │ 📈   │  │          │        │ │                                         │
│  │ ⚙    │  └──────────┴────────┘ │                                         │
│  │ 💻   │  ┌────────────────────┐ │                                         │
│  │ 🎧   │  │ Positions Table    │ │                                         │
│  │      │  └────────────────────┘ │                                         │
│  └──────┴─────────────────────────┘                                         │
│                                                                              │
│  DESKTOP (≥ 1280px)                                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  TNSVT                    🔔 3  🤖 AI:Active  👤 Juan P. Admin      │   │
│  ├──────┬──────────────────────────────────────────────────────────────┤   │
│  │ Nav  │  ┌──────────────────────┬──────────┬──────────┐             │   │
│  │      │  │                      │ Positions│ AI       │             │   │
│  │ 📊   │  │     Chart (50%)      │ (25%)    │ Signals  │             │   │
│  │ 📈   │  │                      │          │ (25%)    │             │   │
│  │ ⚙    │  ├──────────────────────┴──────────┴──────────┤             │   │
│  │ 💻   │  │  Order Entry + Risk Panel + Trade History   │             │   │
│  │ 🎧   │  └────────────────────────────────────────────┘             │   │
│  │      │                                                              │   │
│  │  ──  │  Status Bar: Latencia | Broker | Sync | GPU                  │   │
│  └──────┴──────────────────────────────────────────────────────────────┘   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 10.3 Componentes Adaptativos

| Componente | Mobile | Tablet | Desktop |
|------------|--------|--------|---------|
| Navigation | Bottom bar | Sidebar collapsed | Sidebar expanded |
| Chart | Full width, tap to expand | 60% column | 50% multi-panel |
| Positions | Horizontal scroll cards | Table (compact) | Table (full) |
| Order Entry | Full screen modal | Side panel | Inline panel |
| AI Signals | Bottom drawer | Right column | Right column |
| Trade History | Stacked list | Compact table | Full table |
| Risk Panel | Collapsible section | Compact bar | Full panel |

---

## 11. Sistema de Temas

### 11.1 Temas Disponibles

| Temo | Descripción | Default |
|------|-------------|---------|
| `dark` | Tema oscuro para trading (profesional) | **Sí** |
| `light` | Tema claro (para uso diurno) | No |
| `midnight` | Tema ultra-oscuro (AMOLED-friendly) | No |
| `high-contrast` | Alto contraste (accesibilidad) | No |

### 11.2 Cambio de Tema

```typescript
// El tema se almacena en localStorage y se aplica instantáneamente
// No hay flash de contenido no temático (FOUC)

// next.config.js - Tema se aplica en SSR
// Se usa un script inline en <head> que lee localStorage
// y aplica la clase antes del render

// Cambio de tema:
function useTheme() {
  const { theme, setTheme } = useThemeStore();
  
  useEffect(() => {
    document.documentElement.classList.remove(
      'theme-dark', 'theme-light', 'theme-midnight', 'theme-high-contrast'
    );
    document.documentElement.classList.add(`theme-${theme}`);
    localStorage.setItem('tnsvt-theme', theme);
  }, [theme]);
  
  return { theme, setTheme };
}
```

### 11.3 Tema Dark — Especificaciones

El tema dark está diseñado específicamente para trading profesional:

- **Contraste WCAG AAA** para texto de datos financieros (ratio ≥ 7:1)
- **Colores de P&L** altamente distinguibles (verde vs rojo con diferenciación tonal)
- **Sin luz azul excesiva** — tonos neutros fríos para reducir fatiga ocular
- **Mapas de calor** con escala perceptivamente uniforme (viridis)
- **Charts** con contraste optimizado sobre fondo oscuro

---

## 12. Tauri Desktop App

### 12.1 Diferencias vs Web

| Característica | Web (Next.js) | Desktop (Tauri) |
|---------------|---------------|-----------------|
| **Rendering** | React + SSR | React (sin SSR) |
| **Storage** | localStorage, cookies | SQLite local + filesystem |
| **Notificaciones** | Browser notifications | Notificaciones nativas del OS |
| **Tray Icon** | No disponible | Sí, con menú contextual |
| **Auto-start** | No | Sí, al iniciar el sistema |
| **System Monitor** | No | CPU, RAM, GPU del sistema |
| **Hotkeys Globales** | Limitadas por navegador | Completas, a nivel de OS |
| **Multi-monitor** | Limitado por browser | Soporte completo |
| **Offline Mode** | Limitado (cache) | Datos históricos locales |
| **File System** | No | Acceso completo (sandboxed) |
| **WebSocket nativo** | Sí | Sí (mejor rendimiento) |
| **Actualizaciones** | Auto (refresh) | Auto-update via Tauri updater |
| **Tamaño** | N/A | ~5-10 MB (Rust binary) |

### 12.2 Arquitectura Tauri

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    TAURI DESKTOP APP ARCHITECTURE                             │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    FRONTEND (WebView2 / WebKit)                       │   │
│  │                                                                        │   │
│  │  ┌──────────────────────────────────────────────────────────────┐    │   │
│  │  │ React App (misma codebase que web)                            │    │   │
│  │  │                                                                │    │   │
│  │  │ Diferencias detectadas:                                        │    │   │
│  │  │ • isDesktop = true (habilita features desktop)                │    │   │
│  │  │ • useTauri() hook para funciones nativas                     │    │   │
│  │  │ • SQLite local para cache offline                            │    │   │
│  │  │ • System tray integration                                     │    │   │
│  │  │ • Global hotkeys registration                                 │    │   │
│  │  └──────────────────────────────────────────────────────────────┘    │   │
│  └──────────────────────────────┬───────────────────────────────────────┘   │
│                                 │                                           │
│                                 │ Tauri IPC (invoke / listen)               │
│                                 │                                           │
│  ┌──────────────────────────────▼───────────────────────────────────────┐   │
│  │                    BACKEND (Rust)                                      │   │
│  │                                                                        │   │
│  │  ┌────────────────────────────────────────────────────────────────┐  │   │
│  │  │  Core Modules (Rust)                                            │  │   │
│  │  │                                                                  │  │   │
│  │  │  • local_db: SQLite storage for offline cache                   │  │   │
│  │  │  • notifications: OS-native notification system                 │  │   │
│  │  │  • tray: System tray with real-time P&L display                │  │   │
│  │  │  • hotkeys: Global keyboard shortcuts                           │  │   │
│  │  │  • auto_updater: Seamless version updates                      │  │   │
│  │  │  • deep_link: tnsvt:// protocol handler                        │  │   │
│  │  │  • file_export: CSV/PDF report generation                      │  │   │
│  │  │  • screenshot: Chart capture and sharing                       │  │   │
│  │  │  • system_info: Hardware monitoring for AI Core                │  │   │
│  │  └────────────────────────────────────────────────────────────────┘  │   │
│  │                                                                        │   │
│  │  ┌────────────────────────────────────────────────────────────────┐  │   │
│  │  │  Security Layer (Rust)                                          │  │   │
│  │  │                                                                  │  │   │
│  │  │  • Capabilities: Scoped permissions per window                  │  │   │
│  │  │  • IPC: All calls whitelisted in tauri.conf.json               │  │   │
│  │  │  • Updates: Ed25519 signed release bundles                     │  │   │
│  │  │  • Data: Encrypted local storage (AES-256-GCM)                 │  │   │
│  │  └────────────────────────────────────────────────────────────────┘  │   │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 12.3 Funcionalidades Exclusivas Desktop

| Funcionalidad | Descripción | Implementación |
|---------------|-------------|----------------|
| **Tray con P&L** | Muestra P&L en tiempo real en la bandeja del sistema | Rust tray crate |
| **Alertas sonoras** | Sonidos personalizables para trades y anomalías | OS audio API |
| **Multi-monitor** | Posicionar charts en diferentes pantallas | Window management |
| **Hotkeys globales** | Funcionan incluso cuando la app no está en foco | OS global shortcuts |
| **Exportación rápida** | Generar PDF/CSV sin pasar por el navegador | Rust file I/O |
| **Screenshot chart** | Capturar y compartir charts directamente | Screen capture API |
| **Modo picture-in-picture** | Chart flotante siempre visible | Tauri overlay window |
| **Offline mode** | Ver historial sin conexión | SQLite local cache |

---

## 13. Accesibilidad

### 13.1 Estándar: WCAG 2.1 AA

TNSVT V2 cumple con WCAG 2.1 nivel AA como mínimo, con aspiraciones a AAA
en áreas críticas.

### 13.2 Requisitos por Categoría

| Categoría | Requisito | Implementación |
|-----------|-----------|----------------|
| **Perceptible** | Alternativas de texto para imágenes | `alt` tags en todos los gráficos |
| **Perceptible** | Subtítulos para audio | N/A (no hay audio en la app) |
| **Perceptible** | Contraste ≥ 4.5:1 (texto normal) | Tokens de color validados |
| **Perceptible** | Contraste ≥ 3:1 (texto grande) | Validación en CI |
| **Perceptible** | Redimensionar texto hasta 200% | `rem` units, responsive |
| **Operable** | Navegación por teclado | Todos los elementos focusable |
| **Operable** | Sin trampas de foco | Focus trap solo en modales |
| **Operable** | Tiempo suficiente para leer | Sin timeouts arbitrarios |
| **Operable** | blinking/strobing limitado | No hay elementos parpadeantes |
| **Comprensible** | Labels en todos los inputs | React Hook Form + aria-labels |
| **Comprensible** | Navegación predecible | Layout consistente |
| **Comprensible** | Input assistance | Validación inline, mensajes de error |
| **Robusto** | Parsing válido | HTML5 valid, ARIA roles |
| **Robusto** | Name/role/value | ARIA attributes completos |
| **Robusto** | Status messages | `aria-live` para actualizaciones |

### 13.3 Consideraciones Específicas para Trading

| Elemento | Accesibilidad | Implementación |
|----------|---------------|----------------|
| **Chart** | Descripción de texto del estado del mercado | `aria-label` dinámico con resumen del chart |
| **P&L** | Cambios anunciados a screen readers | `aria-live="polite"` con cambios significativos |
| **Colores P&L** | No solo verde/rojo — usar iconos/texto | ▲/▼ + signo +/- siempre visible |
| **Order Book** | Tabla accesible con navegación por teclado | Role `grid` con `aria-sort` |
| **Positions** | Lista con acciones accesibles | Role `list` con botones accesibles |
| **Live Updates** | Región aria-live con debounce | Actualizar cada 5s, no cada tick |

### 13.4 Testing de Accesibilidad

```json
{
  "a11y_testing": {
    "automated": {
      "tool": "@axe-core/react",
      "ci_integration": true,
      "fail_on": ["critical", "serious"],
      "baseline_file": ".a11y-baseline.json"
    },
    "manual": {
      "keyboard_navigation": true,
      "screen_reader_test": ["NVDA", "VoiceOver"],
      "zoom_test_200pct": true,
      "high_contrast_mode": true,
      "color_blindness_simulation": ["protanopia", "deuteranopia"]
    },
    "schedule": {
      "automated": "every PR",
      "manual": "monthly",
      "audit": "quarterly (external)"
    }
  }
}
```

---

## 14. Rendimiento de UI

### 14.1 Performance Budgets

| Métrica | Objetivo | Herramienta de Medición |
|---------|----------|------------------------|
| **First Contentful Paint** | < 1.0s | Lighthouse |
| **Largest Contentful Paint** | < 2.0s | Lighthouse |
| **First Input Delay** | < 50ms | Core Web Vitals |
| **Cumulative Layout Shift** | < 0.1 | Core Web Vitals |
| **Time to Interactive** | < 3.0s | Lighthouse |
| **Total Bundle Size** | < 250 KB (gzipped) | Webpack analyzer |
| **Initial JS** | < 100 KB (gzipped) | Next.js build |
| **CSS** | < 50 KB (gzipped) | Tailwind purge |

### 14.2 Estrategias de Optimización

| Estrategia | Descripción | Impacto |
|------------|-------------|---------|
| **Code Splitting** | Carga por panel (lazy loading) | -40% initial bundle |
| **React.memo** | Memoización de componentes de datos | -60% re-renders |
| **Virtualized Lists** | Tablas grandes con react-virtual | -90% DOM nodes |
| **WebSocket batching** | Agrupar updates cada 100ms | -70% re-renders |
| **Image optimization** | Next.js Image + WebP | -50% image weight |
| **Font loading** | `font-display: swap` + subset | -30% font weight |
| **Preloading** | Prefetch de datos del siguiente panel | -500ms navigation |

### 14.3 Monitoreo de Performance

```typescript
// Performance monitoring en producción
if (typeof window !== 'undefined') {
  // Core Web Vitals reporting
  import('web-vitals').then(({ onCLS, onFID, onLCP }) => {
    onCLS(({ value }) => sendMetric('CLS', value));
    onFID(({ value }) => sendMetric('FID', value));
    onLCP(({ value }) => sendMetric('LCP', value));
  });
  
  // Custom trading metrics
  const observer = new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) {
      if (entry.name.includes('chart-render')) {
        sendMetric('chart-render', entry.duration);
      }
      if (entry.name.includes('sse-connect')) {
        sendMetric('sse-connect', entry.duration);
      }
    }
  });
  observer.observe({ entryTypes: ['measure'] });
}
```

---

## 15. Internacionalización

### 15.1 Idiomas Soportados

| Idioma | Código | Estado | Cobertura |
|--------|--------|--------|-----------|
| Español | `es` | Primario | 100% |
| Inglés | `en` | Secundario | 100% |
| Portugués | `pt` | Fase 2 | 0% |
| Chino Simplificado | `zh` | Fase 3 | 0% |
| Árabe | `ar` | Fase 4 | 0% (RTL) |

### 15.2 Estrategia i18n

```typescript
// next-intl para internacionalización
// Mensajes en /messages/{locale}.json
// Formato de fechas y números: Intl API nativa
// Trading terms se mantienen en inglés (estándar de la industria)

// Ejemplo de mensaje:
{
  "trading": {
    "position": {
      "buy": "Compra",
      "sell": "Venta",
      "close": "Cerrar posición",
      "modify": "Modificar"
    },
    "metrics": {
      "pnl": "P&L",
      "drawdown": "Drawdown",
      "winRate": "Ratio de acierto",
      "sharpe": "Ratio de Sharpe"
    }
  }
}

// Números y monedas siempre se formatean localmente:
// es-ES: 1.234,56 €
// en-US: $1,234.56
// zh-CN: ¥1,234.56
```

---

## Documentos Relacionados

| Documento | Relación |
|-----------|----------|
| [API-DESIGN.md](./API-DESIGN.md) | Endpoints consumidos por la UI |
| [AI-CORE.md](./AI-CORE.md) | Datos del AI Core mostrados en la UI |
| [ROADMAP.md](./ROADMAP.md) | Cronograma de desarrollo UI |
| [SCALE-100K.md](./SCALE-100K.md) | Optimizaciones de rendimiento a escala |
| [TRADING-CORE.md](./TRADING-CORE.md) | Datos de trading mostrados en la UI |

---

*Documento generado como parte de la arquitectura de TNSVT V2.*  
*Última revisión: 2026-07-14*
