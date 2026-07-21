"""
Handler: /resumen, /stats
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes
from bot.handlers.admin_check import admin_only, dm_only
from bot.services import news_api
from bot.services.tnsvt_status import get_copier_stats_from_tnsvt, get_recent_trades_from_tnsvt

logger = logging.getLogger("Bot.Handlers.Admin")


@admin_only
async def resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resumen diario completo"""
    try:
        user = update.effective_user
        logger.info(f"Comando /resumen desde {user.username or user.id}")

        await update.message.reply_text("🔄 Generando resumen diario...")

        sections = [
            ("📊 IPC/Inflacion", "IPC inflacion precios"),
            ("💼 Empleo", "desempleo empleo trabajo"),
            ("🏦 Morgan Stanley", "Morgan Stanley analisis"),
            ("₿ Cripto", "bitcoin ethereum cripto"),
        ]

        texto = "📋 *Resumen Diario*\n\n"

        for title, query in sections:
            texto += f"\n{title}\n"
            noticia = news_api.get_news(query, page_size=2)
            texto += noticia + "\n"

        await update.message.reply_text(texto, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error en /resumen: {e}")
        await update.message.reply_text("⚠️ Error al generar resumen.")


@dm_only
@admin_only
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Estadisticas del copiador (via TNSVT API)"""
    try:
        user = update.effective_user
        logger.info(f"Comando /stats desde {user.username or user.id}")

        stats = get_copier_stats_from_tnsvt()
        trades = get_recent_trades_from_tnsvt(limit=100)
        trades_today = [t for t in trades if str(t.get("date", "")).startswith(_today_prefix())]

        balance = stats.get("balance", 0)
        daily_pnl = stats.get("daily_pnl", 0)
        weekly_pnl = stats.get("weekly_pnl", 0)
        total_trades = stats.get("total_trades", 0)
        win_rate = stats.get("win_rate", 0)
        mt5_ok = stats.get("mt5_connected", False)

        emoji_mt5 = "🟢" if mt5_ok else "🔴"

        texto = f"""📈 *Estadisticas del Copiador (TNSVT)*

━━━━━━━━━━━━━━━━━━━━━━━━━
💰 *Cuenta:*
• Balance: `${balance:,.2f}`
• MT5: {emoji_mt5} {'Conectado' if mt5_ok else 'Desconectado'}

━━━━━━━━━━━━━━━━━━━━━━━━━
📊 *PnL:*
• Diario: `${daily_pnl:+,.2f}`
• Semanal: `${weekly_pnl:+,.2f}`

━━━━━━━━━━━━━━━━━━━━━━━━━
📋 *Operaciones:*
• Total: `{total_trades}`
• Hoy: `{len(trades_today)}`
• Win Rate: `{win_rate:.1f}%`

━━━━━━━━━━━━━━━━━━━━━━━━━"""

        await update.message.reply_text(texto, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error en /stats: {e}")
        await update.message.reply_text("⚠️ Error al obtener estadisticas.")


def _today_prefix() -> str:
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%d")
