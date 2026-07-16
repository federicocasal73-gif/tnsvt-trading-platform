"""Shared service dependencies: Postgres, Redis, NATS, Ollama client, scorer."""
from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import nats
import nats.js
import redis.asyncio as redis_async
import structlog

from services.config import Settings
from services.ollama_client import OllamaClient
from services.scorer import SignalScorer

log = structlog.get_logger("ai-core.deps")


class Dependencies:
    """Container for shared resources; instantiated once per process."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.redis: redis_async.Redis | None = None
        self.nats_conn: nats.NATS | None = None
        self.nats_js: nats.js.JetStreamContext | None = None
        self.nats_sub_task: asyncio.Task | None = None
        self.ollama = OllamaClient(settings)
        self.scorer = SignalScorer(settings, self.ollama)
        self._stop = asyncio.Event()

    async def connect(self) -> None:
        # ─── Redis ─────────────────────────────────────────────────────────────
        try:
            self.redis = redis_async.from_url(
                self.settings.redis_url(),
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            await self.redis.ping()
            log.info("deps.redis_connected", url=self.settings.redis_url())
        except Exception as e:
            log.warning("deps.redis_unavailable", error=str(e))
            self.redis = None

        # ─── Postgres ──────────────────────────────────────────────────────────
        try:
            import asyncpg

            self.pg_pool = await asyncpg.create_pool(
                dsn=self.settings.postgres_dsn(),
                min_size=2,
                max_size=10,
                command_timeout=10,
            )
            async with self.pg_pool.acquire() as conn:
                await conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{self.settings.postgres_schema}"')
                await self._ensure_tables(conn)
            log.info("deps.postgres_connected", dsn=self.settings.postgres_dsn())
        except Exception as e:
            log.warning("deps.postgres_unavailable", error=str(e))
            self.pg_pool = None

        # ─── NATS ──────────────────────────────────────────────────────────────
        try:
            self.nats_conn = await asyncio.wait_for(
                nats.connect(self.settings.nats_url, connect_timeout=5, max_reconnect_attempts=3),
                timeout=10,
            )
            self.nats_js = self.nats_conn.jetstream()
            await self._ensure_stream()
            log.info("deps.nats_connected", url=self.settings.nats_url)
        except Exception as e:
            log.warning("deps.nats_unavailable", error=str(e))
            self.nats_conn = None
            self.nats_js = None

    async def _ensure_stream(self) -> None:
        if not self.nats_js:
            return
        try:
            await self.nats_js.add_stream(
                name=self.settings.nats_stream,
                subjects=["trading.signal.>"],
            )
        except Exception as e:
            if "already in use" not in str(e).lower() and "exists" not in str(e).lower():
                raise

    async def _ensure_tables(self, conn) -> None:
        await conn.execute(
            f'''
            CREATE TABLE IF NOT EXISTS "{self.settings.postgres_schema}".scored_signals (
                id              UUID PRIMARY KEY,
                source_signal_id UUID NOT NULL,
                tenant_id       UUID NOT NULL,
                symbol          TEXT NOT NULL,
                action          TEXT NOT NULL,
                score           DOUBLE PRECISION NOT NULL,
                confidence      DOUBLE PRECISION NOT NULL,
                decision        TEXT NOT NULL,
                llm_summary     TEXT,
                features        JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                model_version   TEXT NOT NULL,
                scored_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            '''
        )
        await conn.execute(
            f'CREATE INDEX IF NOT EXISTS idx_scored_tenant_time ON "{self.settings.postgres_schema}".scored_signals (tenant_id, scored_at DESC);'
        )
        await conn.execute(
            f'CREATE INDEX IF NOT EXISTS idx_scored_source ON "{self.settings.postgres_schema}".scored_signals (source_signal_id);'
        )

    async def start_subscriber(self) -> None:
        if not self.nats_js:
            log.warning("deps.skip_subscriber_no_nats")
            return
        self.nats_sub_task = asyncio.create_task(self._consume_loop(), name="nats-subscriber")

    async def _consume_loop(self) -> None:
        assert self.nats_js
        sub = await self.nats_js.pull_subscribe(
            subject=self.settings.nats_subject_in,
            durable=self.settings.nats_consumer,
            stream=self.settings.nats_stream,
        )
        log.info("deps.subscriber_started", subject=self.settings.nats_subject_in)

        while not self._stop.is_set():
            try:
                msgs = await sub.fetch(batch=10, timeout=2)
                for msg in msgs:
                    try:
                        payload = json.loads(msg.data.decode("utf-8"))
                        scored = await self.scorer.score(payload)
                        await self._publish(scored)
                        await self._persist(scored, payload)
                        await msg.ack()
                    except Exception as e:
                        log.error("deps.consume_error", error=str(e))
                        await msg.nak()
            except nats.errors.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("deps.consume_loop_error", error=str(e))
                await asyncio.sleep(2)

    async def _publish(self, scored: dict[str, Any]) -> None:
        if not self.nats_js:
            return
        try:
            await self.nats_js.publish(
                self.settings.nats_subject_out,
                json.dumps(scored, default=str).encode("utf-8"),
            )
        except Exception as e:
            log.error("deps.publish_failed", error=str(e))

    async def _persist(self, scored: dict[str, Any], source: dict[str, Any]) -> None:
        if not getattr(self, "pg_pool", None):
            return
        try:
            async with self.pg_pool.acquire() as conn:
                await conn.execute(
                    f'''
                    INSERT INTO "{self.settings.postgres_schema}".scored_signals
                        (id, source_signal_id, tenant_id, symbol, action, score, confidence, decision, llm_summary, features, model_version)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11)
                    ON CONFLICT (id) DO NOTHING
                    ''',
                    scored["id"],
                    source.get("id"),
                    source.get("tenant_id", "00000000-0000-0000-0000-000000000000"),
                    scored["symbol"],
                    scored["action"],
                    scored["score"],
                    scored["confidence"],
                    scored["decision"],
                    scored.get("llm_summary"),
                    json.dumps(scored.get("features", {})),
                    scored.get("model_version", "unknown"),
                )
        except Exception as e:
            log.error("deps.persist_failed", error=str(e))

    async def close(self) -> None:
        self._stop.set()
        if self.nats_sub_task:
            self.nats_sub_task.cancel()
            try:
                await self.nats_sub_task
            except (asyncio.CancelledError, Exception):
                pass
        if self.nats_conn:
            await self.nats_conn.drain()
        if self.redis:
            await self.redis.aclose()
        if getattr(self, "pg_pool", None):
            await self.pg_pool.close()
        await self.ollama.close()