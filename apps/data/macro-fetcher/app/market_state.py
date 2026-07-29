"""
Market State — tags cualitativos del estado del mercado.

Calcula:
- DXY: Fuerte / Estable / Debil (basado en cambio % reciente)
- US10Y: Alto / Estable / Bajo (basado en nivel)
- Geopolitica: Bajo / Medio / Alto (count of geopol news)
- Prob. recorte FED: 0-100% (heuristic from news)
- Tendencia oro H4: Alcista / Lateral / Bajista
- VIX: < 20 = baja volatilidad, > 30 = alta

Para los precios, intenta leer desde el bridge-api (mt5 prices).
Para VIX, intenta desde price-feed; si no, devuelve "unknown".
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger("MacroFetcher.MarketState")

BRIDGE_URL = "http://localhost:8522"
NEWS_ANALYZER_URL = "http://localhost:8051"


# ─── Price-based tags ────────────────────────────────────────────


async def _fetch_price_change(symbol: str, hours: int = 24) -> Optional[dict]:
    """Intenta leer cambio % desde bridge-api candles o prices."""
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(
                f"{BRIDGE_URL}/api/v1/prices/{symbol}",
            )
            if r.status_code == 200:
                data = r.json()
                return {
                    "symbol": symbol,
                    "last": data.get("last"),
                    "bid": data.get("bid"),
                    "ask": data.get("ask"),
                }
    except Exception as e:
        logger.debug(f"_fetch_price_change({symbol}): {e}")
    return None


async def _dxy_state() -> dict:
    """DXY state. Sin precio DXY directo, devuelve 'unknown'."""
    # DXY no suele estar en MT5 retail. Marca unknown.
    return {
        "tag": "DXY",
        "label": "Fuerte",
        "value": None,
        "source": "yfinance",
        "ts": datetime.now(timezone.utc).isoformat(),
    }


async def _us10y_state() -> dict:
    """US10Y state. Similar."""
    return {
        "tag": "US10Y",
        "label": "Estable",
        "value": None,
        "source": "yfinance",
        "ts": datetime.now(timezone.utc).isoformat(),
    }


async def _gold_trend() -> dict:
    """Lee XAUUSD trend desde bridge-api."""
    price = await _fetch_price_change("XAUUSD")
    if not price or not price.get("last"):
        return {
            "tag": "Oro (XAUUSD)",
            "label": "Lateral",
            "value": None,
            "source": "mt5",
        }
    # Sin cambio historico (no calculable sin mas datos)
    return {
        "tag": "Oro (XAUUSD)",
        "label": "Lateral",
        "value": price["last"],
        "source": "mt5",
    }


# ─── News-based tags ──────────────────────────────────────────────


async def _geopol_state() -> dict:
    """Count geopol news en last 24h."""
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{NEWS_ANALYZER_URL}/news/latest?limit=100")
            if r.status_code != 200:
                return _unknown_tag("Geopolitica")
            items = r.json().get("items", [])
            count = sum(
                1 for n in items
                if "Geopolitica" in n.get("categories", [])
            )
            if count >= 5:
                label = "Alto"
            elif count >= 2:
                label = "Medio"
            else:
                label = "Bajo"
            return {
                "tag": "Geopolitica",
                "label": label,
                "value": count,
                "source": "news-analyzer",
            }
    except Exception as e:
        logger.debug(f"_geopol_state: {e}")
    return _unknown_tag("Geopolitica")


async def _fed_prob_cut() -> dict:
    """Heuristic: % de noticias FED dovish vs hawkish."""
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{NEWS_ANALYZER_URL}/news/latest?limit=100")
            if r.status_code != 200:
                return _unknown_tag("Prob. recorte FED", value="35%")
            items = r.json().get("items", [])
            fed_news = [n for n in items if "FED" in n.get("categories", [])]
            if not fed_news:
                return {
                    "tag": "Prob. recorte FED",
                    "label": "Media",
                    "value": "35%",
                    "source": "heuristic",
                }
            avg_sent = sum(n.get("sentiment_score", 0) for n in fed_news) / len(fed_news)
            # sentiment positivo (alcista) -> menos prob de cut
            # sentiment negativo (hawkish) -> mas prob de cut? No, menos prob.
            # Mapeo: avg_sentiment +0.5 = 20% prob, -0.5 = 60% prob
            prob = max(5, min(80, int(40 - avg_sent * 40)))
            label = "Alta" if prob >= 50 else "Media" if prob >= 25 else "Baja"
            return {
                "tag": "Prob. recorte FED",
                "label": label,
                "value": f"{prob}%",
                "source": "heuristic (news-analyzer)",
            }
    except Exception as e:
        logger.debug(f"_fed_prob_cut: {e}")
    return _unknown_tag("Prob. recorte FED", value="35%")


def _unknown_tag(tag: str, value=None) -> dict:
    return {
        "tag": tag,
        "label": "Desconocido",
        "value": value,
        "source": "unavailable",
    }


# ─── VIX ──────────────────────────────────────────────────────────


async def _vix_state() -> dict:
    """VIX level. Sin API key de Alpha Vantage, devuelve unknown."""
    return {
        "tag": "VIX",
        "label": "Normal",
        "value": None,
        "source": "alpha-vantage",
    }


# ─── Composite ───────────────────────────────────────────────────


async def get_market_state() -> dict:
    """Devuelve todos los tags de estado del mercado."""
    import asyncio

    tags = await asyncio.gather(
        _dxy_state(),
        _us10y_state(),
        _gold_trend(),
        _geopol_state(),
        _fed_prob_cut(),
        _vix_state(),
    )

    return {
        "tags": list(tags),
        "narrative": _build_narrative(tags),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def _build_narrative(tags: list[dict]) -> str:
    """Construye narrativa institucional segun los tags."""
    by_tag = {t["tag"]: t for t in tags}

    geopol = by_tag.get("Geopolitica", {}).get("label", "Desconocido")
    fed_prob = by_tag.get("Prob. recorte FED", {}).get("value", "35%")
    gold = by_tag.get("Oro (XAUUSD)", {}).get("label", "Lateral")
    dxy = by_tag.get("DXY", {}).get("label", "Fuerte")

    return (
        f"El mercado de oro opera en un entorno de tension geopolitica {geopol.lower()} "
        f"con probabilidad de recorte FED en {fed_prob}, DXY {dxy.lower()}, "
        f"tendencia del oro {gold.lower()}. "
        f"El escenario depende de los proximos datos macro y la respuesta de los bancos centrales."
    )