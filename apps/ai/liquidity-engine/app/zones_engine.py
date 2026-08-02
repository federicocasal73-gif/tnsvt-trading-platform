"""
Zone-based signal generator (matriz de reglas).

Lee las zonas de liquidez ingeridas por el EA MQL5 (`_zones_store`)
y las combina con el precio actual + microestructura LST para producir
`LSTSignal` con la dirección y confianza finales.

Reglas (decisión del usuario: zonas dan sesgo/dirección, LST valida):
  - bos_bull no-swept + precio cerca/rompiendo  -> liquidity_buy (conf base 0.55)
  - bos_bear no-swept                           -> liquidity_sell
  - equal_high no-swept + precio desde abajo    -> liquidity_sell (liquidez arriba)
  - equal_low no-swept  + precio desde arriba   -> liquidity_buy
  - fvg_bull activa + precio retrocede a mid    -> liquidity_buy
  - fvg_bear activa + precio retrocede a mid    -> liquidity_sell
  - swing_high/low: solo contexto (no dispara señal directa)

Confianza final:
  base * (0.5 + 0.5 * lst_score)  con lst_score entre 0 y 1
  Si la microestructura contradice la zona, la confianza baja al 40% del base.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from app.lst_engine import LSTEngine
from app.models import LSTMetrics, LSTSignal, RateOHLCV

logger = logging.getLogger(__name__)


class ZonesEngine:
    """Genera señales a partir de zonas + LSTEngine."""

    NEAR_PCT = 0.0025

    def __init__(self, lst_engine: LSTEngine):
        self._lst = lst_engine

    def evaluate(
        self,
        symbol: str,
        timeframe: str,
        price: float,
        zones: list[dict],
        rate: Optional[RateOHLCV] = None,
    ) -> Optional[LSTSignal]:
        """Devuelve una LSTSignal si la matriz detecta una oportunidad."""
        if not zones or price <= 0:
            return None

        bias = self._zone_bias(price, zones)
        if bias == "neutral":
            return None

        base_conf = self._base_confidence(bias, zones, price)
        if base_conf <= 0:
            return None

        lst_score = self._lst_alignment(bias, rate)

        if lst_score < 0:
            contradiction = True
            final_conf = round(base_conf * 0.4, 4)
            lst_score_abs = abs(lst_score)
        elif lst_score > 0:
            contradiction = False
            final_conf = round(base_conf * (0.5 + 0.5 * lst_score), 4)
            lst_score_abs = lst_score
        else:
            contradiction = False
            final_conf = round(base_conf * 0.5, 4)
            lst_score_abs = 0.0

        final_conf = max(0.05, min(0.99, final_conf))
        if final_conf < 0.3:
            return None

        signal_type = "liquidity_buy" if bias == "buy" else "liquidity_sell"

        metrics = self._build_metrics(price, rate, lst_score_abs, contradiction)

        return LSTSignal(
            symbol=symbol,
            timestamp=datetime.now(timezone.utc),
            timeframe=timeframe,
            signal_type=signal_type,
            confidence=final_conf,
            metrics=metrics,
        )

    def _zone_bias(self, price: float, zones: list[dict]) -> str:
        for z in zones:
            if z.get("swept"):
                continue
            zt = z.get("type")
            mid = float(z.get("midpoint") or 0)
            high = float(z.get("price_high") or 0)
            low = float(z.get("price_low") or 0)
            near_pct = self.NEAR_PCT * price

            if zt == "bos_bull" and price >= low - near_pct:
                return "buy"
            if zt == "bos_bear" and price <= high + near_pct:
                return "sell"

            if zt == "equal_high" and mid > 0 and price <= mid + near_pct and price >= mid - 2 * near_pct:
                return "sell"

            if zt == "equal_low" and mid > 0 and price >= mid - near_pct and price <= mid + 2 * near_pct:
                return "buy"

            if zt == "fvg_bull" and mid > 0 and abs(price - mid) <= near_pct and price <= mid:
                return "buy"
            if zt == "fvg_bear" and mid > 0 and abs(price - mid) <= near_pct and price >= mid:
                return "sell"

        return "neutral"

    def _base_confidence(self, bias: str, zones: list[dict], price: float) -> float:
        best = 0.0
        for z in zones:
            if z.get("swept"):
                continue
            zt = z.get("type")
            mid = float(z.get("midpoint") or 0)
            near_pct = self.NEAR_PCT * price
            strength = float(z.get("strength") or 1)
            proximity = 1.0
            if mid > 0:
                dist = abs(price - mid) / price
                proximity = max(0.0, 1.0 - dist / self.NEAR_PCT)

            base = 0.0
            if bias == "buy" and zt in ("bos_bull", "equal_low", "fvg_bull"):
                base = 0.55
            elif bias == "sell" and zt in ("bos_bear", "equal_high", "fvg_bear"):
                base = 0.55

            if base == 0:
                continue

            score = base * proximity * (0.85 + 0.05 * min(strength, 5))
            if score > best:
                best = score
        return min(best, 0.85)

    def _lst_alignment(self, bias: str, rate: Optional[RateOHLCV]) -> float:
        """Devuelve score -1..1; positivo = alineado, negativo = contradice."""
        if rate is None:
            return 0.0

        sig = self._lst.compute(rate)
        if sig is None:
            return 0.0

        micro_buy = sig.signal_type == "liquidity_buy"
        micro_sell = sig.signal_type == "liquidity_sell"

        if (bias == "buy" and micro_buy) or (bias == "sell" and micro_sell):
            return sig.confidence
        if (bias == "buy" and micro_sell) or (bias == "sell" and micro_buy):
            return -sig.confidence
        return 0.0

    def _build_metrics(
        self,
        price: float,
        rate: Optional[RateOHLCV],
        lst_score: float,
        contradiction: bool,
    ) -> LSTMetrics:
        rel_spread = 0.0
        volume_imbalance = 0.0
        order_flow_pressure = 0.0
        microstructure = max(0.0, min(1.0, lst_score))
        liquidity = max(0.0, min(1.0, lst_score))

        if rate is not None:
            mid = (rate.high + rate.low) / 2
            rel_spread = (rate.spread / mid * 10000) if mid > 0 else 0.0
            pr = rate.high - rate.low
            if pr > 0:
                cp = (rate.close - rate.low) / pr
                order_flow_pressure = round(2 * (cp - 0.5), 4)
                buy_ratio = max(0.1, min(0.9, 0.5 + (cp - 0.5) * 0.8))
                if rate.tick_volume > 0:
                    volume_imbalance = round(
                        (rate.tick_volume * buy_ratio - rate.tick_volume * (1 - buy_ratio))
                        / rate.tick_volume,
                        4,
                    )

        return LSTMetrics(
            relative_spread=round(rel_spread, 2),
            volume_imbalance=volume_imbalance,
            order_flow_pressure=order_flow_pressure,
            microstructure_score=round(microstructure, 4),
            liquidity_score=round(liquidity, 4),
        )
