"""FastAPI entrypoint para el orchestrator."""
from __future__ import annotations

import asyncio
import logging
import os
import time as _time
from contextlib import asynccontextmanager
from typing import Any

import jwt as pyjwt
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

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


JWT_SECRET = os.getenv("JWT_SECRET", "")
if not JWT_SECRET or len(JWT_SECRET) < 32:
    logger.warning("JWT_SECRET not set; orchestrator auth disabled")

AUTH_REQUIRED_PATHS = {f"{prefix}/pause", f"{prefix}/resume"}


def _verify_token(auth_header: str) -> dict:
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "Authorization header required")
    token = auth_header[7:]
    try:
        payload = pyjwt.decode(
            token, JWT_SECRET, algorithms=["HS256"],
            options={"require": ["exp", "uid", "type"]},
        )
        if payload.get("type") != "access":
            raise HTTPException(401, "refresh tokens not allowed")
        return payload
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(401, "token expired")
    except pyjwt.InvalidTokenError as e:
        raise HTTPException(401, f"invalid token: {e}")


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if path not in AUTH_REQUIRED_PATHS:
        return await call_next(request)
    if not JWT_SECRET or len(JWT_SECRET) < 32:
        return await call_next(request)
    auth_header = request.headers.get("Authorization", "")
    try:
        _verify_token(auth_header)
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"error": e.detail})
    return await call_next(request)


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
    """Analisis multi-horizonte + playbook para un simbolo.

    Devuelve:
    - bias + score master + breakdown por timeframe (M5/H1/H4/D1)
    - drivers[]: 5 categorias con status
    - price_range: zona del precio en su rango
    - playbook_daily + playbook_intraday: accion + entry + SL + TP
    - divergences[]: macro / H1 / M5
    - narrative: parrafo institucional

    Es el payload que consume el frontend /analysis/:symbol y el bot
    /analisis para mostrar veredicto maestro al usuario.
    """
    from app.horizon_analyzer import (
        analyze_horizon,
        combine_horizons,
    )
    from app.macro_filter import check_macro_conditions
    from app.playbook import (
        build_narrative,
        compute_divergences,
        compute_drivers,
        compute_playbook_daily,
        compute_playbook_intraday,
        compute_price_range,
    )

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

    # F1: playbook computation
    h1_dict = scores.get("H1")
    h4_dict = scores.get("H4")
    h1_candles = [
        {"open": c.open, "high": c.high, "low": c.low, "close": c.close}
        for c in orchestrator._candle_buffer.get(symbol_up, [])
    ]

    # Compute ATR-14 from H1 candles (simple)
    atr_h1 = 0.0
    if len(h1_candles) >= 15:
        try:
            from app.risk_manager import OHLC, RiskManager
            rm = RiskManager()
            atr_h1 = rm.calculate_atr([OHLC(open=c["open"], high=c["high"],
                                            low=c["low"], close=c["close"])
                                       for c in h1_candles])
        except Exception:
            pass

    current_price = float(h1_candles[-1]["close"]) if h1_candles else 0.0

    drivers = compute_drivers(sb.master_bias, {tf: h.to_dict() for tf, h in scores.items()})
    price_range = compute_price_range(h1_candles, current_price)
    playbook_daily = compute_playbook_daily(sb.master_bias, sb.master_score, h1_candles, atr_h1)
    playbook_intraday = compute_playbook_intraday(sb.master_bias, sb.master_score, h1_candles, atr_h1)
    divergences = compute_divergences({tf: h.to_dict() for tf, h in scores.items()})
    narrative = build_narrative(sb.master_bias, sb.master_score, symbol_up, drivers, price_range)

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
        "drivers": drivers,
        "price_range": price_range,
        "playbook_daily": playbook_daily,
        "playbook_intraday": playbook_intraday,
        "divergences": divergences,
        "narrative": narrative,
        "ts": _time.time(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, log_level="info")