"""
Handler: About — Brand description + auto-pinned en grupo.

Comando público /about que muestra descripción detallada del bot.
Adicionalmente, intenta pinear el mensaje en el grupo al iniciar
(si el bot tiene can_pin_messages).
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import settings
from bot.constants import (
    TNSVT_BRAND_LINE,
    TNSVT_DISCLAIMER,
    TNSVT_COVERAGE_FOOTER,
)

logger = logging.getLogger("Bot.Handlers.About")


ABOUT_TEXT = (
    f"📊 *{TNSVT_BRAND_LINE} — BIENVENIDO*\n"
    f"━━━━━━━━━━━━━━━━━━━━━━\n"
    f"Sistema automatizado de señales y análisis técnico para "
    f"operar con criterio en mercados globales.\n\n"

    f"✅ *Señales en vivo* — Copiamos señales de canales "
    f"seleccionados y las ejecutamos según reglas de riesgo.\n"
    f"📊 *Análisis técnico* — Multi-timeframe, zonas de oferta "
    f"y demanda, SMC + order flow.\n"
    f"📰 *Alertas económicas* — Avisamos 15/10/5/1 min antes de "
    f"eventos ALTO impacto (IPC, IPP, FOMC, NFP, GDP).\n"
    f"📈 *Dashboard en vivo* — PnL, win rate, equity curve.\n"
    f"💼 *Multi-cuenta MT5* — Gestioná varias cuentas desde un "
    f"solo panel.\n\n"

    f"{TNSVT_COVERAGE_FOOTER}\n\n"

    f"🎮 *Comandos clave:*\n"
    f"• /menu — Menú principal con botones\n"
    f"• /start — Reiniciar el bot\n"
    f"• /status — Estado de servicios\n"
    f"• /eventos — Próximos eventos económicos\n"
    f"• /senales — Señales copiadas\n"
    f"• /statshoy — Stats del día\n"
    f"• /historial — Trades últimos días\n"
    f"• /canales — Canales Telegram configurados\n"
    f"• /cuentas — Cuentas MT5 configuradas\n"
    f"• /cripto — Cripto en vivo\n"
    f"• /calendario — Calendario económico\n"
    f"• /mercados — Resumen de mercados\n"
    f"• /ipc — Datos reales del IPC (BLS.gov)\n"
    f"• /datos — Datos macro por país\n\n"

    f"{TNSVT_DISCLAIMER}"
)


def _about_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Menú Principal", callback_data="cmd:refresh")],
        [
            InlineKeyboardButton("📊 Dashboard", callback_data="cmd:status"),
            InlineKeyboardButton("📡 Canales", callback_data="cmd:canales"),
        ],
    ])


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando público /about — muestra descripción del bot."""
    try:
        await update.message.reply_text(
            ABOUT_TEXT,
            parse_mode="Markdown",
            reply_markup=_about_keyboard(),
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error(f"about_command error: {e}")
        try:
            await update.message.reply_text(
                "⚠️ Error al cargar la descripción.",
            )
        except Exception:
            pass


async def send_about_pinned(app):
    """Publica el mensaje /about en el grupo al iniciar e intenta pinearlo.

    Se ejecuta una sola vez al post_init. Si el bot no tiene
    can_pin_messages, igual publica el mensaje pero sin pinear.
    """
    group_id = settings.BOT_GROUP_ID
    if not group_id:
        logger.warning("send_about_pinned: BOT_GROUP_ID no configurado, skip")
        return

    try:
        sent = await app.bot.send_message(
            chat_id=group_id,
            text=ABOUT_TEXT,
            parse_mode="Markdown",
            reply_markup=_about_keyboard(),
            disable_web_page_preview=True,
        )
        logger.info(f"send_about_pinned: publicado msg_id={sent.message_id}")

        try:
            await app.bot.pin_chat_message(
                chat_id=group_id,
                message_id=sent.message_id,
                disable_notification=True,
            )
            logger.info(
                f"send_about_pinned: pineado msg_id={sent.message_id}"
            )
        except Exception as e:
            logger.debug(
                f"send_about_pinned: no pude pinear (falta can_pin_messages): {e}"
            )

    except Exception as e:
        logger.error(f"send_about_pinned: error publicando: {e}")
