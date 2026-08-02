"""
Macro fetcher service — obtiene datos macroeconómicos:
  - TGA (Treasury General Account) + RRP (Reverse Repo) via M2Quant
  - Economic calendar (CPI, NFP, FOMC, etc.)
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup

from app.config import settings

logger = logging.getLogger(__name__)


# ─── Models ──────────────────────────────────────────────────────


from dataclasses import dataclass


@dataclass
class MacroSnapshot:
    tga_billion: Optional[float] = None
    rrp_billion: Optional[float] = None
    fetched_at: str = ""


@dataclass
class CalendarEvent:
    date: str = ""
    time: str = ""
    currency: str = ""
    event: str = ""
    forecast: str = ""
    previous: str = ""
    impact: str = ""  # Low / Medium / High


# ─── M2Quant scraper ─────────────────────────────────────────────


async def fetch_m2quant() -> tuple[Optional[float], Optional[float]]:
    """Scrape M2Quant RSS for latest TGA and RRP values."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(settings.m2quant_url)
            r.raise_for_status()
    except Exception as e:
        logger.warning("M2Quant fetch failed: %s", e)
        return None, None

    soup = BeautifulSoup(r.text, "lxml-xml")
    items = soup.find_all("item")
    tga = None
    rrp = None
    for item in items:
        title = item.find("title")
        if not title or not title.text:
            continue
        txt = title.text
        # TGA pattern: "TGA: $XXX.XB"
        if tga is None:
            m = re.search(r"TGA.*?\$?([\d,]+\.?\d*)\s*B", txt, re.IGNORECASE)
            if m:
                tga = float(m.group(1).replace(",", ""))
                continue
        # RRP pattern: "RRP: $XXX.XB"
        if rrp is None:
            m = re.search(r"RRP.*?\$?([\d,]+\.?\d*)\s*B", txt, re.IGNORECASE)
            if m:
                rrp = float(m.group(1).replace(",", ""))

    if tga is None and rrp is None:
        logger.warning("Could not parse TGA/RRP from M2Quant feed")
    else:
        logger.info("M2Quant: TGA=%s RRP=%s", tga, rrp)
    return tga, rrp


# ─── Economic calendar scraper ───────────────────────────────────
# Uses investing.com HTML (light scrap) as fallback.
# Primary: free API from econ-calendar if available.

EVENT_IMPACT_KEYWORDS_HIGH = [
    "cpi", "consumer price", "inflation", "nfp", "nonfarm",
    "fomc", "fed decision", "interest rate", "gdp",
    "unemployment", "retail sales",
]


def _classify_impact(event_name: str) -> str:
    name_lower = event_name.lower()
    for kw in EVENT_IMPACT_KEYWORDS_HIGH:
        if kw in name_lower:
            return "High"
    return "Medium"


async def fetch_calendar() -> List[CalendarEvent]:
    """Fetch upcoming economic events from investing.com."""
    url = "https://www.investing.com/economic-calendar/"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
    }

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            r = await client.get(url, headers=headers)
            r.raise_for_status()
    except Exception as e:
        logger.warning("Calendar fetch failed: %s", e)
        return []

    soup = BeautifulSoup(r.text, "lxml")
    rows = soup.select("table#economicCalendarData tbody tr")
    if not rows:
        rows = soup.select("tr.js-event-item")

    events: List[CalendarEvent] = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for row in rows:
        try:
            date_el = row.select_one("td.time, td.date, .date")
            date_str = date_el.text.strip() if date_el else today

            time_el = row.select_one("td.time, .time")
            time_str = time_el.text.strip() if time_el else ""

            flag_el = row.select_one("td.flagCur, .flagCur, .currency")
            currency = flag_el.text.strip() if flag_el else "USD"

            event_el = row.select_one("td.event, .event")
            if not event_el:
                continue
            event_name = event_el.text.strip()

            impact_el = row.select_one("td.impact, .sentiment, .bull")
            impact = "Medium"
            if impact_el:
                ico = impact_el.select_one("i.greenIcon, i.orangeIcon, i.redIcon")
                if ico:
                    cls = ico.get("class", [])
                    if any("red" in c for c in cls):
                        impact = "High"
                    elif any("orange" in c for c in cls):
                        impact = "Medium"
                    else:
                        impact = "Low"
            else:
                impact = _classify_impact(event_name)

            prev_el = row.select_one("td.prev, .prev")
            fore_el = row.select_one("td.fore, .forecast")

            events.append(
                CalendarEvent(
                    date=date_str,
                    time=time_str,
                    currency=currency,
                    event=event_name,
                    forecast=fore_el.text.strip() if fore_el else "",
                    previous=prev_el.text.strip() if prev_el else "",
                    impact=impact,
                )
            )
        except Exception:
            continue

    logger.info("Calendar: %d events parsed", len(events))
    return events


async def get_high_impact_events(next_days: int = 7) -> List[CalendarEvent]:
    """Return high-impact events in the next N days."""
    events = await fetch_calendar()
    return [e for e in events if e.impact == "High"][:20]


async def get_liquidity_snapshot() -> MacroSnapshot:
    """Return current TGA/RRP snapshot."""
    tga, rrp = await fetch_m2quant()
    return MacroSnapshot(
        tga_billion=tga,
        rrp_billion=rrp,
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )