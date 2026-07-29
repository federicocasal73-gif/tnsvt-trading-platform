"""
Handler: Greetings system — Group welcome + private DM to admin.

Bienvenida rica multi-activo con:
- Brand statement TNSVT
- Lista completa de servicios
- Cobertura multi-activo
- Links útiles (dashboard, soporte)
- Disclaimer TNSVT
- Botones inline (Menú principal, Dashboard, Soporte)
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

logger = logging.getLogger("Bot.Handlers.Greetings")


def _welcome_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Menú Principal", callback_data="cmd:refresh")],
        [
            InlineKeyboardButton("📊 Dashboard", callback_data="cmd:status"),
            InlineKeyboardButton("🆘 Soporte", callback_data="cmd:soporte"),
        ],
    ])


async def greet_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cuando un nuevo miembro se une al grupo, manda bienvenida + notifica admin por DM."""
    if not update.my_chat_member and not update.chat_member:
        return

    chat_member = update.chat_member or update.my_chat_member
    if not chat_member:
        return

    new_status = chat_member.new_chat_member
    if not new_status or new_status.status not in ("member", "administrator"):
        return

    user = new_status.user
    if not user or user.is_bot:
        return

    chat = chat_member.chat
    logger.info(f"Nuevo miembro {user.full_name} ({user.id}) en {chat.title}")

    name = user.first_name or "Trader"

    welcome_text = (
        f"👋 ¡Bienvenido {name}!\n\n"
        f"📊 *{TNSVT_BRAND_LINE}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ Señales automatizadas en vivo\n"
        f"📰 Alertas de eventos económicos\n"
        f"📊 Análisis técnico multi-timeframe\n"
        f"📈 Tracking de PnL y rendimiento\n"
        f"💼 Multi-cuenta MT5\n\n"
        f"{TNSVT_COVERAGE_FOOTER}\n\n"
        f"Usá /menu para ver todos los comandos.\n\n"
        f"{TNSVT_DISCLAIMER}"
    )
    try:
        await chat.send_message(
            welcome_text,
            parse_mode="Markdown",
            reply_markup=_welcome_keyboard(),
        )
    except Exception as e:
        logger.error(f"Error en welcome grupal: {e}")

    admin_ids = settings.BOT_ADMIN_IDS
    if admin_ids:
        admin_notify = (
            f"👤 *Nuevo miembro en el grupo*\n\n"
            f"Nombre: {user.full_name}\n"
            f"ID: `{user.id}`\n"
            f"Username: @{user.username or 'N/A'}\n"
            f"Grupo: {chat.title}"
        )
        for admin_id in admin_ids:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_notify,
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.error(f"Error notificando a admin {admin_id}: {e}")
