"""Pure technical indicators used by the regime classifier.

All functions take a numpy array of close prices (or pandas Series) and
return a numeric value. They are designed to be:
- Pure (no I/O, no global state)
- Numerically stable (no division by zero, no log of negative)
- Tested in isolation (see tests/test_indicators.py)

We implement classical formulas with sensible defaults rather than pulling
in a heavy stats library — these have to be fast enough to run on every
market-data tick batch.
"""
from __future__ import annotations

import math
from typing import Iterable, Sequence

import numpy as np


# ─── Helpers ─────────────────────────────────────────────────────────────

def _to_1d(values: Sequence[float] | np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64)
    if arr.ndim != 1:
        arr = arr.flatten()
    return arr


def _safe_log_returns(prices: np.ndarray) -> np.ndarray:
    """log(p[t] / p[t-1]); NaN-safe at the first element."""
    if len(prices) < 2:
        return np.zeros(0)
    out = np.zeros(len(prices) - 1)
    for i in range(1, len(prices)):
        p0, p1 = prices[i - 1], prices[i]
        out[i - 1] = math.log(p1 / p0) if p0 > 0 and p1 > 0 else 0.0
    return out


# ─── GARCH(1,1) volatility ──────────────────────────────────────────────
# Variance update: σ²[t] = ω + α·r²[t-1] + β·σ²[t-1]
# We use a small `lookback` window so the result is bounded by the data we
# actually have. With infinite data, this converges to the unconditional
# variance σ²∞ = ω / (1 - α - β); we don't need that — we want the
# most-recent conditional variance.

def garch_variance(
    prices: Iterable[float],
    omega: float = 0.000001,
    alpha: float = 0.10,
    beta: float = 0.85,
) -> float:
    """Returns the latest conditional variance from a GARCH(1,1) filter.

    Returns 0.0 if there's not enough data (< 3 points).
    """
    arr = _to_1d(list(prices))
    if len(arr) < 3:
        return 0.0

    r = _safe_log_returns(arr)
    if len(r) < 2:
        return 0.0

    # Seed the variance with the sample variance of the first returns.
    sigma2 = float(np.var(r[:min(20, len(r))]))
    for i in range(1, len(r)):
        sigma2 = omega + alpha * r[i - 1] ** 2 + beta * sigma2
    return float(sigma2)


def garch_sigma(prices: Iterable[float], **kwargs) -> float:
    """Square root of garch_variance — the volatility in the same units as price."""
    return math.sqrt(max(0.0, garch_variance(prices, **kwargs)))


def garch_class(sigma: float, low_pct: float, high_pct: float) -> str:
    """Bucket the volatility into LOW / NORMAL / HIGH given percentile thresholds.

    low_pct / high_pct come from a rolling window of historical sigmas
    (computed in the regime classifier); defaults fall back to constants.
    """
    if sigma <= low_pct:
        return "LOW_VOL"
    if sigma >= high_pct:
        return "HIGH_VOL"
    return "NORMAL_VOL"


# ─── ADX (Average Directional Index) ────────────────────────────────────
# True Range, +DM/-DM, then smoothed averages, then DX, then ADX = SMA(DX, n).
# Implementation is explicit (no external ta-lib).

def adx(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> float:
    """Returns the ADX value [0, 100]. 0 if not enough data."""
    h = _to_1d(highs)
    l = _to_1d(lows)
    c = _to_1d(closes)
    n = len(h)
    if n < period + 1 or len(l) != n or len(c) != n:
        return 0.0

    tr = np.zeros(n - 1)
    plus_dm = np.zeros(n - 1)
    minus_dm = np.zeros(n - 1)

    for i in range(1, n):
        up = h[i] - h[i - 1]
        down = l[i - 1] - l[i]
        tr[i - 1] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
        plus_dm[i - 1] = up if (up > down and up > 0) else 0.0
        minus_dm[i - 1] = down if (down > up and down > 0) else 0.0

    # Wilder's smoothing: first smoothed = sum(period); subsequent = prev - prev/period + current
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

    # DI components
    with np.errstate(divide='ignore', invalid='ignore'):
        plus_di = np.where(sm_tr > 0, 100.0 * sm_plus / sm_tr, 0.0)
        minus_di = np.where(sm_tr > 0, 100.0 * sm_minus / sm_tr, 0.0)
        dx = np.where(
            (plus_di + minus_di) > 0,
            100.0 * np.abs(plus_di - minus_di) / (plus_di + minus_di),
            0.0,
        )

    # ADX = Wilder smoothing of DX, normalized by period so the result stays
    # in [0, 100]. The classic Wilder ADX definition uses sum/n for the
    # seed and then Wilder smoothing on top, which is what we do here.
    if len(dx) < period:
        return 0.0
    adx_seed = float(np.sum(dx[:period])) / period
    adx_val = adx_seed
    for i in range(period, len(dx)):
        adx_val = (adx_val * (period - 1) + dx[i]) / period
    return float(adx_val)


def adx_class(adx_value: float, plus_di: float, minus_di: float, threshold: float = 25.0) -> str:
    """Combine ADX with DI+/DI- to pick the trend direction."""
    if adx_value < threshold:
        return "RANGING"
    if plus_di > minus_di:
        return "TRENDING_UP"
    return "TRENDING_DOWN"


# ─── Hurst exponent (R/S analysis) ─────────────────────────────────────
# H = log(R/S) / log(N), where R is the range of cumulative deviations and
# S is the std dev. 0.5 = random walk, >0.5 = persistent, <0.5 = mean-revert.

def hurst(prices: Iterable[float], min_window: int = 20) -> float:
    """Estimate the Hurst exponent via aggregated R/S analysis.

    The classical log(R/S)/log(N) estimator is biased upward for short
    series. We use Peters' variation: split the series into multiple
    sub-windows of size n/k and median-average R/S across them. We also
    apply an empirical bias correction (subtract 0.5 * (1 - log(n)/log(N)))
    to compensate for the known upward bias of R/S on small samples.

    Returns 0.5 if there's not enough data. The result is clipped to
    [0, 1] to defend against numerical noise.
    """
    arr = _to_1d(list(prices))
    if len(arr) < min_window:
        return 0.5

    n = len(arr)
    # Use multiple sub-window sizes: 16, 32, 64, 128, ... up to n/2
    sub_windows = [16, 32, 64, 128, 256, 512]
    sub_windows = [w for w in sub_windows if 4 * w <= n and w >= min_window]
    if not sub_windows:
        sub_windows = [max(min_window, n // 2)]

    estimates = []
    for w in sub_windows:
        # Split the last (k*w) points into k non-overlapping windows of size w
        n_full = (n // w) * w
        if n_full < w:
            continue
        k = n_full // w
        rs_values = []
        for i in range(k):
            sub = arr[-(n_full - i * w):-(n_full - (i + 1) * w) if i < k - 1 else None]
            if sub is None or len(sub) < w:
                continue
            mean = float(np.mean(sub))
            dev = sub - mean
            cum_dev = np.cumsum(dev)
            r = float(np.max(cum_dev) - np.min(cum_dev))
            s = float(np.std(sub, ddof=1))
            if s > 0 and r > 0 and w > 1:
                rs_values.append(r / s)
        if rs_values:
            mean_rs = float(np.mean(rs_values))
            h = math.log(mean_rs) / math.log(w)
            # Bias correction: subtract the small-sample upward bias.
            h -= 0.5 * (1.0 - math.log(w) / math.log(n))
            estimates.append(h)

    if not estimates:
        return 0.5
    return float(max(0.0, min(1.0, float(np.median(estimates)))))


def hurst_class(h: float) -> str:
    if h > 0.55:
        return "TRENDING"  # persistent — momentum
    if h < 0.45:
        return "MEAN_REVERT"  # anti-persistent
    return "RANDOM_WALK"


# ─── Bollinger Band width (squeeze detection) ───────────────────────────
# Width = (upper - lower) / middle. A squeeze is a width below the historical
# 10th percentile — the market is coiling before a breakout.

def bollinger_width(prices: Iterable[float], period: int = 20, num_std: float = 2.0) -> float:
    arr = _to_1d(list(prices))
    if len(arr) < period:
        return 0.0
    window = arr[-period:]
    middle = float(np.mean(window))
    std = float(np.std(window, ddof=1))
    if middle <= 0:
        return 0.0
    return (2.0 * num_std * std) / middle


def is_bollinger_squeeze(current_width: float, history_widths: Sequence[float], percentile: float = 0.10) -> bool:
    """True if the current width is at/below the `percentile` of `history_widths`."""
    if not history_widths or current_width <= 0:
        return False
    sorted_w = sorted(history_widths)
    k = max(0, int(len(sorted_w) * percentile) - 1)
    return current_width <= sorted_w[k]