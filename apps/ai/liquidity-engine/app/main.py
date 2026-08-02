import asyncio
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Optional

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
from app.zones_engine import ZonesEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

settings = Settings()
app = FastAPI(title=settings.app_name, version="0.2.0", root_path="/api/v1/lst")

engine = LSTEngine()
zones_engine = ZonesEngine(engine)
nats_pub = NATSPublisher(settings.nats_url, settings.nats_stream, settings.nats_subject_lst)
http_client: httpx.AsyncClient | None = None

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
        if isinstance(data, dict):
            rates = data.get("rates") or data.get("data") or []
            return [RateOHLCV(**r) for r in rates]
        return None
    except Exception as e:
        logger.warning("Error fetching rates for %s %s: %s", symbol, timeframe, e)
        return None


async def fetch_latest_rate(symbol: str, timeframe: str) -> tuple[Optional[RateOHLCV], Optional[float]]:
    rates = await fetch_rates(symbol, timeframe)
    if not rates:
        return None, None
    last = rates[-1]
    return last, float(last.close)


async def lst_signal_loop():
    await nats_pub.connect()
    logger.info("LST signal loop started (interval=%ds)", settings.lst_interval_seconds)

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


async def zones_signal_loop():
    """Convierte zonas en señales LST y las publica en tnsvt.lst.signal."""
    await nats_pub.connect()
    logger.info("Zones signal loop started (interval=%ds)", settings.lst_interval_seconds)

    while True:
        for symbol in settings.symbols:
            for tf in settings.timeframes:
                zones = list(_zones_store.get((symbol.upper(), tf), []))
                if not zones:
                    continue

                rate, price = await fetch_latest_rate(symbol, tf)
                if price is None or price <= 0:
                    continue

                signal = zones_engine.evaluate(
                    symbol=symbol,
                    timeframe=tf,
                    price=price,
                    zones=zones,
                    rate=rate,
                )
                if signal is None:
                    continue

                await nats_pub.publish(signal)
                logger.info(
                    "ZONES-SIGNAL %s %s %s | conf=%.2f | active_zones=%d",
                    signal.symbol, signal.signal_type, signal.timeframe,
                    signal.confidence, len([z for z in zones if not z.get("swept")]),
                )
        await asyncio.sleep(settings.lst_interval_seconds)


@app.on_event("startup")
async def startup():
    global http_client
    http_client = httpx.AsyncClient(timeout=10)
    asyncio.create_task(lst_signal_loop())
    asyncio.create_task(zones_signal_loop())


@app.on_event("shutdown")
async def shutdown():
    global http_client
    if http_client:
        await http_client.aclose()
    await nats_pub.close()


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": settings.app_name,
        "zones_keys": list(_zones_store.keys()),
        "symbols": settings.symbols,
    }


@app.get("/latest")
async def latest_signal(symbol: str = "XAUUSD", timeframe: str = "M1"):
    rate, price = await fetch_latest_rate(symbol, timeframe)
    if price is None:
        return {"signal": None, "error": "no rates"}

    zones = list(_zones_store.get((symbol.upper(), timeframe), []))
    zone_signal = zones_engine.evaluate(
        symbol=symbol,
        timeframe=timeframe,
        price=price,
        zones=zones,
        rate=rate,
    )
    if zone_signal:
        return {"signal": zone_signal.model_dump(mode="json"), "source": "zones"}

    if rate is not None:
        micro_signal = engine.compute(rate)
        if micro_signal:
            return {"signal": micro_signal.model_dump(mode="json"), "source": "microstructure"}

    return {"signal": None}


@app.post("/reset")
async def reset():
    engine.reset()
    _zones_store.clear()
    return {"status": "reset"}


# ─── Liquidity Zones (from MQL5 EA LiquidityZones.mq5) ────────────────


@app.post("/zones", response_model=LiquidityZonesIngestResponse)
async def ingest_zones(payload: LiquidityZonesPayload):
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
    out = {}
    for (sym, tf), bucket in _zones_store.items():
        if symbol and sym != symbol.upper():
            continue
        counts: dict[str, int] = {}
        active = 0
        for z in bucket:
            counts[z["type"]] = counts.get(z["type"], 0) + 1
            if not z.get("swept"):
                active += 1
        out[f"{sym}|{tf}"] = {
            "symbol": sym,
            "timeframe": tf,
            "total": len(bucket),
            "active": active,
            "by_type": counts,
        }
    return {"groups": out}
