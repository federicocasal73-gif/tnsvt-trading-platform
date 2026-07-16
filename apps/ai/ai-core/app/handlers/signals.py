"""Read endpoints for scored-signal history."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from services.dependencies import Dependencies


def SignalsRouter(deps: Dependencies) -> APIRouter:
    r = APIRouter(prefix="/signals", tags=["signals"])

    @r.get("/scored")
    async def list_scored(
        limit: int = Query(default=50, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
        symbol: str | None = Query(default=None),
    ):
        if not getattr(deps, "pg_pool", None):
            raise HTTPException(status_code=503, detail="PostgreSQL unavailable")
        sql = f'''
            SELECT id, source_signal_id, tenant_id, symbol, action, score,
                   confidence, decision, llm_summary, model_version, scored_at
              FROM "{deps.settings.postgres_schema}".scored_signals
        '''
        params: list = []
        where: list[str] = []
        if symbol:
            where.append("symbol = $" + str(len(params) + 1))
            params.append(symbol.upper())
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY scored_at DESC LIMIT $" + str(len(params) + 1) + " OFFSET $" + str(len(params) + 2)
        params.extend([limit, offset])

        try:
            async with deps.pg_pool.acquire() as conn:
                rows = await conn.fetch(sql, *params)
                total = await conn.fetchval(f'SELECT COUNT(*) FROM "{deps.settings.postgres_schema}".scored_signals')
            return {
                "total": total,
                "limit": limit,
                "offset": offset,
                "items": [_row_to_dict(r) for r in rows],
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return r


def _row_to_dict(row) -> dict:
    return {
        "id": str(row["id"]),
        "source_signal_id": str(row["source_signal_id"]) if row["source_signal_id"] else None,
        "tenant_id": str(row["tenant_id"]),
        "symbol": row["symbol"],
        "action": row["action"],
        "score": row["score"],
        "confidence": row["confidence"],
        "decision": row["decision"],
        "llm_summary": row["llm_summary"],
        "model_version": row["model_version"],
        "scored_at": row["scored_at"].isoformat() if isinstance(row["scored_at"], datetime) else row["scored_at"],
    }