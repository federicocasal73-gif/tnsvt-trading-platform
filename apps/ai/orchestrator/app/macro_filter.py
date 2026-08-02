"""
Macro filter — integra datos macroeconómicos en el pipeline del orchestrator.

- Consulta macro-fetcher para eventos de alto impacto y liquidez (TGA/RRP)
- Filtra señales BUY durante riesgo macro (eventos próximos, liquidez baja)
- Reduce position size si hay incertidumbre
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

MACRO_FETCHER_URL = "http://localhost:8040"  # docker: http://macro-fetcher:8040

# No trading within N hours before a high-impact event
HIGH_IMPACT_BLACKOUT_HOURS = 4

# RRP below this threshold signals low liquidity (risk-off)
RRP_LOW_THRESHOLD = 0.3  # $300B

# TGA above this signals liquidity drain
TGA_HIGH_THRESHOLD = 0.7  # $700B

# Confidence reduction for risky macro conditions
REDUCE_CONFIDENCE_BY = 0.15
REDUCE_LOT_BY = 0.5


async def _fetch_json(path: str) -> Optional[Dict]:
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{MACRO_FETCHER_URL}{path}")
            r.raise_for_status()
            return r.json()
    except Exception as e:
        logger.warning("macro-fetcher %s: %s", path, e)
        return None


async def get_upcoming_high_impact() -> List[Dict[str, Any]]:
    data = await _fetch_json("/api/v1/macro/calendar?days=3")
    if not data:
        return []
    return data.get("events", [])


async def check_macro_conditions() -> Dict[str, Any]:
    """
    Return macro assessment: is it risk-off? confidence/lot modifiers.
    """
    result: Dict[str, Any] = {
        "risk_off": False,
        "reasons": [],
        "confidence_multiplier": 1.0,
        "lot_multiplier": 1.0,
    }

    # 1. Check high-impact events in next N hours
    events = await get_upcoming_high_impact()
    now = datetime.now(timezone.utc)
    near_events = []
    for e in events:
        try:
            event_date = e.get("date", "")
            event_time = e.get("time", "")
            # Attempt parse; skip if unparseable
            dt_str = f"{event_date} {event_time}".strip()
            if not event_date:
                continue
            event_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
            hours_until = (event_dt - now).total_seconds() / 3600
            if 0 <= hours_until <= HIGH_IMPACT_BLACKOUT_HOURS:
                near_events.append(e["event"])
        except (ValueError, KeyError):
            continue

    if near_events:
        result["risk_off"] = True
        result["reasons"].append(f"High-impact events in <{HIGH_IMPACT_BLACKOUT_HOURS}h: {', '.join(near_events[:3])}")
        result["confidence_multiplier"] = 1.0 - REDUCE_CONFIDENCE_BY
        result["lot_multiplier"] = 1.0 - REDUCE_LOT_BY

    # 2. Check TGA/RRP liquidity
    liq = await _fetch_json("/api/v1/macro/liquidity")
    if liq:
        tga = liq.get("tga_billion")
        rrp = liq.get("rrp_billion")
        if tga is not None and tga > TGA_HIGH_THRESHOLD * 1000:
            result["risk_off"] = True
            result["reasons"].append(f"TGA elevated: ${tga:.0f}B")
            result["confidence_multiplier"] = min(result["confidence_multiplier"], 1.0 - REDUCE_CONFIDENCE_BY)
            result["lot_multiplier"] = min(result["lot_multiplier"], 1.0 - REDUCE_LOT_BY)
        if rrp is not None and rrp < RRP_LOW_THRESHOLD * 1000:
            result["risk_off"] = True
            result["reasons"].append(f"RRP low: ${rrp:.0f}B (liquidity drain)")
            result["confidence_multiplier"] = min(result["confidence_multiplier"], 1.0 - REDUCE_CONFIDENCE_BY)
            result["lot_multiplier"] = min(result["lot_multiplier"], 1.0 - REDUCE_LOT_BY)

    if not result["risk_off"]:
        logger.info("Macro conditions: normal")
    else:
        logger.warning("Macro risk-off: %s", "; ".join(result["reasons"]))

    return result