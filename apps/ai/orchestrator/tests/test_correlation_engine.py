"""Tests for CorrelationEngine."""
import numpy as np
import pytest

from app.correlation_engine import CorrelationEngine


def test_perfect_positive_correlation():
    eng = CorrelationEngine(coint_enabled=False)
    p1 = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    p2 = [2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0]
    corr = eng.compute_correlation(p1, p2)
    assert abs(corr - 1.0) < 0.01


def test_perfect_negative_correlation():
    eng = CorrelationEngine(coint_enabled=False)
    p1 = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    p3 = [10.0, 9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0]
    corr = eng.compute_correlation(p1, p3)
    assert abs(corr - (-1.0)) < 0.01


def test_zero_correlation_random():
    eng = CorrelationEngine(coint_enabled=False)
    np.random.seed(42)
    p1 = np.random.randn(50).tolist()
    p2 = np.random.randn(50).tolist()
    corr = eng.compute_correlation(p1, p2)
    assert abs(corr) < 0.3


def test_cointegration_synthetic():
    eng = CorrelationEngine()
    np.random.seed(42)
    base = np.cumsum(np.random.randn(100))
    p1 = (base + np.random.randn(100) * 0.1).tolist()
    p2 = (base + np.random.randn(100) * 0.1).tolist()
    is_coint, pval = eng.check_cointegration(p1, p2)
    assert is_coint is True
    assert pval < 0.05


def test_cointegration_disabled():
    eng = CorrelationEngine(coint_enabled=False)
    is_coint, pval = eng.check_cointegration([1.0, 2.0, 3.0], [4.0, 5.0, 6.0])
    assert is_coint is False
    assert pval == 1.0


def test_align_prices_different_lengths():
    eng = CorrelationEngine(coint_enabled=False)
    p1 = [1.0, 2.0, 3.0, 4.0, 5.0]
    p2 = [10.0, 20.0, 30.0]
    corr = eng.compute_correlation(p1, p2)
    assert -1.0 <= corr <= 1.0


def test_adjust_confidence_boost():
    eng = CorrelationEngine()
    assert eng.adjust_confidence(0.8, 1) == pytest.approx(0.96)
    assert eng.adjust_confidence(1.0, 1) == 1.0
    assert eng.adjust_confidence(0.5, 0) == 0.5


def test_adjust_confidence_reduce():
    eng = CorrelationEngine()
    assert eng.adjust_confidence(0.8, -1) == pytest.approx(0.64)
    assert eng.adjust_confidence(0.1, -1) == pytest.approx(0.08)


def test_recent_trend():
    eng = CorrelationEngine()
    prices_up = [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0]
    prices_down = [2.0, 1.9, 1.8, 1.7, 1.6, 1.5, 1.4, 1.3, 1.2, 1.1, 1.0]
    prices_flat = [1.0] * 11
    assert eng._recent_trend(prices_up) == 1
    assert eng._recent_trend(prices_down) == -1
    assert eng._recent_trend(prices_flat) == 0


def test_filter_signals_aligned_boost():
    eng = CorrelationEngine(coint_enabled=False)
    np.random.seed(123)
    base = np.cumsum(np.random.randn(60))
    p1 = (base + np.random.randn(60) * 0.05).tolist()
    p2 = (base + np.random.randn(60) * 0.05).tolist()
    raw = {
        "XAUUSD": {"action": "BUY", "confidence": 0.7, "price": 2000.0},
        "EURUSD": {"action": "BUY", "confidence": 0.6, "price": 1.1},
    }
    prices = {"XAUUSD": p1, "EURUSD": p2}
    result = eng.filter_signals(raw, prices)
    assert not result["XAUUSD"].filtered_out
    assert not result["EURUSD"].filtered_out
    assert result["XAUUSD"].lot_multiplier >= 1.0
    assert result["EURUSD"].lot_multiplier >= 1.0


def test_filter_signals_opposite_filtered_out():
    eng = CorrelationEngine(coint_enabled=False)
    np.random.seed(456)
    base = np.cumsum(np.random.randn(60))
    p1 = (base + np.random.randn(60) * 0.05).tolist()
    p2 = (base + np.random.randn(60) * 0.05).tolist()
    raw = {
        "XAUUSD": {"action": "BUY", "confidence": 0.7, "price": 2000.0},
        "EURUSD": {"action": "SELL", "confidence": 0.6, "price": 1.1},
    }
    prices = {"XAUUSD": p1, "EURUSD": p2}
    result = eng.filter_signals(raw, prices)
    assert result["XAUUSD"].filtered_out is True
    assert result["EURUSD"].filtered_out is True


def test_filter_signals_low_correlation_no_filter():
    eng = CorrelationEngine(correlation_threshold=0.9, coint_enabled=False)
    np.random.seed(789)
    p1 = np.cumsum(np.random.randn(60)).tolist()
    p2 = np.cumsum(np.random.randn(60)).tolist()
    raw = {
        "XAUUSD": {"action": "BUY", "confidence": 0.7, "price": 2000.0},
        "EURUSD": {"action": "SELL", "confidence": 0.6, "price": 1.1},
    }
    prices = {"XAUUSD": p1, "EURUSD": p2}
    result = eng.filter_signals(raw, prices)
    assert result["XAUUSD"].filtered_out is False
    assert result["EURUSD"].filtered_out is False


def test_analyze_pair_returns_correct_fields():
    eng = CorrelationEngine(coint_enabled=False)
    p1 = [1.0 + i * 0.1 for i in range(60)]
    p2 = [2.0 + i * 0.1 for i in range(60)]
    analysis = eng.analyze_pair("XAUUSD", "EURUSD", p1, p2)
    assert analysis.correlation > 0.99
    assert analysis.strong_correlation is True
    assert analysis.trend_a == 1
    assert analysis.trend_b == 1
    assert analysis.reinforcement == 1