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
