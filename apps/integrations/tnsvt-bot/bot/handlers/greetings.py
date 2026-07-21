"""
Handler: Greetings system — Group welcome + private DM to admin.
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes, ChatMemberHandler
from config import settings

logger = logging.getLogger("Bot.Handlers.Greetings")


async def greet_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """When a new member joins the group, send welcome + notify admin via DM."""
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

    # Group welcome
    welcome_text = (
        f"👋 ¡Bienvenido {user.first_name or 'Trader'}!\n\n"
        f"📊 *Terminal Financiera Pro*\n"
        f"Usá /menu para ver los comandos disponibles.\n"
        f"Comandos públicos: /mercados, /cripto, /noticias, /calendario, /datos"
    )
    try:
        await chat.send_message(welcome_text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error en welcome grupal: {e}")

    # Private DM to admin
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
