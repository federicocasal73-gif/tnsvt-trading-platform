from datetime import datetime, timezone

from app.lst_engine import LSTEngine
from app.models import RateOHLCV


def _rate(
    close=1500.0,
    high=1502.0,
    low=1498.0,
    open_val=1500.0,
    spread=5,
    volume=100.0,
    tick_volume=1000,
    symbol="XAUUSD",
    timeframe="M1",
):
    return RateOHLCV(
        symbol=symbol,
        timeframe=timeframe,
        time=datetime.now(timezone.utc),
        open=open_val,
        high=high,
        low=low,
        close=close,
        volume=volume,
        tick_volume=tick_volume,
        spread=spread,
    )


def test_neutral_until_window_filled():
    engine = LSTEngine(window_size=5)
    for _ in range(4):
        assert engine.compute(_rate()) is None
    signal = engine.compute(_rate())
    assert signal is not None


def test_liquidity_buy_signal():
    engine = LSTEngine(window_size=5)
    for _ in range(5):
        engine.compute(_rate(open_val=1498, close=1502, high=1503, low=1497, tick_volume=2000, volume=200))
    signal = engine.compute(_rate(open_val=1498, close=1502, high=1503, low=1497, tick_volume=2000, volume=200))
    assert signal is not None
    assert signal.signal_type == "liquidity_buy"
    assert signal.confidence > 0


def test_liquidity_sell_signal():
    engine = LSTEngine(window_size=5)
    for _ in range(5):
        engine.compute(_rate(open_val=1502, close=1498, high=1503, low=1497, tick_volume=2000, volume=200))
    signal = engine.compute(_rate(open_val=1502, close=1498, high=1503, low=1497, tick_volume=2000, volume=200))
    assert signal is not None
    assert signal.signal_type == "liquidity_sell"
    assert signal.confidence > 0


def test_neutral_low_volume():
    engine = LSTEngine(window_size=5)
    for _ in range(5):
        engine.compute(_rate(volume=1, tick_volume=10, spread=50))
    signal = engine.compute(_rate(volume=1, tick_volume=10, spread=50))
    if signal:
        assert signal.signal_type == "neutral"


def test_reset():
    engine = LSTEngine(window_size=3)
    engine.compute(_rate())
    engine.reset()
    assert len(engine._spreads) == 0
    assert len(engine._volumes) == 0


def test_metrics_bounds():
    engine = LSTEngine(window_size=5)
    for _ in range(5):
        engine.compute(_rate())
    signal = engine.compute(_rate())
    assert signal is not None
    m = signal.metrics
    assert 0 <= m.liquidity_score <= 1
    assert 0 <= m.microstructure_score <= 1
    assert -1 <= m.volume_imbalance <= 1
    assert -1 <= m.order_flow_pressure <= 1
    assert m.relative_spread >= 0
