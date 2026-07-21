"""
Indicator Wrappers — Secondary confirmation for AMB engine.

Wraps traditional technical indicators (RSI, MACD, EMA, ATR)
and structure analysis (market structure, HH/HL, LH/LL) as scoring
functions that return 0-100 for a given symbol + timeframe.
"""
import asyncio
import logging
from typing import Optional

import aiohttp

logger = logging.getLogger("Bot.AMB.Indicators")

BRIDGE_URL = "http://localhost:5001"

_cache = {}
_CACHE_TTL = 30


async def _fetch_rates(symbol: str) -> Optional[list]:
    cache_key = f"rates:{symbol}"
    import time
    now = time.time()
    cached = _cache.get(cache_key)
    if cached and (now - cached["ts"]) < _CACHE_TTL:
        return cached["data"]

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{BRIDGE_URL}/api/v1/rates",
                params={"symbol": symbol},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    _cache[cache_key] = {"data": data, "ts": now}
                    return data
    except Exception as e:
        logger.debug(f"_fetch_rates error for {symbol}: {e}")
    return None


async def score_indicators(symbol: str, tf: str) -> float:
    score = 50.0
    rsi_val = await _rsi(symbol, tf)
    macd_val = await _macd(symbol, tf)
    ema_val = await _ema_alignment(symbol, tf)

    if rsi_val is not None:
        if 30 <= rsi_val <= 40:
            score += 15  # oversold-bullish
        elif 60 <= rsi_val <= 70:
            score += 10  # overbought-bearish (less weight for bullish bias)
        elif 40 < rsi_val < 60:
            score += 5   # neutral

    if macd_val is not None:
        if macd_val > 0:
            score += 15
        elif macd_val < 0:
            score -= 10

    if ema_val is not None:
        if ema_val > 0:
            score += 10
        elif ema_val < 0:
            score -= 5

    return max(0.0, min(100.0, score))


async def _rsi(symbol: str, tf: str, period: int = 14) -> Optional[float]:
    try:
        from bot.services.trading_economics import get_rsi
        return await asyncio.get_event_loop().run_in_executor(None, get_rsi, symbol, tf, period)
    except (ImportError, AttributeError):
        pass

    try:
        import requests
        resp = requests.get(
            f"{BRIDGE_URL}/api/v1/rsi",
            params={"symbol": symbol, "timeframe": tf, "period": period},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            return float(data.get("rsi", 50))
    except Exception as e:
        logger.debug(f"_rsi error {symbol} {tf}: {e}")
    return None


async def _macd(symbol: str, tf: str) -> Optional[float]:
    try:
        import requests
        resp = requests.get(
            f"{BRIDGE_URL}/api/v1/macd",
            params={"symbol": symbol, "timeframe": tf},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            return float(data.get("macd_line", 0))
    except Exception as e:
        logger.debug(f"_macd error {symbol} {tf}: {e}")
    return None


async def _ema_alignment(symbol: str, tf: str) -> Optional[float]:
    try:
        import requests
        resp = requests.get(
            f"{BRIDGE_URL}/api/v1/ema",
            params={"symbol": symbol, "timeframe": tf, "fast": 50, "slow": 200},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            ema_fast = float(data.get("ema_fast", 0))
            ema_slow = float(data.get("ema_slow", 0))
            if ema_fast and ema_slow:
                return ema_fast - ema_slow
    except Exception as e:
        logger.debug(f"_ema_alignment error {symbol} {tf}: {e}")
    return None


async def score_structure(symbol: str, tf: str) -> float:
    score = 50.0
    rates = await _fetch_rates(symbol)
    if not rates or not isinstance(rates, list) or len(rates) < 20:
        return score

    prices = []
    for r in rates:
        close = r.get("close") or r.get("c") or r.get("price")
        if close:
            prices.append(float(close))

    if len(prices) < 10:
        return score

    recent = prices[-10:]
    highs = [max(prices[i:i+5]) for i in range(0, len(prices)-4, 3)][-3:]
    lows = [min(prices[i:i+5]) for i in range(0, len(prices)-4, 3)][-3:]

    if len(highs) >= 2 and len(lows) >= 2:
        higher_highs = highs[-1] > highs[-2]
        higher_lows = lows[-1] > lows[-2]
        lower_highs = highs[-1] < highs[-2]
        lower_lows = lows[-1] < lows[-2]

        if higher_highs and higher_lows:
            score = 80  # strong uptrend
        elif lower_highs and lower_lows:
            score = 20  # strong downtrend
        elif higher_highs:
            score = 65  # weak uptrend
        elif lower_lows:
            score = 35  # weak downtrend
        else:
            score = 50  # ranging

    return max(0.0, min(100.0, score))


def clear_cache():
    _cache.clear()
