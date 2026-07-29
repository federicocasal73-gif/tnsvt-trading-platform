"""
News Analyzer — FastAPI microservice that fetches RSS news, applies
keyword-based sentiment scoring, categorizes by topic, and maps
"how each symbol reacts" per article.

Endpoints:
  GET  /health
  GET  /news/latest?category=&limit=&min_stars=
  GET  /news/by-symbol/{symbol}
  GET  /news/sentiment-summary
  POST /news/ingest  (admin/internal — accepts manually parsed news)
  POST /news/refresh  (force re-fetch RSS, ignore cache)
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException

from app.categorizer import affected_symbols, categorize, default_stars
from app.fetcher import fetch_all_news, clear_cache as clear_fetcher_cache
from app.models import (
    NewsIngestRequest,
    NewsItem,
    NewsListResponse,
    SentimentBySymbol,
    SentimentSummary,
)
from app.sentiment import score_sentiment, score_to_stars
from app.symbol_impact import impact_for_symbols

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] [%(levelname)s] %(message)s",
)
logger = logging.getLogger("NewsAnalyzer")

_app_state: dict = {"news": [], "last_refresh": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Arranca background task de refresh cada 5 minutos."""
    app.state.refresh_task = asyncio.create_task(_refresh_loop())
    logger.info("NewsAnalyzer started")
    yield
    task = app.state.refresh_task
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass


app = FastAPI(title="news-analyzer", version="1.0.0", lifespan=lifespan)


async def _refresh_loop():
    while True:
        try:
            items = await fetch_all_news(force=False)
            _app_state["news"] = items
            _app_state["last_refresh"] = datetime.now(timezone.utc)
            logger.info(f"refresh_loop: {len(items)} items loaded")
        except Exception as e:
            logger.error(f"refresh_loop error: {e}")
        await asyncio.sleep(300)


def _ingest_raw(title: str, description: str, url: str, source: str,
                category: str, published_at: Optional[datetime]) -> NewsItem:
    """Construye un NewsItem desde datos crudos (aplica sentiment/categorizer)."""
    sentiment_score, sentiment_label = score_sentiment(title, description)
    categories = categorize(title, description)
    affected = affected_symbols(title, description)
    reactions = impact_for_symbols(categories, sentiment_score, title)
    stars = score_to_stars(sentiment_score)
    if categories:
        cat_stars = default_stars(categories, sentiment_score)
        stars = max(stars, cat_stars) if sentiment_score >= 0 else min(stars, cat_stars)

    import hashlib
    item_id = hashlib.md5(f"{url}|{title}|{published_at}".encode()).hexdigest()[:16]

    return NewsItem(
        id=item_id,
        title=title,
        description=description,
        url=url,
        source=source,
        category=category,
        published_at=published_at,
        sentiment_score=round(sentiment_score, 3),
        sentiment_label=sentiment_label,
        star_rating=stars,
        categories=categories,
        affected_symbols=affected,
        reactions=reactions,
    )


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "news-analyzer",
        "news_count": len(_app_state["news"]),
        "last_refresh": _app_state["last_refresh"].isoformat() if _app_state["last_refresh"] else None,
    }


@app.get("/news/latest", response_model=NewsListResponse)
async def latest_news(
    category: str = "all",
    limit: int = 50,
    min_stars: int = 0,
    sentiment: str = "all",
):
    """Devuelve las ultimas noticias con sentiment + categorias + reactions."""
    items = _app_state["news"]

    if category != "all":
        items = [n for n in items if n.category == category]
    if sentiment in ("POSITIVE", "NEGATIVE", "NEUTRAL"):
        items = [n for n in items if n.sentiment_label == sentiment]
    items = [n for n in items if n.star_rating >= min_stars]

    items = items[:limit]
    return NewsListResponse(count=len(items), items=items)


@app.get("/news/by-symbol/{symbol}")
async def news_by_symbol(symbol: str, limit: int = 20):
    """Devuelve las noticias que afectan a un simbolo."""
    sym_up = symbol.upper()
    items = [
        n for n in _app_state["news"]
        if sym_up in n.affected_symbols or sym_up in (n.reactions or {})
    ]
    return NewsListResponse(count=len(items), items=items[:limit])


@app.get("/news/sentiment-summary", response_model=SentimentSummary)
async def sentiment_summary():
    """Sentiment agregado por simbolo y por categoria."""
    items = _app_state["news"]
    if not items:
        return SentimentSummary(
            overall_score=0.0,
            overall_label="NEUTRAL",
            by_symbol=[],
            by_category={},
            total_news=0,
            last_updated=datetime.now(timezone.utc),
        )

    # Overall
    overall = sum(n.sentiment_score for n in items) / len(items)
    overall_label = (
        "POSITIVE" if overall >= 0.25 else
        "NEGATIVE" if overall <= -0.25 else "NEUTRAL"
    )

    # By symbol
    by_sym: dict[str, list[float]] = {}
    for n in items:
        for sym in n.affected_symbols:
            by_sym.setdefault(sym, []).append(n.sentiment_score)

    sym_summaries: list[SentimentBySymbol] = []
    for sym, scores in sorted(by_sym.items()):
        avg = sum(scores) / len(scores)
        lbl = (
            "POSITIVE" if avg >= 0.25 else
            "NEGATIVE" if avg <= -0.25 else "NEUTRAL"
        )
        sym_summaries.append(SentimentBySymbol(
            symbol=sym,
            sentiment_score=round(avg, 3),
            sentiment_label=lbl,
            news_count=len(scores),
            last_updated=datetime.now(timezone.utc),
        ))

    # By category
    by_cat: dict[str, int] = {}
    for n in items:
        for c in n.categories:
            by_cat[c] = by_cat.get(c, 0) + 1

    return SentimentSummary(
        overall_score=round(overall, 3),
        overall_label=overall_label,
        by_symbol=sym_summaries,
        by_category=by_cat,
        total_news=len(items),
        last_updated=datetime.now(timezone.utc),
    )


@app.post("/news/ingest", response_model=NewsItem)
async def ingest_news(req: NewsIngestRequest):
    """Ingesta manual de una noticia (admin / fallback)."""
    item = _ingest_raw(
        req.title, req.description, req.url, req.source,
        req.category, req.published_at,
    )
    # Append sin duplicar
    existing_ids = {n.id for n in _app_state["news"]}
    if item.id not in existing_ids:
        _app_state["news"].insert(0, item)
    return item


@app.post("/news/refresh")
async def refresh_now():
    """Fuerza re-fetch de RSS."""
    items = await fetch_all_news(force=True)
    _app_state["news"] = items
    _app_state["last_refresh"] = datetime.now(timezone.utc)
    return {"refreshed": True, "count": len(items)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8051, log_level="info")