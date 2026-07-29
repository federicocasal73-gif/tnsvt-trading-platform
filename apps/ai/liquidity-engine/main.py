import asyncio
import logging
from collections import deque
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, HTTPException

from app.config import Settings
from app.lst_engine import LSTEngine
from app.models import (
    LiquidityZonesIngestResponse,
    LiquidityZonesPayload,
    RateOHLCV,
)
from app.nats_client import NATSPublisher

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

settings = Settings()
app = FastAPI(title=settings.app_name, version="0.1.0")

engine = LSTEngine()
nats_pub = NATSPublisher(settings.nats_url, settings.nats_stream, settings.nats_subject_lst)
http_client: httpx.AsyncClient | None = None

# ─── In-memory store for liquidity zones (from MQL5 EA) ────────────────
# Keyed by (symbol, timeframe). Bounded to last 200 zones per key.
_zones_store: dict[tuple[str, str], deque] = {}
_last_payload: LiquidityZonesIngestResponse | None = None


async def fetch_rates(symbol: str, timeframe: str) -> list[RateOHLCV] | None:
    if not http_client:
        return None
    try:
        resp = await http_client.get(
            f"{settings.mt5_connector_url}/rates",
            params={"symbol": symbol, "timeframe": timeframe, "limit": 20},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return [RateOHLCV(**r) for r in data]
        return None
    except Exception as e:
        logger.warning("Error fetching rates for %s %s: %s", symbol, timeframe, e)
        return None


async def signal_loop():
    await nats_pub.connect()
    logger.info("Signal loop started (interval=%ds)", settings.lst_interval_seconds)

    while True:
        for symbol in settings.symbols:
            for tf in settings.timeframes:
                rates = await fetch_rates(symbol, tf)
                if not rates:
                    logger.debug("No rates for %s %s", symbol, tf)
                    continue

                for rate in rates:
                    signal = engine.compute(rate)
                    if signal is None:
                        continue

                    await nats_pub.publish(signal)
                    logger.info(
                        "LST %s | %s %s | conf=%.2f | spread=%.1f | score=%.2f",
                        signal.symbol, signal.signal_type, signal.timeframe,
                        signal.confidence, signal.metrics.relative_spread,
                        signal.metrics.liquidity_score,
                    )
        await asyncio.sleep(settings.lst_interval_seconds)


@app.on_event("startup")
async def startup():
    global http_client
    http_client = httpx.AsyncClient(timeout=10)
    asyncio.create_task(signal_loop())


@app.on_event("shutdown")
async def shutdown():
    global http_client
    if http_client:
        await http_client.aclose()
    await nats_pub.close()


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.app_name}


@app.get("/lst/latest")
async def latest_signal(symbol: str = "XAUUSD", timeframe: str = "M1"):
    rates = await fetch_rates(symbol, timeframe)
    if not rates:
        return {"signal": None, "error": "no rates"}
    for rate in rates:
        signal = engine.compute(rate)
        if signal:
            return {"signal": signal.model_dump(mode="json")}
    return {"signal": None}


@app.post("/reset")
async def reset():
    engine.reset()
    return {"status": "reset"}


# ─── Liquidity Zones (from MQL5 EA LiquidityZones.mq5) ────────────────


@app.post("/zones", response_model=LiquidityZonesIngestResponse)
async def ingest_zones(payload: LiquidityZonesPayload):
    """Recibe zonas de liquidez publicadas por el EA MQL5.

    Body example (lo que envia el EA cada InpPublishSeconds):
    {
      "account_id": "10011629660",
      "symbol": "XAUUSD",
      "timeframe": "H1",
      "ts": 1785300000,
      "count": 24,
      "zones": [
        {"symbol":"XAUUSD","timeframe":"H1","type":"swing_high",
         "price_high":2410.5,"price_low":2408.0,"midpoint":2409.25,
         "time_start":1785299000,"time_end":1785300000,"strength":1,"swept":false},
        ...
      ]
    }
    """
    global _last_payload
    accepted = 0
    rejected = 0

    key = (payload.symbol.upper(), payload.timeframe)
    bucket = _zones_store.setdefault(key, deque(maxlen=200))

    for z in payload.zones:
        if z.type not in {
            "swing_high", "swing_low",
            "equal_high", "equal_low",
            "fvg_bull", "fvg_bear",
            "bos_bull", "bos_bear",
        }:
            rejected += 1
            continue
        if z.price_high < z.price_low:
            rejected += 1
            continue
        bucket.append(z.model_dump())
        accepted += 1

    _last_payload = LiquidityZonesIngestResponse(
        accepted=accepted,
        rejected=rejected,
        total=accepted + rejected,
        stored_account_id=payload.account_id,
        stored_at=datetime.now(timezone.utc),
    )

    logger.info(
        "zones ingest: account=%s symbol=%s tf=%s accepted=%d rejected=%d",
        payload.account_id, payload.symbol, payload.timeframe, accepted, rejected,
    )
    return _last_payload


@app.get("/zones/latest")
async def latest_zones(symbol: str, timeframe: str, limit: int = 50):
    """Devuelve las ultimas zonas publicadas para symbol+timeframe."""
    bucket = _zones_store.get((symbol.upper(), timeframe))
    if not bucket:
        return {"symbol": symbol, "timeframe": timeframe, "count": 0, "zones": []}
    items = list(bucket)[-limit:]
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "count": len(items),
        "zones": items,
    }


@app.get("/zones/summary")
async def zones_summary(symbol: str | None = None):
    """Resumen de zonas agrupadas por (symbol, timeframe) y tipo."""
    out = {}
    for (sym, tf), bucket in _zones_store.items():
        if symbol and sym != symbol.upper():
            continue
        counts: dict[str, int] = {}
        for z in bucket:
            counts[z["type"]] = counts.get(z["type"], 0) + 1
        out[f"{sym}|{tf}"] = {
            "symbol": sym,
            "timeframe": tf,
            "total": len(bucket),
            "by_type": counts,
        }
    return {"groups": out}
