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
import uuid
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
            "GET  /api/v1/bridge/analytics/calendar",
            "GET  /api/v1/bridge/mt5/account",
            "GET  /api/v1/bridge/mt5/positions",
            "POST /api/v1/bridge/copier/trades",
            "PUT  /api/v1/bridge/copier/trades/{id}",
            "POST /api/v1/bridge/copier/status",
            "GET  /api/v1/bridge/copier/status",
            "GET  /api/v1/bridge/copier/dashboard",
        ],
    }


# ─── Copier Status (compat con el bot Python Terminal_Financiera_Pro) ───
#
# Estos endpoints reproducen el contrato del "TNSVT Symphony" PHP para que
# el `signal_copier` y el bot de Telegram (que apuntan via tnsvt_client.py)
# puedan seguir hablando con el bridge-api FastAPI del V2 sin reescritura.
#
# Persistencia: tabla `copier_status` (key/value JSON) en bridge_outbox.db.

import threading as _threading
from typing import Any as _Any

_status_lock = _threading.Lock()


def _init_status_table():
    with trades_db._connect() as _conn:
        _conn.execute(
            """CREATE TABLE IF NOT EXISTS copier_status (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )


_init_status_table()


@app.post("/api/v1/bridge/copier/close")
def copier_close(payload: dict):
    """Encolar un comando de cierre (symbol) para que el signal_copier lo procese.

    Body: {"action": "close", "symbol": "XAUUSD", "by_user": "telegram:<id>"}
    Escribe a D:\\TradingBotMT5\\cmd_requests.json (append-safe).
    Devuelve {"ok": True, "request_id": "...", "open_positions": N}
    """
    if not isinstance(payload, dict):
        raise HTTPException(400, "payload debe ser dict")
    action = payload.get("action")
    symbol = (payload.get("symbol") or "").upper().strip()
    by_user = payload.get("by_user", "anonymous")
    if action != "close":
        raise HTTPException(400, f"action no soportado: {action}")
    if not symbol:
        raise HTTPException(400, "symbol requerido")

    # Verificar posiciones abiertas via MT5 snapshot
    pos_path = Path(os.getenv("BOT_DATA_DIR", r"D:\TradingBotMT5")) / "positions_snapshot.json"
    open_count = 0
    if pos_path.exists():
        try:
            with open(pos_path, encoding="utf-8") as f:
                positions = json.load(f)
            if isinstance(positions, list):
                open_count = sum(
                    1 for p in positions
                    if p.get("symbol", "").upper() == symbol
                )
        except Exception:
            pass

    if open_count == 0:
        return {"ok": False, "detail": f"Sin posiciones abiertas para {symbol}", "open_positions": 0}

    # Generar request_id y agregar a cmd_requests.json
    request_id = f"close_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    cmd_path = Path(os.getenv("BOT_DATA_DIR", r"D:\TradingBotMT5")) / "cmd_requests.json"
    existing = []
    if cmd_path.exists():
        try:
            with open(cmd_path, encoding="utf-8") as f:
                existing = json.load(f)
            if not isinstance(existing, list):
                existing = []
        except Exception:
            existing = []
    existing.append({
        "action": "close_symbol",
        "symbol": symbol,
        "by_user": by_user,
        "request_id": request_id,
        "ts": time.time(),
    })
    tmp = cmd_path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    os.replace(tmp, cmd_path)
    logger.warning("copier_close: queued request_id=%s symbol=%s open=%d by=%s",
                   request_id, symbol, open_count, by_user)
    return {
        "ok": True,
        "request_id": request_id,
        "open_positions": open_count,
    }


@app.get("/api/v1/bridge/copier/dashboard")
def copier_dashboard():
    """Snapshot consolidado: status + MT5 account + métricas analytics + posiciones.

    Compat shape: {"success": True, "status": {...}, "config": {...}, "trades": [...]}
    Replica lo que devolvía Symphony PHP en /api/admin/copier/dashboard.
    """
    status = {}
    with _status_lock:
        with trades_db._connect() as conn:
            for row in conn.execute("SELECT key, value FROM copier_status").fetchall():
                try:
                    status[row["key"]] = json.loads(row["value"])
                except Exception:
                    pass

    metrics = compute_metrics(trades_db.fetch_closed_trades())
    live_positions = trades_db.fetch_open_trades()

    status_payload = {
        "balance": status.get("balance", 0.0),
        "daily_pnl": status.get("daily_pnl", 0.0),
        "weekly_pnl": status.get("weekly_pnl", 0.0),
        "total_trades": metrics.get("total", 0),
        "win_rate": round(metrics.get("win_rate", 0) * 100, 1),
        "mt5_connected": status.get("mt5_connected", False),
        "telegram_bot": status.get("telegram_bot", False),
        "bot_username": status.get("bot_username", ""),
        "last_heartbeat": status.get("last_heartbeat", ""),
        **status.get("extras", {}),
    }

    return {
        "success": True,
        "status": status_payload,
        "config": {},
        "trades": trades_db.fetch_all_trades()[:50],
        "metrics": metrics,
        "live_positions_count": len(live_positions),
    }


@app.post("/api/v1/bridge/copier/status")
def copier_status_upsert(payload: dict):
    """POST /api/v1/bridge/copier/status — heartbeat + merge con campos nuevos.

    El bot lo llama con: telegram_bot=True, bot_username=@x, etc.
    Mergemos con el status actual (igual que Symphony hacia read+merge+POST).
    """
    if not isinstance(payload, dict):
        raise HTTPException(400, "payload debe ser dict")
    with _status_lock, trades_db._connect() as conn:
        # Read current + merge + write back
        cur: dict = {}
        for row in conn.execute("SELECT key, value FROM copier_status").fetchall():
            try:
                cur[row["key"]] = json.loads(row["value"])
            except Exception:
                pass
        cur.update({k: v for k, v in payload.items() if v is not None})
        cur["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
        # Persist every key as separate row
        for k, v in cur.items():
            conn.execute(
                "INSERT OR REPLACE INTO copier_status (key, value, updated_at) VALUES (?, ?, ?)",
                (k, json.dumps(v), datetime.now(timezone.utc).isoformat()),
            )
    return {"success": True, "merged_keys": list(payload.keys()), "total_keys": len(cur)}


@app.get("/api/v1/bridge/copier/status")
def copier_status_get():
    """GET /api/v1/bridge/copier/status — devuelve el status actual (cache)."""
    out = {}
    with _status_lock, trades_db._connect() as conn:
        for row in conn.execute("SELECT key, value FROM copier_status").fetchall():
            try:
                out[row["key"]] = json.loads(row["value"])
            except Exception:
                pass
    return {"status": out}


@app.post("/api/v1/bridge/copier/trades")
def copier_log_trade(payload: dict):
    """POST /api/v1/bridge/copier/trades — log_trade del signal_copier.

    Body: {symbol, action, price, sl, tp, result, pnl, notes, account_id?, channel_id?, channel_title?}
    Mapping:
      - genera ticket deterministico NEGATIVO a partir de timestamp+symbol si no hay
      - persiste en trades_db (que es el mismo store que ya usa /api/v1/bridge/mt5/order)
      - devuelve {id, ticket} para que el bot pueda mapear luego en trade_map.json
    """
    required = ["symbol", "action"]
    for k in required:
        if k not in payload:
            raise HTTPException(400, f"missing field: {k}")

    action = payload["action"]
    symbol = payload["symbol"]
    result = payload.get("result", "OPEN")

    # Ticket sintetico solo si el bot no proporciona uno (signal_copier no lleva counter).
    ticket = payload.get("ticket")
    if not ticket:
        # tick negativo basado en epoch microsegundo, unico
        ticket = -int(datetime.now(timezone.utc).timestamp() * 1_000_000) % 2_000_000_000

    pnl_val = float(payload.get("pnl") or 0)

    now_iso = datetime.now(timezone.utc).isoformat()

    # extraer canal si viene en notes
    notes = payload.get("notes") or ""
    channel_title = payload.get("channel_title") or ""
    if not channel_title and notes:
        channel_title = notes

    row = {
        "ticket": ticket,
        "symbol": symbol,
        "action": action,
        "volume": float(payload.get("volume") or 0.01),
        "price": payload.get("price"),
        "open_price": payload.get("price"),
        "sl": payload.get("sl"),
        "tp": payload.get("tp"),
        "pnl": pnl_val,
        "status": "CLOSED" if result in ("WIN", "LOSS", "CLOSED", "BREAKEVEN", "ERROR") else "OPEN",
        "opened_at": now_iso,
        "closed_at": now_iso if result in ("WIN", "LOSS", "CLOSED", "BREAKEVEN", "ERROR") else None,
        "channel_id": payload.get("channel_id"),
        "channel_title": channel_title,
        "topic_id": payload.get("topic_id"),
        "received_at": now_iso,
        "tenant_id": payload.get("tenant_id") or "default",
        "source": payload.get("source") or "signal_copier",
    }
    trades_db.upsert_trade(row)
    # devolver id interno (autoincrement) aproximado via rowcount/ticket
    return {"id": ticket, "ticket": ticket, "success": True}


@app.put("/api/v1/bridge/copier/trades/{trade_id}")
def copier_update_trade(trade_id: int, payload: dict):
    """PUT /api/v1/bridge/copier/trades/{id} — update_trade del bot.

    Acepta update parcial: {result?, pnl?, sl?, tp?}.
    """
    if not isinstance(payload, dict) or not payload:
        raise HTTPException(400, "payload vacio")

    fields = {}
    if "result" in payload:
        result = payload["result"]
        fields["status"] = "CLOSED" if result in ("WIN", "LOSS", "CLOSED", "BREAKEVEN") else result
        if result in ("WIN", "LOSS", "CLOSED", "BREAKEVEN"):
            fields["closed_at"] = datetime.now(timezone.utc).isoformat()
    if "pnl" in payload:
        fields["pnl"] = float(payload["pnl"])
    if "sl" in payload:
        fields["sl"] = payload["sl"]
    if "tp" in payload:
        fields["tp"] = payload["tp"]

    if not fields:
        raise HTTPException(400, "no actualizable")

    set_clause = ", ".join(f"{k}=?" for k in fields)
    values = list(fields.values())
    values.append(trade_id)

    with trades_db._lock, trades_db._connect() as conn:
        cur = conn.execute(
            f"UPDATE trades SET {set_clause} WHERE ticket=? OR id=?",
            (*values, trade_id),
        )
        if cur.rowcount == 0:
            # intentar por id interno
            cur = conn.execute(
                f"UPDATE trades SET {set_clause} WHERE id=?",
                tuple(values),
            )
    return {"success": True, "updated": cur.rowcount}


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


@app.get("/api/v1/bridge/analytics/calendar")
def analytics_calendar(request: Request, tenant_id: Optional[str] = None,
                       year: Optional[int] = None):
    """Daily P&L aggregated for a heatmap view.

    Returns [{date: 'YYYY-MM-DD', pnl: float, trades: int}, ...]
    for the given year (default: current year).
    """
    tid = _resolve_tenant(request, tenant_id)
    all_trades = trades_db.fetch_all_trades(tid)
    closed = [t for t in all_trades if t.get("status") == "CLOSED"]
    y = year or datetime.now(timezone.utc).year
    daily: dict[str, dict] = {}
    for t in closed:
        d = (t.get("closed_at") or "")[:10]
        if not d or not d.startswith(str(y)):
            continue
        if d not in daily:
            daily[d] = {"date": d, "pnl": 0.0, "trades": 0}
        daily[d]["pnl"] += t.get("pnl") or 0
        daily[d]["trades"] += 1
    for v in daily.values():
        v["pnl"] = round(v["pnl"], 2)
    return _cached(f"calendar:{tid}:{y}", lambda: sorted(daily.values(), key=lambda x: x["date"]))


@app.get("/api/v1/bridge/analytics/live-positions")
def analytics_live_positions(request: Request, tenant_id: Optional[str] = None):
    return trades_db.fetch_open_trades(_resolve_tenant(request, tenant_id))


@app.get("/api/v1/bridge/analytics/trades")
def analytics_trades(request: Request, status: Optional[str] = None,
                     tenant_id: Optional[str] = None,
                     since_days: Optional[int] = None):
    """Filtros:
       ?status=OPEN|CLOSED
       ?tenant_id=xxx
       ?since_days=N   -> ignorar trades con mas de N dias de antiguedad
                          (para destrabar la vista cuando hay muchos viejos)
    """
    tid = _resolve_tenant(request, tenant_id)
    all_trades = trades_db.fetch_all_trades(tid)
    if since_days is not None and since_days > 0:
        from datetime import datetime as _dt, timedelta as _td
        cutoff = (_dt.now(timezone.utc) - _td(days=since_days)).isoformat()
        all_trades = [t for t in all_trades if (t.get("opened_at") or "") >= cutoff]

    if status == "OPEN":
        return [t for t in all_trades if t.get("status") == "OPEN"]
    if status == "CLOSED":
        return [t for t in all_trades if t.get("status") == "CLOSED"]
    return all_trades


@app.post("/api/v1/admin/trades/cleanup")
def admin_cleanup_trades(older_than_days: int = 90,
                          confirm: bool = False,
                          tenant_id: Optional[str] = None):
    """Limpia trades viejos (>older_than_days) de bridge_outbox.db.

    Safety: requiere confirm=True. Mantiene el schema Copernicus intacto.
    Devuelve el numero de trades eliminados.
    """
    if not confirm:
        raise HTTPException(400, "Se requiere confirm=true para ejecutar cleanup")
    with trades_db._connect() as conn:
        count_before = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        conn.execute(
            "DELETE FROM trades WHERE opened_at < datetime('now', ?)",
            (f"-{int(older_than_days)} days",),
        )
        conn.commit()
        count_after = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    deleted = count_before - count_after
    logger.warning("admin_cleanup_trades: borrados %d trades viejos (older than %d days) by tenant=%s",
                  deleted, older_than_days, tenant_id)
    return {"ok": True, "deleted": deleted, "remaining": count_after}


@app.post("/api/v1/admin/seed_demo")
def admin_seed_demo():
    """Crea trades semilla para que la pagina Admin tenga data visible.

    Idempotente: solo siembra si la tabla esta vacia.
    """
    with trades_db._connect() as conn:
        existing = conn.execute("SELECT COUNT(*) FROM trades WHERE tenant_id='admin_demo'").fetchone()[0]
        if existing > 0:
            return {"ok": True, "skipped": True, "reason": f"ya hay {existing} trades demo"}

        now = datetime.now(timezone.utc).isoformat()
        demo = [
            ("EURUSD",  "BUY",  1.08500,  1.080,    1.090,   35.50,  "@canal_test",                 999,  "tenant_demo_starter"),
            ("XAUUSD",  "SELL", 3997.06,  4031.8,   3959.3, -28.50, "XAU LIQUIDITY PRIVADO", 1001,  "tenant_demo_pro"),
            ("GBPUSD",  "BUY",  1.26800,  1.262,    1.275,   12.50,  "@canal_test",                999,  "tenant_demo_starter"),
            ("BTCUSD",  "BUY",  89110.6,  88000.0,  89500.0, -10.00, "INVESTMENTH VIP",        1002,  "tenant_demo_enterprise"),
            ("USDJPY",  "BUY",  138.500,  137.800,  139.200,  22.50, "Señales Vip",              1003,  "tenant_demo_pro"),
            ("ETHUSD",  "BUY",  3450.0,   3300.0,   3600.0,  -8.50,  "Cobrax VIP",               1004,  "tenant_demo_enterprise"),
            ("AUDUSD",  "SELL", 0.6580,   0.6650,   0.6520,   4.50,  "World Forex Research",    1005,  "tenant_demo_starter"),
            ("EURJPY",  "BUY",  155.40,   154.50,   156.50,  -2.50,  "@canal_test",                999,  "tenant_demo_starter"),
        ]
        for sym, action, price, sl, tp, pnl, channel, cid, tid in demo:
            conn.execute(
                """INSERT INTO trades
                   (ticket, symbol, action, volume, open_price, close_price,
                    sl, tp, pnl, commission, swap,
                    opened_at, closed_at,
                    channel_id, channel_title, topic_id,
                    status, received_at, tenant_id, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    abs(hash(sym + action + str(price))) % 1_000_000_000,
                    sym, action, 0.01, price, price,
                    sl, tp, pnl, 0.0, 0.0,
                    now, now, cid, channel, None,
                    "CLOSED", now, tid, "admin_demo"
                )
            )
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM trades WHERE tenant_id='admin_demo'").fetchone()[0]
    return {"ok": True, "seeded": count}


@app.get("/api/v1/admin/tenants_demo")
def admin_tenants_demo():
    """Lista de tenants demo para la pagina Admin.

    Devuelve tenants ficticios (free / starter / pro / enterprise) con
    metricas para que la UI muestre como se ve en produccion.
    """
    from datetime import datetime as _dt, timedelta as _td
    base = _dt.now() - _td(days=20)

    demo = [
        {"id": "tn_demo_free_01",       "name": "Juan Picapiedra",      "slug": "juan-picapiedra",      "schema": "tenant_demo_free",       "status": "active",    "plan": "free",       "max_users": 1,   "max_signals_per_day": 25,  "created_at": (base + _td(days=5)).isoformat(),  "last_login_at": (_dt.now() - _td(hours=2)).isoformat()},
        {"id": "tn_demo_starter_01",    "name": "Sofia Starter",        "slug": "sofia-starter",        "schema": "tenant_demo_starter",    "status": "active",    "plan": "starter",    "max_users": 3,   "max_signals_per_day": 100, "created_at": (base + _td(days=8)).isoformat(),  "last_login_at": (_dt.now() - _td(minutes=15)).isoformat()},
        {"id": "tn_demo_pro_01",        "name": "Carlos Pro",           "slug": "carlos-pro",           "schema": "tenant_demo_pro",        "status": "active",    "plan": "pro",        "max_users": 10,  "max_signals_per_day": 500, "created_at": (base + _td(days=12)).isoformat(), "last_login_at": (_dt.now() - _td(minutes=2)).isoformat()},
        {"id": "tn_demo_enterprise_01", "name": "Trading Corp SA",      "slug": "trading-corp-sa",      "schema": "tenant_demo_enterprise", "status": "active",    "plan": "enterprise", "max_users": 50,  "max_signals_per_day": 2500,"created_at": (base + _td(days=18)).isoformat(), "last_login_at": (_dt.now() - _td(hours=8)).isoformat()},
        {"id": "tn_demo_trial_01",      "name": "Maria Trial (12 dias)","slug": "maria-trial",          "schema": "tenant_demo_trial",      "status": "trial",     "plan": "pro",        "max_users": 5,   "max_signals_per_day": 200, "created_at": (base + _td(days=15)).isoformat(), "last_login_at": (_dt.now() - _td(days=1)).isoformat()},
    ]

    stats = {
        "total_tenants": len(demo),
        "active_subscriptions": sum(1 for t in demo if t["status"] == "active" and t["plan"] != "free"),
        "mrr_usd": sum({"free": 0, "starter": 49, "pro": 199, "enterprise": 999}[t["plan"]] for t in demo if t["status"] == "active"),
        "churn_pct": 2.4,
        "by_plan": [
            {"plan": "free",       "count": sum(1 for t in demo if t["plan"] == "free")},
            {"plan": "starter",    "count": sum(1 for t in demo if t["plan"] == "starter")},
            {"plan": "pro",        "count": sum(1 for t in demo if t["plan"] == "pro")},
            {"plan": "enterprise", "count": sum(1 for t in demo if t["plan"] == "enterprise")},
        ],
        "pricing_per_plan_usd": {"free": 0, "starter": 49, "pro": 199, "enterprise": 999},
    }
    return {"ok": True, "tenants": demo, "stats": stats}


# ─── Config del bot (canales, lot, risk) ──────────────────────────────────


class ConfigUpdate(BaseModel):
    channels_data: Optional[list[dict]] = None
    risk_management: Optional[dict] = None
    lot_mode: Optional[str] = None
    lot_size: Optional[float] = None
    lot_percentage: Optional[float] = None
    deviation: Optional[int] = None
    symbol_suffix: Optional[str] = None
    trailing_stop: Optional[dict] = None


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


# ─── MT5 Live Snapshots (leídos del bot) ─────────────────────────────────


BOT_SNAPSHOT_DIR = os.getenv("BOT_SNAPSHOT_DIR", r"D:\TradingBotMT5")


def _read_json_safe(path: str) -> dict | list | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


@app.get("/api/v1/bridge/mt5/account")
def get_mt5_account(request: Request):
    """Cuenta MT5 en vivo: balance, equity, margin, leverage, etc.

    Acepta ?login=XXXX para pedir una cuenta especifica.
    Sin param devuelve la cuenta legacy/principal.
    """
    login_param = None
    if "login" in request.query_params:
        try:
            login_param = int(request.query_params["login"])
        except ValueError:
            pass

    if login_param is not None:
        snap_path = Path(os.getenv("BOT_DATA_DIR", r"D:\TradingBotMT5")) / f"account_snapshot_{login_param}.json"
        data = _read_json_safe(str(snap_path))
        if data is None:
            raise HTTPException(404, f"No hay snapshot para login {login_param}")
        return {"ok": True, "data": data, "login": login_param}

    data = _read_json_safe(os.path.join(BOT_SNAPSHOT_DIR, "account_snapshot.json"))
    if data is None:
        raise HTTPException(503, "MT5 snapshot not available (bot may be disconnected)")
    return {"ok": True, "data": data}


@app.get("/api/v1/bridge/mt5/accounts")
def list_mt5_accounts():
    """Lista todas las cuentas configuradas en accounts.json con sus snapshots.

    Multi-cuenta: detecta cada account_snapshot_<login>.json y lo combina
    con el alias y nombre del accounts.json.
    """
    base_dir = Path(os.getenv("BOT_DATA_DIR", r"D:\TradingBotMT5"))
    accounts_file = base_dir / "accounts.json"
    accounts_cfg: list = []
    if accounts_file.exists():
        try:
            data = json.loads(accounts_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                accounts_cfg = data
        except Exception:
            pass

    accounts_out = []
    seen_logins = set()
    for cfg in accounts_cfg:
        login = cfg.get("login")
        if not login or login in seen_logins:
            continue
        seen_logins.add(login)
        snap = _read_json_safe(str(base_dir / f"account_snapshot_{login}.json")) or {}
        accounts_out.append({
            "login": login,
            "alias": cfg.get("alias", f"acc_{login}"),
            "name": cfg.get("name", snap.get("name", "?")),
            "server": cfg.get("server", snap.get("server", "?")),
            "balance": snap.get("balance"),
            "equity": snap.get("equity"),
            "margin": snap.get("margin"),
            "profit": snap.get("profit"),
            "open_positions": snap.get("open_positions"),
            "updated_at": snap.get("updated_at"),
        })

    # Tambien detectar cuentas que tienen snapshot pero no estan en accounts.json
    for path in base_dir.glob("account_snapshot_*.json"):
        try:
            login = int(path.stem.replace("account_snapshot_", ""))
        except ValueError:
            continue
        if login in seen_logins:
            continue
        seen_logins.add(login)
        snap = _read_json_safe(str(path)) or {}
        accounts_out.append({
            "login": login,
            "alias": f"acc_{login}",
            "name": snap.get("name", "?"),
            "server": snap.get("server", "?"),
            "balance": snap.get("balance"),
            "equity": snap.get("equity"),
            "margin": snap.get("margin"),
            "profit": snap.get("profit"),
            "open_positions": snap.get("open_positions"),
            "updated_at": snap.get("updated_at"),
        })

    total_balance = sum(a["balance"] for a in accounts_out if a.get("balance"))
    total_equity = sum(a["equity"] for a in accounts_out if a.get("equity"))
    total_pnl = sum(a["profit"] for a in accounts_out if a.get("profit"))
    total_open = sum(a.get("open_positions") or 0 for a in accounts_out)

    return {
        "ok": True,
        "count": len(accounts_out),
        "accounts": accounts_out,
        "aggregate": {
            "total_balance": round(total_balance, 2),
            "total_equity": round(total_equity, 2),
            "total_pnl": round(total_pnl, 2),
            "total_open_positions": total_open,
        },
    }


@app.get("/api/v1/bridge/mt5/positions")
def get_mt5_positions(request: Request):
    """Todas las posiciones abiertas en MT5 (bot + manuales).

    Acepta ?login=XXXX para pedir posiciones de una cuenta especifica.
    """
    login_param = None
    if "login" in request.query_params:
        try:
            login_param = int(request.query_params["login"])
        except ValueError:
            pass

    if login_param is not None:
        pos_path = Path(os.getenv("BOT_DATA_DIR", r"D:\TradingBotMT5")) / f"positions_snapshot_{login_param}.json"
        data = _read_json_safe(str(pos_path))
        if data is None:
            raise HTTPException(404, f"No hay posiciones para login {login_param}")
        return {"ok": True, "data": data, "count": len(data) if data else 0}

    data = _read_json_safe(os.path.join(BOT_SNAPSHOT_DIR, "positions_snapshot.json"))
    if data is None:
        raise HTTPException(503, "Positions snapshot not available")
    return {"ok": True, "data": data, "count": len(data) if data else 0}


@app.get("/api/v1/bridge/mt5/signal_copier_status")
def signal_copier_status():
    """Lee el archivo var/mt5_status.json que escribe el signal_copier (Python).

    Devuelve connected, balance, open_positions, y los P&L agregados.
    Si el signal_copier no ha escrito nunca, devuelve connected=False.
    """
    import json as _json
    from pathlib import Path as _P
    # El bridge-api corre dentro de TNSVT V2; el signal_copier escribe en
    # la carpeta var/ del proyecto Python. La ruta se resuelve via env o default.
    candidate_paths = [
        os.getenv("SIGNAL_COPIER_VAR", ""),
        r"D:\TradingBotMT5\var\mt5_status.json",
        r"C:\Users\HP 240 inch G9\OneDrive\Desktop\Importante ultimas cosas\Terminal_Financiera_Pro_Completo\Terminal_Financiera_Pro\var\mt5_status.json",
    ]
    for path in candidate_paths:
        if not path:
            continue
        p = _P(path)
        if p.exists():
            try:
                data = _json.loads(p.read_text(encoding="utf-8"))
                return {"ok": True, "data": data, "path": str(p)}
            except Exception as e:
                return {"ok": False, "error": str(e)}
    return {"ok": False, "error": "signal_copier status file not found", "connected": False}


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
