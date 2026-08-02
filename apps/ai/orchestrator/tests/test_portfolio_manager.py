"""Tests for PortfolioManager."""
import pytest

from app.portfolio_manager import (
    OpenPosition,
    PortfolioConfig,
    PortfolioManager,
)


def test_initial_state():
    pm = PortfolioManager()
    stats = pm.stats()
    assert stats["drawdown"] == 0.0
    assert stats["open_positions"] == 0
    assert stats["equity_peak"] == 0.0


def test_update_equity_increases_peak():
    pm = PortfolioManager()
    pm.update_equity(10000)
    assert pm.state.equity_peak == 10000
    pm.update_equity(11000)
    assert pm.state.equity_peak == 11000


def test_current_drawdown():
    pm = PortfolioManager()
    pm.update_equity(10000)
    pm.update_equity(9500)
    assert pytest.approx(pm.current_drawdown(), 0.001) == 0.05
    pm.update_equity(11000)
    assert pm.state.equity_peak == 11000
    pm.update_equity(9900)
    assert pytest.approx(pm.current_drawdown(), 0.001) == pytest.approx(0.10, 0.001)


def test_can_open_new_within_limits():
    pm = PortfolioManager(PortfolioConfig(max_positions=3))
    pm.update_equity(10000)
    assert pm.can_open_new() is True


def test_cannot_open_when_max_positions():
    pm = PortfolioManager(PortfolioConfig(max_positions=2))
    pm.update_equity(10000)
    for i in range(2):
        pm.add_position(
            OpenPosition(symbol=f"SYM{i}", side="BUY", entry=1.0, sl=0.99, tp=1.02, lot=0.01, opened_at=0.0)
        )
    assert pm.can_open_new() is False


def test_cannot_open_when_max_drawdown():
    pm = PortfolioManager(PortfolioConfig(max_drawdown=0.10))
    pm.update_equity(10000)
    pm.update_equity(8900)
    assert pm.can_open_new() is False


def test_calculate_position_size_baseline():
    pm = PortfolioManager(
        PortfolioConfig(account_balance=10000, risk_per_trade=0.01)
    )
    pm.update_equity(10000)
    lot = pm.calculate_position_size("XAUUSD", entry=2000.0, sl=1995.0)
    assert lot > 0
    assert lot >= 0.01


def test_calculate_position_size_reduces_with_dd():
    pm_no_dd = PortfolioManager(PortfolioConfig(account_balance=10000, risk_per_trade=0.01))
    pm_no_dd.update_equity(10000)
    lot_no_dd = pm_no_dd.calculate_position_size("XAUUSD", entry=2000.0, sl=1995.0)

    pm_with_dd = PortfolioManager(PortfolioConfig(account_balance=10000, risk_per_trade=0.01))
    pm_with_dd.update_equity(10000)
    pm_with_dd.update_equity(9400)
    lot_with_dd = pm_with_dd.calculate_position_size("XAUUSD", entry=2000.0, sl=1995.0)

    assert lot_with_dd < lot_no_dd


def test_calculate_position_size_reduces_with_correlated_count():
    pm0 = PortfolioManager(PortfolioConfig(account_balance=100, risk_per_trade=0.01))
    pm0.update_equity(100)
    lot0 = pm0.calculate_position_size("EURUSD", entry=1.1000, sl=1.0500, correlation_count=0)

    pm2 = PortfolioManager(PortfolioConfig(account_balance=100, risk_per_trade=0.01))
    pm2.update_equity(100)
    lot2 = pm2.calculate_position_size("EURUSD", entry=1.1000, sl=1.0500, correlation_count=2)

    assert lot2 < lot0
    assert lot2 == pytest.approx(lot0 * 0.5, 0.01)


def test_calculate_position_size_min_lot():
    pm = PortfolioManager(PortfolioConfig(account_balance=1, risk_per_trade=0.001))
    pm.update_equity(1)
    lot = pm.calculate_position_size("XAUUSD", entry=2000.0, sl=1990.0)
    assert lot >= 0.01


def test_calculate_position_size_max_lot():
    pm = PortfolioManager(PortfolioConfig(account_balance=10**12, risk_per_trade=0.5))
    pm.update_equity(10**12)
    lot = pm.calculate_position_size("XAUUSD", entry=2000.0, sl=1999.0)
    assert lot <= 10.0


def test_remove_position():
    pm = PortfolioManager()
    pm.update_equity(10000)
    pm.add_position(
        OpenPosition(symbol="XAUUSD", side="BUY", entry=2000.0, sl=1995.0, tp=2010.0, lot=0.01, opened_at=0.0)
    )
    assert len(pm.state.open_positions) == 1
    pm.remove_position("XAUUSD")
    assert len(pm.state.open_positions) == 0