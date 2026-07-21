"""
Handler: /senales, /copiador
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes
from bot.handlers.admin_check import admin_only
from bot.services.tnsvt_status import (
    get_copier_status_from_tnsvt,
    get_recent_trades_from_tnsvt,
)

logger = logging.getLogger("Bot.Handlers.Signals")


@admin_only
async def senales(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el estado del copiador de senales (via TNSVT)"""
    try:
        user = update.effective_user
        logger.info(f"Comando /senales desde {user.username or user.id}")

        status = get_copier_status_from_tnsvt()
        trades = get_recent_trades_from_tnsvt(limit=10)

        if status is None:
            await update.message.reply_text(
                "⚠️ No se pudo conectar con TNSVT.\n"
                "Verifica que el servidor este activo."
            )
            return

        is_online = bool(status.get("running", False))
        mt5_ok = bool(status.get("mt5_connected", False))
        news_ok = bool(status.get("news_filter", False))
        balance = float(status.get("balance", 0))
        daily_pnl = float(status.get("daily_pnl", 0))
        trades_today = int(status.get("trades_today", 0))
        channels = status.get("channels", []) or []

        emoji_status = "🟢" if is_online else "🔴"
        texto_status = "ACTIVO" if is_online else "DETENIDO"
        emoji_mt5 = "🟢" if mt5_ok else "🔴"

        channels_txt = "\n".join([f"   • {c}" for c in channels[:6]]) if channels else "   (ninguno)"

        last_trades_txt = ""
        if trades:
            last_trades_txt = "\n━━━━━━━━━━━━━━━━━━━━━━━━━\n📊 *Ultimos Trades:*\n"
            for t in trades[:5]:
                sym = t.get("symbol", t.get("asset", "?"))
                act = t.get("action", t.get("direction", "?"))
                pnl = float(t.get("pnl", 0) or 0)
                res = t.get("result", "?")
                pnl_emoji = "🟢" if pnl > 0 else ("🔴" if pnl < 0 else "⚪")
                last_trades_txt += f"   {pnl_emoji} {sym} {act} · ${pnl:+.2f} · _{res}_\n"

        texto = f"""📡 *Copiador de Senales (TNSVT)*

{emoji_status} Estado: *{texto_status}*
{emoji_mt5} MT5: {'Conectado' if mt5_ok else 'Desconectado'}
   News Filter: {'🟢 ON' if news_ok else '⚫ OFF'}

━━━━━━━━━━━━━━━━━━━━━━━━━
💰 *Cuenta:*
• Balance: `${balance:,.2f}`
• PnL Diario: `${daily_pnl:+,.2f}`
• Trades Hoy: `{trades_today}`

━━━━━━━━━━━━━━━━━━━━━━━━━
📢 *Canales Monitoreados:*
{channels_txt}{last_trades_txt}

━━━━━━━━━━━━━━━━━━━━━━━━━
💡 _El copiador escucha canales de Telegram
y ejecuta trades automaticamente en MT5_"""

        await update.message.reply_text(texto, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error en /senales: {e}")
        await update.message.reply_text("⚠️ Error al obtener estado del copiador.")
