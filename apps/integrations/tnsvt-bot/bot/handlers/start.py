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
• /zona SYMBOL — Análisis profundo de un par
• /z SYMBOL — Atajo de /zona
• /reporte SIMBOLO — Multi-timeframe
• /r SIMBOLO — Atajo de /reporte
• /analisis — Panorama 5 pares
• /grafico — Equity curve

📈 *Mercados*
• /mercados — Resumen global
• /cripto — Criptomonedas
• /calendario — Calendario economico real
• /noticias — Ultimas noticias

📡 *Senales & Trades*
• /status — Dashboard completo del sistema
• /statshoy — Stats del dia
• /historial — Trades 7/30 dias
• /canales — Canales Telegram monitoreados
• /cerrar SYMBOL — Cerrar posiciones (solo admin)
• /cuentas — Cuentas MT5 multi-cuenta

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
