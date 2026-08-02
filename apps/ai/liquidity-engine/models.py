from datetime import datetime

from pydantic import BaseModel, Field


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
