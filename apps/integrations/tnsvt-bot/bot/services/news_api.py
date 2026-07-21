"""
Service: NewsAPI with free RSS fallback.
Usa NewsAPI si hay API key, sino usa RSS feeds gratis.
"""
import asyncio
import logging
import time
import requests
from config import settings
from bot.services.free_news import get_free_news

logger = logging.getLogger("Services.NewsAPI")

_news_cache = {}
_CACHE_TTL = 300


def _get_cached(key: str):
    if key in _news_cache:
        ts, data = _news_cache[key]
        if time.time() - ts < _CACHE_TTL:
            return data
    return None


def _set_cached(key: str, data):
    _news_cache[key] = (time.time(), data)


def get_news(query: str, page_size: int = 5) -> str:
    cache_key = f"newsapi:{query}:{page_size}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    if settings.NEWSAPI_KEY:
        try:
            url = "https://newsapi.org/v2/everything"
            params = {
                "q": query,
                "sortBy": "publishedAt",
                "pageSize": page_size,
                "apiKey": settings.NEWSAPI_KEY,
            }
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            articles = data.get("articles", [])

            if articles:
                texto = ""
                for article in articles[:page_size]:
                    title = article.get("title", "Sin titulo")
                    url_art = article.get("url", "")
                    texto += f"📰 <b>{title}</b>\n{url_art}\n\n"
                result = texto.strip()
                _set_cached(cache_key, result)
                return result
        except Exception as e:
            logger.warning(f"NewsAPI error, usando RSS fallback: {e}")

    logger.info("Usando RSS feeds gratis (sin NewsAPI key)")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        topic = _query_to_topic(query)
        result = loop.run_until_complete(get_free_news(topic, page_size))
        _set_cached(cache_key, result)
        return result
    finally:
        loop.close()


def _query_to_topic(query: str) -> str:
    q = query.lower()
    if any(w in q for w in ("bitcoin", "ethereum", "crypto", "cripto")):
        return "crypto"
    if any(w in q for w in ("inflation", "cpi", "economic", "economy", "fed", "federal")):
        return "economy"
    if any(w in q for w in ("stock", "wall street", "morgan", "earnings", "microsoft", "apple", "tesla")):
        return "stocks"
    return "markets"


def get_market_news(page_size: int = 5) -> str:
    return get_news("stock market trading Wall Street", page_size)


def get_economic_calendar(page_size: int = 5) -> str:
    return get_news("economic calendar Federal Reserve interest rates inflation", page_size)


def get_inflation_news(page_size: int = 5) -> str:
    return get_news("inflation CPI prices Federal Reserve", page_size)


def get_crypto_news(page_size: int = 5) -> str:
    return get_news("bitcoin ethereum cryptocurrency", page_size)


def get_wall_street_news(page_size: int = 5) -> str:
    return get_news("Wall Street earnings Microsoft Apple Tesla", page_size)


def clear_cache():
    _news_cache.clear()
