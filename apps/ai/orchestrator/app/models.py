"""
Models para el orchestrator.

SignalInput: formato compatible con execution-engine (apps/trading/execution-engine/internal/models).
LSTSignalIn: signal cruda que llega del liquidity-engine vía NATS.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class LSTSignalIn(BaseModel):
    """Signal cruda recibida del liquidity-engine vía NATS subject tnsvt.lst.signal."""
    symbol: str
    timestamp: datetime
    timeframe: str
    signal_type: str = Field(..., pattern="^(liquidity_buy|liquidity_sell|neutral)$")
    confidence: float = Field(..., ge=0, le=1)
    metrics: dict = Field(default_factory=dict)


class SignalInput(BaseModel):
    """
    Formato de señal para execution-engine.
    Ver apps/trading/execution-engine/internal/models/signal.go.
    """
    id: str
    tenant_id: str
    source: str = "orchestrator"
    symbol: str
    action: str = Field(..., pattern="^(BUY|SELL|CLOSE)$")
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profits: list[float] = Field(default_factory=list)
    lot_size: Optional[float] = None
    lot_mode: str = Field(default="fixed", pattern="^(fixed|risk_percent)$")
    risk_percent: Optional[float] = None
    confidence: float = Field(..., ge=0, le=1)
    recommended_lot_size: Optional[float] = None
    hash: str

    def to_json_bytes(self) -> bytes:
        import json

        return json.dumps(self.model_dump(mode="json")).encode()