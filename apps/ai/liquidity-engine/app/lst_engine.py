import logging
from collections import deque
from datetime import datetime, timezone

from app.models import LSTSignal, LSTMetrics, RateOHLCV

logger = logging.getLogger(__name__)


class LSTEngine:
    def __init__(self, window_size: int = 20):
        self._spreads: deque[float] = deque(maxlen=window_size)
        self._volumes: deque[float] = deque(maxlen=window_size)
        self._tick_volumes: deque[float] = deque(maxlen=window_size)
        self._window_size = window_size

    def compute(self, rate: RateOHLCV) -> LSTSignal | None:
        mid = (rate.high + rate.low) / 2
        rel_spread = (rate.spread / mid * 10000) if mid > 0 else 0

        self._spreads.append(rel_spread)
        self._volumes.append(rate.volume)
        self._tick_volumes.append(rate.tick_volume)

        if len(self._spreads) < self._window_size:
            return None

        metrics = LSTMetrics(
            relative_spread=round(rel_spread, 2),
            volume_imbalance=round(self._volume_imbalance(rate), 4),
            order_flow_pressure=round(self._order_flow_pressure(rate), 4),
            microstructure_score=round(self._microstructure_score(rel_spread, rate), 4),
            liquidity_score=round(self._liquidity_score(rel_spread, rate), 4),
        )

        signal_type, confidence = self._classify(metrics, rate)

        return LSTSignal(
            symbol=rate.symbol,
            timestamp=datetime.now(timezone.utc),
            timeframe=rate.timeframe,
            signal_type=signal_type,
            confidence=round(confidence, 4),
            metrics=metrics,
        )

    def _volume_imbalance(self, rate: RateOHLCV) -> float:
        price_range = rate.high - rate.low
        if price_range == 0:
            return 0
        close_position = (rate.close - rate.low) / price_range
        buy_ratio = 0.5 + (close_position - 0.5) * 0.8
        buy_ratio = max(0.1, min(0.9, buy_ratio))
        avg_buy = rate.tick_volume * buy_ratio
        avg_sell = rate.tick_volume - avg_buy
        return (avg_buy - avg_sell) / rate.tick_volume if rate.tick_volume > 0 else 0

    def _order_flow_pressure(self, rate: RateOHLCV) -> float:
        price_range = rate.high - rate.low
        if price_range == 0:
            return 0
        close_position = (rate.close - rate.low) / price_range
        return 2 * (close_position - 0.5)

    def _microstructure_score(self, rel_spread: float, rate: RateOHLCV) -> float:
        avg_spread = sum(self._spreads) / len(self._spreads)
        spread_ratio = rel_spread / avg_spread if avg_spread > 0 else 1
        vol_ratio = rate.volume / (sum(self._volumes) / len(self._volumes)) if self._volumes else 1
        score = 1 - min(spread_ratio * 0.5, 0.5) + min(vol_ratio * 0.1, 0.2)
        return max(0, min(1, score))

    def _liquidity_score(self, rel_spread: float, rate: RateOHLCV) -> float:
        vol_consistency = 1 - min(len(self._volumes) and (abs(rate.volume - sum(self._volumes) / len(self._volumes)) / (sum(self._volumes) / len(self._volumes))), 1) if self._volumes else 0
        spread_quality = max(0, 1 - rel_spread / 100)
        depth = min(rate.volume / 1000, 1)
        return max(0, min(1, 0.4 * spread_quality + 0.3 * vol_consistency + 0.3 * depth))

    def _classify(self, metrics: LSTMetrics, rate: RateOHLCV) -> tuple[str, float]:
        if metrics.liquidity_score < 0.3:
            return "neutral", 0.0

        vi, ofp = metrics.volume_imbalance, metrics.order_flow_pressure
        aligned_buy = vi > 0 and ofp > 0
        aligned_sell = vi < 0 and ofp < 0
        pressure = abs(vi * ofp)

        if aligned_buy and pressure > 0.15 and metrics.liquidity_score > 0.5:
            conf = min(pressure * 2, 1.0) * metrics.liquidity_score
            return ("liquidity_buy", conf)

        if aligned_sell and pressure > 0.15 and metrics.liquidity_score > 0.5:
            conf = min(pressure * 2, 1.0) * metrics.liquidity_score
            return ("liquidity_sell", conf)

        return ("neutral", 0.0)

    def reset(self):
        self._spreads.clear()
        self._volumes.clear()
        self._tick_volumes.clear()
