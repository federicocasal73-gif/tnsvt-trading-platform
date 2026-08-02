"""Tests for RiskManager."""
import pytest

from app.risk_manager import OHLC, RiskManager


def _make_candles(prices):
    return [OHLC(open=p, high=p * 1.001, low=p * 0.999, close=p) for p in prices]


def test_atr_basic():
    rm = RiskManager(atr_period=14)
    candles = _make_candles([100 + i for i in range(20)])
    atr = rm.calculate_atr(candles)
    assert atr > 0


def test_atr_too_short_returns_zero():
    rm = RiskManager(atr_period=14)
    candles = _make_candles([100, 101, 102])
    atr = rm.calculate_atr(candles)
    assert atr == 0.0


def test_sl_tp_buy():
    rm = RiskManager(atr_period=14, sl_atr_multiplier=1.5, tp_atr_multiplier=2.5)
    candles = _make_candles([100 + i * 0.5 for i in range(20)])
    sltp = rm.calculate_sl_tp(candles, "BUY", entry_price=110.0)
    assert sltp.sl < 110.0
    assert sltp.tp > 110.0
    assert sltp.rr_ratio == pytest.approx(2.5 / 1.5, 0.01)


def test_sl_tp_sell():
    rm = RiskManager(atr_period=14, sl_atr_multiplier=1.5, tp_atr_multiplier=2.5)
    candles = _make_candles([100 + i * 0.5 for i in range(20)])
    sltp = rm.calculate_sl_tp(candles, "SELL", entry_price=110.0)
    assert sltp.sl > 110.0
    assert sltp.tp < 110.0
    assert sltp.rr_ratio == pytest.approx(2.5 / 1.5, 0.01)


def test_sl_tp_invalid_action():
    rm = RiskManager()
    candles = _make_candles([100, 101, 102, 103, 104])
    with pytest.raises(ValueError):
        rm.calculate_sl_tp(candles, "HOLD")


def test_trailing_sl_buy_moves_up():
    rm = RiskManager(sl_atr_multiplier=1.5)
    initial_sl = 100.0
    new_sl = rm.calculate_trailing_sl(initial_sl, current_price=110.0, atr=2.0, side="BUY")
    assert new_sl > initial_sl


def test_trailing_sl_buy_does_not_move_down():
    rm = RiskManager(sl_atr_multiplier=1.5)
    initial_sl = 100.0
    new_sl = rm.calculate_trailing_sl(initial_sl, current_price=90.0, atr=2.0, side="BUY")
    assert new_sl == initial_sl


def test_trailing_sl_sell_moves_down():
    rm = RiskManager(sl_atr_multiplier=1.5)
    initial_sl = 110.0
    new_sl = rm.calculate_trailing_sl(initial_sl, current_price=100.0, atr=2.0, side="SELL")
    assert new_sl < initial_sl


def test_trailing_sl_sell_does_not_move_up():
    rm = RiskManager(sl_atr_multiplier=1.5)
    initial_sl = 100.0
    new_sl = rm.calculate_trailing_sl(initial_sl, current_price=110.0, atr=2.0, side="SELL")
    assert new_sl == initial_sl


def test_trailing_sl_zero_atr_keeps_initial():
    rm = RiskManager()
    new_sl = rm.calculate_trailing_sl(100.0, current_price=110.0, atr=0.0, side="BUY")
    assert new_sl == 100.0