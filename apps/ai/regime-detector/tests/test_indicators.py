"""Tests for technical indicators."""
import math
import numpy as np
import pytest

from app.indicators.indicators import (
    garch_variance,
    garch_sigma,
    garch_class,
    adx,
    adx_class,
    hurst,
    hurst_class,
    bollinger_width,
    is_bollinger_squeeze,
)


def test_garch_variance_too_few_points():
    assert garch_variance([]) == 0.0
    assert garch_variance([1.0, 2.0]) == 0.0


def test_garch_variance_is_finite_and_positive():
    """A random walk of 200 points should yield a small but positive variance."""
    rng = np.random.default_rng(42)
    prices = 100 + np.cumsum(rng.normal(0, 0.5, 200))
    v = garch_variance(prices)
    assert v > 0
    assert math.isfinite(v)


def test_garch_sigma_matches_sqrt_of_variance():
    prices = [100 + 0.01 * i + 0.5 * (i % 7) for i in range(80)]
    s = garch_sigma(prices)
    v = garch_variance(prices)
    assert math.isclose(s, math.sqrt(v), rel_tol=1e-9)


def test_garch_class_buckets():
    assert garch_class(0.1, 0.5, 1.0) == "LOW_VOL"
    assert garch_class(2.0, 0.5, 1.0) == "HIGH_VOL"
    assert garch_class(0.7, 0.5, 1.0) == "NORMAL_VOL"


def test_adx_too_few_points():
    assert adx([1, 2, 3], [1, 2, 3], [1, 2, 3]) == 0.0


def test_adx_strong_uptrend():
    """A monotonic uptrend should give ADX > 25 and classify as TRENDING_UP."""
    n = 100  # enough data for ADX to stabilize via Wilder smoothing
    closes = [100 + i * 0.5 for i in range(n)]
    highs = [c + 0.3 for c in closes]
    lows = [c - 0.3 for c in closes]
    a = adx(highs, lows, closes)
    assert a > 25, f"got ADX={a}"
    assert adx_class(a, plus_di=30, minus_di=10) == "TRENDING_UP"


def test_adx_strong_downtrend():
    n = 100
    closes = [200 - i * 0.5 for i in range(n)]
    highs = [c + 0.3 for c in closes]
    lows = [c - 0.3 for c in closes]
    a = adx(highs, lows, closes)
    assert a > 25, f"got ADX={a}"
    assert adx_class(a, plus_di=10, minus_di=30) == "TRENDING_DOWN"


def test_adx_ranging_market():
    """Sideways prices → ADX < 25 → RANGING.

    Tight, mostly-flat range with high/low that don't exhibit a directional
    bias. We use 200 points so ADX has enough history for Wilder smoothing
    to settle.
    """
    rng = np.random.default_rng(11)
    n = 200
    # Pure mean-reverting around 100
    closes = []
    p = 100.0
    for _ in range(n):
        p += rng.normal(0, 0.05)
        p = 100 + (p - 100) * 0.3  # mean reversion
        closes.append(p)
    highs = [c + abs(rng.normal(0, 0.04)) for c in closes]
    lows = [c - abs(rng.normal(0, 0.04)) for c in closes]
    a = adx(highs, lows, closes)
    assert a < 25, f"got ADX={a} for ranging market"
    assert adx_class(a, plus_di=15, minus_di=15) == "RANGING"


def test_hurst_too_few_points():
    assert hurst([1, 2, 3]) == 0.5


def test_hurst_random_walk_is_near_half():
    """A geometric random walk should have H ≈ 0.5 (within tolerance).

    Note: R/S-based Hurst estimation is notoriously noisy on short
    synthetic series. We use 2000 points and a generous [0.25, 0.75] band.
    """
    rng = np.random.default_rng(123)
    n = 2000
    log_returns = rng.normal(0, 0.01, n)
    prices = 100 * np.exp(np.cumsum(log_returns))
    h = hurst(prices)
    assert 0.25 < h < 0.75, f"got H={h}"


def test_hurst_persistent_series():
    """A persistent (trending) series should have H > H of a random walk.

    We don't pin a specific H value because R/S is noisy; we just assert
    that a strong-positive-autocorrelation series has higher H than a
    pure random walk.
    """
    rng = np.random.default_rng(7)
    n = 2000
    persistent = [100.0]
    for _ in range(n - 1):
        ret = 0.005 + rng.normal(0, 0.002)
        persistent.append(persistent[-1] * (1 + ret))

    random_walk = [100.0]
    rng2 = np.random.default_rng(42)
    for _ in range(n - 1):
        random_walk.append(random_walk[-1] * (1 + rng2.normal(0, 0.01)))

    h_p = hurst(persistent)
    h_r = hurst(random_walk)
    assert h_p > h_r, f"persistent H ({h_p}) should exceed random H ({h_r})"


def test_hurst_class():
    assert hurst_class(0.7) == "TRENDING"
    assert hurst_class(0.3) == "MEAN_REVERT"
    assert hurst_class(0.5) == "RANDOM_WALK"


def test_bollinger_width_too_few():
    assert bollinger_width([1, 2, 3]) == 0.0


def test_bollinger_width_is_positive_for_normal_data():
    rng = np.random.default_rng(99)
    prices = 100 + np.cumsum(rng.normal(0, 1, 50))
    w = bollinger_width(prices)
    assert w > 0


def test_is_bollinger_squeeze_triggers_on_low_width():
    """If current width is at the 10th percentile of history → squeeze=True."""
    history = [0.05] * 90 + [0.01]  # 0.01 is at the 10th percentile
    assert is_bollinger_squeeze(0.01, history) is True


def test_is_bollinger_squeeze_does_not_trigger_on_high_width():
    history = [0.05] * 100
    assert is_bollinger_squeeze(0.10, history) is False


def test_is_bollinger_squeeze_handles_empty():
    assert is_bollinger_squeeze(0.1, []) is False
    assert is_bollinger_squeeze(-0.1, [0.1, 0.2]) is False