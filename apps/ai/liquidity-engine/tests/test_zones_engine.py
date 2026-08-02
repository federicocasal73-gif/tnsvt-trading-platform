"""Tests para el motor de reglas de zonas (zones_engine)."""
from datetime import datetime, timezone

from app.lst_engine import LSTEngine
from app.models import RateOHLCV
from app.zones_engine import ZonesEngine


def _rate(symbol="XAUUSD", timeframe="M1", close=1500.0, high=1502.0, low=1498.0,
          open_val=1500.0, spread=5, volume=100.0, tick_volume=1000):
    return RateOHLCV(
        symbol=symbol, timeframe=timeframe, time=datetime.now(timezone.utc),
        open=open_val, high=high, low=low, close=close,
        volume=volume, tick_volume=tick_volume, spread=spread,
    )


def _bullish_rate():
    return _rate(open_val=1498.0, close=1502.0, high=1503.0, low=1497.0,
                 volume=200.0, tick_volume=2000.0)


def _bearish_rate():
    return _rate(open_val=1502.0, close=1498.0, high=1503.0, low=1497.0,
                 volume=200.0, tick_volume=2000.0)


def _warm_lst(engine: LSTEngine, n: int = 25, bullish: bool = True):
    for _ in range(n):
        engine.compute(_bullish_rate() if bullish else _bearish_rate())


def _zone(type_, midpoint=1500.0, price_high=1501.0, price_low=1499.0, swept=False, strength=1):
    return {
        "type": type_, "midpoint": midpoint, "price_high": price_high,
        "price_low": price_low, "swept": swept, "strength": strength,
    }


def test_neutral_when_no_zones():
    eng = ZonesEngine(LSTEngine())
    assert eng.evaluate("XAUUSD", "M1", 1500.0, []) is None


def test_swept_zone_ignored():
    eng = ZonesEngine(LSTEngine())
    zones = [_zone("bos_bull", midpoint=1500.0, swept=True)]
    assert eng.evaluate("XAUUSD", "M1", 1500.0, zones, _rate()) is None


def test_bos_bull_aligned_with_lst_buy():
    lst = LSTEngine()
    _warm_lst(lst, bullish=True)
    eng = ZonesEngine(lst)
    zones = [_zone("bos_bull", midpoint=1500.0, price_high=1505.0, price_low=1495.0)]
    sig = eng.evaluate("XAUUSD", "M1", 1500.0, zones, _bullish_rate())
    assert sig is not None
    assert sig.signal_type == "liquidity_buy"
    assert sig.confidence >= 0.3


def test_bos_bear_aligned_with_lst_sell():
    lst = LSTEngine()
    _warm_lst(lst, bullish=False)
    eng = ZonesEngine(lst)
    zones = [_zone("bos_bear", midpoint=1500.0, price_high=1505.0, price_low=1495.0)]
    sig = eng.evaluate("XAUUSD", "M1", 1500.0, zones, _bearish_rate())
    assert sig is not None
    assert sig.signal_type == "liquidity_sell"
    assert sig.confidence >= 0.3


def test_bos_bull_zone_but_lst_sells_returns_low_confidence():
    lst = LSTEngine()
    _warm_lst(lst, bullish=False)
    eng = ZonesEngine(lst)
    zones = [_zone("bos_bull", midpoint=1500.0, price_high=1505.0, price_low=1495.0)]
    sig = eng.evaluate("XAUUSD", "M1", 1500.0, zones, _bearish_rate())
    if sig is not None:
        assert sig.signal_type == "liquidity_buy"
        assert sig.confidence < 0.3


def test_equal_high_aligned_sell():
    lst = LSTEngine()
    _warm_lst(lst, bullish=False)
    eng = ZonesEngine(lst)
    zones = [_zone("equal_high", midpoint=1510.0, price_high=1511.0, price_low=1509.0)]
    sig = eng.evaluate("XAUUSD", "M1", 1510.0, zones, _bearish_rate())
    assert sig is not None
    assert sig.signal_type == "liquidity_sell"


def test_far_price_no_signal():
    eng = ZonesEngine(LSTEngine())
    zones = [_zone("bos_bull", midpoint=1600.0)]
    assert eng.evaluate("XAUUSD", "M1", 1500.0, zones, _rate()) is None


def test_metrics_present():
    lst = LSTEngine()
    _warm_lst(lst, bullish=True)
    eng = ZonesEngine(lst)
    zones = [_zone("bos_bull", midpoint=1500.0)]
    sig = eng.evaluate("XAUUSD", "M1", 1500.0, zones, _bullish_rate())
    assert sig is not None
    m = sig.metrics
    assert m.relative_spread >= 0
    assert -1 <= m.volume_imbalance <= 1
    assert 0.0 <= m.liquidity_score <= 1.0


def test_signal_has_timeframe():
    lst = LSTEngine()
    _warm_lst(lst, bullish=True)
    eng = ZonesEngine(lst)
    zones = [_zone("bos_bull", midpoint=1500.0)]
    sig = eng.evaluate("XAUUSD", "H1", 1500.0, zones, _bullish_rate())
    assert sig is not None
    assert sig.timeframe == "H1"
