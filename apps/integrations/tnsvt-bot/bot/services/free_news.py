"""
Free News — Financial news from free RSS feeds (no API key required).

Fallback cuando NEWSAPI_KEY no está configurada.
Fuentes: Yahoo Finance, CNBC, MarketWatch, Investing.com
"""
import asyncio
import logging
import time
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger("Services.FreeNews")

_cache = {}
_CACHE_TTL = 300

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


async def fetch_rss(url: str, max_items: int = 5) -> list[dict]:
    try:
        async with aiohttp.ClientSession() as session:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status != 200:
                    return []
                text = await resp.text()
                return _parse_rss_xml(text, max_items)
    except Exception as e:
        logger.debug(f"RSS fetch error {url}: {e}")
        return []


def _parse_rss_xml(xml_text: str, max_items: int) -> list[dict]:
    items = []
    try:
        soup = BeautifulSoup(xml_text, "lxml-xml")
        for item in soup.find_all("item")[:max_items]:
            title = item.find("title")
            link = item.find("link")
            description = item.find("description")
            pub_date = item.find("pubDate")

            items.append({
                "title": title.get_text(strip=True) if title else "Sin titulo",
                "url": link.get_text(strip=True) if link else "",
                "description": description.get_text(strip=True)[:200] if description else "",
                "date": pub_date.get_text(strip=True)[:16] if pub_date else "",
            })
    except Exception as e:
        logger.warning(f"RSS parse error: {e}")
    return items


def _format_news_telegraph(items: list[dict], source_name: str = "") -> str:
    if not items:
        return ""
    lines = []
    if source_name:
        lines.append(f"📡 *{source_name}*")
    for item in items:
        title = item.get("title", "")
        url = item.get("url", "")
        date = item.get("date", "")
        lines.append(f"📰 {title}")
        if date:
            lines.append(f"   🕐 {date}")
        if url:
            lines.append(f"   🔗 {url}")
        lines.append("")
    return "\n".join(lines)


async def get_free_news(topic: str = "markets", max_items: int = 5) -> str:
    cache_key = f"{topic}:{max_items}"
    cached = _cache.get(cache_key)
    if cached and (time.time() - cached["ts"]) < _CACHE_TTL:
        return cached["data"]

    feeds = RSS_FEEDS.get(topic, RSS_FEEDS["markets"])
    all_items = []
    for url in feeds:
        items = await fetch_rss(url, max_items)
        all_items.extend(items)
        if len(all_items) >= max_items:
            break

    if not all_items:
        logger.warning(f"No se pudieron obtener noticias para: {topic}")
        result = "⚠️ No se pudieron obtener noticias en este momento."
        _cache[cache_key] = {"data": result, "ts": time.time()}
        return result

    all_items = all_items[:max_items]

    source_names = {
        "markets": "Mercados Financieros",
        "crypto": "Criptomonedas",
        "economy": "Economia",
        "stocks": "Empresas y Wall Street",
    }
    source = source_names.get(topic, "Noticias")

    result = _format_news_telegraph(all_items, source)
    _cache[cache_key] = {"data": result, "ts": time.time()}
    return result


async def get_market_news_free(max_items: int = 5) -> str:
    return await get_free_news("markets", max_items)


async def get_crypto_news_free(max_items: int = 5) -> str:
    return await get_free_news("crypto", max_items)


async def get_economy_news_free(max_items: int = 5) -> str:
    return await get_free_news("economy", max_items)


async def get_stock_news_free(max_items: int = 5) -> str:
    return await get_free_news("stocks", max_items)


def clear_cache():
    _cache.clear()
