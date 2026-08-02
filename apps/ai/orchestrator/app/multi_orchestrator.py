"""
MultiSymbolOrchestrator — orquestador principal.

Responsabilidades:
1. Mantener un buffer de precios por símbolo/timeframe
2. Cuando llega una señal cruda del liquidity-engine (vía NATS):
   - Recalcular correlación entre todos los símbolos
   - Aplicar filtro de correlación (descartar opuestas, reforzar alineadas)
   - Calcular SL/TP dinámicos por ATR
   - Calcular lot size ajustado por portfolio (drawdown, posiciones abiertas)
   - Publicar SignalInput final en NATS trading.signal.validated
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional

from app.config import Settings
from app.correlation_engine import CorrelationEngine, FilteredSignal
from app.horizon_analyzer import (
    HorizonScore,
    SymbolBias,
    analyze_horizon,
    combine_horizons,
)
from app.macro_filter import check_macro_conditions
from app.models import LSTSignalIn, SignalInput
from app.nats_client import NATSClient
from app.portfolio_manager import (
    OpenPosition,
    PortfolioConfig,
    PortfolioManager,
)
from app.price_feed import PriceFeedClient
from app.risk_manager import OHLC, RiskManager

logger = logging.getLogger(__name__)

HORIZON_TIMEFRAMES = ("M5", "H1", "H4", "D1")


@dataclass
class _PendingSignal:
    """Acumulación de señales por símbolo en una ventana de tiempo."""
    action: str
    confidence: float
    received_at: float


class MultiSymbolOrchestrator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.nats = NATSClient(
            url=settings.nats_url,
            stream=settings.nats_stream,
            subject_in=settings.nats_subject_in,
            subject_out=settings.nats_subject_out,
        )
        self.price_feed = PriceFeedClient(settings.mt5_connector_url)

        self.correlation_engine = CorrelationEngine(
            lookback=settings.history_window,
            correlation_threshold=settings.correlation_threshold,
            coint_enabled=settings.coint_enabled,
        )
        self.portfolio = PortfolioManager(
            PortfolioConfig(
                account_balance=settings.account_balance,
                risk_per_trade=settings.risk_per_trade,
                max_drawdown=settings.max_drawdown,
                max_positions=settings.max_positions,
            )
        )
        self.risk_manager = RiskManager(
            atr_period=settings.atr_period,
            sl_atr_multiplier=settings.sl_atr_multiplier,
            tp_atr_multiplier=settings.tp_atr_multiplier,
        )

        self._price_buffer: Dict[str, Deque[float]] = defaultdict(
            lambda: deque(maxlen=settings.history_window)
        )
        self._candle_buffer: Dict[str, Deque[OHLC]] = defaultdict(
            lambda: deque(maxlen=settings.atr_period + 50)
        )
        self._pending_signals: Dict[str, _PendingSignal] = {}
        self._pending_window_seconds = max(60, settings.poll_interval_seconds * 2)

        self._published_signals: Deque[Dict] = deque(maxlen=200)
        self._paused = False

        self._last_health_emit = 0.0

    async def start(self) -> None:
        await self.nats.connect()
        await self.price_feed.start()
        await self._warmup_buffers()
        self.nats.set_control_callback(self._on_control)
        await self.nats.subscribe_control()
        await self.nats.subscribe_signals(self._on_lst_signal)

        asyncio.create_task(self._periodic_publish_task())
        asyncio.create_task(self._periodic_health_task())
        logger.info(
            "MultiSymbolOrchestrator started — symbols=%s, timeframes=%s",
            self.settings.symbols, self.settings.timeframes,
        )

    async def stop(self) -> None:
        await self.nats.close()
        await self.price_feed.close()

    async def _warmup_buffers(self) -> None:
        for symbol in self.settings.symbols:
            primary_tf = "H1"
            rates = await self.price_feed.get_rates(symbol, primary_tf, self.settings.history_window)
            for r in rates:
                self._price_buffer[symbol].append(float(r.get("close", 0.0)))
                self._candle_buffer[symbol].append(
                    OHLC(
                        open=float(r.get("open", 0.0)),
                        high=float(r.get("high", 0.0)),
                        low=float(r.get("low", 0.0)),
                        close=float(r.get("close", 0.0)),
                    )
                )
            logger.info("Warmed up %s with %d candles", symbol, len(rates))

    async def _on_control(self, action: str) -> None:
        if action == "pause":
            self._paused = True
            logger.warning("Orchestrator PAUSED — no signals will be processed")
        elif action == "resume":
            self._paused = False
            logger.warning("Orchestrator RESUMED — signal processing active")
        else:
            logger.warning("Unknown control action: %s", action)

    async def _on_lst_signal(self, sig: LSTSignalIn) -> None:
        """Callback cuando llega una señal cruda del liquidity-engine."""
        if self._paused:
            logger.info("Signal ignored — orchestrator is paused")
            return
        if sig.signal_type == "neutral":
            return
        if sig.confidence < 0.3:
            return

        action = "BUY" if sig.signal_type == "liquidity_buy" else "SELL"
        self._pending_signals[sig.symbol] = _PendingSignal(
            action=action,
            confidence=sig.confidence,
            received_at=time.time(),
        )
        logger.info(
            "Pending signal: %s %s conf=%.2f (will publish on next window)",
            sig.symbol, action, sig.confidence,
        )

    async def _periodic_publish_task(self) -> None:
        while True:
            try:
                await self._refresh_buffers()
                await self._evaluate_pending_signals()
            except Exception as e:
                logger.error("periodic_publish_task error: %s", e, exc_info=True)
            await asyncio.sleep(self.settings.poll_interval_seconds)

    async def _periodic_health_task(self) -> None:
        while True:
            try:
                self._refresh_account_state()
            except Exception as e:
                logger.warning("health task error: %s", e)
            await asyncio.sleep(30)

    async def _refresh_buffers(self) -> None:
        for symbol in self.settings.symbols:
            primary_tf = "H1"
            rates = await self.price_feed.get_rates(symbol, primary_tf, self.settings.history_window)
            if not rates:
                continue
            latest = rates[-1]
            self._price_buffer[symbol].append(float(latest.get("close", 0.0)))
            self._candle_buffer[symbol].append(
                OHLC(
                    open=float(latest.get("open", 0.0)),
                    high=float(latest.get("high", 0.0)),
                    low=float(latest.get("low", 0.0)),
                    close=float(latest.get("close", 0.0)),
                )
            )

    def _refresh_account_state(self) -> None:
        for sym in list(self._pending_signals.keys()):
            ps = self._pending_signals[sym]
            if time.time() - ps.received_at > self._pending_window_seconds:
                logger.info("Dropping stale pending signal for %s", sym)
                del self._pending_signals[sym]
    async def _evaluate_pending_signals(self) -> None:
        if not self._pending_signals:
            return

        if not self.portfolio.can_open_new():
            logger.warning("Skipping evaluation: portfolio cannot open new positions")
            self._pending_signals.clear()
            return

        raw_signals: Dict[str, Dict] = {}
        for sym, ps in self._pending_signals.items():
            raw_signals[sym] = {
                "action": ps.action,
                "confidence": ps.confidence,
                "price": self._price_buffer[sym][-1] if self._price_buffer[sym] else 0.0,
            }

        prices = {sym: list(buf) for sym, buf in self._price_buffer.items()}
        filtered = self.correlation_engine.filter_signals(raw_signals, prices)

        for sym, fs in filtered.items():
            if fs.filtered_out:
                logger.info("Skipping %s — filtered out: %s", sym, fs.reasons)
                self._published_signals.appendleft(
                    {
                        "symbol": sym,
                        "action": fs.action,
                        "confidence": fs.confidence,
                        "adjusted_confidence": fs.adjusted_confidence,
                        "lot_multiplier": fs.lot_multiplier,
                        "filtered_out": True,
                        "reasons": fs.reasons,
                        "published_at": time.time(),
                    }
                )
                continue

            if fs.action == "NEUTRAL":
                continue
            await self._publish_final_signal(sym, fs)

        self._pending_signals.clear()

    async def _publish_final_signal(self, symbol: str, fs: FilteredSignal) -> None:
        candles = list(self._candle_buffer[symbol])
        if len(candles) < 5:
            logger.warning("Not enough candles for %s — skipping", symbol)
            return

        entry_price = self._price_buffer[symbol][-1] if self._price_buffer[symbol] else 0.0
        sltp = self.risk_manager.calculate_sl_tp(candles, fs.action, entry_price)

        corr_count = self._count_correlated_positions(symbol)
        base_lot = self.portfolio.calculate_position_size(
            symbol=symbol,
            entry=entry_price,
            sl=sltp.sl,
            correlation_count=corr_count,
        )
        final_lot = round(base_lot * fs.lot_multiplier, 2)
        final_lot = max(0.01, min(final_lot, 10.0))

        # F5: Analisis multi-horizonte (M5, H1, H4, D1)
        horizon_scores = await self._build_horizon_scores(symbol, fs.action)

        # F5: Macro filter (eventos alto impacto, TGA/RRP)
        macro = await check_macro_conditions()
        macro_conf_mult = float(macro.get("confidence_multiplier", 1.0))
        macro_lot_mult = float(macro.get("lot_multiplier", 1.0))

        adjusted_conf = round(fs.adjusted_confidence * macro_conf_mult, 4)
        final_lot_adjusted = round(final_lot * macro_lot_mult, 2)
        final_lot_adjusted = max(0.01, min(final_lot_adjusted, 10.0))

        signal = SignalInput(
            id=str(uuid.uuid4()),
            tenant_id=self.settings.tenant_id,
            source="orchestrator-multi",
            symbol=symbol,
            action=fs.action,
            entry_price=None,
            stop_loss=round(sltp.sl, 5),
            take_profits=[round(sltp.tp, 5)],
            lot_size=final_lot_adjusted,
            lot_mode="fixed",
            confidence=adjusted_conf,
            recommended_lot_size=final_lot_adjusted,
            hash=f"orch:{symbol}:{fs.action}:{int(time.time())}",
        )

        await self.nats.publish_signal(signal)

        # Construir payload publicado con info multi-horizonte + macro
        sb = combine_horizons(symbol, horizon_scores)
        published_payload = {
            "id": signal.id,
            "symbol": signal.symbol,
            "action": signal.action,
            "lot_size": signal.lot_size,
            "stop_loss": signal.stop_loss,
            "take_profits": signal.take_profits,
            "confidence": signal.confidence,
            "source": signal.source,
            "reasons": fs.reasons,
            "atr": sltp.atr,
            "rr_ratio": sltp.rr_ratio,
            "correlation_count": corr_count,
            "lot_multiplier": fs.lot_multiplier,
            "filtered_out": fs.filtered_out,
            # F5 enhancements
            "bias": sb.master_bias,
            "master_score": round(sb.master_score, 1),
            "horizon_scores": {tf: h.to_dict() for tf, h in horizon_scores.items()},
            "macro_risk_off": bool(macro.get("risk_off", False)),
            "macro_reasons": macro.get("reasons", []),
            "macro_confidence_multiplier": macro_conf_mult,
            "macro_lot_multiplier": macro_lot_mult,
            "published_at": time.time(),
        }
        self._published_signals.appendleft(published_payload)

        self.portfolio.add_position(
            OpenPosition(
                symbol=symbol,
                side=fs.action,
                entry=entry_price,
                sl=sltp.sl,
                tp=sltp.tp,
                lot=final_lot_adjusted,
                opened_at=time.time(),
            )
        )

        logger.info(
            "Final signal: %s %s lot=%.2f conf=%.2f bias=%s score=%.1f "
            "macro_risk_off=%s reasons=%s",
            symbol, fs.action, final_lot_adjusted, adjusted_conf,
            sb.master_bias, sb.master_score, macro.get("risk_off", False), fs.reasons,
        )

    async def _build_horizon_scores(
        self, symbol: str, action: str
    ) -> Dict[str, HorizonScore]:
        """Calcula HorizonScore por timeframe para un simbolo.

        Usa las candles ya en _candle_buffer (H1) como base. Para M5/H4/D1
        intenta fetch del price_feed. Si falla, devuelve dict con un solo
        horizonte (H1) para no bloquear el pipeline.
        """
        scores: Dict[str, HorizonScore] = {}

        for tf in HORIZON_TIMEFRAMES:
            try:
                if tf == "H1":
                    candles = [
                        {"open": c.open, "high": c.high, "low": c.low, "close": c.close}
                        for c in self._candle_buffer[symbol]
                    ]
                else:
                    rates = await self.price_feed.get_rates(symbol, tf, 100)
                    candles = [
                        {
                            "open": float(r.get("open", 0.0)),
                            "high": float(r.get("high", 0.0)),
                            "low": float(r.get("low", 0.0)),
                            "close": float(r.get("close", 0.0)),
                        }
                        for r in rates
                    ]
                if candles:
                    scores[tf] = analyze_horizon(candles, tf)
            except Exception as e:
                logger.debug(f"horizon_analyzer {symbol} {tf} failed: {e}")

        if not scores:
            scores["H1"] = analyze_horizon(
                [
                    {"open": c.open, "high": c.high, "low": c.low, "close": c.close}
                    for c in self._candle_buffer[symbol]
                ],
                "H1",
            )
        return scores

    def _count_correlated_positions(self, symbol: str) -> int:
        if not self._price_buffer.get(symbol) or len(self._price_buffer[symbol]) < 10:
            return 0
        count = 0
        prices_sym = list(self._price_buffer[symbol])
        for pos in self.portfolio.state.open_positions:
            if pos.symbol == symbol:
                continue
            other_prices = self._price_buffer.get(pos.symbol)
            if not other_prices or len(other_prices) < 10:
                continue
            corr = abs(self.correlation_engine.compute_correlation(prices_sym, list(other_prices)))
            if corr > self.settings.correlation_threshold:
                count += 1
        return count

    def stats(self) -> Dict:
        return {
            "paused": self._paused,
            "pending_signals": len(self._pending_signals),
            "buffer_sizes": {k: len(v) for k, v in self._price_buffer.items()},
            "published_signals_buffer": len(self._published_signals),
            "portfolio": self.portfolio.stats(),
        }

    def published_signals(self, limit: int = 50, symbol: str | None = None) -> list[Dict]:
        items = list(self._published_signals)
        if symbol:
            items = [s for s in items if s.get("symbol") == symbol]
        return items[:limit]