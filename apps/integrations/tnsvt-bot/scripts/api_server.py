"""
TNSVT Copier Bridge - FastAPI Server
Permite que TNSVT envie senales al copiador de forma remota.
"""
import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

load_dotenv(ROOT_DIR / ".env")

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("CopierBridge")

ADMIN_PASSWORD = os.getenv("TNSVT_ADMIN_PASSWORD", "")
SIGNAL_QUEUE: asyncio.Queue = asyncio.Queue(maxsize=100)


class SignalPayload(BaseModel):
    symbol: str
    action: str
    price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[list[float]] = None
    lot: Optional[float] = None
    channel: str = "TNSVT"


class ConfigPayload(BaseModel):
    channels: Optional[dict] = None
    lot_size: Optional[float] = None
    risk_daily_loss_limit: Optional[float] = None
    risk_weekly_loss_limit: Optional[float] = None
    risk_max_open_positions: Optional[int] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Copier Bridge started on port %s", os.getenv("BRIDGE_PORT", "8502"))
    yield
    logger.info("Copier Bridge shutting down")


app = FastAPI(
    title="TNSVT Copier Bridge",
    version="1.0.0",
    lifespan=lifespan,
)


def verify_admin(x_admin_password: str = Header(default="")):
    if not ADMIN_PASSWORD:
        raise HTTPException(500, "TNSVT_ADMIN_PASSWORD not configured")
    if x_admin_password != ADMIN_PASSWORD:
        raise HTTPException(403, "Invalid admin password")


@app.post("/api/signals")
async def receive_signal(signal: SignalPayload, x_admin_password: str = Header(default="")):
    """TNSVT envia una senal para ser copiada en MT5"""
    verify_admin(x_admin_password)
    await SIGNAL_QUEUE.put(signal.model_dump())
    logger.info(f"Signal queued: {signal.action} {signal.symbol}")
    return {"status": "queued", "symbol": signal.symbol, "action": signal.action}


@app.get("/api/signals/pending")
async def get_pending_signals(x_admin_password: str = Header(default="")):
    """El copiador consulta senales pendientes"""
    verify_admin(x_admin_password)

    signals = []
    while not SIGNAL_QUEUE.empty():
        try:
            sig = SIGNAL_QUEUE.get_nowait()
            signals.append(sig)
        except asyncio.QueueEmpty:
            break

    return {"signals": signals, "count": len(signals)}


@app.get("/api/status")
async def get_status(x_admin_password: str = Header(default="")):
    """Estado del copiador"""
    verify_admin(x_admin_password)

    try:
        from signal_copier.risk_manager import RiskManager
        from signal_copier.news_filter import NewsFilter

        risk = RiskManager()
        news = NewsFilter()
        status = risk.get_status()

        return {
            "running": True,
            "mt5_connected": True,
            "daily_pnl": status.get("daily_pnl", 0),
            "weekly_pnl": status.get("weekly_pnl", 0),
            "trades_today": status.get("trades_today", 0),
            "total_trades": status.get("total_trades", 0),
            "win_rate": status.get("win_rate", 0),
            "balance": status.get("balance", 0),
            "news_filter": news.enabled,
        }
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return {"running": True, "error": str(e)}


@app.get("/api/config")
async def get_config(x_admin_password: str = Header(default="")):
    """Configuracion actual del copiador"""
    verify_admin(x_admin_password)

    from config import settings
    return {
        "channels": settings.CHANNELS_CONFIG,
        "lot_size": settings.LOT_SIZE,
        "deviation": settings.DEVIATION,
        "risk_daily_loss_limit": settings.RISK_DAILY_LOSS_LIMIT,
        "risk_daily_profit_target": settings.RISK_DAILY_PROFIT_TARGET,
        "risk_weekly_loss_limit": settings.RISK_WEEKLY_LOSS_LIMIT,
        "risk_max_open_positions": settings.RISK_MAX_OPEN_POSITIONS,
        "risk_trailing_stop": settings.RISK_TRAILING_STOP,
        "risk_trailing_step": settings.RISK_TRAILING_STEP,
        "risk_trailing_start": settings.RISK_TRAILING_START,
        "news_filter_enabled": settings.NEWS_FILTER_ENABLED,
        "news_filter_minutes_before": settings.NEWS_FILTER_MINUTES_BEFORE,
        "news_filter_minutes_after": settings.NEWS_FILTER_MINUTES_AFTER,
    }


@app.put("/api/config")
async def update_config(config: ConfigPayload, x_admin_password: str = Header(default="")):
    """Actualiza configuracion del copiador"""
    verify_admin(x_admin_password)

    updates = {k: v for k, v in config.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No config updates provided")

    env_map = {
        "channels": "CHANNELS",
        "lot_size": "LOT_SIZE",
        "risk_daily_loss_limit": "RISK_DAILY_LOSS_LIMIT",
        "risk_weekly_loss_limit": "RISK_WEEKLY_LOSS_LIMIT",
        "risk_max_open_positions": "RISK_MAX_OPEN_POSITIONS",
    }

    from config import settings
    env_updates = {}
    for key, value in updates.items():
        env_key = env_map.get(key)
        if env_key:
            if key == "channels":
                channels_str = ",".join(f"{name}={enabled}" for name, enabled in value.items())
                env_updates[env_key] = channels_str
            else:
                env_updates[env_key] = str(value)

    if env_updates:
        settings.save(env_updates)
        logger.info(f"Config updated: {list(updates.keys())}")

        trigger_path = ROOT_DIR / "config" / "reload.trigger"
        trigger_path.write_text(str(asyncio.get_event_loop().time()))

    return {"success": True, "updated": list(updates.keys())}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "copier-bridge"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("BRIDGE_PORT", "8502"))
    uvicorn.run(app, host="0.0.0.0", port=port)
