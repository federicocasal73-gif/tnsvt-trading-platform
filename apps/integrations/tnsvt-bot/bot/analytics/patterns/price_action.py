"""
Price Action Pattern Detection — S/R, trendlines, candlestick patterns.

Serves as primary input (30% weight) to AMB scoring per timeframe.
Returns a 0-100 score based on detected price action patterns.

All data sourced from MT5 directly via mt5_provider.
"""
import logging
from typing import Optional

from bot.services.mt5_provider import get_provider

logger = logging.getLogger("Bot.AMB.PriceAction")

_CACHE_TTL = 20
_cache = {}


async def _get_ohlc(symbol: str, tf: str, bars: int = 100) -> Optional[list]:
    import time
    cache_key = f"pa_ohlc:{symbol}:{tf}:{bars}"
    now = time.time()
    cached = _cache.get(cache_key)
    if cached and (now - cached["ts"]) < _CACHE_TTL:
        return cached["data"]

    provider = get_provider()
    rates = await provider.get_candles(symbol, tf, bars)
    if rates:
        _cache[cache_key] = {"data": rates, "ts": now}
    return rates


async def evaluate_price_action(symbol: str, tf: str) -> float:
    ohlc = await _get_ohlc(symbol, tf)
    if not ohlc or not isinstance(ohlc, list) or len(ohlc) < 10:
        return 50.0

    score = 50.0
    score += _score_trend_structure(ohlc)
    score += _score_candlestick_patterns(ohlc)
    score += _score_support_resistance(ohlc)

    return max(0.0, min(100.0, score))


def _score_trend_structure(ohlc: list) -> float:
    if len(ohlc) < 10:
        return 0.0

    highs = [float(c.get("high", 0)) for c in ohlc[-20:]]
    lows = [float(c.get("low", 0)) for c in ohlc[-20:]]

    if len(highs) < 5:
        return 0.0

    recent_highs = highs[-5:]
    recent_lows = lows[-5:]

    hh = all(recent_highs[i] <= recent_highs[i+1] for i in range(len(recent_highs)-1))
    hl = all(recent_lows[i] <= recent_lows[i+1] for i in range(len(recent_lows)-1))
    lh = all(recent_highs[i] >= recent_highs[i+1] for i in range(len(recent_highs)-1))
    ll = all(recent_lows[i] >= recent_lows[i+1] for i in range(len(recent_lows)-1))

    if hh and hl:
        return 20.0
    elif lh and ll:
        return -15.0
    elif hh:
        return 10.0
    elif ll:
        return -10.0
    return 0.0


def _score_candlestick_patterns(ohlc: list) -> float:
    if len(ohlc) < 3:
        return 0.0

    score = 0.0
    last = ohlc[-1]
    prev = ohlc[-2]

    def _is_bullish(c):
        return float(c.get("close", 0)) > float(c.get("open", 0))

    def _is_bearish(c):
        return float(c.get("close", 0)) < float(c.get("open", 0))

    body = abs(float(last.get("close", 0)) - float(last.get("open", 0)))
    upper = float(last.get("high", 0)) - max(float(last.get("close", 0)), float(last.get("open", 0)))
    lower = min(float(last.get("close", 0)), float(last.get("open", 0))) - float(last.get("low", 0))
    total_range = float(last.get("high", 0)) - float(last.get("low", 0))

    if total_range == 0:
        return 0.0

    if _is_bearish(prev) and _is_bullish(last):
        prev_body = float(prev.get("close", 0)) - float(prev.get("open", 0))
        if abs(body) > abs(prev_body):
            score += 10.0

    if lower >= 2 * body and upper < body * 0.3 and total_range > 0:
        score += 8.0

    if body < total_range * 0.1:
        score += 3.0

    if upper >= 2 * body and lower < body * 0.3 and total_range > 0:
        score -= 8.0

    return max(-10.0, min(10.0, score))


def _score_support_resistance(ohlc: list) -> float:
    if len(ohlc) < 30:
        return 0.0

    highs = [float(c.get("high", 0)) for c in ohlc]
    lows = [float(c.get("low", 0)) for c in ohlc]
    closes = [float(c.get("close", 0)) for c in ohlc]

    if not highs or not closes:
        return 0.0

    current_price = closes[-1]
    resistance = max(highs[-20:])
    support = min(lows[-20:])

    if current_price <= support * 1.02:
        return 10.0
    elif current_price >= resistance * 0.98:
        return -8.0
    return 2.0


def clear_cache():
    _cache.clear()
