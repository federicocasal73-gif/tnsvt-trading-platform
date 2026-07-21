"""
SMC Pattern Detection — Smart Money Concepts for AMB engine.

Detects FVG (Fair Value Gap), Order Blocks, Liquidity Sweeps,
and CISD (Change in State of Delivery) as primary SMC inputs.
"""
import asyncio
import logging
from typing import Optional

import aiohttp

logger = logging.getLogger("Bot.AMB.SMC")

BRIDGE_URL = "http://localhost:5001"


async def evaluate_smc(symbol: str, tf: str) -> float:
    score = 50.0
    fvg = await _detect_fvg(symbol, tf)
    ob = await _detect_order_blocks(symbol, tf)
    sweep = await _detect_liquidity_sweep(symbol, tf)
    cisd = await _detect_cisd(symbol, tf)

    if fvg.get("bullish"):
        score += 15.0
    elif fvg.get("bearish"):
        score -= 12.0

    if ob.get("bullish"):
        score += 10.0
    elif ob.get("bearish"):
        score -= 8.0

    if sweep.get("bullish"):
        score += 8.0
    elif sweep.get("bearish"):
        score -= 6.0

    if cisd.get("detected"):
        score += 12.0 if cisd.get("bullish") else -10.0

    return max(0.0, min(100.0, score))


async def _fetch_ohlc(symbol: str, tf: str, bars: int = 50) -> Optional[list]:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{BRIDGE_URL}/api/v1/rates",
                params={"symbol": symbol, "timeframe": tf, "bars": bars},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        logger.debug(f"_fetch_ohlc error {symbol} {tf}: {e}")
    return None


async def _detect_fvg(symbol: str, tf: str) -> dict:
    ohlc = await _fetch_ohlc(symbol, tf)
    if not ohlc or not isinstance(ohlc, list) or len(ohlc) < 3:
        return {"bullish": False, "bearish": False, "count": 0}

    bullish_fvg = 0
    bearish_fvg = 0

    for i in range(len(ohlc) - 2):
        c1, c2, c3 = ohlc[i], ohlc[i+1], ohlc[i+2]
        try:
            h1 = float(c1.get("high", 0))
            l1 = float(c1.get("low", 0))
            h2 = float(c2.get("high", 0))
            l2 = float(c2.get("low", 0))
            h3 = float(c3.get("high", 0))
            l3 = float(c3.get("low", 0))
        except (TypeError, ValueError):
            continue

        # Bullish FVG: gap up (c1 low > c3 high)
        if l1 > h3:
            bullish_fvg += 1

        # Bearish FVG: gap down (c3 low > c1 high)
        if l3 > h1:
            bearish_fvg += 1

    return {
        "bullish": bullish_fvg > 0,
        "bearish": bearish_fvg > 0,
        "count": bullish_fvg + bearish_fvg,
    }


async def _detect_order_blocks(symbol: str, tf: str) -> dict:
    ohlc = await _fetch_ohlc(symbol, tf)
    if not ohlc or not isinstance(ohlc, list) or len(ohlc) < 5:
        return {"bullish": False, "bearish": False}

    bullish_ob = 0
    bearish_ob = 0

    for i in range(len(ohlc) - 2):
        c = ohlc[i]
        n1 = ohlc[i+1]
        try:
            high = float(c.get("high", 0))
            low = float(c.get("low", 0))
            close = float(c.get("close", 0))
            next_close = float(n1.get("close", 0))
        except (TypeError, ValueError):
            continue

        body = abs(float(c.get("close", 0)) - float(c.get("open", 0)))
        total_range = high - low
        if total_range == 0:
            continue

        # Bullish OB: bearish candle with large body followed by strong rally
        if close < float(c.get("open", 0)) and body > total_range * 0.6:
            if next_close > high:
                bullish_ob += 1

        # Bearish OB: bullish candle with large body followed by strong selloff
        if close > float(c.get("open", 0)) and body > total_range * 0.6:
            if next_close < low:
                bearish_ob += 1

    return {
        "bullish": bullish_ob > 0,
        "bearish": bearish_ob > 0,
        "bullish_count": bullish_ob,
        "bearish_count": bearish_ob,
    }


async def _detect_liquidity_sweep(symbol: str, tf: str) -> dict:
    ohlc = await _fetch_ohlc(symbol, tf)
    if not ohlc or not isinstance(ohlc, list) or len(ohlc) < 10:
        return {"bullish": False, "bearish": False}

    recent = ohlc[-10:]
    if len(recent) < 5:
        return {"bullish": False, "bearish": False}

    highs = []
    lows = []
    for c in recent:
        try:
            highs.append(float(c.get("high", 0)))
            lows.append(float(c.get("low", 0)))
        except (TypeError, ValueError):
            continue

    if len(highs) < 5:
        return {"bullish": False, "bearish": False}

    prev_high = max(highs[:-1])
    prev_low = min(lows[:-1])
    last_high = highs[-1]
    last_low = lows[-1]
    last_close = float(recent[-1].get("close", 0))

    bullish_sweep = last_low < prev_low and last_close > prev_low
    bearish_sweep = last_high > prev_high and last_close < prev_high

    return {
        "bullish": bullish_sweep,
        "bearish": bearish_sweep,
    }


async def _detect_cisd(symbol: str, tf: str) -> dict:
    ohlc = await _fetch_ohlc(symbol, tf)
    if not ohlc or not isinstance(ohlc, list) or len(ohlc) < 15:
        return {"detected": False, "bullish": False}

    closes = []
    for c in ohlc[-15:]:
        try:
            closes.append(float(c.get("close", 0)))
        except (TypeError, ValueError):
            continue

    if len(closes) < 10:
        return {"detected": False, "bullish": False}

    mid = len(closes) // 2
    first_half = closes[:mid]
    second_half = closes[mid:]

    first_uptrend = first_half[-1] > first_half[0]
    second_uptrend = second_half[-1] > second_half[0]

    # CISD = change in structure: from uptrend to downtrend or vice versa
    if first_uptrend and not second_uptrend:
        return {"detected": True, "bullish": False}
    elif not first_uptrend and second_uptrend:
        return {"detected": True, "bullish": True}

    return {"detected": False, "bullish": False}
