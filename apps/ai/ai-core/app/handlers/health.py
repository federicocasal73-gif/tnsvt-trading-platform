"""Health and metrics endpoints."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest

from services.dependencies import Dependencies

REQUEST_COUNT = Counter("ai_core_requests_total", "HTTP requests", ["method", "path", "status"])
SCORING_DURATION = Gauge("ai_core_last_scoring_seconds", "Last scoring duration")


def HealthRouter(deps: Dependencies) -> APIRouter:
    r = APIRouter(tags=["health"])

    @r.get("/health")
    async def health():
        return {
            "status": "ok",
            "service": "ai-core",
            "version": "0.1.0",
            "dependencies": await _check(deps),
        }

    @r.get("/health/live")
    async def live():
        return {"status": "alive"}

    @r.get("/health/ready")
    async def ready():
        deps_status = await _check(deps)
        ready_ok = deps_status["redis"] and deps_status["nats"]
        return Response(
            content='{"status":"ready"}' if ready_ok else '{"status":"degraded"}',
            media_type="application/json",
            status_code=200 if ready_ok else 503,
        )

    @r.get("/metrics")
    async def metrics():
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return r


async def _check(deps: Dependencies) -> dict[str, bool]:
    redis_ok = False
    nats_ok = False
    pg_ok = False
    ollama_ok = False

    if deps.redis:
        try:
            redis_ok = await asyncio.wait_for(deps.redis.ping(), timeout=2)
        except Exception:
            redis_ok = False

    if deps.nats_conn:
        nats_ok = deps.nats_conn.is_connected

    if getattr(deps, "pg_pool", None):
        try:
            async with deps.pg_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            pg_ok = True
        except Exception:
            pg_ok = False

    ollama_ok = await deps.ollama.ping()

    return {"redis": redis_ok, "nats": nats_ok, "postgres": pg_ok, "ollama": ollama_ok}