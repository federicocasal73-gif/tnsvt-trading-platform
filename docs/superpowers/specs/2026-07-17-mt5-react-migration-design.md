# Migración MT5→React + Vendibilidad TNSVT V2

**Fecha:** 2026-07-17
**Estado:** Especificación aprobada, pendiente implementación
**Sesión:** continuación en próxima sesión
**Owner:** usuario + asistente

---

## 1. Contexto y motivación

### 1.1 Estado actual

El usuario opera dos sistemas en paralelo:

- **`D:\TradingBotMT5`** (v14.2, "Golden Release") — Bot Python standalone con Streamlit dashboard en `:8501`. Monitorea canales Telegram, parsea señales (regex + Gemini AI), ejecuta en MT5, gestiona riesgo. Madura, en producción, **no debe romperse**.
- **`E:\Nueva carpeta\TNSVT-V2-Architecture`** (TNSVT V2, Fase 1 MVP) — Plataforma multi-tenant con frontend Vite/React en `:5180`, gateway en `:8000`, auth en `:8001`, 14 microservicios. Stack moderno pero con UI incompleta.

Hoy conviven: el bot nativo maneja todo lo operativo, el frontend TNSVT está en stub. El usuario quiere **unificar** para vender la plataforma TNSVT como producto SaaS.

### 1.2 Stack ya integrado (esta sesión)

| Componente | Estado | Puerto |
|------------|--------|--------|
| Frontend TNSVT (Vite/React) | corriendo | 5180 |
| API Gateway (Go) | corriendo | 8000 |
| Auth Service (Go) | corriendo | 8001 |
| Bridge API (FastAPI, NUEVO) | corriendo | **8522** |
| PostgreSQL 16 + TimescaleDB | nativo Windows | 5432 |
| Redis | nativo Windows | 6379 |
| Bot MT5 (D:\TradingBotMT5) | corriendo | 8501 (Streamlit) |
| Bridge outbox con SQLite WAL | funcionando | — |

Endpoints bridge ya disponibles:
- `GET /health` (con outbox stats)
- `POST /api/v1/bridge/mt5/order` (recibe orden ejecutada, encola)
- `POST /api/v1/bridge/telegram/signal` (recibe señal cruda)
- `POST /api/v1/bridge/mt5/mobile` (webhook MT5 mobile)
- `GET /api/v1/bridge/outbox/stats`

Garantía anti-pérdida verificada: **552 eventos entregados, 0 perdidos** tras matar/levantar el bridge durante el test.

### 1.3 Hallazgo clave sobre `Terminal_Financiera_Pro` (commit `a609694`)

El usuario pidió revisar el commit `a609694` de `E:\Nueva carpeta\Terminal_Financiera_Pro` (TFP). Conclusión:

- TFP es un sistema MUY maduro (FASE 22.1, 121 tests de seguridad, commit `a609694` = fix UX de spread)
- Streamlit dashboard tiene **todo** lo que el usuario quiere mostrar (Win Rate 66.7%, Profit Factor 6.38, Expectancy, Sharpe, heatmap, breakdowns)
- El bot ya tiene **toda** la lógica de trading: parser multi-formato, multi-account, trailing-stop pip-aware, partial closes, news filter, MT5 watchdog
- TFP NO es lo que hay que copiar: hay que **portar la inteligencia** de su dashboard y bot a React + TNSVT, **manteniendo el bot original como productor de eventos**

---

## 2. Decisiones de diseño (de esta sesión)

| Decisión | Elección | Justificación |
|----------|----------|---------------|
| ¿Cómo se persiste P&L/channel para KPIs? | **A** — Modificar `executor.py` para guardar en SQLite local del bot | Bot ya tiene acceso a MT5; bridge no debería tocar MT5 |
| ¿Cómo se propaga el canal del trade? | **A+B** — Bot guarda contexto + publica al bridge | Doble garantía, sin acoplamiento |
| ¿Streamlit se mantiene? | **Sí, hasta ver resultado final** | El usuario decide después; React es UI primaria, Streamlit queda como "modo clásico" |
| ¿Nivel de vendibilidad inicial? | **Básica** (multi-tenant + landing + auth), **Completa después** | Balance entre "vendible mañana" y terminable en una sesión |
| ¿Plan de ejecución? | **Camino 2** (sub-fase 1 hoy, sub-fase 2 mañana) | Cada bloque testeado antes de seguir |

---

## 3. Plan de implementación — Sub-fase 1 (HOY al retomar)

### A — Datos enriquecidos en el bot MT5 (~1h)

#### A.1 — Extender SQLite del bot

**Archivo:** `D:\TradingBotMT5\database.py`

Añadir columnas a tabla `trades`:

```sql
ALTER TABLE trades ADD COLUMN pnl REAL DEFAULT 0;
ALTER TABLE trades ADD COLUMN close_price REAL;
ALTER TABLE trades ADD COLUMN closed_at TEXT;
ALTER TABLE trades ADD COLUMN channel_id INTEGER;
ALTER TABLE trades ADD COLUMN channel_title TEXT;
ALTER TABLE trades ADD COLUMN topic_id INTEGER;
ALTER TABLE trades ADD COLUMN commission REAL DEFAULT 0;
ALTER TABLE trades ADD COLUMN swap REAL DEFAULT 0;
ALTER TABLE trades ADD COLUMN status TEXT DEFAULT 'OPEN';
```

Implementar como migration idempotente en `init_db()`: `ALTER TABLE ... ADD COLUMN` envuelto en try/except que ignore "duplicate column".

#### A.2 — Propagar contexto del handler

**Archivo:** `D:\TradingBotMT5\main.py`

En el `handler` (línea ~129), adjuntar contexto al signal antes de ejecutar:

```python
signal['_context'] = {
    'channel_id': event.chat_id,
    'channel_title': getattr(event.chat, 'title', 'Unknown'),
    'topic_id': msg_topic_id,
}
executor.execute_trade(signal)
```

#### A.3 — Persistir contexto en executor

**Archivo:** `D:\TradingBotMT5\executor.py`

Modificar `execute_trade()` (línea 62) para:

1. Leer `signal.get('_context', {})` y extraer `channel_id`, `channel_title`, `topic_id`
2. En `database.log_trade()` (línea 160), pasar estos campos como nuevos parámetros
3. Insertar con `status='OPEN'`

Modificar `database.log_trade()` para aceptar nuevos parámetros opcionales:
```python
def log_trade(symbol, action, price, sl, tp, result_msg, ticket=0,
              channel_id=None, channel_title=None, topic_id=None):
    ...
    c.execute("""INSERT INTO trades
        (date, symbol, action, price, sl, tp, result, ticket,
         channel_id, channel_title, topic_id, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')""",
        (date_str, symbol, action, price, sl, tp_str, status_msg, ticket,
         channel_id, channel_title, topic_id))
```

#### A.4 — Modificar `_publish_to_tnsvt`

**Archivo:** `D:\TradingBotMT5\executor.py`

En `_publish_to_tnsvt()` (línea ~181), enriquecer el payload:

```python
ctx = getattr(signal, '_context', {}) or {}
payload = {
    "symbol": symbol, "action": action, "volume": volume,
    "price": price, "sl": sl, "tp": tp, "ticket": ticket,
    "comment": comment, "source": "telegram-bot",
    "channel_id": ctx.get('channel_id'),
    "channel_title": ctx.get('channel_title'),
    "topic_id": ctx.get('topic_id'),
}
```

#### A.5 — Backfill worker

**Archivo NUEVO:** `D:\TradingBotMT5\backfill_worker.py`

Thread daemon que cada 5 minutos:

1. Lee trades con `status='OPEN'` y `ticket != 0` desde SQLite
2. Para cada uno, llama `mt5.history_deals_get(ticket)` para obtener `close_price`, `pnl`, `commission`, `swap`
3. Si el deal existe → actualiza `close_price`, `pnl`, `commission`, `swap`, `closed_at`, `status='CLOSED'`
4. Log con conteo de trades actualizados

Estructura:
```python
import threading, time, sqlite3, logging
from datetime import datetime, timezone, timedelta
import MetaTrader5 as mt5
import database

logger = logging.getLogger("bot.backfill")
INTERVAL = 300  # 5 minutos

class BackfillWorker(threading.Thread):
    daemon = True
    def __init__(self): super().__init__(name="bot-backfill")
    def run(self):
        while True:
            try: self._tick()
            except Exception as e: logger.exception(f"backfill error: {e}")
            time.sleep(INTERVAL)
    def _tick(self):
        # SELECT * FROM trades WHERE status='OPEN' AND ticket != 0
        # Para cada uno: mt5.history_deals_get(ticket)
        # Si hay deal cerrado: UPDATE trades SET ...
        ...
```

Arrancarlo en `main.py` igual que `OutboxWorker`.

---

### B — Bridge API :8522 — endpoints analytics (~1h)

#### B.1 — Nueva tabla en bridge_outbox.db

**Archivo NUEVO:** `apps/bridge/bridge-api/db.py`

Crear tabla `trades` que el bridge mantiene sincronizada desde el bot:

```sql
CREATE TABLE IF NOT EXISTS trades (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ticket INTEGER UNIQUE NOT NULL,
  symbol TEXT NOT NULL,
  action TEXT NOT NULL,
  volume REAL NOT NULL,
  open_price REAL NOT NULL,
  close_price REAL,
  sl REAL,
  tp REAL,
  pnl REAL DEFAULT 0,
  commission REAL DEFAULT 0,
  swap REAL DEFAULT 0,
  opened_at TEXT NOT NULL,
  closed_at TEXT,
  channel_id INTEGER,
  channel_title TEXT,
  topic_id INTEGER,
  status TEXT NOT NULL DEFAULT 'OPEN',
  received_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_channel ON trades(channel_id);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_closed_at ON trades(closed_at);
```

Añadir helper `upsert_trade(payload)` que inserta o actualiza por `ticket`.

#### B.2 — Endpoint nuevo en `main.py`

Cuando llega POST `/api/v1/bridge/mt5/order`, además de encolar en outbox, también upsert directo a tabla `trades` (read-after-write):

```python
@app.post("/api/v1/bridge/mt5/order")
def mt5_order(order: MT5Order):
    payload = order.model_dump()
    payload["received_at"] = ...
    event_id = outbox.enqueue(payload, source="mt5-bot")
    db.upsert_trade(payload)  # ← NUEVO: persiste en tabla analytics
    return {"accepted": True, "event_id": event_id, ...}
```

#### B.3 — 5 endpoints de analytics

**Archivo:** `apps/bridge/bridge-api/main.py`

```python
@app.get("/api/v1/bridge/analytics/metrics")
def analytics_metrics():
    """KPIs globales: Win Rate, PF, Expectancy, Sharpe, Sortino, Max DD."""
    closed = db.fetch_closed_trades()
    return compute_metrics(closed)

@app.get("/api/v1/bridge/analytics/equity-curve")
def analytics_equity():
    """Serie (date, equity, drawdown) para graficar."""
    closed = db.fetch_closed_trades()
    return build_equity_curve(closed)

@app.get("/api/v1/bridge/analytics/by-channel")
def analytics_by_channel():
    """Agrupado por channel_id y channel_title."""
    all_trades = db.fetch_all_trades()
    return aggregate_by_channel(all_trades)

@app.get("/api/v1/bridge/analytics/by-symbol")
def analytics_by_symbol():
    """Agrupado por symbol."""
    all_trades = db.fetch_all_trades()
    return aggregate_by_symbol(all_trades)

@app.get("/api/v1/bridge/analytics/live-positions")
def analytics_live_positions():
    """Trades con status='OPEN' (posiciones abiertas)."""
    return db.fetch_open_trades()
```

**Implementación de `compute_metrics()`** (portado de TFP `dashboard/visualizations.py:compute_strategy_metrics`):

```python
import math
from typing import Iterable

def compute_metrics(trades: list[dict]) -> dict:
    closed = [t for t in trades if t.get("status") == "CLOSED"]
    if not closed:
        return empty_metrics()
    
    pnls = [t["pnl"] for t in closed]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    
    total = len(closed)
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = win_count / total if total else 0
    
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses)) if losses else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    avg_win = sum(wins) / win_count if wins else 0
    avg_loss = abs(sum(losses)) / loss_count if losses else 0
    expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
    
    # Daily returns from pnl
    daily_pnl = group_by_day(closed)
    returns = list(daily_pnl.values())
    if len(returns) > 1:
        mean_r = sum(returns) / len(returns)
        std_r = math.sqrt(sum((r - mean_r)**2 for r in returns) / (len(returns) - 1))
        sharpe = (mean_r / std_r) * math.sqrt(252) if std_r > 0 else 0
        downside = [r for r in returns if r < 0]
        if downside:
            d_std = math.sqrt(sum(r**2 for r in downside) / len(downside))
            sortino = (mean_r / d_std) * math.sqrt(252) if d_std > 0 else 0
        else:
            sortino = float('inf')
    else:
        sharpe = 0
        sortino = 0
    
    # Max drawdown
    equity_curve = build_equity_curve(closed)
    max_dd = compute_max_drawdown(equity_curve)
    
    return {
        "total": total,
        "wins": win_count,
        "losses": loss_count,
        "win_rate": round(win_rate, 4),
        "profit_factor": round(profit_factor, 2),
        "expectancy": round(expectancy, 2),
        "sharpe": round(sharpe, 2),
        "sortino": round(sortino, 2),
        "max_drawdown": round(max_dd, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
    }
```

**Cache de 5s** para no recalcular en cada request:

```python
from functools import lru_cache
import time

_cache = {"data": {}, "ts": 0}
CACHE_TTL = 5

def cached_analytics(key: str, loader):
    now = time.time()
    if now - _cache["ts"] > CACHE_TTL or key not in _cache["data"]:
        _cache["data"][key] = loader()
        _cache["ts"] = now
    return _cache["data"][key]
```

#### B.4 — Syncer (worker) bot → bridge

**Archivo NUEVO:** `apps/bridge/bridge-api/syncer.py`

Thread daemon que lee trades del SQLite del bot (`D:\TradingBotMT5\bot_data.db` vía ruta configurable) y los upsert al bridge:

```python
import threading, time, sqlite3, logging, os

logger = logging.getLogger("bridge.syncer")
SYNC_INTERVAL = 30
BOT_DB_PATH = os.getenv("BOT_SQLITE_PATH", r"D:\TradingBotMT5\bot_data.db")

class BotSyncer(threading.Thread):
    def __init__(self, bridge_db):
        super().__init__(name="bridge-syncer", daemon=True)
        self.bridge_db = bridge_db
    
    def run(self):
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as e:
                logger.warning(f"syncer tick error: {e}")
            self._stop_event.wait(SYNC_INTERVAL)
    
    def _tick(self):
        if not os.path.exists(BOT_DB_PATH):
            return
        with sqlite3.connect(BOT_DB_PATH, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""SELECT ticket, symbol, action, sl, tp,
                                         channel_id, channel_title, topic_id,
                                         status, closed_at, pnl, close_price
                                  FROM trades WHERE ticket > 0""").fetchall()
        for row in rows:
            self.bridge_db.upsert_trade(dict(row))
```

Arrancarlo en `lifespan` del FastAPI app.

**Importante:** el path del SQLite es Windows (`D:\TradingBotMT5\bot_data.db`). Si el bridge corre en otra máquina, este path no funcionará. Para v1 asumimos mismo host; si se quiere deploy distribuido, se reemplaza por HTTP al bot.

---

### C — UI React Mt5Dashboard + Mt5Positions (~2h)

#### C.1 — `Mt5DashboardPage.tsx`

**Archivo:** `apps/frontend/src/pages/Mt5DashboardPage.tsx`

**Diseño (aplicando skill `interface-design`):**

```
┌─────────────────────────────────────────────────────────────────┐
│ Header: "🤖 MT5 Trading"     Status badge (Online/Offline)    │
├─────────────────────────────────────────────────────────────────┤
│ HERO: Equity Curve (SVG con gradient + drawdown overlay)        │
│        Stats inline: Equity Final | Peak | Max DD | Max DD %    │
├─────────────────────────────────────────────────────────────────┤
│ Grid 8 KPI cards (4 columnas × 2 filas):                        │
│   TOTAL | EJECUTADAS | BLOQUEADAS | HOY                          │
│   WIN RATE % | GANADAS | PERDIDAS | PNL TOTAL $                  │
├─────────────────────────────────────────────────────────────────┤
│ Tabla "Por Canal": channel | trades | wins | pnl | win_rate | bar│
├─────────────────────────────────────────────────────────────────┤
│ Tabla "Por Símbolo": Mejor | Peor | Total símbolos + lista      │
└─────────────────────────────────────────────────────────────────┘
```

**Componentes:**

```tsx
export function Mt5DashboardPage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [equity, setEquity] = useState<EquityPoint[]>([]);
  const [byChannel, setByChannel] = useState<ChannelAgg[]>([]);
  const [bySymbol, setBySymbol] = useState<SymbolAgg[]>([]);
  
  useEffect(() => {
    const fetch = async () => {
      const [m, e, c, s] = await Promise.all([
        api.bridge.metrics(),
        api.bridge.equityCurve(),
        api.bridge.byChannel(),
        api.bridge.bySymbol(),
      ]);
      setMetrics(m); setEquity(e); setByChannel(c); setBySymbol(s);
    };
    fetch();
    const id = setInterval(fetch, 30000); // polling 30s
    return () => clearInterval(id);
  }, []);
  
  return (
    <div className="space-y-6">
      <EquityCurve data={equity} />
      <KPIGrid metrics={metrics} />
      <ChannelTable rows={byChannel} />
      <SymbolTable rows={bySymbol} />
    </div>
  );
}
```

**Tokens existentes** (`tnvs-*`) se reutilizan:
- `bg-tnvs-surface`, `border-tnvs-border`, `text-tnvs-muted`
- `text-tnvs-win` (verde), `text-tnvs-loss` (rojo), `text-tnvs-warn` (ámbar)

#### C.2 — `Mt5PositionsPage.tsx`

**Archivo:** `apps/frontend/src/pages/Mt5PositionsPage.tsx`

3 tabs internas: **Open** | **Closed** | **All**

Tabla con:
- Symbol | Side | Volume | Open Price | Close Price | P&L | Channel | Opened | Closed
- Sort por columna
- Filtros: por symbol, por channel, por rango de fechas
- Color coding: verde/rojo/ámbar en P&L
- Click row → drawer con detalle completo

Polling cada 30s. Polling reactivo (useEffect con setInterval).

#### C.3 — Routing

**Archivo:** `apps/frontend/src/router.tsx`

```tsx
import { Mt5DashboardPage } from './pages/Mt5DashboardPage';
import { Mt5PositionsPage } from './pages/Mt5PositionsPage';

// ...
{ path: 'mt5-dashboard', element: <Mt5DashboardPage /> },
{ path: 'mt5-positions', element: <Mt5PositionsPage /> },
```

**Archivo:** `apps/frontend/src/router.tsx` — reemplazar Mt5BotPage

```tsx
import { Navigate } from 'react-router-dom';

// Dentro de las rutas de ProtectedShell:
{ path: 'mt5-bot', element: <Navigate to="/mt5-dashboard" replace /> },
```

(Conservar `Mt5BotPage.tsx` por si el usuario quiere volver al Streamlit; agregar un link "Modo clásico →" en la esquina superior derecha del header de Mt5DashboardPage que apunte a `window.open('http://localhost:8501', '_blank')`.)

**Archivo:** `apps/frontend/src/components/Sidebar.tsx` — actualizar navegación

```tsx
// En ROUTES (router.tsx):
{ path: '/mt5-dashboard', name: 'mt5-dashboard', label: 'MT5 Dashboard', icon: 'dashboard' },
{ path: '/mt5-positions', name: 'mt5-positions', label: 'MT5 Positions', icon: 'positions' },

// En ICON_MAP (Sidebar.tsx): los iconos 'dashboard' (LayoutDashboard) y
// 'positions' (Activity) YA EXISTEN. No requiere cambios.
```

#### C.4 — API helpers

**Archivo:** `apps/frontend/src/lib/api.ts`

```typescript
export interface Metrics {
  total: number;
  wins: number;
  losses: number;
  win_rate: number;
  profit_factor: number;
  expectancy: number;
  sharpe: number;
  sortino: number;
  max_drawdown: number;
  gross_profit: number;
  gross_loss: number;
}

export interface EquityPoint {
  date: string;
  equity: number;
  drawdown: number;
}

export interface ChannelAgg {
  channel_id: number | null;
  channel_title: string;
  trades: number;
  wins: number;
  pnl: number;
  win_rate: number;
}

export interface SymbolAgg {
  symbol: string;
  trades: number;
  pnl: number;
  best: boolean;
  worst: boolean;
}

bridge: {
  metrics: () => request<Metrics>('/api/v1/bridge/analytics/metrics'),
  equityCurve: () => request<EquityPoint[]>('/api/v1/bridge/analytics/equity-curve'),
  byChannel: () => request<ChannelAgg[]>('/api/v1/bridge/analytics/by-channel'),
  bySymbol: () => request<SymbolAgg[]>('/api/v1/bridge/analytics/by-symbol'),
  livePositions: () => request<any[]>('/api/v1/bridge/analytics/live-positions'),
}
```

#### C.5 — Equity Curve SVG

Componente custom sin librerías externas (recharts/tradingview-lightweight pesan mucho):

```tsx
function EquityCurve({ data }: { data: EquityPoint[] }) {
  if (!data.length) return <Empty>Sin historial aún</Empty>;
  
  const W = 800, H = 240, P = 20;
  const maxE = Math.max(...data.map(d => d.equity));
  const minE = Math.min(...data.map(d => d.equity), 0);
  const range = maxE - minE || 1;
  
  const points = data.map((d, i) => {
    const x = P + (i / (data.length - 1 || 1)) * (W - 2*P);
    const y = P + (1 - (d.equity - minE) / range) * (H - 2*P);
    return `${x},${y}`;
  }).join(' ');
  
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto">
      <defs>
        <linearGradient id="eq-gradient" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="rgb(16, 185, 129)" stopOpacity="0.4" />
          <stop offset="100%" stopColor="rgb(16, 185, 129)" stopOpacity="0" />
        </linearGradient>
      </defs>
      <polyline points={points} fill="none" stroke="rgb(16, 185, 129)" strokeWidth="2" />
      <polygon points={`${P},${H-P} ${points} ${W-P},${H-P}`} fill="url(#eq-gradient)" />
    </svg>
  );
}
```

---

### D — Test E2E + Documentación (~30 min)

#### D.1 — Test E2E

```powershell
# 1. Verificar que todo está corriendo
Test-NetConnection localhost -Port 5180
Test-NetConnection localhost -Port 8000
Test-NetConnection localhost -Port 8522
Test-NetConnection localhost -Port 8001

# 2. Login
$body = '{"email":"admin@tnsvt.local","password":"Admin123!Demo"}'
$resp = curl.exe -s -X POST http://localhost:5180/api/v1/auth/login -H "Content-Type: application/json" -d $body
$token = ($resp | ConvertFrom-Json).access_token

# 3. Simular orden ejecutada en MT5
$order = '{"symbol":"EURUSD","action":"BUY","volume":0.01,"price":1.0845,"ticket":88888,"source":"telegram-bot"}'
curl.exe -s -X POST http://localhost:5180/api/v1/bridge/mt5/order -H "Content-Type: application/json" -d $order

# 4. Esperar 2s y verificar que aparece en analytics
Start-Sleep -Seconds 2
curl.exe -s http://localhost:5180/api/v1/bridge/analytics/metrics
curl.exe -s http://localhost:5180/api/v1/bridge/analytics/live-positions

# 5. Verificar en frontend
start http://localhost:5180/mt5-dashboard
```

#### D.2 — Guía de arranque

```cmd
# === ARRANCAR TNSVT V2 CON BRIDGE + BOT MT5 ===

# PASO 1: Verificar servicios base
Get-Service postgresql-x64-16, Redis
# Si están "Stopped", arrancarlos:
Start-Service postgresql-x64-16
Start-Service Redis

# PASO 2: Arrancar stack TNSVT
cd "E:\Nueva carpeta\TNSVT-V2-Architecture"
.\start-all.bat
# Esto inicia:
#   - Bridge API :8522
#   - Auth Service :8001
#   - API Gateway :8000
#   - Frontend Vite :5180

# PASO 3: En otra ventana, arrancar bot MT5
cd /d D:\TradingBotMT5
.\START_BOT.bat
# Esto inicia:
#   - Dashboard Streamlit :8501 (modo clásico)
#   - Bot Telethon + MT5 + backfill worker + outbox worker

# PASO 4: Abrir navegador
start http://localhost:5180
# Login: admin@tnsvt.local / Admin123!Demo
# Click "MT5 Dashboard" en el sidebar

# === PARA PARAR ===
.\stop-all.bat
# Cierra la ventana negra de START_BOT.bat
```

---

## 4. Sub-fase 2 (después)

### E — Mt5ChannelsPage

Replica la Tab 3 de Streamlit. UI para:
- Listar canales Telegram detectados
- Checkboxes para activar/desactivar cada canal + cada topic (forum)
- Botón "Escanear canales" → llama endpoint nuevo en bridge `/api/v1/bridge/telegram/channels`
- Persiste selección en `config.json` del bot (vía outbox)

### F — Mt5SettingsPage

Replica Tabs 1+2 de Streamlit. Form para:
- Modo de lote (Fijo / % Riesgo)
- Lot size, lot percentage, deviation
- Risk diario/semanal/mensual (profit target + loss limit, cada uno con toggle on/off)
- Persiste vía outbox al `config.json` del bot

### G — Mt5ControlWidget

Reemplaza la sidebar Start/Stop de Streamlit:
- Botón grande "🚀 INICIAR PROGRAMA" / "🛑 DETENER PROGRAMA"
- Lee/escribe `bot_state.json`
- Estado actual visible (STOPPED / DEPLOYED / WAITING_CONFIG)
- Polling cada 5s para actualizar estado

### H — Multi-tenant

- Agregar `tenant_id` al `config.json` del bot
- Cada orden publicada al bridge lleva `tenant_id`
- Bridge filtra queries de analytics por `tenant_id`
- Por ahora: 1 tenant único (admin). Multi-tenant real cuando haya más tenants en TNSVT.

### I — Landing + Pricing + Signup

- `LandingPage.tsx` (página pública `/` antes del login)
  - Hero: "TNSVT — Terminal Financiera Pro"
  - Features: Multi-tenant, MT5 integrado, AI scoring, Copy trading
  - CTA: "Empezar gratis"
- `PricingPage.tsx` con 3 planes
  - Free: 1 cuenta, 100 señales/día
  - Starter: $29/mes, 5 cuentas, 1000 señales
  - Pro: $99/mes, ilimitado, copy trading, AI scoring
- `SignupWizard.tsx` (multi-step)
  - Step 1: Email + Password
  - Step 2: Tenant name + slug
  - Step 3: Confirmación → redirect a login

---

## 5. Sub-fase 3 (vendibilidad completa — solo si decidís borrar Streamlit)

### J — Decisión final Streamlit

Si en sub-fase 2 todo se ve bien en React y el usuario está conforme:
- Borrar `D:\TradingBotMT5\dashboard.py`
- Quitar dependencia `streamlit` de `requirements.txt`
- Quitar `subprocess.Popen(["streamlit", ...])` de `D:\TradingBotMT5\main.py:52`
- Agregar link "Modo clásico" en React que abre :8501 directo (para nostalgia)

Si no:
- Dejar Streamlit como fallback
- React queda como UI principal

### K — Billing, Admin, Monitoring

- Stripe integration (auth-service ya tiene schema, falta webhook handler)
- Admin panel: lista de tenants, MRR, churn
- Prometheus + Grafana reales (docker-compose con prometheus.yml scrape config)
- CI/CD (`.github/workflows/ci.yml` ya existe en scaffold, falta wirearlo)

---

## 6. Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|-----------|
| Bot MT5 nativo se cae y deja de publicar | Media | Alto | Outbox persistente + backfill worker al volver |
| Bridge se cae | Baja | Medio | Outbox persistente, ningún evento se pierde |
| SQLite del bot se corrompe | Baja | Alto | Backups diarios (ya existe patrón en TFP) |
| MT5 cambia formato de history_deals_get | Baja | Medio | Versionar schema, manejar con try/except |
| Frontend polling sobrecarga el bridge | Baja | Bajo | Cache 5s en analytics, polling 30s |
| Multi-tenant rompe al haber 2+ bots | Media | Medio | v1 con 1 tenant, schema listo para escalar |

---

## 7. Criterios de éxito de Sub-fase 1

- [ ] Bot MT5 persiste `pnl`, `channel_id`, `channel_title`, `topic_id`, `closed_at` en SQLite
- [ ] Backfill worker cierra trades abiertos consultando MT5 cada 5 min
- [ ] Bridge expone 5 endpoints de analytics funcionando
- [ ] `Mt5DashboardPage` muestra 8 KPI + equity curve + breakdowns por canal/símbolo
- [ ] `Mt5PositionsPage` muestra open/closed/all con filtros
- [ ] `/mt5-bot` redirige a `/mt5-dashboard`
- [ ] Streamlit sigue funcionando en `:8501` (no se rompe)
- [ ] Test E2E pasa: orden simulada aparece en `/api/v1/bridge/analytics/metrics`
- [ ] Documento de arranque guardado en este spec

---

## 8. Comandos de la próxima sesión

```powershell
# Cuando retomes, decime: "Retomemos el plan guardado" y arranco con:

# Verificar servicios
Get-Service postgresql-x64-16, Redis

# Ver specs/
Get-ChildItem "E:\Nueva carpeta\TNSVT-V2-Architecture\docs\superpowers\specs\"

# Listo, arranco con Bloque A (datos enriquecidos)
```

---

## 9. Apéndice: archivos que se modifican/crean

### Nuevos
- `D:\TradingBotMT5\backfill_worker.py`
- `apps\bridge\bridge-api\db.py`
- `apps\bridge\bridge-api\analytics.py`
- `apps\bridge\bridge-api\syncer.py`
- `apps\frontend\src\pages\Mt5DashboardPage.tsx`
- `apps\frontend\src\pages\Mt5PositionsPage.tsx`
- `apps\frontend\src\components\EquityCurve.tsx`
- `apps\frontend\src\components\KPIGrid.tsx`
- `apps\frontend\src\components\ChannelTable.tsx`
- `apps\frontend\src\components\SymbolTable.tsx`
- `docs\superpowers\specs\2026-07-17-mt5-react-migration-design.md` (este archivo)

### Modificados
- `D:\TradingBotMT5\database.py` (ALTER TABLE migrations)
- `D:\TradingBotMT5\executor.py` (payload enriquecido + nuevos campos en log_trade)
- `D:\TradingBotMT5\main.py` (handler adjunta _context, arranca backfill worker)
- `apps\bridge\bridge-api\main.py` (5 endpoints nuevos + syncer)
- `apps\frontend\src\lib\api.ts` (tipos Metrics/EquityPoint/ChannelAgg/SymbolAgg)
- `apps\frontend\src\router.tsx` (rutas /mt5-dashboard, /mt5-positions)
- `apps\frontend\src\components\Sidebar.tsx` (iconos nuevos)

---

## 10. Apéndice: matemática de métricas (referencia)

```python
# Sharpe Ratio (annualizado, 252 días de trading)
sharpe = (mean_daily_return / std_daily_return) * sqrt(252)

# Sortino Ratio (solo downside deviation)
downside_deviation = sqrt(sum(min(r, 0)**2 for r in returns) / N)
sortino = (mean_return / downside_deviation) * sqrt(252)

# Profit Factor
profit_factor = sum(winning_pnl) / abs(sum(losing_pnl))

# Expectancy (por trade)
expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

# Max Drawdown
running_max = 0
max_dd = 0
for equity_point in equity_curve:
    running_max = max(running_max, equity_point)
    dd = running_max - equity_point
    max_dd = max(max_dd, dd)
```

---

**FIN DEL DESIGN DOC**

Próxima sesión: retomar con Bloque A (datos enriquecidos en el bot). Cuando arranques, decime **"Retomemos el plan guardado"** y leo este spec para arrancar sin perder contexto.
