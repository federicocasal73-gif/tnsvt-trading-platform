"""HTTP endpoints for the regime-detector service.

Exposes:
- GET  /health                  liveness + dependency status
- GET  /health/ready             readiness (Redis + NATS reachable)
- GET  /metrics                  Prometheus
- POST /api/v1/regime/classify   run classification on a synthetic OHLC
- GET  /api/v1/regime/:symbol    latest cached regime for a symbol
- GET  /api/v1/regime            list all cached regimes
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field

from app.indicators.classifier import RegimeSignal
from app.services.dependencies import Dependencies

REQUEST_COUNT = __import__("prometheus_client", fromlist=["Counter"]).Counter(
    "regime_detector_requests_total", "HTTP requests", ["method", "path", "status"]
)


class OhlcBars(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    closes: list[float] = Field(..., min_length=30)
    highs: list[float] | None = None
    lows: list[float] | None = None


def create_app(deps: Dependencies) -> FastAPI:
    app = FastAPI(title="TNSVT Regime Detector", version="0.1.0", description="Market regime classification (GARCH+ADX+Hurst+BB squeeze)")

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "service": "regime-detector",
            "version": "0.1.0",
            "dependencies": await _check(deps),
            "symbols_tracked": list(deps.classifier.states.keys()),
        }

    @app.get("/health/live")
    async def live():
        return {"status": "alive"}

    @app.get("/health/ready")
    async def ready():
        deps_status = await _check(deps)
        ok = deps_status["nats"]
        return Response(
            content='{"status":"ready"}' if ok else '{"status":"degraded"}',
            media_type="application/json",
            status_code=200 if ok else 503,
        )

    @app.get("/metrics")
    async def metrics():
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.post("/api/v1/regime/classify", response_model=dict)
    async def classify(payload: OhlcBars):
        """Run the regime classifier on the supplied OHLC series.

        Useful for ad-hoc analysis and unit-testing the model via HTTP.
        Feeds each (high, low, close) into a fresh classifier and returns
        the final signal.
        """
        from app.indicators.classifier import RegimeClassifier

        n = len(payload.closes)
        highs = payload.highs or payload.closes
        lows = payload.lows or payload.closes
        if len(highs) != n or len(lows) != n:
            raise HTTPException(status_code=400, detail="closes/highs/lows length mismatch")

        cls = RegimeClassifier()
        for i in range(n):
            cls.feed(payload.symbol, payload.closes[i], highs[i], lows[i])
        sig = cls.classify(payload.symbol)
        if sig is None:
            raise HTTPException(status_code=400, detail="Not enough bars to classify")
        return sig.to_dict()

    @app.get("/api/v1/regime")
    async def list_regimes():
        out = []
        for sym, st in deps.classifier.states.items():
            sig = deps.classifier.classify(sym)
            if sig is not None:
                out.append(sig.to_dict())
        return {"count": len(out), "items": out}

    @app.get("/api/v1/regime/{symbol}")
    async def get_regime(symbol: str):
        sig = deps.classifier.classify(symbol.upper())
        if sig is None:
            raise HTTPException(status_code=404, detail="No data for symbol yet")
        return sig.to_dict()

    return app


async def _check(deps: Dependencies) -> dict[str, bool]:
    redis_ok = False
    nats_ok = False
    pg_ok = False
    if deps.redis:
        try:
            redis_ok = await asyncio.wait_for(deps.redis.ping(), timeout=2)
        except Exception:
            redis_ok = False
    if deps.nats_conn:
        nats_ok = deps.nats_conn.is_connected
    if deps.pg_pool:
        try:
            async with deps.pg_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            pg_ok = True
        except Exception:
            pg_ok = False
    return {"redis": redis_ok, "nats": nats_ok, "postgres": pg_ok}