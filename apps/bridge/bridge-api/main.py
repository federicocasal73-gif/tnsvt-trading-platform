"""
TNSVT Bridge API — Recibe órdenes ejecutadas por el bot MT5 nativo
(D:\\TradingBotMT5) y las publica al ecosistema TNSVT (signal-engine,
audit-engine, risk-engine).

Garantías:
- Cada orden se persiste en SQLite ANTES de intentar publicarla.
- Si TNSVT está caído, la orden queda en cola y se reintenta con backoff.
- Ningún evento se pierde, aunque el bridge se reinicie.

Endpoints:
  GET  /health                       → health check
  POST /api/v1/bridge/mt5/order      → orden ejecutada en MT5
  POST /api/v1/bridge/telegram/signal → señal cruda desde Telegram
  POST /api/v1/bridge/mt5/mobile     → webhook desde app MT5 mobile
  GET  /api/v1/bridge/outbox/stats   → métricas de la cola
"""

import logging
import math
import os
import sys
import time
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from outbox import Outbox
from publisher import Publisher
from db import TradesDB
from syncer import BotSyncer
from config_manager import ConfigManager

# ─── Config ────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
DB_PATH = os.getenv("BRIDGE_DB", str(BASE_DIR / "bridge_outbox.db"))
GATEWAY_URL = os.getenv("TNSVT_GATEWAY_URL", "http://localhost:8000")
BRIDGE_API_KEY = os.getenv("BRIDGE_API_KEY", "dev-bridge-key-change-me")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("bridge.api")

# ─── App ────────────────────────────────────────────────────────────────

outbox = Outbox(DB_PATH)
trades_db = TradesDB(DB_PATH)
config_mgr = ConfigManager()
publisher: Optional[Publisher] = None
syncer: Optional[BotSyncer] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global publisher, syncer
    publisher = Publisher(outbox, GATEWAY_URL, BRIDGE_API_KEY)
    publisher.start()
    syncer = BotSyncer(trades_db)
    syncer.start()
    logger.info(f"Bridge API ready → gateway={GATEWAY_URL}, db={DB_PATH}")
    yield
    if publisher:
        publisher.stop()
    if syncer:
        syncer.stop()


app = FastAPI(
    title="TNSVT Bridge API",
    description="Bridged between D:\\TradingBotMT5 and TNSVT microservices",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5180",
        "http://127.0.0.1:5180",
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "http://localhost:8502",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Models ─────────────────────────────────────────────────────────────


class MT5Order(BaseModel):
    symbol: str
    action: str = Field(..., pattern="^(BUY|SELL|CLOSE)$")
    volume: float
    price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    ticket: Optional[int] = None
    comment: Optional[str] = None
    source: Optional[str] = "telegram-bot"
    received_at: Optional[str] = None
    channel_id: Optional[int] = None
    channel_title: Optional[str] = None
    topic_id: Optional[int] = None
    close_price: Optional[float] = None
    pnl: Optional[float] = None
    commission: Optional[float] = None
    swap: Optional[float] = None
    closed_at: Optional[str] = None
    status: Optional[str] = None
    tenant_id: Optional[str] = None


class TelegramSignal(BaseModel):
    raw_text: str
    chat_id: Optional[int] = None
    chat_title: Optional[str] = None
    topic_id: Optional[int] = None
    parsed_action: Optional[str] = None
    parsed_symbol: Optional[str] = None
    parsed_price: Optional[float] = None
    parsed_sl: Optional[float] = None
    parsed_tp: Optional[list[float]] = None


class MT5Mobile(BaseModel):
    event: str
    payload: dict[str, Any]


# ─── Routes ─────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    stats = outbox.stats()
    return {
        "status": "ok",
        "service": "bridge-api",
        "version": "1.0.0",
        "gateway": GATEWAY_URL,
        "outbox": stats,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/v1/bridge/mt5/order")
def mt5_order(order: MT5Order):
    """Recibe orden ejecutada en MT5 y la encola para publicar a TNSVT."""
    payload = order.model_dump()
    payload["received_at"] = payload.get("received_at") or datetime.now(
        timezone.utc
    ).isoformat()
    event_id = outbox.enqueue(payload, source="mt5-bot")
    trades_db.upsert_trade(payload)
    logger.info(f"Order enqueued #{event_id}: {order.action} {order.symbol} @ {order.price}")
    return {
        "accepted": True,
        "event_id": event_id,
        "queue_position": outbox.stats().get("PENDING", 0),
    }


@app.post("/api/v1/bridge/telegram/signal")
def telegram_signal(signal: TelegramSignal):
    """Recibe señal cruda de Telegram para que TNSVT la processe."""
    payload = signal.model_dump()
    payload["received_at"] = datetime.now(timezone.utc).isoformat()
    event_id = outbox.enqueue(payload, source="telegram-signal")
    logger.info(f"Telegram signal enqueued #{event_id} from {signal.chat_title}")
    return {"accepted": True, "event_id": event_id}


@app.post("/api/v1/bridge/mt5/mobile")
def mt5_mobile(payload: MT5Mobile):
    """Webhook desde la app móvil MT5."""
    data = payload.model_dump()
    data["received_at"] = datetime.now(timezone.utc).isoformat()
    event_id = outbox.enqueue(data, source="mt5-mobile")
    logger.info(f"Mobile event enqueued #{event_id}: {payload.event}")
    return {"accepted": True, "event_id": event_id}


@app.get("/api/v1/bridge/outbox/stats")
def outbox_stats():
    return outbox.stats()


@app.get("/")
def root():
    return {
        "service": "TNSVT Bridge API",
        "docs": "/docs",
        "health": "/health",
        "endpoints": [
            "POST /api/v1/bridge/mt5/order",
            "POST /api/v1/bridge/telegram/signal",
            "POST /api/v1/bridge/mt5/mobile",
            "GET  /api/v1/bridge/outbox/stats",
            "GET  /api/v1/bridge/analytics/metrics",
            "GET  /api/v1/bridge/analytics/equity-curve",
            "GET  /api/v1/bridge/analytics/by-channel",
            "GET  /api/v1/bridge/analytics/by-symbol",
            "GET  /api/v1/bridge/analytics/live-positions",
        ],
    }


# ─── Analytics ──────────────────────────────────────────────────────────

_cache: dict = {"data": {}, "ts": 0}
CACHE_TTL = 5


def _cached(key: str, loader):
    now = time.time()
    if now - _cache["ts"] > CACHE_TTL or key not in _cache["data"]:
        _cache["data"][key] = loader()
        _cache["ts"] = now
    return _cache["data"][key]


def compute_metrics(trades: list[dict]) -> dict:
    closed = [t for t in trades if t.get("status") == "CLOSED"]
    if not closed:
        return {
            "total": 0, "wins": 0, "losses": 0,
            "win_rate": 0, "profit_factor": 0, "expectancy": 0,
            "sharpe": 0, "sortino": 0, "max_drawdown": 0,
            "gross_profit": 0, "gross_loss": 0,
        }

    pnls = [t.get("pnl") or 0 for t in closed]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    total = len(closed)
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = win_count / total if total else 0

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses)) if losses else 0
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else None

    avg_win = sum(wins) / win_count if wins else 0
    avg_loss = abs(sum(losses)) / loss_count if losses else 0
    expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

    daily_pnl: dict[str, float] = {}
    for t in closed:
        day = (t.get("closed_at") or "")[:10]
        if day:
            daily_pnl[day] = daily_pnl.get(day, 0) + t["pnl"]
    returns = list(daily_pnl.values())

    sharpe = 0
    sortino = 0
    if len(returns) > 1:
        mean_r = sum(returns) / len(returns)
        std_r = math.sqrt(sum((r - mean_r)**2 for r in returns) / (len(returns) - 1))
        sharpe = (mean_r / std_r) * math.sqrt(252) if std_r > 0 else 0
        downside = [r for r in returns if r < 0]
        if downside:
            d_std = math.sqrt(sum(r**2 for r in downside) / len(downside))
            sortino = (mean_r / d_std) * math.sqrt(252) if d_std > 0 else 0
        else:
            sortino = None

    equity_curve = _build_equity_curve(closed)
    max_dd = _compute_max_drawdown(equity_curve)

    return {
        "total": total,
        "wins": win_count,
        "losses": loss_count,
        "win_rate": round(win_rate, 4),
        "profit_factor": profit_factor,
        "expectancy": round(expectancy, 2),
        "sharpe": round(sharpe, 2),
        "sortino": sortino,
        "max_drawdown": round(max_dd, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
    }


def _build_equity_curve(trades: list[dict]) -> list[dict]:
    equity = 0.0
    curve: list[dict] = []
    running_max = 0.0
    for t in trades:
        equity += t.get("pnl") or 0
        running_max = max(running_max, equity)
        dd = running_max - equity
        curve.append({
            "date": t.get("closed_at", ""),
            "equity": round(equity, 2),
            "drawdown": round(dd, 2),
        })
    return curve


def _compute_max_drawdown(curve: list[dict]) -> float:
    if not curve:
        return 0.0
    running_max = 0.0
    max_dd = 0.0
    for pt in curve:
        running_max = max(running_max, pt["equity"])
        dd = running_max - pt["equity"]
        max_dd = max(max_dd, dd)
    return max_dd


def _aggregate_by_channel(trades: list[dict]) -> list[dict]:
    groups: dict = {}
    for t in trades:
        cid = t.get("channel_id") or 0
        title = t.get("channel_title") or "Unknown"
        key = f"{cid}:{title}"
        if key not in groups:
            groups[key] = {"channel_id": cid, "channel_title": title, "trades": 0, "wins": 0, "pnl": 0.0}
        groups[key]["trades"] += 1
        groups[key]["pnl"] += t.get("pnl") or 0
        if (t.get("pnl") or 0) > 0:
            groups[key]["wins"] += 1
    result = []
    for g in groups.values():
        g["win_rate"] = round(g["wins"] / g["trades"], 4) if g["trades"] else 0
        g["pnl"] = round(g["pnl"], 2)
        result.append(g)
    return sorted(result, key=lambda x: x["pnl"], reverse=True)


def _aggregate_by_symbol(trades: list[dict]) -> list[dict]:
    groups: dict = {}
    for t in trades:
        sym = t.get("symbol", "Unknown")
        if sym not in groups:
            groups[sym] = {"symbol": sym, "trades": 0, "pnl": 0.0}
        groups[sym]["trades"] += 1
        groups[sym]["pnl"] += t.get("pnl") or 0
    result = []
    for g in groups.values():
        g["pnl"] = round(g["pnl"], 2)
        result.append(g)
    result.sort(key=lambda x: x["pnl"], reverse=True)
    if result:
        result[0]["best"] = True
        result[-1]["worst"] = True
    return result


def _resolve_tenant(request: Request, supplied: Optional[str]) -> str:
    """Decide tenant_id para queries: ?tenant_id=... tiene prioridad, sino
    header X-Tenant-Id, sino 'default'. En futuro se cruzará con el JWT.
    """
    if supplied:
        return supplied
    header = request.headers.get("X-Tenant-Id")
    return header or "default"


@app.get("/api/v1/bridge/analytics/metrics")
def analytics_metrics(request: Request, tenant_id: Optional[str] = None):
    closed = trades_db.fetch_closed_trades(_resolve_tenant(request, tenant_id))
    return _cached(f"metrics:{tenant_id or 'all'}",
                   lambda: compute_metrics(closed))


@app.get("/api/v1/bridge/analytics/equity-curve")
def analytics_equity(request: Request, tenant_id: Optional[str] = None):
    closed = trades_db.fetch_closed_trades(_resolve_tenant(request, tenant_id))
    return _cached(f"equity:{tenant_id or 'all'}",
                   lambda: _build_equity_curve(closed))


@app.get("/api/v1/bridge/analytics/by-channel")
def analytics_by_channel(request: Request, tenant_id: Optional[str] = None):
    all_trades = trades_db.fetch_all_trades(_resolve_tenant(request, tenant_id))
    return _cached(f"by_channel:{tenant_id or 'all'}",
                   lambda: _aggregate_by_channel(all_trades))


@app.get("/api/v1/bridge/analytics/by-symbol")
def analytics_by_symbol(request: Request, tenant_id: Optional[str] = None):
    all_trades = trades_db.fetch_all_trades(_resolve_tenant(request, tenant_id))
    return _cached(f"by_symbol:{tenant_id or 'all'}",
                   lambda: _aggregate_by_symbol(all_trades))


@app.get("/api/v1/bridge/analytics/live-positions")
def analytics_live_positions(request: Request, tenant_id: Optional[str] = None):
    return trades_db.fetch_open_trades(_resolve_tenant(request, tenant_id))


@app.get("/api/v1/bridge/analytics/trades")
def analytics_trades(request: Request, status: Optional[str] = None,
                     tenant_id: Optional[str] = None):
    """Filtros: ?status=OPEN|CLOSED, ?tenant_id=xxx"""
    tid = _resolve_tenant(request, tenant_id)
    if status == "OPEN":
        return trades_db.fetch_open_trades(tid)
    if status == "CLOSED":
        return trades_db.fetch_closed_trades(tid)
    return trades_db.fetch_all_trades(tid)


# ─── Config del bot (canales, lot, risk) ──────────────────────────────────


class ConfigUpdate(BaseModel):
    channels_data: Optional[list[dict]] = None
    risk_management: Optional[dict] = None
    lot_mode: Optional[str] = None
    lot_size: Optional[float] = None
    lot_percentage: Optional[float] = None
    deviation: Optional[int] = None
    symbol_suffix: Optional[str] = None


@app.get("/api/v1/bridge/config")
def get_bot_config():
    """Lee config.json del bot MT5."""
    cfg = config_mgr.read_config()
    return cfg


@app.post("/api/v1/bridge/config")
def update_bot_config(update: ConfigUpdate):
    """Merge atómico de cambios en config.json del bot.

    Solo se persisten los campos provistos en el payload. Útil para que la
    UI React cambie channels_data / risk_management sin pisar el resto.
    """
    payload = update.model_dump(exclude_none=True)
    if not payload:
        raise HTTPException(400, "No fields to update")
    ok, msg = config_mgr.update_config(payload)
    if not ok:
        raise HTTPException(500, msg)
    return {"ok": True, "updated_keys": list(payload.keys())}


# ─── Scan de canales Telegram ──────────────────────────────────────────────


@app.post("/api/v1/bridge/telegram/scan")
def trigger_telegram_scan():
    """Dispara un scan de canales Telegram en el bot vía file signaling.

    El ScanWorker del bot consume cmd_requests.json, ejecuta el scan y
    escribe resultado a cmd_responses.json. Devuelve 202 con request_id.
    """
    request_id = config_mgr.request_scan()
    return {
        "accepted": True,
        "request_id": request_id,
        "poll_url": "/api/v1/bridge/telegram/channels",
    }


@app.get("/api/v1/bridge/telegram/channels")
def get_telegram_channels():
    """Devuelve el último resultado del scan de Telegram.

    Estados posibles:
    - {"status": "NO_SCAN"} — todavía nunca se ejecutó
    - {"status": "PENDING"} — request en curso (cmd_requests.json existe)
    - {"status": "OK", "data": [...]} — scan exitoso
    - {"status": "OK", "error": "..."} — scan terminó con error
    """
    if config_mgr.scan_in_progress():
        return {"status": "PENDING"}

    result = config_mgr.read_scan_result()
    if result is None:
        return {"status": "NO_SCAN"}

    if "error" in result:
        return {"status": "ERROR", "error": result["error"]}

    return {
        "status": "OK",
        "completed_at": result.get("completed_at"),
        "request_id": result.get("request_id"),
        "data": result.get("data", []),
    }


# ─── Bot control (start/stop) ─────────────────────────────────────────────


class BotControlRequest(BaseModel):
    action: str = Field(..., pattern="^(start|stop|wait_config)$")


@app.get("/api/v1/bridge/control/state")
def get_bot_state():
    """Lee bot_state.json: {status, updated_at}."""
    return config_mgr.read_state()


@app.post("/api/v1/bridge/control")
def control_bot(req: BotControlRequest):
    """Set bot_state.json para start/stop/wait_config."""
    mapping = {
        "start": "DEPLOYED",
        "stop": "STOPPED",
        "wait_config": "WAITING_CONFIG",
    }
    new_status = mapping[req.action]
    ok, msg = config_mgr.write_state(new_status)
    if not ok:
        raise HTTPException(500, msg)
    return {"ok": True, "status": new_status}


# ─── Prometheus /metrics ──────────────────────────────────────────────────


# Import lazily so the bridge doesn't fail if the lib is missing.
try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
    PROM_OK = True
except ImportError:
    PROM_OK = False

if PROM_OK:
    # Counters / histograms de las rutas bridge (instrumentadas globalmente
    # con un middleware: cada request entra con un Counter por método/path).
    REQ_COUNTER = Counter(
        "bridge_http_requests_total",
        "Total HTTP requests serviced by the bridge API",
        ["method", "path", "status"],
    )
    REQ_LATENCY = Histogram(
        "bridge_http_request_duration_seconds",
        "Request latency in seconds",
        ["method", "path"],
    )
    OUTBOX_QUEUE_GAUGE = Gauge(
        "bridge_outbox_pending_total",
        "Currently pending outbox events",
    )
    TRADES_GAUGE = Gauge(
        "bridge_trades_total",
        "Total trades recorded",
        ["status"],
    )

    @app.middleware("http")
    async def prometheus_middleware(request: Request, call_next):
        import time
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start
        # Patrón del path para evitar cardinalidad infinita:
        # /api/v1/bridge/config → /api/v1/bridge/config
        # /api/v1/bridge/analytics/metrics → /api/v1/bridge/analytics/{kind}
        path = request.url.path
        if path.startswith("/api/v1/bridge/analytics/"):
            label = "/api/v1/bridge/analytics/{kind}"
        elif path.startswith("/api/v1/bridge/telegram/"):
            label = "/api/v1/bridge/telegram/{kind}"
        elif path.startswith("/api/v1/bridge/"):
            label = "/api/v1/bridge/{kind}"
        else:
            label = path
        REQ_COUNTER.labels(request.method, label, str(response.status_code)).inc()
        REQ_LATENCY.labels(request.method, label).observe(elapsed)
        return response

    @app.get("/metrics")
    def metrics():
        # Updatear gauges al vuelo (no usamos background poll para no agregar
        # más threads en el bridge).
        try:
            stats = outbox.stats()
            OUTBOX_QUEUE_GAUGE.set(stats.get("PENDING", 0))

            by_status = {}
            for t in trades_db.fetch_all_trades():
                by_status[t.get("status", "UNKNOWN")] = by_status.get(t.get("status", "UNKNOWN"), 0) + 1
            for s, n in by_status.items():
                TRADES_GAUGE.labels(s).set(n)
        except Exception:
            pass

        body = generate_latest()
        from fastapi.responses import Response
        return Response(content=body, media_type=CONTENT_TYPE_LATEST)
else:
    @app.get("/metrics")
    def metrics_disabled():
        return {"error": "prometheus_client not installed", "pip": "install prometheus-client"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("BRIDGE_PORT", "8522"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level=LOG_LEVEL.lower())
