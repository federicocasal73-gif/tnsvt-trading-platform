"""
Macro Filter — Detects macro-level crises and RED_ALERT conditions.

If VIX > 35 or other crisis indicators are triggered,
all trading is halted regardless of AMB score.
"""
import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("Bot.AMB.MacroFilter")

_cache = {"vix": None, "last_check": None, "red_alert": False}
_CACHE_TTL = timedelta(minutes=5)


async def check_macro_alert() -> dict:
    now = datetime.now()
    if _cache["last_check"] and (now - _cache["last_check"]) < _CACHE_TTL:
        return {"red_alert": _cache["red_alert"], "vix": _cache["vix"]}

    try:
        vix = await _fetch_vix()
        _cache["vix"] = vix
        _cache["red_alert"] = vix is not None and vix > 35
        _cache["last_check"] = now
    except Exception as e:
        logger.warning(f"Error fetching VIX: {e}")
        if _cache["vix"] is None:
            _cache["red_alert"] = False

    return {"red_alert": _cache["red_alert"], "vix": _cache["vix"]}


async def _fetch_vix() -> float | None:
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://www.alphavantage.co/query",
                params={
                    "function": "GLOBAL_QUOTE",
                    "symbol": "VIX",
                    "apikey": "demo",
                },
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    quote = data.get("Global Quote", {})
                    price_str = quote.get("05. price", "")
                    if price_str:
                        return float(price_str)
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"_fetch_vix error: {e}")

    try:
        import requests
        resp = requests.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "GLOBAL_QUOTE",
                "symbol": "VIX",
                "apikey": "demo",
            },
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            quote = data.get("Global Quote", {})
            price_str = quote.get("05. price", "")
            if price_str:
                return float(price_str)
    except Exception as e:
        logger.debug(f"_fetch_vix requests fallback error: {e}")

    return None


def reset_cache():
    _cache["vix"] = None
    _cache["last_check"] = None
    _cache["red_alert"] = False
