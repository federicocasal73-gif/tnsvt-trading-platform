"""
Service: NewsAPI - Con cache TTL
"""
import logging
import time
import requests
from config import settings

logger = logging.getLogger("Services.NewsAPI")

_news_cache = {}
_CACHE_TTL = 300  # 5 minutos


def _get_cached(key: str):
    """Obtiene de cache si no expiró."""
    if key in _news_cache:
        ts, data = _news_cache[key]
        if time.time() - ts < _CACHE_TTL:
            return data
    return None


def _set_cached(key: str, data):
    """Guarda en cache con timestamp."""
    _news_cache[key] = (time.time(), data)


def get_news(query: str, page_size: int = 5) -> str:
    """Obtiene noticias de NewsAPI con cache de 5 min."""
    cache_key = f"{query}:{page_size}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    if not settings.NEWSAPI_KEY:
        return "⚠️ API Key de NewsAPI no configurada."

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

        if not articles:
            result = f"No se encontraron noticias sobre: {query}"
        else:
            texto = ""
            for article in articles[:page_size]:
                title = article.get("title", "Sin titulo")
                url_art = article.get("url", "")
                texto += f"📰 <b>{title}</b>\n{url_art}\n\n"
            result = texto.strip()

        _set_cached(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"Error: {e}")
        return "⚠️ Error al obtener noticias"


def get_market_news(page_size: int = 5) -> str:
    """Noticias de mercados y bolsa"""
    return get_news("stock market trading Wall Street", page_size)


def get_economic_calendar(page_size: int = 5) -> str:
    """Noticias de eventos economicos"""
    return get_news("economic calendar Federal Reserve interest rates inflation", page_size)


def get_inflation_news(page_size: int = 5) -> str:
    """Noticias de inflacion"""
    return get_news("inflation CPI prices Federal Reserve", page_size)


def get_crypto_news(page_size: int = 5) -> str:
    """Noticias de criptomonedas"""
    return get_news("bitcoin ethereum cryptocurrency", page_size)


def get_wall_street_news(page_size: int = 5) -> str:
    """Noticias de Wall Street y empresas"""
    return get_news("Wall Street earnings Microsoft Apple Tesla", page_size)


def clear_cache():
    """Limpia la cache"""
    _news_cache.clear()
