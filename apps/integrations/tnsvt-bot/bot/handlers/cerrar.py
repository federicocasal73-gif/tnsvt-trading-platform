"""
Handler: /cerrar SYMBOL — Cierra posiciones abiertas para un símbolo.

Flujo:
  1. User: /cerrar XAUUSD
  2. Bot llama a bridge-api POST /api/v1/bridge/copier/close
  3. bridge-api escribe comando a D:\\TradingBotMT5\\cmd_requests.json
  4. El signal_copier poll (lo agregamos) lee el comando y cierra las posiciones
     usando MT5Executor._close_positions(symbol).

Si el símbolo no tiene posiciones abiertas, devuelve error.
"""
import asyncio
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger("Bot.Handlers.Cerrar")

BASE_URL = "http://localhost:8522"


async def cerrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cierra posiciones del símbolo especificado."""
    try:
        user = update.effective_user
        if not context.args:
            await update.message.reply_text(
                "❌ *Uso:* `/cerrar SYMBOL`\n"
                "Ejemplo: `/cerrar XAUUSD` o `/cerrar EURUSD`",
                parse_mode="Markdown",
            )
            return

        symbol = context.args[0].upper().strip()
        logger.info(f"Comando /cerrar {symbol} desde {user.username or user.id}")

        await update.message.reply_text(
            f"🔒 Cerrando posiciones de *{symbol}*...",
            parse_mode="Markdown",
        )

        # POST al bridge-api
        loop = asyncio.get_event_loop()
        def _do_close():
            return requests.post(
                f"{BASE_URL}/api/v1/bridge/copier/close",
                json={"action": "close", "symbol": symbol, "by_user": str(user.id)},
                timeout=5,
            )

        resp = await loop.run_in_executor(None, _do_close)

        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                await update.message.reply_text(
                    f"✅ Comando enviado para cerrar *{symbol}*\n"
                    f"Positiones que se cerraran: {data.get('open_positions', '?')}\n\n"
                    "_El signal_copier procesara el comando en su proximo poll._",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Refrescar", callback_data="senales:menu")],
                        [InlineKeyboardButton("📋 Menú principal", callback_data="cmd:refresh")],
                    ]),
                )
            else:
                await update.message.reply_text(
                    f"⚠️ {data.get('detail', 'No se pudo cerrar')}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Volver", callback_data="senales:menu")],
                    ]),
                )
        else:
            await update.message.reply_text(
                f"⚠️ Error del bridge-api: HTTP {resp.status_code}"
            )
    except Exception as e:
        logger.error(f"Error en /cerrar: {e}")
        await update.message.reply_text("⚠️ Error al ejecutar el cierre.")
