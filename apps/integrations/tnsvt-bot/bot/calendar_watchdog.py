"""
Calendar Watchdog — Avisa si hay un evento economico ALTO impacto y hay
posiciones abiertas en MT5.

3 etapas de alerta:
  15min ⚠️  → primera advertencia
  5min  🔥  → segunda advertencia
  1min  🚨  → alerta final

Corre cada 60s. Solo publica si ambas condiciones son verdaderas:
  1. Evento ALTO impacto detectado en alguna ventana
  2. Hay posiciones abiertas en MT5 (positions.json)
"""
import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytz
import requests

from config import settings
from bot.analytics.calendar import get_calendar_events

logger = logging.getLogger("Bot.CalendarWatchdog")

ART = pytz.timezone("America/Argentina/Buenos_Aires")
BRIDGE_URL = "http://localhost:8522"
POSITIONS_PATH = Path(r"D:\TradingBotMT5\positions_snapshot.json")

INTERVAL_SEC = 60

# 3 etapas de alerta: (minutos, emoji, label)
ALERT_STAGES = [
    (15, "⚠️", "15 minutos"),
    (5,  "🔥", "5 minutos"),
    (1,  "🚨", "1 minuto"),
]

_warned_events: dict[str, set[int]] = {}


def _is_in_window(event_dt_utc: datetime, window_min: int) -> bool:
    """True si el evento esta entre (now, now+window_min)."""
    now = datetime.now(timezone.utc)
    delta = event_dt_utc - now
    return timedelta(0) <= delta <= timedelta(minutes=window_min)


def _minutes_to_event(event_dt_utc: datetime) -> int:
    return max(0, int((event_dt_utc - datetime.now(timezone.utc)).total_seconds() / 60))


def _best_stage(minutes_left: int) -> tuple[int, str, str] | None:
    """Devuelve la etapa mas ajustada que aun no paso."""
    for mins, emoji, label in sorted(ALERT_STAGES, key=lambda x: -x[0]):
        if minutes_left >= mins:
            return mins, emoji, label
    return None


def _parse_event_dt(ev: dict) -> datetime | None:
    """Parsea fecha+hora del evento segun Investing.com."""
    try:
        ds = ev.get("date", "")
        ts = ev.get("time", "")
        if not ds:
            return None
        dt_naive = datetime.strptime(ds, "%Y-%m-%d")
        if ts and ":" in ts:
            try:
                hh, mm = ts.split(":")[:2]
                dt_naive = dt_naive.replace(hour=int(hh), minute=int(mm))
            except Exception:
                pass
        return ART.localize(dt_naive).astimezone(timezone.utc)
    except Exception as e:
        logger.debug(f"_parse_event_dt error: {e}")
        return None


def _read_open_positions() -> list:
    try:
        if not POSITIONS_PATH.exists():
            return []
        with open(POSITIONS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.debug(f"_read_open_positions error: {e}")
        return []


def _alert_key(ev: dict) -> str:
    return f"{ev.get('date', '')}_{ev.get('time', '')}_{ev.get('event', '')}"


async def _publish_alert(app, event: dict, stage_mins: int, stage_emoji: str,
                         stage_label: str, minutes_left: int, positions: list) -> None:
    target = settings.BOT_GROUP_ID
    if not target:
        return

    pos_lines = []
    for p in positions[:5]:
        sym = p.get("symbol", "?")
        tipo = p.get("type", "?")
        vol = p.get("volume", 0)
        pnl = float(p.get("profit", 0) or 0)
        emoji = "🟢" if pnl >= 0 else "🔴"
        pos_lines.append(f"  • `{sym}` ({tipo}) vol={vol} {emoji} `{pnl:+.2f}`")

    if len(positions) > 5:
        pos_lines.append(f"  • ... y {len(positions)-5} mas")

    urgency = "⚠️" if minutes_left > 10 else ("🔥" if minutes_left > 3 else "🚨")

    msg = (
        f"{urgency} *EVENTO ALTO IMPACTO EN {stage_label}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔴 {event.get('country', '')} | {event.get('event', '')}\n"
        f"🕐 {event.get('date', '')} {event.get('time', '')} ART\n"
        f"📊 Previous: `{event.get('previous', '-')}` | "
        f"Forecast: `{event.get('forecast', '-')}`\n\n"
        f"📂 *Posiciones abiertas ({len(positions)}):*\n"
        + "\n".join(pos_lines) + "\n\n"
        f"💡 Considerá cerrar posiciones antes del evento."
    )

    try:
        await app.bot.send_message(
            chat_id=target,
            text=msg,
            parse_mode="Markdown",
        )
        logger.info(
            f"calendar_watchdog: alerta {stage_label} por {event.get('event')} "
            f"en {minutes_left}min, {len(positions)} posiciones"
        )
    except Exception as e:
        logger.error(f"calendar_watchdog: fallo publicando: {e}")


async def calendar_watchdog_loop(app, interval_sec: int = INTERVAL_SEC):
    """Loop principal. Chequea calendario cada 60s y avisa al grupo."""
    logger.info(
        f"calendar_watchdog arrancado (interval={interval_sec}s, "
        f"etapas={[m for m,_,_ in ALERT_STAGES]})"
    )

    await asyncio.sleep(30)

    while True:
        try:
            events = await get_calendar_events(days=1)
            if not events:
                await asyncio.sleep(interval_sec)
                continue

            high_events = [
                e for e in events
                if e.get("impact_level", 0) == 3
            ]

            for ev in high_events:
                evt_dt = _parse_event_dt(ev)
                if not evt_dt:
                    continue

                minutes_left = _minutes_to_event(evt_dt)

                stage = _best_stage(minutes_left)
                if not stage:
                    continue

                stage_mins, stage_emoji, stage_label = stage
                key = _alert_key(ev)

                # Inicializar set de etapas ya avisadas
                if key not in _warned_events:
                    _warned_events[key] = set()

                # Si esta etapa ya fue avisada, skip
                if stage_mins in _warned_events[key]:
                    continue

                positions = await asyncio.get_event_loop().run_in_executor(
                    None, _read_open_positions
                )
                if not positions:
                    logger.debug(
                        f"calendar_watchdog: evento {ev.get('event')} "
                        f"en ventana {stage_label} pero sin posiciones, skip"
                    )
                    # Marcamos igual para no re-intentar sin posiciones
                    _warned_events[key].add(stage_mins)
                    continue

                await _publish_alert(
                    app, ev, stage_mins, stage_emoji,
                    stage_label, minutes_left, positions
                )
                _warned_events[key].add(stage_mins)

            # Limpiar eventos viejos (>24h)
            cutoff = datetime.now().timestamp() - 86400
            # No tenemos timestamp, limpiar por clave si paso mucho tiempo
            if len(_warned_events) > 200:
                _warned_events.clear()
                logger.debug("calendar_watchdog: limpieza de _warned_events")

        except Exception as e:
            logger.error(f"calendar_watchdog tick error: {e}")

        await asyncio.sleep(interval_sec)
