"""
Trade Alerts — Live notifications for trade open/close events.

Signal copier calls these functions when a trade is opened or closed.
Alerts are sent to admin DMs in real-time.
"""
import logging
from telegram.ext import ContextTypes
from config import settings

logger = logging.getLogger("Bot.Handlers.TradeAlerts")


async def send_trade_open_alert(context: ContextTypes.DEFAULT_TYPE, symbol: str, action: str,
                                  price: float, sl: float, tp: float, rr: float = 0):
    admin_ids = settings.BOT_ADMIN_IDS
    if not admin_ids:
        return

    action_emoji = "🟢 COMPRA" if action.upper() in ("BUY", "COMPRA", "LONG") else "🔴 VENTA"
    text = (
        f"🚀 *Trade Abierto*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{action_emoji} *{symbol}*\n"
        f"Precio: `{price}`\n"
        f"SL: `{sl}`\n"
        f"TP: `{tp}`\n"
    )
    if rr:
        text += f"RR: `1:{rr:.1f}`\n"

    for admin_id in admin_ids:
        try:
            await context.bot.send_message(chat_id=admin_id, text=text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error send_trade_open_alert: {e}")


async def send_trade_close_alert(context: ContextTypes.DEFAULT_TYPE, symbol: str, action: str,
                                  pnl: float, result: str, price: float = 0):
    admin_ids = settings.BOT_ADMIN_IDS
    if not admin_ids:
        return

    pnl_emoji = "🟢" if pnl > 0 else ("🔴" if pnl < 0 else "⚪")
    result_emoji = "✅" if result.upper() in ("WIN", "TP") else "❌"

    text = (
        f"{result_emoji} *Trade Cerrado*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{symbol} ({action})\n"
        f"Resultado: {result}\n"
        f"PnL: {pnl_emoji} `${pnl:+.2f}`\n"
    )
    if price:
        text += f"Precio salida: `{price}`\n"

    for admin_id in admin_ids:
        try:
            await context.bot.send_message(chat_id=admin_id, text=text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error send_trade_close_alert: {e}")


async def send_blocked_trade_alert(context: ContextTypes.DEFAULT_TYPE, symbol: str,
                                    reason: str, score: int = 0):
    admin_ids = settings.BOT_ADMIN_IDS
    if not admin_ids:
        return

    text = (
        f"🚫 *Trade Bloqueado*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{symbol}\n"
        f"Razón: {reason}\n"
    )
    if score:
        text += f"Score AMB: `{score}/100`\n"

    for admin_id in admin_ids:
        try:
            await context.bot.send_message(chat_id=admin_id, text=text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error send_blocked_trade_alert: {e}")
