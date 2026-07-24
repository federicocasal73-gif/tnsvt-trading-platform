"""
MT5 Price Provider — direct OHLCV, ticks, and indicators
from MetaTrader 5. Replaces the dead legacy API on port 5001.
"""
import asyncio
import logging
import time
from typing import Optional

import MetaTrader5 as mt5

logger = logging.getLogger("Bot.MT5Provider")

TF_MAP = {
    "MACRO": mt5.TIMEFRAME_MN1,
    "WEEKLY": mt5.TIMEFRAME_W1,
    "DAILY": mt5.TIMEFRAME_D1,
    "H4": mt5.TIMEFRAME_H4,
    "H1": mt5.TIMEFRAME_H1,
    "M15": mt5.TIMEFRAME_M15,
    "M5": mt5.TIMEFRAME_M5,
    "M1": mt5.TIMEFRAME_M1,
}


class MT5Provider:
    def __init__(self):
        self._connected = False
        self._lock = asyncio.Lock()
        self._cache = {}
        self._cache_ttl = 10

    def _connect_sync(self) -> bool:
        if not mt5.initialize():
            logger.error("MT5 initialize failed")
            return False
        info = mt5.account_info()
        if info:
            logger.info(f"MT5 connected: {info.server} | balance=${info.balance:.2f}")
            self._connected = True
            return True
        logger.error("MT5 account_info() returned None")
        return False

    async def connect(self) -> bool:
        async with self._lock:
            if self._connected:
                return True
            return await asyncio.get_event_loop().run_in_executor(None, self._connect_sync)

    def _ensure_connected_sync(self) -> bool:
        if self._connected:
            info = mt5.account_info()
            if info:
                return True
            logger.warning("MT5 connection lost, reconnecting...")
        return self._connect_sync()

    async def ensure_connected(self) -> bool:
        async with self._lock:
            return await asyncio.get_event_loop().run_in_executor(None, self._ensure_connected_sync)

    async def get_candles(self, symbol: str, tf: str, bars: int = 100) -> Optional[list[dict]]:
        mtf = TF_MAP.get(tf)
        if mtf is None:
            logger.warning(f"Unknown timeframe: {tf}")
            return None

        cache_key = f"{symbol}:{tf}:{bars}"
        now = time.time()
        cached = self._cache.get(cache_key)
        if cached and (now - cached["ts"]) < self._cache_ttl:
            return cached["data"]

        if not await self.ensure_connected():
            return None

        try:
            rates = await asyncio.get_event_loop().run_in_executor(
                None, lambda: mt5.copy_rates_from_pos(symbol, mtf, 0, bars)
            )
            if rates is None or len(rates) == 0:
                logger.warning(f"No rates for {symbol} {tf}")
                return None

            result = []
            for r in rates:
                result.append({
                    "time": r[0],
                    "open": float(r[1]),
                    "high": float(r[2]),
                    "low": float(r[3]),
                    "close": float(r[4]),
                    "volume": int(r[5]),
                    "spread": int(r[6]),
                    "real_volume": int(r[7]),
                })

            self._cache[cache_key] = {"data": result, "ts": now}
            return result

        except Exception as e:
            logger.error(f"get_candles error {symbol} {tf}: {e}")
            return None

    async def get_tick(self, symbol: str) -> Optional[dict]:
        if not await self.ensure_connected():
            return None

        try:
            tick = await asyncio.get_event_loop().run_in_executor(
                None, lambda: mt5.symbol_info_tick(symbol)
            )
            if tick is None:
                return None

            spread = (tick.ask - tick.bid) * 10000 if "JPY" not in symbol else (tick.ask - tick.bid) * 100
            return {
                "bid": tick.bid,
                "ask": tick.ask,
                "spread": round(spread, 1),
                "time": tick.time,
                "last": tick.last,
                "volume": tick.volume,
            }
        except Exception as e:
            logger.error(f"get_tick error {symbol}: {e}")
            return None

    async def get_ticks(self, symbol: str, count: int = 100) -> Optional[list[dict]]:
        if not await self.ensure_connected():
            return None

        try:
            ticks = await asyncio.get_event_loop().run_in_executor(
                None, lambda: mt5.copy_ticks_from(symbol, mt5.TickInfo(time=0), count)
            )
            if ticks is None or len(ticks) == 0:
                return None

            result = []
            for t in ticks:
                result.append({
                    "time": t[0],
                    "bid": t[1],
                    "ask": t[2],
                    "last": t[3],
                    "volume": int(t[4]),
                    "flags": t[5],
                })
            return result
        except Exception as e:
            logger.error(f"get_ticks error {symbol}: {e}")
            return None

    def clear_cache(self):
        self._cache.clear()

    async def disconnect(self):
        async with self._lock:
            if self._connected:
                await asyncio.get_event_loop().run_in_executor(None, mt5.shutdown)
                self._connected = False
                logger.info("MT5 disconnected")


_mt5_provider = None


def get_provider() -> MT5Provider:
    global _mt5_provider
    if _mt5_provider is None:
        _mt5_provider = MT5Provider()
    return _mt5_provider
