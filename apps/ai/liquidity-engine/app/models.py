from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class LSTMetrics(BaseModel):
    relative_spread: float = Field(..., ge=0, description="(ask - bid) / mid * 10000")
    volume_imbalance: float = Field(..., ge=-1, le=1, description="(buy_vol - sell_vol) / total_vol")
    order_flow_pressure: float = Field(..., ge=-1, le=1, description="tick-level directional pressure")
    microstructure_score: float = Field(..., ge=0, le=1, description="composite market quality score")
    liquidity_score: float = Field(..., ge=0, le=1, description="overall liquidity (1 = highly liquid)")


class LSTSignal(BaseModel):
    symbol: str
    timestamp: datetime
    timeframe: str
    signal_type: str = Field(..., pattern="^(liquidity_buy|liquidity_sell|neutral)$")
    confidence: float = Field(..., ge=0, le=1)
    metrics: LSTMetrics


class RateOHLCV(BaseModel):
    symbol: str
    timeframe: str
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    tick_volume: float
    spread: int

    @field_validator("time", mode="before")
    @classmethod
    def coerce_time(cls, v):
        if isinstance(v, int):
            return datetime.fromtimestamp(v, tz=timezone.utc)
        return v


# ─── Liquidity Zones (from MQL5 EA LiquidityZones.mq5) ────────────────

ALLOWED_ZONE_TYPES = {
    "swing_high",
    "swing_low",
    "equal_high",
    "equal_low",
    "fvg_bull",
    "fvg_bear",
    "bos_bull",
    "bos_bear",
}


class LiquidityZone(BaseModel):
    """Una zona de liquidez detectada por el EA MQL5."""
    symbol: str
    timeframe: str
    type: str = Field(..., description=f"one of {sorted(ALLOWED_ZONE_TYPES)}")
    price_high: float
    price_low: float
    midpoint: float
    time_start: int = Field(..., description="epoch seconds")
    time_end: int = Field(..., description="epoch seconds")
    strength: int = Field(default=1, ge=1)
    swept: bool = False


class LiquidityZonesPayload(BaseModel):
    """Payload enviado por el EA LiquidityZones.mq5 cada InpPublishSeconds."""
    account_id: str
    symbol: str
    timeframe: str
    ts: int
    count: int
    zones: List[LiquidityZone]


class LiquidityZonesIngestResponse(BaseModel):
    accepted: int
    rejected: int
    total: int
    stored_account_id: Optional[str] = None
    stored_at: datetime
    error: Optional[str] = None
