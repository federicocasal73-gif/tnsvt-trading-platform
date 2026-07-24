"""
Indicator Wrappers — Secondary confirmation for AMB engine.

Wraps traditional technical indicators (RSI, MACD, EMA, ATR)
and structure analysis (market structure, HH/HL, LH/LL) as scoring
functions that return 0-100 for a given symbol + timeframe.

All calculations are local via pandas/numpy using MT5 real data.
"""
import asyncio
import logging
from typing import Optional

import numpy as np
import pandas as pd

from bot.services.mt5_provider import get_provider

logger = logging.getLogger("Bot.AMB.Indicators")

_CACHE_TTL = 20
_cache = {}


def _rma(series: pd.Series, period: int) -> pd.Series:
    """Wilder's smoothed moving average (RMA)."""
    alpha = 1.0 / period
    return series.ewm(alpha=alpha, adjust=False).mean()


async def _get_ohlc(symbol: str, tf: str, bars: int = 200) -> Optional[pd.DataFrame]:
    cache_key = f"ohlc:{symbol}:{tf}:{bars}"
    import time
    now = time.time()
    cached = _cache.get(cache_key)
    if cached and (now - cached["ts"]) < _CACHE_TTL:
        return cached["data"]

    provider = get_provider()
    rates = await provider.get_candles(symbol, tf, bars)
    if not rates:
        return None

    df = pd.DataFrame(rates)
    _cache[cache_key] = {"data": df, "ts": now}
    return df


async def score_indicators(symbol: str, tf: str) -> float:
    score = 50.0
    rsi_val = await _rsi(symbol, tf)
    macd_val = await _macd(symbol, tf)
    ema_val = await _ema_alignment(symbol, tf)

    if rsi_val is not None:
        if 30 <= rsi_val <= 40:
            score += 15
        elif 60 <= rsi_val <= 70:
            score += 10
        elif 40 < rsi_val < 60:
            score += 5

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
    df = await _get_ohlc(symbol, tf)
    if df is None or len(df) < period + 1:
        return None

    closes = df["close"].astype(float)
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    avg_gain = _rma(gain, period)
    avg_loss = _rma(loss, period)

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None


async def _macd(symbol: str, tf: str) -> Optional[float]:
    df = await _get_ohlc(symbol, tf)
    if df is None or len(df) < 35:
        return None

    closes = df["close"].astype(float)
    ema12 = closes.ewm(span=12, adjust=False).mean()
    ema26 = closes.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26

    return float(macd_line.iloc[-1])


async def _ema_alignment(symbol: str, tf: str) -> Optional[float]:
    df = await _get_ohlc(symbol, tf)
    if df is None or len(df) < 200:
        return None

    closes = df["close"].astype(float)
    ema50 = closes.ewm(span=50, adjust=False).mean()
    ema200 = closes.ewm(span=200, adjust=False).mean()

    return float(ema50.iloc[-1] - ema200.iloc[-1])


async def score_structure(symbol: str, tf: str) -> float:
    score = 50.0
    df = await _get_ohlc(symbol, tf)
    if df is None or len(df) < 20:
        return score

    closes = df["close"].astype(float).values
    if len(closes) < 10:
        return score

    recent = closes[-10:]
    segments = len(recent) // 3
    highs = [float(max(recent[i*3:(i+1)*3])) for i in range(segments) if i*3+3 <= len(recent)]
    lows = [float(min(recent[i*3:(i+1)*3])) for i in range(segments) if i*3+3 <= len(recent)]

    if len(highs) >= 2 and len(lows) >= 2:
        higher_highs = highs[-1] > highs[-2]
        higher_lows = lows[-1] > lows[-2]
        lower_highs = highs[-1] < highs[-2]
        lower_lows = lows[-1] < lows[-2]

        if higher_highs and higher_lows:
            score = 80
        elif lower_highs and lower_lows:
            score = 20
        elif higher_highs:
            score = 65
        elif lower_lows:
            score = 35
        else:
            score = 50

    return max(0.0, min(100.0, score))


def clear_cache():
    _cache.clear()
