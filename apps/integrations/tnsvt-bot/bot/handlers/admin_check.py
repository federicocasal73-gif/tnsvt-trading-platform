"""
Utilidad: Verificacion de admin para handlers del bot.
Si BOT_ADMIN_IDS esta vacio, todos tienen acceso.
"""
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from config import settings


def admin_only(handler):
    """Decorator: solo usuarios en BOT_ADMIN_IDS pueden usar el comando."""
    @wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        admin_ids = settings.BOT_ADMIN_IDS
        if not admin_ids:
            return await handler(update, context)

        user_id = update.effective_user.id if update.effective_user else 0
        if user_id not in admin_ids:
            await update.message.reply_text(
                "🔒 Acceso restringido a administradores."
            )
            return
        return await handler(update, context)
    return wrapper


def dm_only(handler):
    """Decorator: solo funciona en mensajes directos (DM) con el bot."""
    @wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.effective_chat:
            return
        if update.effective_chat.type != "private":
            await update.message.reply_text(
                "🔒 Este comando solo funciona en mensajes privados con el bot.\n"
                "Enviame un mensaje directo para usarlo."
            )
            return
        return await handler(update, context)
    return wrapper


def group_only(handler):
    """Decorator: solo funciona en grupos."""
    @wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.effective_chat:
            return
        if update.effective_chat.type == "private":
            await update.message.reply_text(
                "📢 Este comando solo funciona en el grupo."
            )
            return
        return await handler(update, context)
    return wrapper
