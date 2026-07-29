"""
Macro indicators — Latest readings for key US economic indicators.

Returns the most recent value + previous value + forecast for each
indicator, with vs-previous direction. Used by /macro page "Pulso Macro".

NOTE: This is mock data with realistic values. Replace with real fetcher
(integrate FRED, TradingEconomics, or BLS.gov) when API keys are available.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import httpx
import logging

logger = logging.getLogger("MacroFetcher.Indicators")

# Mock latest readings (illustrative values; replace with real data source)
_MOCK_INDICATORS: dict[str, dict] = {
    "CPI": {
        "name": "CPI (Indice Precios Consumidor)",
        "country": "USA",
        "previous": "3.0%",
        "actual": "2.9%",
        "forecast": "2.9%",
        "unit": "% YoY",
        "release_date": "2026-07-15",
        "next_release": "2026-08-12",
    },
    "CoreCPI": {
        "name": "Core CPI (sin alimentos/energia)",
        "country": "USA",
        "previous": "3.2%",
        "actual": "3.0%",
        "forecast": "3.1%",
        "unit": "% YoY",
        "release_date": "2026-07-15",
        "next_release": "2026-08-12",
    },
    "PPI": {
        "name": "PPI (Indice Precios Productor)",
        "country": "USA",
        "previous": "2.6%",
        "actual": "2.5%",
        "forecast": "2.4%",
        "unit": "% YoY",
        "release_date": "2026-07-16",
        "next_release": "2026-08-14",
    },
    "NFP": {
        "name": "Non-Farm Payrolls (empleo)",
        "country": "USA",
        "previous": "175k",
        "actual": "206k",
        "forecast": "190k",
        "unit": "cambio mensual",
        "release_date": "2026-07-08",
        "next_release": "2026-08-05",
    },
    "Unemployment": {
        "name": "Tasa de desempleo",
        "country": "USA",
        "previous": "4.1%",
        "actual": "4.2%",
        "forecast": "4.1%",
        "unit": "%",
        "release_date": "2026-07-08",
        "next_release": "2026-08-05",
    },
    "RetailSales": {
        "name": "Ventas Minoristas",
        "country": "USA",
        "previous": "0.1%",
        "actual": "0.4%",
        "forecast": "0.3%",
        "unit": "% MoM",
        "release_date": "2026-07-17",
        "next_release": "2026-08-15",
    },
}


def _parse_pct(value: str) -> Optional[float]:
    """Convierte '3.0%' o '0.4%' o '206k' a float. None si no parseable."""
    try:
        s = value.strip().replace("%", "").replace(",", "").replace("k", "")
        s = s.replace("+", "")
        return float(s)
    except Exception:
        return None


def _direction(previous: str, actual: str) -> str:
    """Devuelve 'up' / 'down' / 'flat' segun cambio entre previous y actual."""
    p = _parse_pct(previous)
    a = _parse_pct(actual)
    if p is None or a is None:
        return "flat"
    if a > p + 0.01:
        return "up"
    if a < p - 0.01:
        return "down"
    return "flat"


def _beat(actual: str, forecast: str) -> str:
    """Devuelve 'beat' / 'miss' / 'in-line' segun vs forecast."""
    a = _parse_pct(actual)
    f = _parse_pct(forecast)
    if a is None or f is None:
        return "unknown"
    if a > f + 0.01:
        return "beat"
    if a < f - 0.01:
        return "miss"
    return "in-line"


async def get_indicators() -> list[dict]:
    """Devuelve lista de indicadores con previous/actual/forecast + direction."""
    out: list[dict] = []
    for key, ind in _MOCK_INDICATORS.items():
        direction = _direction(ind["previous"], ind["actual"])
        beat = _beat(ind["actual"], ind["forecast"])
        out.append({
            "key": key,
            "name": ind["name"],
            "country": ind["country"],
            "previous": ind["previous"],
            "actual": ind["actual"],
            "forecast": ind["forecast"],
            "unit": ind["unit"],
            "direction": direction,
            "vs_forecast": beat,
            "release_date": ind["release_date"],
            "next_release": ind["next_release"],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        })
    return out


# Semaforo de impacto: para el frontend
def _impact_label(beat: str, direction: str) -> str:
    """Mapeo a High/Medium/Low segun beat/miss/direction."""
    if beat == "beat":
        return "High"
    if beat == "miss":
        return "High"
    return "Medium"