"""TNSVT V2 — AI Core Service.

Signal scoring engine: takes raw trading signals, enriches them with technical
features, queries Ollama LLM for qualitative analysis, and publishes a
calibrated score (0-100) back to NATS.

Endpoints:
    GET    /health                  # Liveness + dependency status
    GET    /health/live             # Liveness only
    GET    /health/ready            # Readiness (Redis + NATS reachable)
    GET    /metrics                 # Prometheus metrics
    POST   /api/v1/score            # Score a single signal (sync)
    POST   /api/v1/score/batch      # Score up to 100 signals
    GET    /api/v1/signals/scored   # List recent scored signals (paginated)
    GET    /api/v1/registry         # List tracked signals with scores

NATS:
    consume  trading.signal.received  -> publish trading.signal.scored
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from handlers.health import HealthRouter
from handlers.scoring import ScoringRouter
from handlers.signals import SignalsRouter
from services.config import Settings
from services.dependencies import Dependencies

# ─── Logging ────────────────────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.dev.ConsoleRenderer() if os.getenv("LOG_FORMAT", "json") == "console" else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    cache_logger_on_first_use=True,
)
log = structlog.get_logger("ai-core")

settings = Settings()
deps = Dependencies(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("ai-core.starting", port=settings.port, env=settings.env, ollama_model=settings.ollama_model)

    await deps.connect()
    await deps.start_subscriber()

    try:
        yield
    finally:
        log.info("ai-core.shutting_down")
        await deps.close()


app = FastAPI(
    title="TNSVT AI Core",
    version="0.1.0",
    description="Signal scoring + qualitative LLM analysis for TNSVT V2",
    lifespan=lifespan,
)

# ─── Routers ────────────────────────────────────────────────────────────────
app.include_router(HealthRouter(deps))
app.include_router(ScoringRouter(deps), prefix="/api/v1")
app.include_router(SignalsRouter(deps), prefix="/api/v1")


def handle_signal(*_):
    log.info("ai-core.shutdown_signal")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)