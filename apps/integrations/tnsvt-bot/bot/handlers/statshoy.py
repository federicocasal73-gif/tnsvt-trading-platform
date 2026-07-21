"""
Handler: /statshoy — Estadísticas del día actual (del signal_copier + bridge-api).
"""
import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes
from bot.handlers.admin_check import dm_only
from bot.services.tnsvt_status import get_client
from signal_copier.database import get_stats_today, get_stats_since

logger = logging.getLogger("Bot.Handlers.StatsHoy")


@dm_only
async def statshoy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Estadísticas del día (usando signal_copier local SQLite)."""
    try:
        user = update.effective_user
        logger.info(f"Comando /statshoy desde {user.username or user.id}")

        await update.message.reply_text("📊 Calculando stats de hoy...")

        loop = asyncio.get_event_loop()
        today_stats = await loop.run_in_executor(None, get_stats_today)
        week_stats = await loop.run_in_executor(None, get_stats_since, 7)

        executed = today_stats.get("executed", 0)
        wins = today_stats.get("wins", 0)
        losses = today_stats.get("losses", 0)
        blocked = today_stats.get("blocked", 0)
        wr = today_stats.get("win_rate", 0)
        pnl = today_stats.get("total_pnl", 0)

        emoji_pnl = "🟢" if pnl > 0 else ("🔴" if pnl < 0 else "⚪")

        texto = f"""📊 *Stats de Hoy*

━━━━━━━━━━━━━━━━━━━
🟢 *Ejecutadas hoy:* {executed}
✅ *Ganadas:* {wins}
❌ *Perdidas:* {losses}
🚫 *Bloqueadas:* {blocked}
📈 *Win rate hoy:* {wr}%

💵 *PnL hoy:* {emoji_pnl} `${pnl:+,.2f}`

━━━━━━━━━━━━━━━━━━━
📅 *Última semana:*
🎯 Win rate: {week_stats.get('win_rate', 0)}%
💰 Total PnL: ${week_stats.get('total_pnl', 0):+,.2f}
📊 Trades: {week_stats.get('total', 0)}
━━━━━━━━━━━━━━━━━━━

_Usa el boton /menu para volver_"""

        await update.message.reply_text(texto, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error en /statshoy: {e}")
        await update.message.reply_text("⚠️ Error al obtener stats de hoy.")
