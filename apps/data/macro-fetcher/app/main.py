from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.fetcher import get_high_impact_events, get_liquidity_snapshot
from app.indicators import get_indicators
from app.market_state import get_market_state

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Macro-fetcher starting")
    yield
    logger.info("Macro-fetcher stopping")


app = FastAPI(
    title="TNSVT Macro Fetcher",
    version="0.2.0",
    lifespan=lifespan,
    root_path="/api/v1/macro",
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "macro-fetcher"}


@app.get("/liquidity")
async def liquidity():
    snap = await get_liquidity_snapshot()
    return {
        "tga_billion": snap.tga_billion,
        "rrp_billion": snap.rrp_billion,
        "fetched_at": snap.fetched_at,
    }


@app.get("/calendar")
async def calendar(days: int = 7):
    events = await get_high_impact_events(next_days=days)
    return {
        "count": len(events),
        "days": days,
        "events": [
            {
                "date": e.date,
                "time": e.time,
                "currency": e.currency,
                "event": e.event,
                "forecast": e.forecast,
                "previous": e.previous,
                "impact": e.impact,
            }
            for e in events
        ],
    }


# ─── F2 — Macro Dashboard endpoints ─────────────────────────────────


@app.get("/indicators")
async def indicators():
    """Pulso Macro — latest CPI, Core CPI, PPI, NFP, Unemployment, Retail."""
    items = await get_indicators()
    return {"count": len(items), "items": items}


@app.get("/market-state")
async def market_state():
    """Estado del mercado — tags cualitativos: DXY, US10Y, Geopolitica, FED, VIX."""
    return await get_market_state()


@app.get("/radar")
async def radar(days: int = 7):
    """Radar Macro — alias de /calendar con default 7d + formateado para cards."""
    events = await get_high_impact_events(next_days=days)
    return {
        "count": len(events),
        "days": days,
        "events": [
            {
                "date": e.date,
                "time": e.time,
                "currency": e.currency,
                "event": e.event,
                "forecast": e.forecast,
                "previous": e.previous,
                "impact": e.impact,
            }
            for e in events
        ],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, log_level="info")