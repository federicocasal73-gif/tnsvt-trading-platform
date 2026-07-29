"""
Handler: Weekly Calendar — Resumen semanal de eventos macro.

Cada lunes a las 9:30 ART publica los próximos eventos ALTO impacto
de la semana, agrupados por día.

Loop independiente. Comando admin /resumen_semana para forzar manualmente.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Iterable

import pytz
from telegram import Update
from telegram.ext import ContextTypes
from config import settings
from bot.constants import (
    TNSVT_BRAND_LINE,
    TNSVT_SHORT_DISCLAIMER,
    WEEKLY_CALENDAR_HOUR,
    WEEKLY_CALENDAR_MINUTE,
)
from bot.analytics.calendar import (
    get_calendar_events,
    clear_cache,
    format_calendar_text,
)

logger = logging.getLogger("Bot.Handlers.WeeklyCalendar")

ART = pytz.timezone("America/Argentina/Buenos_Aires")

_last_publish_iso: str | None = None


def _next_monday_target(now_art: datetime, hour: int, minute: int) -> datetime:
    target = now_art.replace(
        hour=hour, minute=minute, second=0, microsecond=0,
    )
    days_ahead = (0 - now_art.weekday()) % 7
    if days_ahead == 0 and now_art >= target:
        days_ahead = 7
    return target + timedelta(days=days_ahead)


def _group_by_date(events: Iterable[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for ev in events:
        d = ev.get("date", "?")
        grouped.setdefault(d, []).append(ev)
    return grouped


def _weekday_label(date_str: str) -> str:
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        names = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
        return names[dt.weekday()]
    except Exception:
        return "?"


async def _publish_weekly_calendar(app) -> None:
    target = settings.BOT_GROUP_ID
    if not target:
        logger.warning("weekly_calendar: BOT_GROUP_ID no configurado")
        return

    bot = app.bot if hasattr(app, "bot") else app.bot

    clear_cache()

    try:
        events = await get_calendar_events(days=7)
    except Exception as e:
        logger.error(f"weekly_calendar: error fetching events: {e}")
        events = []

    high = [e for e in events if e.get("impact_level", 0) == 3]

    if not high:
        try:
            await bot.send_message(
                chat_id=target,
                text=(
                    "📅 *RESUMEN SEMANAL*\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "Sin eventos ALTO impacto esta semana.\n\n"
                    f"{TNSVT_SHORT_DISCLAIMER}"
                ),
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"weekly_calendar: fallo publicando 'sin eventos': {e}")
        return

    grouped = _group_by_date(high)

    lines = [
        "📅 *RESUMEN SEMANAL — Eventos macro ALTO impacto*",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"🗓 Semana del {datetime.now(ART).strftime('%d/%m/%Y')}",
        "",
    ]

    for date_str in sorted(grouped.keys()):
        day_evts = grouped[date_str]
        wd = _weekday_label(date_str)
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            date_fmt = dt.strftime("%d/%m")
        except Exception:
            date_fmt = date_str

        lines.append(f"📆 *{wd} {date_fmt}*")

        for ev in day_evts[:6]:
            country = ev.get("country", "")
            event_name = ev.get("event", "?")
            time_str = ev.get("time", "")
            forecast = ev.get("forecast", "-")
            previous = ev.get("previous", "-")
            line = f"  🔴 `{time_str} ART` — {event_name} ({country})"
            if forecast != "-" or previous != "-":
                line += f"\n      📊 Prev: {previous} | Est: {forecast}"
            lines.append(line)

        lines.append("")

    lines.append(TNSVT_SHORT_DISCLAIMER)

    msg = "\n".join(lines)

    try:
        await bot.send_message(
            chat_id=target,
            text=msg,
            parse_mode="Markdown",
            disable_notification=False,
        )
        logger.info(
            f"weekly_calendar: publicado {len(high)} eventos en {len(grouped)} dias"
        )
    except Exception as e:
        logger.error(f"weekly_calendar: fallo publicando: {e}")


async def weekly_calendar_loop(app):
    """Loop asincrono. Duerme hasta el próximo lunes 9:30 ART y publica."""
    logger.info("weekly_calendar_loop arrancado")

    global _last_publish_iso

    while True:
        try:
            now_art = datetime.now(ART)
            next_run = _next_monday_target(
                now_art, WEEKLY_CALENDAR_HOUR, WEEKLY_CALENDAR_MINUTE,
            )
            secs = (next_run - now_art).total_seconds()
            logger.info(
                f"weekly_calendar: proxima corrida en {secs/3600:.1f}h ({next_run})"
            )
            await asyncio.sleep(secs)

            now_iso = datetime.now(ART).isoformat()
            if _last_publish_iso:
                try:
                    last = datetime.fromisoformat(_last_publish_iso)
                    if last.tzinfo is None:
                        last = ART.localize(last)
                    if (datetime.now(ART) - last) < timedelta(hours=24):
                        logger.debug(
                            f"weekly_calendar: ya publicado hoy ({_last_publish_iso})"
                        )
                        await asyncio.sleep(60)
                        continue
                except Exception:
                    pass

            await _publish_weekly_calendar(app)
            _last_publish_iso = now_iso

        except Exception as e:
            logger.error(f"weekly_calendar_loop tick error: {e}")
            await asyncio.sleep(300)


async def force_calendar_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE,
):
    """Comando admin /resumen_semana — fuerza publicación manual."""
    user_id = update.effective_user.id if update.effective_user else 0
    admins = settings.BOT_ADMIN_IDS or []
    if not admins or user_id not in admins:
        await update.message.reply_text(
            "❌ Solo el admin puede forzar el resumen semanal."
        )
        return

    await update.message.reply_text("🔄 Generando resumen semanal...")
    global _last_publish_iso
    _last_publish_iso = None
    await _publish_weekly_calendar(context.application)
    await update.message.reply_text("✅ Resumen semanal publicado.")
