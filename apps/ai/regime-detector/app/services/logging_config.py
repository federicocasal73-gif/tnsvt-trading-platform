"""Pydantic-compatible logging setup (JSON in prod, console in dev)."""
from __future__ import annotations

import logging
import os

import structlog


def configure_logging(service: str, level: str = "INFO") -> structlog.stdlib.BoundLogger:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(message)s",
    )
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
    return structlog.get_logger(service)