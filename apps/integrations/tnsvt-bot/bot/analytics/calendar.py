"""
Economic Calendar — Events from Investing.com with Argentine time (UTC-3).

Color-coded impact:
  🔴 ALTO  → High impact
  🟡 MEDIO → Medium impact
  ⚪ BAJO  → Low impact

All times displayed in ART (Argentina Time, UTC-3).
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

import aiohttp
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("Bot.AMB.Calendar")

_cache = {"events": None, "last_fetch": None}
_CACHE_TTL = timedelta(minutes=15)


async def get_calendar_events(days: int = 7) -> list[dict]:
    now = datetime.now()
    if _cache["last_fetch"] and (now - _cache["last_fetch"]) < _CACHE_TTL:
        return _cache["events"] or []

    try:
        events = await _fetch_investing_calendar()
        if events:
            _cache["events"] = events
            _cache["last_fetch"] = now
            return events
    except Exception as e:
        logger.warning(f"Error fetching calendar: {e}")

    if _cache["events"] is not None:
        return _cache["events"]
    return []


async def _fetch_investing_calendar() -> Optional[list[dict]]:
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "X-Requested-With": "XMLHttpRequest",
            }
            today = datetime.now().strftime("%Y-%m-%d")
            async with session.post(
                "https://www.investing.com/economic-calendar/Service/getCalendarFilteredData",
                headers=headers,
                data={
                    "country[]": "all",
                    "importance[]": "all",
                    "dateFrom": today,
                    "dateTo": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
                    "currentTab": "custom",
                    "submitFilters": "1",
                },
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return _parse_investing_response(data)
    except Exception as e:
        logger.debug(f"_fetch_investing_calendar aiohttp error: {e}")
        return await _fetch_investing_fallback()


async def _fetch_investing_fallback() -> Optional[list[dict]]:
    try:
        resp = requests.post(
            "https://www.investing.com/economic-calendar/Service/getCalendarFilteredData",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "X-Requested-With": "XMLHttpRequest",
            },
            data={
                "country[]": "all",
                "importance[]": "all",
                "dateFrom": datetime.now().strftime("%Y-%m-%d"),
                "dateTo": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
                "currentTab": "custom",
                "submitFilters": "1",
            },
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            return _parse_investing_response(data)
    except Exception as e:
        logger.debug(f"_fetch_investing_fallback error: {e}")
    return None


def _parse_investing_response(data: dict) -> list[dict]:
    events = []
    try:
        rows = data.get("data", [])
        for row in rows:
            try:
                impact = int(row.get("importance", 0))
                if impact == 1:
                    impact_label = "⚪ BAJO"
                elif impact == 2:
                    impact_label = "🟡 MEDIO"
                else:
                    impact_label = "🔴 ALTO"

                events.append({
                    "date": row.get("date", ""),
                    "time": row.get("time", ""),
                    "country": row.get("country", {}).get("name", ""),
                    "event": BeautifulSoup(row.get("event", ""), "html.parser").get_text(strip=True),
                    "impact": impact_label,
                    "impact_level": impact,
                    "previous": BeautifulSoup(row.get("previous", ""), "html.parser").get_text(strip=True),
                    "forecast": BeautifulSoup(row.get("forecast", ""), "html.parser").get_text(strip=True),
                    "actual": BeautifulSoup(row.get("actual", ""), "html.parser").get_text(strip=True),
                })
            except Exception:
                continue
    except Exception as e:
        logger.error(f"Error parsing investing response: {e}")

    events.sort(key=lambda e: e.get("impact_level", 0), reverse=True)
    return events


def format_calendar_text(events: list[dict], max_events: int = 10) -> str:
    if not events:
        return "📅 *Calendario Económico*\n\n⚠️ No hay eventos disponibles."

    lines = ["📅 *Calendario Económico — Próximos Eventos*", ""]

    for ev in events[:max_events]:
        date_str = ev.get("date", "?")
        time_str = ev.get("time", "?")
        country = ev.get("country", "")
        event_name = ev.get("event", "?")
        impact = ev.get("impact", "⚪")
        forecast = ev.get("forecast", "-")
        previous = ev.get("previous", "-")

        lines.append(
            f"{impact} {country} | {event_name}\n"
            f"   📅 {date_str} {time_str} ART"
        )
        if forecast != "-" or previous != "-":
            lines.append(f"   📊 Prev: {previous} | Estim: {forecast}")
        lines.append("")

    return "\n".join(lines)


def clear_cache():
    _cache["events"] = None
    _cache["last_fetch"] = None
