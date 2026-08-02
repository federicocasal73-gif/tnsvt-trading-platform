"""
Portfolio Manager para el Multi-Symbol Orchestrator.

Responsabilidades:
- Position sizing ajustado por drawdown actual
- Reducción de lot cuando hay múltiples posiciones correlacionadas
- Tracking de equity peak y drawdown
- Límites globales (max DD, max posiciones abiertas)
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PortfolioConfig:
    account_balance: float = 10000.0
    risk_per_trade: float = 0.01
    max_drawdown: float = 0.15
    max_positions: int = 3
    correlation_threshold: float = 0.7
    dd_reduce_threshold: float = 0.05
    dd_reduce_factor: float = 0.7
    dd_critical_threshold: float = 0.10
    dd_critical_factor: float = 0.5
    pos_reduce_threshold: int = 2
    pos_reduce_factor: float = 0.8
    pos_critical_threshold: int = 3
    pos_critical_factor: float = 0.5


@dataclass
class OpenPosition:
    symbol: str
    side: str
    entry: float
    sl: float
    tp: float
    lot: float
    opened_at: float


@dataclass
class PortfolioState:
    equity_peak: float = 0.0
    current_equity: float = 0.0
    open_positions: List[OpenPosition] = field(default_factory=list)


class PortfolioManager:
    def __init__(self, config: PortfolioConfig | None = None) -> None:
        self.config = config or PortfolioConfig()
        self.state = PortfolioState()

    def update_equity(self, current_equity: float) -> float:
        self.state.current_equity = current_equity
        if current_equity > self.state.equity_peak:
            self.state.equity_peak = current_equity
        return self.current_drawdown()

    def current_drawdown(self) -> float:
        if self.state.equity_peak <= 0:
            return 0.0
        dd = (self.state.equity_peak - self.state.current_equity) / self.state.equity_peak
        return max(0.0, dd)

    def add_position(self, pos: OpenPosition) -> None:
        self.state.open_positions.append(pos)

    def remove_position(self, symbol: str) -> None:
        self.state.open_positions = [p for p in self.state.open_positions if p.symbol != symbol]

    def can_open_new(self) -> bool:
        if len(self.state.open_positions) >= self.config.max_positions:
            logger.warning("max positions reached (%d)", self.config.max_positions)
            return False
        if self.current_drawdown() >= self.config.max_drawdown:
            logger.warning("max drawdown reached (%.2f%%)", self.current_drawdown() * 100)
            return False
        return True

    def calculate_position_size(
        self,
        symbol: str,
        entry: float,
        sl: float,
        correlation_count: int = 0,
    ) -> float:
        """
        Calcula lot size ajustado por:
        - Riesgo base (1% del equity)
        - Drawdown actual (reduce si DD > 5%)
        - Número de posiciones abiertas (reduce si > 2)
        - Correlación con otras posiciones (reduce si high correlation)
        """
        equity = self.state.current_equity or self.config.account_balance
        base_risk_amount = equity * self.config.risk_per_trade

        sl_distance = abs(entry - sl)
        if sl_distance <= 0:
            logger.warning("SL distance is zero for %s, using minimum lot", symbol)
            return 0.01

        dd = self.current_drawdown()
        dd_factor = 1.0
        if dd > self.config.dd_critical_threshold:
            dd_factor = self.config.dd_critical_factor
        elif dd > self.config.dd_reduce_threshold:
            dd_factor = self.config.dd_reduce_factor

        pos_count = len(self.state.open_positions)
        pos_factor = 1.0
        if pos_count >= self.config.pos_critical_threshold:
            pos_factor = self.config.pos_critical_factor
        elif pos_count >= self.config.pos_reduce_threshold:
            pos_factor = self.config.pos_reduce_factor

        corr_factor = 1.0
        if correlation_count >= 2:
            corr_factor = 0.5
        elif correlation_count == 1:
            corr_factor = 0.75

        risk_amount = base_risk_amount * dd_factor * pos_factor * corr_factor

        pip_value = self._pip_value(symbol, entry)
        if pip_value <= 0:
            return 0.01

        lot_size = risk_amount / (sl_distance * pip_value)

        lot_size = max(0.01, min(lot_size, 10.0))
        return round(lot_size, 2)

    @staticmethod
    def _pip_value(symbol: str, price: float) -> float:
        """
        Valor de 1 pip por lote estándar (100k).
        Aproximación simplificada para los símbolos principales.
        """
        sym = symbol.upper().replace("/", "").replace(".PRO", "").replace(".M", "")
        if sym.endswith("USD"):
            base, quote = sym[:-3], "USD"
        elif sym.startswith("USD"):
            base, quote = "USD", sym[3:]
        else:
            return 10.0

        if quote == "USD":
            return 10.0
        if base == "USD":
            return 10.0 / price if price > 0 else 10.0
        return 10.0

    def stats(self) -> Dict:
        return {
            "equity_peak": self.state.equity_peak,
            "current_equity": self.state.current_equity,
            "drawdown": self.current_drawdown(),
            "open_positions": len(self.state.open_positions),
            "max_drawdown_limit": self.config.max_drawdown,
            "max_positions_limit": self.config.max_positions,
        }