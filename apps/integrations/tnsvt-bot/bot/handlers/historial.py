"""
Handler: /historial
"""
import asyncio
import json
import logging
from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes
from bot.handlers.admin_check import admin_only
from signal_copier.database import get_trades_since, get_stats_since

logger = logging.getLogger("Bot.Handlers.Historial")

MT5_STATUS_FILE = Path(__file__).parent.parent.parent / "var" / "mt5_status.json"


def _read_mt5_status() -> dict:
    """Lee el estado de MT5 desde el archivo compartido"""
    try:
        if MT5_STATUS_FILE.exists():
            data = json.loads(MT5_STATUS_FILE.read_text(encoding="utf-8"))
            return data
    except Exception:
        pass
    return {"connected": False}


@admin_only
async def historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra historial de trades por periodo + estado de cuenta"""
    try:
        user = update.effective_user
        args = context.args or []

        period = "semana"
        days = 7
        if args and args[0].lower() in ("mes", "m", "month"):
            period = "mes"
            days = 30

        logger.info(f"Comando /historial {period} desde {user.username or user.id}")

        await update.message.reply_text(f"🔄 Obteniendo historial de la {period}...")

        stats = await asyncio.to_thread(get_stats_since, days)
        trades = await asyncio.to_thread(get_trades_since, days)
        mt5 = await asyncio.to_thread(_read_mt5_status)

        executed = stats.get("executed", 0)
        wins = stats.get("wins", 0)
        losses = stats.get("losses", 0)
        win_rate = stats.get("win_rate", 0)
        total_pnl = stats.get("total_pnl", 0)
        pnl_wins = stats.get("pnl_wins", 0)
        pnl_losses = stats.get("pnl_losses", 0)
        blocked = stats.get("blocked", 0)

        balance = mt5.get("balance", 0)
        equity = mt5.get("equity", 0)
        profit = mt5.get("profit", 0)
        open_positions = mt5.get("open_positions", 0)
        login = mt5.get("login", "")
        server = mt5.get("server", "")

        emoji_pnl = "🟢" if total_pnl >= 0 else "🔴"
        emoji_account = "🟢" if mt5.get("connected") else "🔴"
        pnl_pct = ((equity / balance - 1) * 100) if balance > 0 else 0
        emoji_pnl_pct = "🟢" if pnl_pct >= 0 else "🔴"

        texto = f"""📋 *Historial - Ultima {period.capitalize()}*

━━━━━━━━━━━━━━━━━━━━━━━━━━
🏦 *Cuenta MT5:*
{emoji_account} Cuenta: `{login}` — {server}
• Balance: `${balance:,.2f}`
• Equity: `${equity:,.2f}`
• PnL Abierto: `${profit:+,.2f}` ({emoji_pnl_pct} {pnl_pct:+.2f}%)
• Posiciones Abiertas: `{open_positions}`

━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 *Resumen {period.capitalize()}:*
• Operaciones: `{executed}`
• Ganadas: `{wins}` | Perdidas: `{losses}`
• Win Rate: `{win_rate}%`
• Bloqueadas: `{blocked}`

💰 *PnL Cerrado:*
• Total: {emoji_pnl} `${total_pnl:+,.2f}`
• Ganancias: `${pnl_wins:+,.2f}`
• Perdidas: `${pnl_losses:+,.2f}`
━━━━━━━━━━━━━━━━━━━━━━━━━━"""

        if trades:
            texto += "\n📋 *Detalle de trades:*\n"
            for t in trades[:15]:
                date = t[0] if t[0] else "?"
                symbol = t[1] or "?"
                action = t[2] or "?"
                pnl = float(t[9] or 0)
                result = t[6] or "?"

                date_short = date[:10] if len(date) >= 10 else date
                pnl_emoji = "🟢" if pnl > 0 else ("🔴" if pnl < 0 else "⚪")

                texto += f"   {pnl_emoji} {date_short} · {symbol} {action} · ${pnl:+.2f} · _{result}_\n"

            if len(trades) > 15:
                texto += f"\n   _... y {len(trades) - 15} trades mas_"
        else:
            texto += "\n_No hay trades cerrados en este periodo._"

        texto += "\n\n_Uso: /historial o /historial mes_"

        await update.message.reply_text(texto, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error en /historial: {e}")
        await update.message.reply_text("⚠️ Error al obtener historial.")
