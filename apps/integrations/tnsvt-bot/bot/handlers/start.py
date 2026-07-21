"""
Handler: /start, /help — Menu principal con botones inline.
"""
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from bot.callbacks import main_menu_keyboard

logger = logging.getLogger("Bot.Handlers.Start")

MENU_TEXT = """💼 *Terminal Financiera Pro v3*

━━━━━━━━━━━━━━━━━━━━━━━━━

📊 *Analisis Tecnico*
• /reporte SIMBOLO — Multi-timeframe
• /r SIMBOLO — Atajo rapido
• /analisis — Panorama 5 pares
• /grafico — Equity curve

📈 *Mercados*
• /mercados — Resumen global
• /cripto — Criptomonedas
• /calendario — Calendario economico
• /noticias — Ultimas noticias

📡 *Senales*
• /senales — Senales copiadas (con botones)
• /statshoy — Stats de hoy
• /stats — Estadisticas detalladas
• /historial — Ultima semana
• /canales — Canales Telegram
• /cuentas — Cuentas MT5

━━━━━━━━━━━━━━━━━━━━━━━━━

Usa los botones para navegar, o escribe el comando directo"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja /start y /help — ahora con botones inline."""
    try:
        user = update.effective_user
        logger.info(f"Comando /start desde {user.username or user.id}")
        await update.message.reply_text(
            MENU_TEXT,
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )
    except Exception as e:
        logger.error(f"Error en /start: {e}")
        await update.message.reply_text("⚠️ Error al mostrar el menu.")
