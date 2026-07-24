"""
Handler: /calendario, /mercados, /cripto

Usa el scraper real de Investing.com (analytics/calendar.py) en lugar
del fake anterior que mostraba headlines de noticias.
"""
import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes
from bot.services import markets
from bot.analytics.calendar import get_calendar_events, format_calendar_text

logger = logging.getLogger("Bot.Handlers.Calendar")


async def calendario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra eventos economicos reales (Investing.com scraper)"""
    try:
        user = update.effective_user
        logger.info(f"Comando /calendario desde {user.username or user.id}")

        await update.message.reply_text("🔄 Buscando eventos económicos reales...")

        events = await get_calendar_events(days=7)
        texto = format_calendar_text(events, max_events=15)
        await update.message.reply_text(texto, parse_mode="Markdown")

        if not events:
            await update.message.reply_text(
                "⚠️ No se pudieron obtener eventos. Reintentá en unos minutos."
            )
    except Exception as e:
        logger.error(f"Error en /calendario: {e}")
        await update.message.reply_text("⚠️ Error al obtener eventos económicos.")


async def calendariosolo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Devuelve SOLO los eventos de ALTO impacto de los próximos 3 días.

    Usado por el job diario del watchdog y por /calendarioalto.
    """
    try:
        events = await get_calendar_events(days=3)
        high = [e for e in events if e.get("impact_level", 0) == 3]
        return high
    except Exception as e:
        logger.error(f"Error calendariosolo: {e}")
        return []


async def mercados(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra resumen de mercados"""
    try:
        user = update.effective_user
        logger.info(f"Comando /mercados desde {user.username or user.id}")

        await update.message.reply_text("🔄 Obteniendo datos de mercados...")

        texto = markets.get_market_overview()
        await update.message.reply_text(texto, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error en /mercados: {e}")
        await update.message.reply_text("⚠️ Error al obtener mercados.")


async def cripto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra precios de criptomonedas"""
    try:
        user = update.effective_user
        logger.info(f"Comando /cripto desde {user.username or user.id}")

        await update.message.reply_text("🔄 Obteniendo precios de cripto...")

        texto = markets.get_crypto_prices()
        await update.message.reply_text(texto, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error en /cripto: {e}")
        await update.message.reply_text("⚠️ Error al obtener criptomonedas.")
