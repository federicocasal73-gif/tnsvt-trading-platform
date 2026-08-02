"""
Correlation Engine para el Multi-Symbol Orchestrator.

Funcionalidades:
1. Correlación móvil entre pares de activos (Pearson)
2. Detección de cointegración (Engle-Granger)
3. Filtrado de señales conflictivas en activos correlacionados
4. Refuerzo de señales alineadas (boost de confianza + lot size)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np
from scipy.stats import pearsonr

logger = logging.getLogger(__name__)


@dataclass
class PairAnalysis:
    correlation: float
    rolling_correlation: List[float]
    is_cointegrated: bool
    coint_pvalue: float
    trend_a: int
    trend_b: int
    reinforcement: int
    strong_correlation: bool


@dataclass
class FilteredSignal:
    symbol: str
    action: str
    confidence: float
    adjusted_confidence: float
    lot_multiplier: float
    filtered_out: bool
    reasons: List[str] = field(default_factory=list)


class CorrelationEngine:
    """
    Motor de correlaciones y cointegración.

    Args:
        lookback: número de velas para correlación móvil.
        correlation_threshold: |corr| > threshold => correlación fuerte.
        coint_pvalue_threshold: p < threshold => cointegrados.
        coint_enabled: si False, salta el test de cointegración (acelera tests).
    """

    def __init__(
        self,
        lookback: int = 50,
        correlation_threshold: float = 0.7,
        coint_pvalue_threshold: float = 0.05,
        coint_enabled: bool = True,
    ) -> None:
        self.lookback = lookback
        self.correlation_threshold = correlation_threshold
        self.coint_pvalue_threshold = coint_pvalue_threshold
        self.coint_enabled = coint_enabled

    @staticmethod
    def _align(prices_a: List[float], prices_b: List[float]) -> Tuple[np.ndarray, np.ndarray]:
        n = min(len(prices_a), len(prices_b))
        if n == 0:
            return np.array([]), np.array([])
        return np.array(prices_a[-n:]), np.array(prices_b[-n:])

    def compute_correlation(self, prices_a: List[float], prices_b: List[float]) -> float:
        a, b = self._align(prices_a, prices_b)
        if len(a) < 5:
            return 0.0
        try:
            corr, _ = pearsonr(a, b)
            if not np.isfinite(corr):
                return 0.0
            return float(corr)
        except Exception as e:
            logger.debug("compute_correlation failed: %s", e)
            return 0.0

    def compute_rolling_correlation(
        self, prices_a: List[float], prices_b: List[float], window: int | None = None
    ) -> List[float]:
        if window is None:
            window = self.lookback
        a, b = self._align(prices_a, prices_b)
        if len(a) < window:
            return []
        out: List[float] = []
        for i in range(window, len(a) + 1):
            try:
                corr, _ = pearsonr(a[i - window:i], b[i - window:i])
                out.append(float(corr) if np.isfinite(corr) else 0.0)
            except Exception:
                out.append(0.0)
        return out

    def check_cointegration(
        self, prices_a: List[float], prices_b: List[float]
    ) -> Tuple[bool, float]:
        if not self.coint_enabled:
            return False, 1.0
        a, b = self._align(prices_a, prices_b)
        if len(a) < 20:
            return False, 1.0
        try:
            from statsmodels.tsa.stattools import coint

            score, pvalue, _ = coint(a, b)
            return bool(pvalue < self.coint_pvalue_threshold), float(pvalue)
        except Exception as e:
            logger.debug("check_cointegration failed: %s", e)
            return False, 1.0

    @staticmethod
    def _recent_trend(prices: List[float], window: int = 10) -> int:
        if len(prices) < window:
            return 0
        if prices[-1] > prices[-window]:
            return 1
        if prices[-1] < prices[-window]:
            return -1
        return 0

    def analyze_pair(
        self,
        symbol_a: str,
        symbol_b: str,
        prices_a: List[float],
        prices_b: List[float],
    ) -> PairAnalysis:
        corr = self.compute_correlation(prices_a, prices_b)
        is_coint, pval = self.check_cointegration(prices_a, prices_b)
        trend_a = self._recent_trend(prices_a)
        trend_b = self._recent_trend(prices_b)
        if trend_a == trend_b and trend_a != 0:
            reinforcement = 1
        elif trend_a != trend_b and trend_a != 0 and trend_b != 0:
            reinforcement = -1
        else:
            reinforcement = 0
        rolling = self.compute_rolling_correlation(prices_a, prices_b)
        return PairAnalysis(
            correlation=corr,
            rolling_correlation=rolling,
            is_cointegrated=is_coint,
            coint_pvalue=pval,
            trend_a=trend_a,
            trend_b=trend_b,
            reinforcement=reinforcement,
            strong_correlation=abs(corr) > self.correlation_threshold,
        )

    @staticmethod
    def adjust_confidence(base: float, reinforcement: int) -> float:
        if reinforcement == 1:
            return min(base * 1.2, 1.0)
        if reinforcement == -1:
            return max(base * 0.8, 0.0)
        return base

    def filter_signals(
        self,
        raw_signals: Dict[str, Dict],
        prices_by_symbol: Dict[str, List[float]],
    ) -> Dict[str, FilteredSignal]:
        """
        Args:
            raw_signals: {symbol: {action, confidence, price}}
            prices_by_symbol: {symbol: [closes...]}
        """
        result: Dict[str, FilteredSignal] = {}
        for sym, sig in raw_signals.items():
            result[sym] = FilteredSignal(
                symbol=sym,
                action=sig.get("action", "NEUTRAL"),
                confidence=float(sig.get("confidence", 0.0)),
                adjusted_confidence=float(sig.get("confidence", 0.0)),
                lot_multiplier=1.0,
                filtered_out=False,
            )

        symbols = list(raw_signals.keys())
        for i, sym_a in enumerate(symbols):
            for sym_b in symbols[i + 1:]:
                if sym_a not in prices_by_symbol or sym_b not in prices_by_symbol:
                    continue
                analysis = self.analyze_pair(
                    sym_a, sym_b, prices_by_symbol[sym_a], prices_by_symbol[sym_b]
                )

                action_a = result[sym_a].action
                action_b = result[sym_b].action

                if not analysis.strong_correlation:
                    continue

                if action_a != "NEUTRAL" and action_b != "NEUTRAL" and action_a != action_b:
                    result[sym_a].filtered_out = True
                    result[sym_b].filtered_out = True
                    result[sym_a].reasons.append(
                        f"opposite_signal_to_{sym_b}_corr={analysis.correlation:.2f}"
                    )
                    result[sym_b].reasons.append(
                        f"opposite_signal_to_{sym_a}_corr={analysis.correlation:.2f}"
                    )
                    logger.info(
                        "filtered out %s and %s (opposite signals, corr=%.2f)",
                        sym_a, sym_b, analysis.correlation,
                    )

                elif action_a == action_b and action_a != "NEUTRAL":
                    boost = 1.2 if analysis.correlation > 0 else 0.8
                    result[sym_a].lot_multiplier *= boost
                    result[sym_b].lot_multiplier *= boost
                    result[sym_a].adjusted_confidence = self.adjust_confidence(
                        result[sym_a].confidence, 1
                    )
                    result[sym_b].adjusted_confidence = self.adjust_confidence(
                        result[sym_b].confidence, 1
                    )
                    result[sym_a].reasons.append(
                        f"aligned_with_{sym_b}_corr={analysis.correlation:.2f}"
                    )
                    result[sym_b].reasons.append(
                        f"aligned_with_{sym_a}_corr={analysis.correlation:.2f}"
                    )
                    logger.info(
                        "boosted %s and %s (aligned signals, corr=%.2f)",
                        sym_a, sym_b, analysis.correlation,
                    )

        return result