"""
Handler: /stats canal X, /stats simbolo X — Rendimiento por canal/símbolo.
"""
import asyncio
import json
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.handlers.admin_check import dm_only, admin_only

logger = logging.getLogger("Bot.Handlers.Analytics")

BRIDGE_URL = "http://localhost:8522"


def _fetch_json(url: str, timeout: int = 5):
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        return None
    return None


def _format_analytics_text(data: list, title: str, key_name: str, is_channel: bool = False) -> str:
    """Formatea datos de analytics por canal o símbolo."""
    if not data:
        return f"📊 {title}\n\n⚠️ Sin datos disponibles."

    lines = [f"📊 *{title}*\n"]
    for item in data:
        name = item.get(key_name, "?")
        pnl = item.get("total_pnl", 0)
        trades = item.get("total_trades", 0)
        wins = item.get("wins", 0)
        losses = item.get("losses", 0)
        wr = item.get("win_rate", 0)
        avg_rr = item.get("avg_rr", 0)
        pnl_emoji = "🟢" if pnl > 0 else ("🔴" if pnl < 0 else "⚪")

        lines.append(
            f"{pnl_emoji} *{name}*\n"
            f"   Trades: {trades} | WR: {wr}%\n"
            f"   PnL: `${pnl:+,.2f}` | RR: {avg_rr}"
        )
        if wins + losses > 0:
            lines.append(f"   🟢 {wins} / 🔴 {losses}")
        lines.append("")

    return "\n".join(lines)


async def _show_channel_stats(update: Update, context: ContextTypes.DEFAULT_TYPE, channel_name: str = None):
    """Muestra estadísticas por canal."""
    loop = asyncio.get_event_loop()
    by_channel = await loop.run_in_executor(
        None, lambda: _fetch_json(f"{BRIDGE_URL}/api/v1/bridge/analytics/by-channel")
    )

    if not by_channel:
        await update.message.reply_text("⚠️ No hay datos de rendimiento por canal.")
        return

    text = _format_analytics_text(by_channel, "Rendimiento por Canal", "channel", is_channel=True)
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 /status", callback_data="cmd:status")],
            [InlineKeyboardButton("📋 Menú principal", callback_data="cmd:refresh")],
        ]),
    )


async def _show_symbol_stats(update: Update, context: ContextTypes.DEFAULT_TYPE, symbol: str = None):
    """Muestra estadísticas por símbolo."""
    loop = asyncio.get_event_loop()
    by_symbol = await loop.run_in_executor(
        None, lambda: _fetch_json(f"{BRIDGE_URL}/api/v1/bridge/analytics/by-symbol")
    )

    if not by_symbol:
        await update.message.reply_text("⚠️ No hay datos de rendimiento por símbolo.")
        return

    text = _format_analytics_text(by_symbol, "Rendimiento por Símbolo", "symbol")
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 /status", callback_data="cmd:status")],
            [InlineKeyboardButton("📋 Menú principal", callback_data="cmd:refresh")],
        ]),
    )


@admin_only
@dm_only
async def stats_canal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /stats canal NOMBRE"""
    await _show_channel_stats(update, context)


@admin_only
@dm_only
async def stats_simbolo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /stats simbolo SYMBOL"""
    await _show_symbol_stats(update, context)
