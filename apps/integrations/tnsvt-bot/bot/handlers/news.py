"""
Handler: /noticias, /ipc, /morgan, /datos
"""
import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes
from bot.services import news_api, trading_economics, cpi

logger = logging.getLogger("Bot.Handlers.News")


async def noticias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Noticias de mercados y bolsa"""
    try:
        user = update.effective_user
        logger.info(f"Comando /noticias desde {user.username or user.id}")

        await update.message.reply_text("🔄 Buscando noticias de mercados...")

        texto = await asyncio.to_thread(news_api.get_market_news, 5)
        await update.message.reply_text(texto, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error en /noticias: {e}")
        await update.message.reply_text("⚠️ Error al obtener noticias.")


async def ipc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Datos reales del IPC de EEUU (BLS.gov)"""
    try:
        user = update.effective_user
        logger.info(f"Comando /ipc desde {user.username or user.id}")

        await update.message.reply_text("🔄 Obteniendo datos del IPC de EEUU...")

        data = await asyncio.to_thread(cpi.get_cpi_data)
        texto = cpi.format_cpi_message(data)

        if data.get("error"):
            await update.message.reply_text(
                "⚠️ No se pudo obtener datos del IPC.\n"
                "Intenta con /noticias para ver noticias de inflacion."
            )
        else:
            await update.message.reply_text(texto, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error en /ipc: {e}")
        await update.message.reply_text("⚠️ Error al obtener datos del IPC.")


async def morgan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Noticias de empresas y Wall Street"""
    try:
        user = update.effective_user
        logger.info(f"Comando /morgan desde {user.username or user.id}")

        await update.message.reply_text("🔄 Buscando noticias de empresas...")

        texto = news_api.get_wall_street_news(page_size=5)
        await update.message.reply_text(texto, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error en /morgan: {e}")
        await update.message.reply_text("⚠️ Error al obtener noticias.")


async def datos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Datos macroeconomicos por pais"""
    try:
        user = update.effective_user

        if not context.args:
            await update.message.reply_text(
                "📍 *Uso:*\n"
                "`/datos ARG` - Argentina\n"
                "`/datos USA` - Estados Unidos",
                parse_mode="Markdown",
            )
            return

        country = context.args[0].upper()
        logger.info(f"Comando /datos {country} desde {user.username or user.id}")

        await update.message.reply_text(f"🔄 Obteniendo datos de {country}...")

        if not trading_economics._initialized:
            await update.message.reply_text(
                "⚠️ TradingEconomics no esta disponible.\n"
                "Usa /mercados para ver datos de mercados."
            )
            return

        indicators = trading_economics.get_indicators(country=country)
        texto = trading_economics.format_indicators(country, indicators)
        await update.message.reply_text(texto, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error en /datos: {e}")
        await update.message.reply_text("⚠️ Error al obtener datos.")
