"""
Risk Manager — calcula SL/TP dinámicos basados en ATR.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class OHLC:
    open: float
    high: float
    low: float
    close: float


@dataclass
class SLTPResult:
    sl: float
    tp: float
    rr_ratio: float
    atr: float


class RiskManager:
    def __init__(self, atr_period: int = 14, sl_atr_multiplier: float = 1.5, tp_atr_multiplier: float = 2.5) -> None:
        self.atr_period = atr_period
        self.sl_atr_multiplier = sl_atr_multiplier
        self.tp_atr_multiplier = tp_atr_multiplier

    def calculate_atr(self, candles: List[OHLC]) -> float:
        if len(candles) < self.atr_period + 1:
            return 0.0

        true_ranges: List[float] = []
        for i in range(1, len(candles)):
            prev_close = candles[i - 1].close
            high = candles[i].high
            low = candles[i].low
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(tr)

        if len(true_ranges) < self.atr_period:
            return sum(true_ranges) / len(true_ranges) if true_ranges else 0.0

        atr = sum(true_ranges[: self.atr_period]) / self.atr_period
        for tr in true_ranges[self.atr_period:]:
            atr = (atr * (self.atr_period - 1) + tr) / self.atr_period
        return atr

    def calculate_sl_tp(
        self,
        candles: List[OHLC],
        action: str,
        entry_price: Optional[float] = None,
    ) -> SLTPResult:
        atr = self.calculate_atr(candles)
        if atr <= 0:
            last = candles[-1]
            atr = (last.high - last.low) * 0.01 if last.high > last.low else 0.0001

        if entry_price is None:
            entry_price = candles[-1].close

        sl_distance = atr * self.sl_atr_multiplier
        tp_distance = atr * self.tp_atr_multiplier

        if action.upper() == "BUY":
            sl = entry_price - sl_distance
            tp = entry_price + tp_distance
        elif action.upper() == "SELL":
            sl = entry_price + sl_distance
            tp = entry_price - tp_distance
        else:
            raise ValueError(f"action must be BUY or SELL, got {action}")

        rr = tp_distance / sl_distance if sl_distance > 0 else 0.0
        return SLTPResult(sl=sl, tp=tp, rr_ratio=rr, atr=atr)

    def calculate_trailing_sl(
        self,
        current_sl: float,
        current_price: float,
        atr: float,
        side: str,
    ) -> float:
        if atr <= 0:
            return current_sl

        new_sl_distance = atr * self.sl_atr_multiplier
        if side.upper() == "BUY":
            proposed = current_price - new_sl_distance
            return max(current_sl, proposed)
        proposed = current_price + new_sl_distance
        return min(current_sl, proposed)