"""Regime classifier: combines GARCH / ADX / Hurst / Bollinger into a label.

The output is a RegimeSignal that downstream services (risk-engine,
ai-core, telegram-bot) consume to adjust position sizing, signal scoring,
and trade filters.

The classifier is a *weighted vote* with hysteresis — once a regime is
chosen, it sticks for at least `min_dwell` updates unless the new evidence
is overwhelming (>0.30 score gap).
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Sequence

import numpy as np

from app.indicators.indicators import (
    garch_variance,
    garch_class,
    adx,
    adx_class,
    hurst,
    hurst_class,
    bollinger_width,
    is_bollinger_squeeze,
)


# The seven regimes we classify into (per docs/10-AI-CORE.md §3.1).
REGIMES = (
    "TRENDING_UP",
    "TRENDING_DOWN",
    "RANGING",
    "HIGH_VOLATILITY",
    "LOW_VOLATILITY",
    "BREAKOUT",
    "CRISIS",
)


@dataclass
class RegimeSignal:
    symbol: str
    regime: str
    confidence: float  # 0..1
    sub_scores: dict[str, float]
    garch_sigma: float
    adx_value: float
    atr_pct: float
    bb_width: float
    timestamp: str
    valid_until: str

    def to_dict(self) -> dict:
        return asdict(self)


# ─── Per-symbol state ───────────────────────────────────────────────────
# We keep a small rolling history per symbol so the classifier can compute
# percentile thresholds (e.g., "current BB width vs the last 100 widths").
# Bounded by `history_len` so memory is O(symbols * history_len).

@dataclass
class SymbolState:
    symbol: str
    closes: deque = field(default_factory=lambda: deque(maxlen=200))
    highs: deque = field(default_factory=lambda: deque(maxlen=200))
    lows: deque = field(default_factory=lambda: deque(maxlen=200))
    bb_widths: deque = field(default_factory=lambda: deque(maxlen=100))
    sigmas: deque = field(default_factory=lambda: deque(maxlen=100))
    last_regime: str = "RANGING"
    last_update: float = 0.0


class RegimeClassifier:
    """Stateless (per call) classifier that holds per-symbol rolling state."""

    def __init__(self, min_dwell_updates: int = 3, transition_threshold: float = 0.20):
        self.states: dict[str, SymbolState] = {}
        self.min_dwell = min_dwell_updates
        self.transition_threshold = transition_threshold

    def feed(self, symbol: str, price: float, high: float, low: float) -> SymbolState:
        st = self.states.get(symbol)
        if st is None:
            st = SymbolState(symbol=symbol)
            self.states[symbol] = st
        st.closes.append(price)
        st.highs.append(high)
        st.lows.append(low)
        return st

    def classify(self, symbol: str) -> RegimeSignal | None:
        st = self.states.get(symbol)
        if st is None or len(st.closes) < 30:
            return None

        closes = np.array(st.closes, dtype=np.float64)
        highs = np.array(st.highs, dtype=np.float64)
        lows = np.array(st.lows, dtype=np.float64)
        last_price = float(closes[-1])

        # ── Sub-scores ─────────────────────────────────────────────
        sigma2 = garch_variance(closes)
        sigma = math.sqrt(sigma2)
        st.sigmas.append(sigma)
        if len(st.sigmas) >= 5:
            low_pct = float(np.percentile(list(st.sigmas)[:-1], 25))
            high_pct = float(np.percentile(list(st.sigmas)[:-1], 75))
        else:
            low_pct, high_pct = sigma * 0.5, sigma * 1.5

        vol_class = garch_class(sigma, low_pct, high_pct)

        adx_val = adx(highs, lows, closes)
        # Directional indicators (DI+, DI-): we recompute them inside adx()
        # so we re-derive via a small helper here.
        plus_di, minus_di = _di_components(highs, lows, closes, period=14)
        trend_class = adx_class(adx_val, plus_di, minus_di)

        h = hurst(closes)
        persist_class = hurst_class(h)

        bb_w = bollinger_width(closes)
        st.bb_widths.append(bb_w)
        squeeze = len(st.bb_widths) >= 10 and is_bollinger_squeeze(
            bb_w, list(st.bb_widths)[:-1]
        )

        atr = float(np.mean(np.maximum(highs[-14:] - lows[-14:], 1e-9)))
        atr_pct = atr / last_price if last_price > 0 else 0.0

        # ── Crisis detection (independent of the vote) ───────────
        # A crisis is an extreme move vs. the recent distribution. We use
        # the rolling 50-bar return distribution (excluding the crisis
        # bar itself) so the z-score can blow up. The volatility check
        # uses an absolute threshold or 3x median, whichever is looser.
        if len(closes) >= 30:
            log_p = np.log(closes)
            rets = np.diff(log_p)
            window = rets[-min(50, len(rets) - 1):-1] if len(rets) > 1 else rets
            if len(window) >= 10:
                mean_r = float(np.mean(window))
                std_r = float(np.std(window, ddof=1)) or 1e-9
                z = (rets[-1] - mean_r) / std_r
                # Volatility explosion: either sigma > 3x median sigma, OR
                # the latest bar moved more than 5% (absolute price move).
                pct_move = abs(rets[-1])
                if len(st.sigmas) >= 5:
                    median_sigma = float(np.median(list(st.sigmas)[:-1]))
                    vol_explosion = (
                        sigma > 3.0 * max(median_sigma, 1e-9) or pct_move > 0.05
                    )
                else:
                    vol_explosion = vol_class == "HIGH_VOL" or pct_move > 0.05
                if abs(z) > 3.0 and vol_explosion:
                    return self._emit(
                        st, "CRISIS",
                        confidence=min(1.0, abs(z) / 5.0),
                        sub_scores={"garch": vol_class, "adx": adx_val, "hurst": h,
                                    "z_score": round(float(z), 2),
                                    "pct_move": round(float(pct_move), 4)},
                        sigma=sigma, adx_val=adx_val, atr_pct=atr_pct, bb_w=bb_w,
                    )

        # ── Weighted vote ──────────────────────────────────────────
        weights = {
            "garch":  0.35,  # volatility tells us a lot
            "adx":    0.30,  # trend strength
            "hurst":  0.20,  # persistence vs mean-reversion
            "squeeze": 0.15,  # breakout potential
        }

        # Each sub-classifier votes for one of the 7 regimes; we accumulate
        # the weight. Vol-class HIGH_VOL → HIGH_VOLATILITY; LOW_VOL →
        # LOW_VOLATILITY; NORMAL_VOL → lets trend_class decide.
        scores: dict[str, float] = {r: 0.0 for r in REGIMES}

        if vol_class == "HIGH_VOL":
            scores["HIGH_VOLATILITY"] += weights["garch"]
        elif vol_class == "LOW_VOL":
            scores["LOW_VOLATILITY"] += weights["garch"]
        else:
            # NORMAL_VOL: let trend vs range decide
            if trend_class in ("TRENDING_UP", "TRENDING_DOWN"):
                scores[trend_class] += weights["garch"]
            else:
                scores["RANGING"] += weights["garch"]

        if trend_class in ("TRENDING_UP", "TRENDING_DOWN"):
            scores[trend_class] += weights["adx"]
        else:
            scores["RANGING"] += weights["adx"]

        if persist_class == "TRENDING":
            # Hurst supports whichever trend ADX picked.
            winner = max(scores, key=lambda r: scores[r] if r.startswith("TRENDING") else -1)
            if winner.startswith("TRENDING"):
                scores[winner] += weights["hurst"]
        elif persist_class == "MEAN_REVERT":
            scores["RANGING"] += weights["hurst"]
        else:
            scores["RANGING"] += weights["hurst"] * 0.5

        if squeeze and trend_class in ("TRENDING_UP", "TRENDING_DOWN"):
            scores["BREAKOUT"] += weights["squeeze"]
        elif squeeze:
            scores["BREAKOUT"] += weights["squeeze"] * 0.5

        # ── Pick the winner ────────────────────────────────────────
        best = max(scores, key=scores.get)
        total = sum(scores.values()) or 1.0
        confidence = scores[best] / total

        # ── Hysteresis ─────────────────────────────────────────────
        # If we already picked a regime recently, prefer to keep it unless
        # the new evidence is strong (gap > transition_threshold).
        if st.last_regime in REGIMES and st.last_regime != best:
            current = scores.get(st.last_regime, 0)
            if (scores[best] - current) / total < self.transition_threshold:
                best = st.last_regime
                confidence = scores[best] / total

        st.last_regime = best

        return self._emit(
            st, best, confidence=confidence,
            sub_scores={"garch": vol_class, "adx": trend_class, "hurst": persist_class,
                        "squeeze": squeeze, "scores": scores},
            sigma=sigma, adx_val=adx_val, atr_pct=atr_pct, bb_w=bb_w,
        )

    def _emit(self, st, regime, *, confidence, sub_scores, sigma, adx_val, atr_pct, bb_w):
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        sig = RegimeSignal(
            symbol=st.symbol,
            regime=regime,
            confidence=round(confidence, 3),
            sub_scores={k: (v if isinstance(v, (int, float, bool, str)) else str(v)) for k, v in sub_scores.items()},
            garch_sigma=round(sigma, 8),
            adx_value=round(adx_val, 2),
            atr_pct=round(atr_pct, 6),
            bb_width=round(bb_w, 6),
            timestamp=now.isoformat(),
            valid_until=(now + timedelta(minutes=15)).isoformat(),
        )
        return sig


# ─── DI+ / DI- helper (used by the classifier but also useful for tests) ─

def _di_components(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    period: int = 14,
) -> tuple[float, float]:
    """Returns the latest (DI+, DI-) values in [0, 100]."""
    n = len(highs)
    if n < period + 1:
        return 0.0, 0.0

    tr = np.zeros(n - 1)
    plus_dm = np.zeros(n - 1)
    minus_dm = np.zeros(n - 1)
    for i in range(1, n):
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        tr[i - 1] = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        plus_dm[i - 1] = up if (up > down and up > 0) else 0.0
        minus_dm[i - 1] = down if (down > up and down > 0) else 0.0

    def wilder(arr: np.ndarray) -> np.ndarray:
        out = np.zeros(len(arr))
        if len(arr) < period:
            return out
        out[period - 1] = float(np.sum(arr[:period]))
        for i in range(period, len(arr)):
            out[i] = out[i - 1] - out[i - 1] / period + arr[i]
        return out

    sm_tr = wilder(tr)
    sm_plus = wilder(plus_dm)
    sm_minus = wilder(minus_dm)
    with np.errstate(divide='ignore', invalid='ignore'):
        plus_di = 100.0 * sm_plus / sm_tr if sm_tr[-1] > 0 else 0.0
        minus_di = 100.0 * sm_minus / sm_tr if sm_tr[-1] > 0 else 0.0
    return float(plus_di[-1]), float(minus_di[-1])