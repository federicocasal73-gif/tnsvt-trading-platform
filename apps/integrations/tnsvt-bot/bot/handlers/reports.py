"""
Handler: Daily and Weekly reports sent at ART time (UTC-3).

Daily report: 23:59 ART
Weekly report: Sunday 23:59 ART
"""
import asyncio
import logging
from datetime import datetime, timedelta

import pytz
from telegram.ext import ContextTypes

from config import settings
from bot.services.tnsvt_status import (
    get_copier_stats_from_tnsvt,
    get_recent_trades_from_tnsvt,
)

logger = logging.getLogger("Bot.Handlers.Reports")

ART = pytz.timezone("America/Argentina/Buenos_Aires")


async def send_daily_report(context: ContextTypes.DEFAULT_TYPE):
    await _send_report(context.bot, period="daily")


async def send_weekly_report(context: ContextTypes.DEFAULT_TYPE):
    await _send_report(context.bot, period="weekly")


async def _send_report(bot, period: str):
    admin_ids = settings.BOT_ADMIN_IDS
    if not admin_ids:
        logger.warning("No hay admins configurados para enviar reportes")
        return

    stats = get_copier_stats_from_tnsvt()
    trades = get_recent_trades_from_tnsvt(limit=200)

    if period == "daily":
        trades_filtered = [t for t in trades if str(t.get("date", "")).startswith(
            datetime.now(ART).strftime("%Y-%m-%d")
        )]
        title = "📊 *Reporte Diario*"
    else:
        week_ago = datetime.now(ART) - timedelta(days=7)
        trades_filtered = [
            t for t in trades
            if str(t.get("date", "")).startswith(week_ago.strftime("%Y-%m"))
        ]
        title = "📊 *Reporte Semanal*"

    balance = stats.get("balance", 0)
    daily_pnl = stats.get("daily_pnl", 0) if period == "daily" else stats.get("weekly_pnl", 0)
    total_trades = len(trades_filtered)
    wins = len([t for t in trades_filtered if float(t.get("pnl", 0) or 0) > 0])
    losses = len([t for t in trades_filtered if float(t.get("pnl", 0) or 0) < 0])
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    pnl_emoji = "🟢" if daily_pnl > 0 else ("🔴" if daily_pnl < 0 else "⚪")

    text = (
        f"{title}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💳 Balance: `${balance:,.2f}`\n"
        f"{pnl_emoji} PnL {period}: `${daily_pnl:+,.2f}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 *Operaciones:*\n"
        f"Total: {total_trades}\n"
        f"🟢 Ganadas: {wins}\n"
        f"🔴 Perdidas: {losses}\n"
        f"📊 Win Rate: {win_rate:.1f}%\n"
    )

    if period == "daily":
        text += "\n📈 Domingo — *Reporte Semanal* completo."

    for admin_id in admin_ids:
        try:
            await bot.send_message(chat_id=admin_id, text=text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error enviando reporte a admin {admin_id}: {e}")
