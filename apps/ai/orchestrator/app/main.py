"""FastAPI entrypoint para el orchestrator."""
from __future__ import annotations

import asyncio
import logging
import time as _time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from app.config import Settings
from app.multi_orchestrator import MultiSymbolOrchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

settings = Settings()
orchestrator: MultiSymbolOrchestrator | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global orchestrator
    orchestrator = MultiSymbolOrchestrator(settings)
    await orchestrator.start()
    try:
        yield
    finally:
        await orchestrator.stop()


prefix = "/api/v1/orchestrator"

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)


@app.get(f"{prefix}/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "symbols": settings.symbols,
        "timeframes": settings.timeframes,
    }


@app.get(f"{prefix}/stats")
async def stats() -> dict[str, Any]:
    if orchestrator is None:
        return {"error": "not started"}
    return orchestrator.stats()


@app.get(f"{prefix}/signals")
async def signals(limit: int = 50, symbol: str | None = None) -> dict[str, Any]:
    if orchestrator is None:
        return {"error": "not started"}
    items = orchestrator.published_signals(limit=limit, symbol=symbol)
    return {"count": len(items), "limit": limit, "items": items}


@app.get(f"{prefix}/buffer/{{symbol}}")
async def buffer(symbol: str) -> dict[str, Any]:
    if orchestrator is None:
        return {"error": "not started"}
    buf = orchestrator._price_buffer.get(symbol)
    if not buf:
        return {"error": "no buffer", "symbol": symbol}
    return {"symbol": symbol, "size": len(buf), "last": list(buf)[-10:]}


@app.post(f"{prefix}/pause")
async def pause() -> dict[str, Any]:
    if orchestrator is None:
        return {"error": "not started"}
    orchestrator._paused = True
    logger.warning("Orchestrator paused via REST API")
    return {"status": "paused"}


@app.post(f"{prefix}/resume")
async def resume() -> dict[str, Any]:
    if orchestrator is None:
        return {"error": "not started"}
    orchestrator._paused = False
    logger.warning("Orchestrator resumed via REST API")
    return {"status": "resumed"}


@app.get(f"{prefix}/analysis/{{symbol}}")
async def analysis(symbol: str) -> dict[str, Any]:
    """Analisis multi-horizonte para un simbolo.

    Devuelve bias + score master + breakdown por timeframe (M5/H1/H4/D1).
    Es el payload que consume el frontend /analysis/:symbol y el bot
    /analisis para mostrar veredicto maestro al usuario.
    """
    from app.horizon_analyzer import (
        analyze_horizon,
        combine_horizons,
    )
    from app.macro_filter import check_macro_conditions

    if orchestrator is None:
        return {"error": "not started"}

    symbol_up = symbol.upper()
    scores = {}
    for tf in ("M5", "H1", "H4", "D1"):
        try:
            if tf == "H1":
                candles = [
                    {"open": c.open, "high": c.high, "low": c.low, "close": c.close}
                    for c in orchestrator._candle_buffer.get(symbol_up, [])
                ]
            else:
                rates = await orchestrator.price_feed.get_rates(symbol_up, tf, 100)
                candles = [
                    {
                        "open": float(r.get("open", 0.0)),
                        "high": float(r.get("high", 0.0)),
                        "low": float(r.get("low", 0.0)),
                        "close": float(r.get("close", 0.0)),
                    }
                    for r in rates
                ]
            if candles:
                scores[tf] = analyze_horizon(candles, tf)
        except Exception as e:
            logger.warning(f"analysis({symbol_up}, {tf}) failed: {e}")

    if not scores:
        return {
            "symbol": symbol_up,
            "master_bias": "NEUTRAL",
            "master_score": 50.0,
            "horizons": {},
            "macro": {"risk_off": False, "reasons": []},
            "error": "no data",
        }

    sb = combine_horizons(symbol_up, scores)
    macro = await check_macro_conditions()
    return {
        "symbol": symbol_up,
        "master_bias": sb.master_bias,
        "master_score": round(sb.master_score, 1),
        "horizons": {tf: h.to_dict() for tf, h in scores.items()},
        "macro": {
            "risk_off": bool(macro.get("risk_off", False)),
            "reasons": macro.get("reasons", []),
            "confidence_multiplier": float(macro.get("confidence_multiplier", 1.0)),
            "lot_multiplier": float(macro.get("lot_multiplier", 1.0)),
        },
        "ts": _time.time(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, log_level="info")