"""Signal scoring HTTP endpoints."""
from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.dependencies import Dependencies


class RawSignal(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    action: str = Field(..., pattern="^(?i)(buy|sell)$")
    entry_price: float = Field(..., gt=0)
    stop_loss: float = Field(0.0, ge=0)
    take_profit: float = Field(0.0, ge=0)
    lot_size: float = Field(0.01, gt=0)
    confidence: float | None = Field(None, ge=0, le=100)
    source: str | None = Field(None, max_length=50)
    tenant_id: str | None = Field(None)
    id: str | None = None


class BatchScoringRequest(BaseModel):
    signals: list[RawSignal] = Field(..., min_length=1, max_length=100)


def ScoringRouter(deps: Dependencies) -> APIRouter:
    r = APIRouter(prefix="/score", tags=["scoring"])

    @r.post("")
    async def score_signal(signal: RawSignal):
        start = time.monotonic()
        try:
            result = await deps.scorer.score(signal.model_dump())
            elapsed = time.monotonic() - start
            result["scoring_ms"] = round(elapsed * 1000, 2)
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @r.post("/batch")
    async def score_batch(body: BatchScoringRequest):
        start = time.monotonic()
        results = await asyncio.gather(
            *[deps.scorer.score(s.model_dump()) for s in body.signals],
            return_exceptions=True,
        )
        elapsed = (time.monotonic() - start) * 1000
        return {
            "count": len(results),
            "elapsed_ms": round(elapsed, 2),
            "results": [r if not isinstance(r, Exception) else {"error": str(r)} for r in results],
        }

    return r


import asyncio  # noqa: E402