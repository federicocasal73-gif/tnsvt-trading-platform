"""
Handler: /calendario, /mercados, /cripto
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes
from bot.services import news_api, markets

logger = logging.getLogger("Bot.Handlers.Calendar")


async def calendario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra eventos economicos proximos"""
    try:
        user = update.effective_user
        logger.info(f"Comando /calendario desde {user.username or user.id}")

        await update.message.reply_text("🔄 Buscando eventos economicos...")

        texto = news_api.get_economic_calendar(page_size=5)
        await update.message.reply_text(texto, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error en /calendario: {e}")
        await update.message.reply_text("⚠️ Error al obtener eventos economicos.")


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
