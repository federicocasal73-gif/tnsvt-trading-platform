"""
Handler: Weekly Poll — Encuesta semanal de sentimiento por instrumento.

Cada lunes a las 9:00 ART publica 5 polls Telegram nativos
(BTCUSD, XAUUSD, EURUSD, DXY, NAS100) con opciones:
  🟢 Alcista | 🔴 Bajista | 🟡 Rango | ⚪ Afuera

Loop independiente con cleanup de duplicados.
Comando admin /encuesta para forzar manualmente.
"""
import asyncio
import logging
from datetime import datetime, timedelta

import pytz
from telegram import Update
from telegram.ext import ContextTypes
from config import settings
from bot.constants import (
    TNSVT_BRAND_LINE,
    TNSVT_SHORT_DISCLAIMER,
    POLL_INSTRUMENTS,
    POLL_OPTIONS,
    WEEKLY_POLL_HOUR,
)

logger = logging.getLogger("Bot.Handlers.WeeklyPoll")

ART = pytz.timezone("America/Argentina/Buenos_Aires")

_last_publish_iso: str | None = None


def _next_monday_9am(now_art: datetime) -> datetime:
    """Próximo lunes 9:00 ART. Si hoy es lunes y ya pasó, devuelve el siguiente."""
    target = now_art.replace(
        hour=WEEKLY_POLL_HOUR, minute=0, second=0, microsecond=0,
    )
    days_ahead = (0 - now_art.weekday()) % 7
    if days_ahead == 0 and now_art >= target:
        days_ahead = 7
    return target + timedelta(days=days_ahead)


def _is_monday_9am_window(now_art: datetime) -> bool:
    """True si estamos dentro de la ventana de 5 min para publicar."""
    if now_art.weekday() != 0:
        return False
    target_hour = now_art.replace(
        hour=WEEKLY_POLL_HOUR, minute=0, second=0, microsecond=0,
    )
    return target_hour <= now_art < target_hour + timedelta(minutes=5)


async def _publish_polls(app, context=None) -> None:
    """Publica 5 polls Telegram nativos en el grupo."""
    target = settings.BOT_GROUP_ID
    if not target:
        logger.warning("weekly_poll: BOT_GROUP_ID no configurado")
        return

    bot = app.bot if hasattr(app, "bot") else context.bot

    header = (
        f"📊 *ENCUESTA SEMANAL — Sentimiento de mercado*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🗓 Semana del {datetime.now(ART).strftime('%d/%m/%Y')}\n"
        f"🎯 Votá tu visión para los próximos 5 días.\n\n"
        f"{TNSVT_SHORT_DISCLAIMER}"
    )

    try:
        await bot.send_message(
            chat_id=target,
            text=header,
            parse_mode="Markdown",
            disable_notification=False,
        )
        logger.info("weekly_poll: header publicado")
    except Exception as e:
        logger.error(f"weekly_poll: fallo publicando header: {e}")

    polls_ok = 0
    polls_fail = 0

    for symbol in POLL_INSTRUMENTS:
        question = f"¿Cómo ves {symbol} esta semana?"
        try:
            await bot.send_poll(
                chat_id=target,
                question=question,
                options=POLL_OPTIONS,
                is_anonymous=True,
                allows_multiple_answers=False,
            )
            polls_ok += 1
            logger.info(f"weekly_poll: poll {symbol} publicado")
        except Exception as e:
            polls_fail += 1
            logger.warning(
                f"weekly_poll: fallo publicando poll {symbol}: {e}"
            )
            try:
                fallback = (
                    f"📊 *Encuesta semanal — {symbol}*\n"
                    f"¿Cómo ves *{symbol}* esta semana?\n"
                    f"• 🟢 Alcista\n• 🔴 Bajista\n• 🟡 Rango\n• ⚪ Afuera\n"
                    f"_Respondé en el chat_"
                )
                await bot.send_message(
                    chat_id=target,
                    text=fallback,
                    parse_mode="Markdown",
                )
            except Exception as e2:
                logger.error(f"weekly_poll: fallback tambien fallo: {e2}")

        await asyncio.sleep(0.5)

    logger.info(
        f"weekly_poll: completo OK={polls_ok}/{len(POLL_INSTRUMENTS)} FAIL={polls_fail}"
    )


async def weekly_poll_loop(app):
    """Loop asincrono. Duerme hasta el próximo lunes 9:00 ART y publica."""
    logger.info(
        f"weekly_poll_loop arrancado (instrumentos={POLL_INSTRUMENTS})"
    )

    global _last_publish_iso

    while True:
        try:
            now_art = datetime.now(ART)
            next_run = _next_monday_9am(now_art)
            secs = (next_run - now_art).total_seconds()
            logger.info(
                f"weekly_poll: proxima corrida en {secs/3600:.1f}h ({next_run})"
            )
            await asyncio.sleep(secs)

            now_iso = datetime.now(ART).isoformat()
            if _last_publish_iso and _is_within_last_24h(_last_publish_iso):
                logger.debug(
                    f"weekly_poll: ya publicado hoy ({_last_publish_iso}), skip"
                )
                await asyncio.sleep(60)
                continue

            await _publish_polls(app)
            _last_publish_iso = now_iso

        except Exception as e:
            logger.error(f"weekly_poll_loop tick error: {e}")
            await asyncio.sleep(300)


def _is_within_last_24h(iso_str: str) -> bool:
    try:
        last = datetime.fromisoformat(iso_str)
        if last.tzinfo is None:
            last = ART.localize(last)
        return (datetime.now(ART) - last) < timedelta(hours=24)
    except Exception:
        return False


async def force_poll_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando admin /encuesta — fuerza publicación manual de polls."""
    user_id = update.effective_user.id if update.effective_user else 0
    admins = settings.BOT_ADMIN_IDS or []
    if not admins or user_id not in admins:
        await update.message.reply_text(
            "❌ Solo el admin puede forzar la encuesta semanal."
        )
        return

    await update.message.reply_text("🔄 Publicando encuestas semanales...")
    global _last_publish_iso
    _last_publish_iso = None
    await _publish_polls(context.application, context=context)
    await update.message.reply_text(
        f"✅ {len(POLL_INSTRUMENTS)} encuestas publicadas."
    )
