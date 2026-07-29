"""
Pydantic models for the news-analyzer service.
"""
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field


class NewsItem(BaseModel):
    """Una noticia individual con sentiment + categorias."""
    id: str
    title: str
    description: str = ""
    url: str = ""
    source: str = ""
    category: str = "markets"
    published_at: Optional[datetime] = None
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sentiment_score: float = Field(default=0.0, ge=-1, le=1, description="-1 muy negativo, 0 neutral, +1 muy positivo")
    sentiment_label: str = Field(default="NEUTRAL", pattern="^(POSITIVE|NEUTRAL|NEGATIVE)$")
    star_rating: int = Field(default=2, ge=0, le=4, description="0-4 stars, derivado de sentiment+impacto")
    categories: List[str] = Field(default_factory=list, description="[Geopolitica, FED, Inflacion, ...]")
    affected_symbols: List[str] = Field(default_factory=list)
    reactions: dict[str, str] = Field(
        default_factory=dict,
        description="Reaction por simbolo: {XAUUSD: 'Alcista (FED dovish)', ...}",
    )


class NewsListResponse(BaseModel):
    count: int
    items: List[NewsItem]


class NewsIngestRequest(BaseModel):
    """Para que el bot/frontend ingeste noticias parseadas externamente."""
    title: str
    description: str = ""
    url: str = ""
    source: str = ""
    category: str = "markets"
    published_at: Optional[datetime] = None


class SentimentBySymbol(BaseModel):
    symbol: str
    sentiment_score: float
    sentiment_label: str
    news_count: int
    last_updated: datetime


class SentimentSummary(BaseModel):
    overall_score: float = Field(description="Promedio ponderado -1..+1")
    overall_label: str
    by_symbol: List[SentimentBySymbol]
    by_category: dict[str, int]
    total_news: int
    last_updated: datetime