"""
Fetcher — RSS news fetcher. Reusa la logica de free_news.py pero devuelve
items estructurados para el pipeline de sentiment + categorizer.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
from datetime import datetime, timezone
from typing import List, Optional

import aiohttp
from bs4 import BeautifulSoup

from app.categorizer import categorize, affected_symbols, default_stars
from app.models import NewsItem
from app.sentiment import score_sentiment, score_to_stars
from app.symbol_impact import impact_for_symbols

logger = logging.getLogger("NewsAnalyzer.Fetcher")

_CACHED: List[NewsItem] = []
_CACHE_TS: float = 0.0
_CACHE_TTL: int = 300

RSS_FEEDS = {
    "markets": [
        "https://feeds.content.dowjones.io/public/rss/mw_topstories",
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    ],
    "crypto": [
        "https://cointelegraph.com/rss",
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
    ],
    "economy": [
        "https://www.investing.com/rss/news.rss",
        "https://feeds.bloomberg.com/markets/news.rss",
    ],
    "stocks": [
        "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    ],
}


async def _fetch_rss(url: str, max_items: int = 10) -> List[dict]:
    try:
        async with aiohttp.ClientSession() as session:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            async with session.get(
                url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status != 200:
                    return []
                text = await resp.text()
                return _parse_rss(text, max_items)
    except Exception as e:
        logger.debug(f"RSS fetch {url}: {e}")
        return []


def _parse_rss(xml_text: str, max_items: int) -> List[dict]:
    items: List[dict] = []
    try:
        soup = BeautifulSoup(xml_text, "lxml-xml")
        for item in soup.find_all("item")[:max_items]:
            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")
            pub_el = item.find("pubDate")
            title = title_el.get_text(strip=True) if title_el else ""
            link = ""
            if link_el:
                link = link_el.get_text(strip=True) or link_el.get("href", "")
            description = desc_el.get_text(strip=True)[:300] if desc_el else ""
            date_str = pub_el.get_text(strip=True) if pub_el else ""

            if not title:
                continue

            published_at = _parse_date(date_str)

            items.append({
                "title": title,
                "url": link,
                "description": description,
                "published_at": published_at,
                "date_str": date_str,
            })
    except Exception as e:
        logger.warning(f"RSS parse error: {e}")
    return items


def _parse_date(date_str: str) -> Optional[datetime]:
    """Parse RFC 822 date (formato RSS comun)."""
    if not date_str:
        return None
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _build_id(item: dict) -> str:
    """ID estable para deduplicacion."""
    raw = f"{item.get('url', '')}|{item.get('title', '')}|{item.get('date_str', '')}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]


def _to_news_item(raw: dict, source: str, category: str) -> NewsItem:
    title = raw.get("title", "")
    description = raw.get("description", "")
    url = raw.get("url", "")
    published_at = raw.get("published_at")

    sentiment_score, sentiment_label = score_sentiment(title, description)
    categories = categorize(title, description)
    affected = affected_symbols(title, description)
    reactions = impact_for_symbols(categories, sentiment_score, title)

    # Estrellas: combina sentiment + importance de categoria
    stars = score_to_stars(sentiment_score)
    if categories:
        # Ajustar segun categoria mas importante
        cat_stars = default_stars(categories, sentiment_score)
        stars = max(stars, cat_stars) if sentiment_score >= 0 else min(stars, cat_stars)

    return NewsItem(
        id=_build_id(raw),
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


async def fetch_all_news(force: bool = False) -> List[NewsItem]:
    """Devuelve todas las noticias parseadas (markets + crypto + economy + stocks).

    Cachea por 5 minutos para evitar fetch repetido.
    """
    global _CACHED, _CACHE_TS

    if not force and _CACHED and (time.time() - _CACHE_TS) < _CACHE_TTL:
        return _CACHED

    source_names = {
        "markets": "MarketWatch/CNBC",
        "crypto": "CoinTelegraph/CoinDesk",
        "economy": "Investing/Bloomberg",
        "stocks": "MarketWatch",
    }

    all_items: List[NewsItem] = []
    seen_ids: set[str] = set()

    for cat, feeds in RSS_FEEDS.items():
        for url in feeds:
            raw_items = await _fetch_rss(url, max_items=5)
            for raw in raw_items:
                item = _to_news_item(raw, source_names[cat], cat)
                if item.id not in seen_ids:
                    seen_ids.add(item.id)
                    all_items.append(item)

    # Ordenar por fecha desc
    def _sort_key(item: NewsItem):
        return item.published_at or datetime.min.replace(tzinfo=timezone.utc)

    all_items.sort(key=_sort_key, reverse=True)
    _CACHED = all_items
    _CACHE_TS = time.time()
    logger.info(f"fetch_all_news: {len(all_items)} items from RSS")
    return all_items


def clear_cache():
    global _CACHED, _CACHE_TS
    _CACHED = []
    _CACHE_TS = 0.0