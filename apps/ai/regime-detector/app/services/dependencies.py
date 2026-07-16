"""Shared dependencies: Postgres, Redis, NATS, classifier, OHLC aggregator."""
from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import asyncpg
import nats
import nats.js
import redis.asyncio as redis_async
import structlog

from app.indicators.classifier import RegimeClassifier, RegimeSignal
from app.services.config import Settings

log = structlog.get_logger("regime-detector.deps")


# ─── OHLC bar aggregator ────────────────────────────────────────────────
# price-feed publishes ticks (bid/ask/last). We aggregate them into
# 1-minute OHLC bars per symbol, since regime detection needs OHLC.
# We keep at most `max_bars` per symbol in memory.

@dataclass
class Bar:
    symbol: str
    open_time: int  # minute epoch
    open: float = 0.0
    high: float = float("-inf")
    low: float = float("inf")
    close: float = 0.0
    n: int = 0

    def update(self, price: float):
        if self.n == 0:
            self.open = price
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price
        self.n += 1


class OhlcAggregator:
    def __init__(self, max_bars: int = 240):
        self.bars: dict[str, list[Bar]] = defaultdict(list)
        self.max_bars = max_bars

    @staticmethod
    def _minute(dt: datetime) -> int:
        return int(dt.replace(second=0, microsecond=0).timestamp())

    def feed(self, symbol: str, price: float, when: datetime | None = None) -> list[float]:
        """Returns the latest OHLC array if a bar just closed, else []."""
        when = when or datetime.now(timezone.utc)
        minute = self._minute(when)
        bars = self.bars[symbol]
        current = bars[-1] if bars else None
        if current is None or current.open_time != minute:
            if current is not None and current.n > 0:
                # The previous bar just closed
                closed_ohlc = [current.open, current.high, current.low, current.close]
                bars.append(Bar(symbol, minute, price, price, price, price, 1))
                if len(bars) > self.max_bars:
                    bars.pop(0)
                return closed_ohlc
            else:
                bars.append(Bar(symbol, minute, price, price, price, price, 1))
                return []
        else:
            current.update(price)
            return []

    def history(self, symbol: str, n: int = 200) -> tuple[list[float], list[float], list[float]]:
        bars = self.bars.get(symbol, [])
        if not bars:
            return [], [], []
        closes = [b.close for b in bars[-n:]]
        highs = [b.high for b in bars[-n:]]
        lows = [b.low for b in bars[-n:]]
        return highs, lows, closes


# ─── Dependencies container ─────────────────────────────────────────────

class Dependencies:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.redis: redis_async.Redis | None = None
        self.pg_pool: asyncpg.Pool | None = None
        self.nats_conn: nats.NATS | None = None
        self.nats_js: nats.js.JetStreamContext | None = None
        self.classifier = RegimeClassifier(
            min_dwell_updates=settings.min_dwell_updates,
            transition_threshold=settings.transition_threshold,
        )
        self.ohlc = OhlcAggregator()
        self._last_regime: dict[str, str] = {}
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task] = []

    async def connect(self) -> None:
        # Redis (optional)
        try:
            self.redis = redis_async.from_url(
                self.settings.redis_url(),
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
            await self.redis.ping()
            log.info("deps.redis_connected", url=self.settings.redis_url())
        except Exception as e:
            log.warning("deps.redis_unavailable", error=str(e))
            self.redis = None

        # Postgres
        try:
            self.pg_pool = await asyncpg.create_pool(
                dsn=self.settings.postgres_dsn(),
                min_size=2, max_size=8, command_timeout=10,
            )
            await self._ensure_table()
            log.info("deps.postgres_connected", dsn=self.settings.postgres_dsn())
        except Exception as e:
            log.warning("deps.postgres_unavailable", error=str(e))
            self.pg_pool = None

        # NATS
        try:
            self.nats_conn = await nats.connect(self.settings.nats_url, connect_timeout=5, max_reconnect_attempts=3)
            self.nats_js = self.nats_conn.jetstream()
            # Subscribe to ALL tick subjects using a wildcard stream
            await self._ensure_stream()
            log.info("deps.nats_connected", url=self.settings.nats_url)
        except Exception as e:
            log.warning("deps.nats_unavailable", error=str(e))
            self.nats_conn = None
            self.nats_js = None

    async def _ensure_table(self) -> None:
        assert self.pg_pool is not None
        async with self.pg_pool.acquire() as conn:
            await conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{self.settings.postgres_schema}"')
            await conn.execute(
                f'''
                CREATE TABLE IF NOT EXISTS "{self.settings.postgres_schema}".market_regime (
                    id            BIGSERIAL PRIMARY KEY,
                    symbol        TEXT NOT NULL,
                    regime        TEXT NOT NULL,
                    confidence    DOUBLE PRECISION NOT NULL,
                    garch_sigma   DOUBLE PRECISION,
                    adx_value     DOUBLE PRECISION,
                    atr_pct       DOUBLE PRECISION,
                    bb_width      DOUBLE PRECISION,
                    sub_scores    JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    detected_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    valid_until   TIMESTAMPTZ
                );
                '''
            )
            await conn.execute(
                f'CREATE INDEX IF NOT EXISTS idx_regime_symbol_time ON "{self.settings.postgres_schema}".market_regime (symbol, detected_at DESC);'
            )

    async def _ensure_stream(self) -> None:
        assert self.nats_js is not None
        try:
            await self.nats_js.add_stream(
                name=self.settings.nats_stream,
                subjects=["marketdata.>", "ai.regime.>"],
            )
        except Exception as e:
            if "already" not in str(e).lower():
                raise

    async def start_subscriber(self) -> None:
        if not self.nats_js:
            log.warning("deps.skip_subscriber_no_nats")
            return
        self._tasks.append(asyncio.create_task(self._consume_ticks(), name="nats-subscriber"))
        self._tasks.append(asyncio.create_task(self._classify_loop(), name="classify-loop"))

    async def _consume_ticks(self) -> None:
        assert self.nats_js is not None
        sub = await self.nats_js.pull_subscribe(
            subject=self.settings.nats_subject_in,
            durable=self.settings.nats_consumer,
            stream=self.settings.nats_stream,
        )
        log.info("deps.subscriber_started", subject=self.settings.nats_subject_in)

        while not self._stop.is_set():
            try:
                msgs = await sub.fetch(batch=20, timeout=2)
                for msg in msgs:
                    try:
                        payload = json.loads(msg.data.decode("utf-8"))
                        sym = payload.get("symbol")
                        price = float(payload.get("last") or payload.get("ask") or payload.get("bid") or 0.0)
                        if not sym or price <= 0:
                            await msg.ack()
                            continue
                        # Use bid/ask/last for high/low approximation
                        bid = float(payload.get("bid") or price)
                        ask = float(payload.get("ask") or price)
                        # We don't have a true high/low per tick; use max(ask, bid, last)
                        # as a cheap approximation. Real OHLC will come from the
                        # aggregator at the bar level.
                        high = max(ask, bid, price)
                        low = min(ask, bid, price)
                        # Feed the OHLC aggregator (used to compute history)
                        self.ohlc.feed(sym, price)
                        # Feed the classifier directly with per-tick high/low proxy
                        self.classifier.feed(sym, price, high, low)
                        await msg.ack()
                    except Exception as e:
                        log.error("deps.tick_error", error=str(e))
                        await msg.nak()
            except nats.errors.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("deps.consume_loop_error", error=str(e))
                await asyncio.sleep(2)

    async def _classify_loop(self) -> None:
        """Periodically classify all symbols and publish regime changes."""
        interval = self.settings.classify_interval_sec
        while not self._stop.is_set():
            try:
                await asyncio.sleep(interval)
                for sym in list(self.classifier.states.keys()):
                    sig = self.classifier.classify(sym)
                    if sig is None:
                        continue
                    last = self._last_regime.get(sym)
                    if self.settings.publish_on_change_only and last == sig.regime:
                        continue
                    self._last_regime[sym] = sig.regime
                    await self._publish(sig)
                    await self._persist(sig)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("deps.classify_error", error=str(e))

    async def _publish(self, sig: RegimeSignal) -> None:
        if not self.nats_js:
            return
        try:
            subject = f"ai.regime.{sig.symbol}"
            await self.nats_js.publish(subject, json.dumps(sig.to_dict(), default=str).encode("utf-8"))
        except Exception as e:
            log.error("deps.publish_failed", error=str(e))

    async def _persist(self, sig: RegimeSignal) -> None:
        if not self.pg_pool:
            return
        try:
            async with self.pg_pool.acquire() as conn:
                await conn.execute(
                    f'''
                    INSERT INTO "{self.settings.postgres_schema}".market_regime
                        (symbol, regime, confidence, garch_sigma, adx_value, atr_pct, bb_width, sub_scores, valid_until)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9)
                    ''',
                    sig.symbol, sig.regime, sig.confidence,
                    sig.garch_sigma, sig.adx_value, sig.atr_pct, sig.bb_width,
                    json.dumps(sig.sub_scores), sig.valid_until,
                )
        except Exception as e:
            log.error("deps.persist_failed", error=str(e))

    async def close(self) -> None:
        self._stop.set()
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        if self.nats_conn:
            await self.nats_conn.drain()
        if self.redis:
            await self.redis.aclose()
        if self.pg_pool:
            await self.pg_pool.close()