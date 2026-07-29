"""
Categorizer — tagger de categoria + activos afectados.

Asigna a cada noticia:
- categorias tematicas (Geopolitica, FED, Inflacion, Macro, Politica, Dolar, Commodities, Cripto)
- simbolos afectados (XAUUSD, EURUSD, BTCUSD, NAS100, etc.)
"""
from __future__ import annotations

import re
from typing import List, Tuple


CATEGORY_DEFINITIONS = {
    "Geopolitica": {
        "weight": 0.6,
        "keywords": [
            "war", "conflict", "tension", "tensions", "sanction", "sanctions",
            "tariff", "tariffs", "trade war", "mar rojo", "red sea", "houthi",
            "russia", "ukraine", "china", "taiwan", "north korea", "iran",
            "israel", "middle east", "opec", "oil supply", "geopolit",
        ],
        "stars_default": 3,
    },
    "FED": {
        "weight": 0.7,
        "keywords": [
            "fomc", "fed", "powell", "federal reserve", "interest rate",
            "rate decision", "rate hike", "rate cut", "dot plot", "dovish",
            "hawkish", "fed chair", "jerome powell", "us central bank",
        ],
        "stars_default": 4,
    },
    "Inflacion": {
        "weight": 0.5,
        "keywords": [
            "cpi", "consumer price", "inflation", "ppi", "producer price",
            "core inflation", "core cpi", "core ppi", "pce", "deflator",
            "inflation rate", "inflation data", "price index",
        ],
        "stars_default": 3,
    },
    "Macro": {
        "weight": 0.4,
        "keywords": [
            "gdp", "employment", "nfp", "nonfarm", "jobs report",
            "unemployment", "payrolls", "ism", "pmi", "retail sales",
            "industrial production", "housing starts", "consumer confidence",
        ],
        "stars_default": 3,
    },
    "Politica": {
        "weight": 0.5,
        "keywords": [
            "trump", "biden", "election", "congress", "senate",
            "white house", "federal government", "shutdown", "impeachment",
            "policy", "administration", "democrat", "republican",
        ],
        "stars_default": 2,
    },
    "Dolar": {
        "weight": 0.6,
        "keywords": [
            "dollar", "dxy", "usd", "greenback", "buck", "currency",
            "forex", "exchange rate",
        ],
        "stars_default": 2,
    },
    "Commodities": {
        "weight": 0.4,
        "keywords": [
            "gold", "oro", "xauusd", "silver", "xagusd", "oil", "crude",
            "wti", "brent", "commodit", "natural gas", "goldman",
            "gold price",
        ],
        "stars_default": 3,
    },
    "Cripto": {
        "weight": 0.4,
        "keywords": [
            "bitcoin", "btc", "crypto", "cryptocurrency", "ethereum",
            "eth", "blockchain", "btcusd", "ethusd", "digital asset",
        ],
        "stars_default": 2,
    },
    "Acciones": {
        "weight": 0.3,
        "keywords": [
            "stocks", "equities", "share", "wall street", "nasdaq",
            "s&p 500", "spx", "dow jones", "earnings", "tech stocks",
            "magnificent 7",
        ],
        "stars_default": 2,
    },
    "Bancos": {
        "weight": 0.4,
        "keywords": [
            "bank", "banking", "jpmorgan", "goldman sachs", "morgan stanley",
            "wells fargo", "citigroup", "credit suisse", "ubs",
        ],
        "stars_default": 2,
    },
}


# Mapeo de keyword -> simbolos afectados
SYMBOL_KEYWORDS = {
    "XAUUSD": ["gold", "oro", "xauusd", "xau/", "goldman", "bullion"],
    "EURUSD": ["eur/usd", "eurusd", "euro", "european", "ecb", "lagarde"],
    "GBPUSD": ["gbp/usd", "gbpusd", "pound", "sterling", "boe", "bailey"],
    "USDJPY": ["usd/jpy", "usdjpy", "yen", "boj", "japan", "japanese"],
    "AUDUSD": ["aud/usd", "audusd", "aussie", "rba"],
    "USDCAD": ["usd/cad", "usdcad", "loonie", "canadian", "boc"],
    "BTCUSD": ["bitcoin", "btc", "btcusd", "btc/usd"],
    "ETHUSD": ["ethereum", "eth", "ethusd", "eth/usd"],
    "NAS100": ["nasdaq", "nas100", "tech stocks", "magnificent 7", "nvidia",
               "apple", "microsoft", "amazon", "google", "meta"],
    "US30":   ["dow jones", "dow", "us30", "industrial"],
    "US500":  ["s&p 500", "spx", "sp500", "us500"],
    "WTI":    ["wti", "crude oil", "west texas"],
    "BRENT":  ["brent", "brent crude"],
    "XAGUSD": ["silver", "xagusd", "xag"],
}


def categorize(title: str, description: str = "") -> List[str]:
    """Devuelve lista de categorias detectadas."""
    full = f"{title} {description}".lower()
    matched: List[str] = []

    for cat, defn in CATEGORY_DEFINITIONS.items():
        for kw in defn["keywords"]:
            if kw.lower() in full:
                matched.append(cat)
                break
    return matched


def affected_symbols(title: str, description: str = "") -> List[str]:
    """Devuelve simbolos afectados segun keywords."""
    full = f"{title} {description}".lower()
    matched: List[str] = []
    for symbol, kws in SYMBOL_KEYWORDS.items():
        for kw in kws:
            if kw.lower() in full:
                matched.append(symbol)
                break
    # Tambien incluir simbolos basados en categoria general
    cats = categorize(title, description)
    if "Cripto" in cats and "BTCUSD" not in matched:
        matched.append("BTCUSD")
    if "Commodities" in cats and "XAUUSD" not in matched:
        matched.append("XAUUSD")
    if "Dolar" in cats or "FED" in cats:
        if "DXY" not in matched:
            matched.append("DXY")
    return matched


def default_stars(categories: List[str], sentiment_score: float) -> int:
    """Estima estrellas si sentiment da muchas (categoria cambia el peso)."""
    if not categories:
        return 2  # neutral
    base = max(
        CATEGORY_DEFINITIONS.get(c, {}).get("stars_default", 2)
        for c in categories
    )
    # Ajustar segun sentiment
    if sentiment_score >= 0.5:
        base = max(base, 3)
    if sentiment_score <= -0.5:
        base = min(base, 1)
    return min(4, max(0, base))