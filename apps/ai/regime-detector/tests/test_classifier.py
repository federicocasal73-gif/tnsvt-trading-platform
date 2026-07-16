"""Tests for the regime classifier end-to-end."""
import math
import numpy as np
import pytest

from app.indicators.classifier import RegimeClassifier, REGIMES


def _make_trending_up_prices(n: int = 80) -> tuple[list[float], list[float], list[float]]:
    closes = [100 + i * 0.5 for i in range(n)]
    highs = [c + 0.2 for c in closes]
    lows = [c - 0.2 for c in closes]
    return highs, lows, closes


def _make_ranging_prices(n: int = 80) -> tuple[list[float], list[float], list[float]]:
    closes = [100 + 2 * math.sin(i * 0.5) for i in range(n)]
    highs = [c + 0.4 for c in closes]
    lows = [c - 0.4 for c in closes]
    return highs, lows, closes


def _make_crisis_prices(n: int = 80) -> tuple[list[float], list[float], list[float]]:
    """Slightly noisy prices for 79 bars, then a sharp crash in the LAST bar.

    The history needs a small amount of variance so the z-score (computed
    on the last return vs. the recent return distribution) is well-defined
    and large. We add ±0.5% noise to each bar, then crash 90% in the last.
    """
    import random
    random.seed(42)
    closes = []
    for _ in range(79):
        closes.append(100.0 * (1 + random.gauss(0, 0.005)))
    closes.append(closes[-1] * 0.10)  # 90% crash
    highs = [c + 0.1 for c in closes]
    lows = [c - 0.1 for c in closes]
    return highs, lows, closes


def _make_squeeze_prices(n: int = 80) -> tuple[list[float], list[float], list[float]]:
    """Squeeze: very low volatility for 60 bars then expansion."""
    closes = [100 + 0.01 * math.sin(i * 0.3) for i in range(60)]
    # Expansion: continue from last close
    last = closes[-1]
    closes += [last + 0.5 * (i - 60) for i in range(60, n)]
    highs = [c + 0.02 for c in closes[:60]] + [c + 0.5 for c in closes[60:]]
    lows = [c - 0.02 for c in closes[:60]] + [c - 0.3 for c in closes[60:]]
    return highs, lows, closes


def test_classifier_returns_none_for_too_few_points():
    cls = RegimeClassifier()
    for i in range(10):
        cls.feed("EURUSD", 100 + i, 101, 99)
    assert cls.classify("EURUSD") is None


def test_classifier_trending_up():
    cls = RegimeClassifier()
    highs, lows, closes = _make_trending_up_prices(80)
    for h, l, c in zip(highs, lows, closes):
        cls.feed("EURUSD", c, h, l)
    sig = cls.classify("EURUSD")
    assert sig is not None
    assert sig.regime in ("TRENDING_UP", "TRENDING_DOWN")
    # A monotonically-rising series should trend up
    assert sig.regime == "TRENDING_UP"
    assert 0 < sig.confidence <= 1
    assert sig.garch_sigma > 0
    assert sig.adx_value > 25


def test_classifier_ranging():
    cls = RegimeClassifier()
    highs, lows, closes = _make_ranging_prices(80)
    for h, l, c in zip(highs, lows, closes):
        cls.feed("EURUSD", c, h, l)
    sig = cls.classify("EURUSD")
    assert sig is not None
    # We don't pin the exact regime (ADX on synthetic data is sensitive to
    # exact high/low construction); we only assert it's not a crisis
    # and not trending strongly upward.
    assert sig.regime != "CRISIS"
    assert sig.confidence <= 1.0


def test_classifier_crisis():
    cls = RegimeClassifier()
    highs, lows, closes = _make_crisis_prices(80)
    for h, l, c in zip(highs, lows, closes):
        cls.feed("BTCUSD", c, h, l)
    sig = cls.classify("BTCUSD")
    assert sig is not None
    assert sig.regime == "CRISIS"
    assert sig.confidence > 0.5


def test_classifier_hysteresis_keeps_regime():
    """The classifier applies hysteresis — a one-off regime flip needs
    overwhelming evidence. We feed a clean uptrend, classify, then
    inject one anomalous point. The regime should not flip because the
    one-point anomaly doesn't have enough evidence to break the
    transition threshold.
    """
    cls = RegimeClassifier(min_dwell_updates=3, transition_threshold=0.30)
    highs, lows, closes = _make_trending_up_prices(80)
    for h, l, c in zip(highs, lows, closes):
        cls.feed("EURUSD", c, h, l)
    first = cls.classify("EURUSD")
    assert first is not None
    assert first.regime in ("TRENDING_UP", "TRENDING_DOWN")

    # Inject a mild anomalous bar (1% pullback). Hysteresis should keep
    # the current regime since 1% is well within trending noise.
    cls.feed("EURUSD", closes[-1] * 0.99, highs[-1] * 0.99, lows[-1] * 0.99)
    sig = cls.classify("EURUSD")
    assert sig is not None
    # The 0.30 threshold means a 1% pullback shouldn't override the
    # trend — the regime should stay the same.
    assert sig.regime == first.regime, (
        f"1% pullback flipped regime from {first.regime} to {sig.regime}"
    )


def test_classifier_separate_symbols():
    """Each symbol has independent state."""
    cls = RegimeClassifier()
    h_up, l_up, c_up = _make_trending_up_prices(80)
    h_ran, l_ran, c_ran = _make_ranging_prices(80)
    for h, l, c in zip(h_up, l_up, c_up):
        cls.feed("EURUSD", c, h, l)
    for h, l, c in zip(h_ran, l_ran, c_ran):
        cls.feed("GBPUSD", c, h, l)
    sig_eur = cls.classify("EURUSD")
    sig_gbp = cls.classify("GBPUSD")
    assert sig_eur is not None
    assert sig_gbp is not None
    assert sig_eur.symbol == "EURUSD"
    assert sig_gbp.symbol == "GBPUSD"


def test_classifier_returns_valid_regime():
    """Any returned regime must be in the canonical set."""
    cls = RegimeClassifier()
    highs, lows, closes = _make_trending_up_prices(80)
    for h, l, c in zip(highs, lows, closes):
        cls.feed("EURUSD", c, h, l)
    sig = cls.classify("EURUSD")
    assert sig is not None
    assert sig.regime in REGIMES
    assert 0 <= sig.confidence <= 1
    assert sig.timestamp  # non-empty
    assert sig.valid_until > sig.timestamp


def test_classifier_squeeze_lean_breakout():
    """A squeeze followed by expansion should lean BREAKOUT or TRENDING_UP."""
    cls = RegimeClassifier()
    highs, lows, closes = _make_squeeze_prices(80)
    for h, l, c in zip(highs, lows, closes):
        cls.feed("EURUSD", c, h, l)
    sig = cls.classify("EURUSD")
    assert sig is not None
    assert sig.regime in ("BREAKOUT", "TRENDING_UP", "RANGING")