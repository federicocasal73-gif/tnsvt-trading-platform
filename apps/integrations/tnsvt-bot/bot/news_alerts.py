"""
News Alerts — Countdown de eventos económicos ALTO impacto cada 5 minutos.

A diferencia de calendar_watchdog (que solo alerta si hay posiciones abiertas),
este módulo siempre alerta, con foco en IPC e IPP.

Ciclo de alerta:
- Cada 5 minutos revisa los próximos eventos ALTO impacto
- 15 min antes → 🚨 primera alerta con countdown
- 10 min antes → ⏰ recordatorio
- 5 min antes  → 🔥 alerta final
- 1 min antes  → 🚨 última llamada
- También publica al grupo automáticamente
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

import pytz

from config import settings
from bot.analytics.calendar import get_calendar_events

logger = logging.getLogger("Bot.NewsAlerts")

ART = pytz.timezone("America/Argentina/Buenos_Aires")
POLL_INTERVAL = 300

KEYWORDS_HIGHLIGHT = {
    "cpi": "📊 IPC",
    "consumer price index": "📊 IPC",
    "ppi": "📊 IPP",
    "producer price index": "📊 IPP",
    "fomc": "🏦 FOMC",
    "fed interest rate": "🏦 FED",
    "non farm": "📋 NFP",
    "employment": "📋 EMPLEO",
    "gdp": "📈 GDP",
    "retail sales": "🛒 VENTAS MINORISTAS",
}

ALERT_STAGES = [(15, "🚨"), (10, "⏰"), (5, "🔥"), (1, "🚨")]

_notified: dict[str, set[int]] = {}


def _find_highlight(event_name: str) -> str | None:
    low = event_name.lower()
    for kw, label in KEYWORDS_HIGHLIGHT.items():
        if kw in low:
            return label
    return None


def _parse_event_dt(ev: dict) -> datetime | None:
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
    except Exception:
        return None


def _minutes_until(event_dt_utc: datetime) -> int:
    return max(0, int((event_dt_utc - datetime.now(timezone.utc)).total_seconds() / 60))


def _event_key(ev: dict) -> str:
    return f"{ev.get('date', '')}_{ev.get('time', '')}_{ev.get('event', '')}"


async def news_alerts_loop(app):
    logger.info(f"news_alerts arrancado (poll={POLL_INTERVAL}s)")
    await asyncio.sleep(15)

    while True:
        try:
            events = await get_calendar_events(days=3)
            if not events:
                await asyncio.sleep(POLL_INTERVAL)
                continue

            high_events = [e for e in events if e.get("impact_level", 0) == 3]
            now = datetime.now(ART)

            for ev in high_events:
                evt_dt = _parse_event_dt(ev)
                if not evt_dt:
                    continue

                mins_left = _minutes_until(evt_dt)
                key = _event_key(ev)

                if key not in _notified:
                    _notified[key] = set()

                highlight = _find_highlight(ev.get("event", ""))

                # Solo apto para stage si mins_left es exactamente o está cerca de un stage
                # Buscamos el stage más cercano: 1, 5, 10, 15
                for stage_min, stage_emoji in ALERT_STAGES:
                    # Notificar si mins_left está en [stage_min, stage_min + 2]
                    # y no hemos notificado este stage aún
                    if stage_min <= mins_left <= stage_min + 3:
                        if stage_min not in _notified[key]:
                            await _send_alert(app, ev, stage_min, stage_emoji, mins_left, highlight)
                            _notified[key].add(stage_min)

            # Cleanup: eventos pasados hace > 1 hora
            cutoff = datetime.now().timestamp() - 3600
            for k in list(_notified.keys()):
                parts = k.split("_", 2)
                if len(parts) >= 2:
                    try:
                        dt = datetime.strptime(parts[0] + "_" + parts[1], "%Y-%m-%d_%H:%M")
                        if dt.timestamp() < cutoff:
                            del _notified[k]
                    except Exception:
                        pass

            if len(_notified) > 500:
                _notified.clear()

        except Exception as e:
            logger.error(f"news_alerts tick error: {e}")

        await asyncio.sleep(POLL_INTERVAL)


async def _send_alert(app, ev: dict, stage_min: int, stage_emoji: str,
                      mins_left: int, highlight: str | None):
    target = settings.BOT_GROUP_ID
    admin_ids = settings.BOT_ADMIN_IDS
    if not target and not admin_ids:
        return

    event_name = ev.get("event", "?")
    country = ev.get("country", "")
    date_str = ev.get("date", "")
    time_str = ev.get("time", "")
    previous = ev.get("previous", "-")
    forecast = ev.get("forecast", "-")

    # Si es IPC o IPP, usamos emoji especial
    header_emoji = stage_emoji
    header_text = f"EVENTO ECONÓMICO ALTO IMPACTO"
    if highlight:
        header_text = f"{highlight}"
        if "IPC" in highlight or "IPP" in highlight:
            header_emoji = "📊"

    msg = (
        f"{header_emoji} *{header_text}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔴 {country} | {event_name}\n"
        f"🕐 {date_str} {time_str} ART\n"
        f"⏱ Faltan *{mins_left} min*\n"
        f"📊 Anterior: `{previous}` | Estimado: `{forecast}`\n"
        f"{'💡 Alta volatilidad esperada — tomar precauciones.' if highlight else ''}"
    )

    if target:
        try:
            await app.bot.send_message(chat_id=target, text=msg, parse_mode="Markdown")
            logger.info(f"news_alerts: publicado {event_name} ({stage_min}min) al grupo")
        except Exception as e:
            logger.error(f"news_alerts: error grupo: {e}")

    for admin_id in admin_ids:
        try:
            await app.bot.send_message(chat_id=admin_id, text=msg, parse_mode="Markdown")
            logger.info(f"news_alerts: DM a admin {admin_id} por {event_name}")
        except Exception as e:
            logger.error(f"news_alerts: error admin DM {admin_id}: {e}")


async def eventos_command(update, context):
    """Comando /eventos — muestra próximos eventos ALTO impacto."""
    from bot.handlers.calendar import calendariosolo

    try:
        events = await calendariosolo(None, None)
        if not events:
            await update.message.reply_text("📅 No hay eventos ALTO impacto próximos.")
            return

        high = [e for e in events if e.get("impact_level", 0) == 3]
        if not high:
            await update.message.reply_text("📅 No hay eventos ALTO impacto próximos.")
            return

        from bot.analytics.calendar import format_calendar_text
        text = format_calendar_text(high, max_events=10)

        msg = (
            "📅 *EVENTOS ECONÓMICOS — Próximos 3 días*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{text}\n"
            "🔔 Las alarmas automáticas avisan 15/10/5/1 min antes."
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"eventos_command error: {e}")
        await update.message.reply_text("⚠️ Error al consultar calendario.")
