"""
Handler: /status — Dashboard completo del estado del sistema en Telegram.
"""
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

import pytz
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from config import settings
from bot.handlers.admin_check import dm_only

logger = logging.getLogger("Bot.Handlers.Status")

ART = pytz.timezone("America/Argentina/Buenos_Aires")
BRIDGE_URL = "http://localhost:8522"


def _fetch_json(url: str, timeout: int = 5):
    try:
        import requests
        r = requests.get(url, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        return None
    return None


@dm_only
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el dashboard completo del sistema."""
    try:
        user = update.effective_user
        logger.info(f"Comando /status desde {user.username or user.id}")

        await update.message.reply_text("🔄 Recopilando estado del sistema...")

        loop = asyncio.get_event_loop()

        bridge_cfg = await loop.run_in_executor(
            None, lambda: _fetch_json(f"{BRIDGE_URL}/api/v1/bridge/config")
        )
        copier_status = await loop.run_in_executor(
            None, lambda: _fetch_json(f"{BRIDGE_URL}/api/v1/bridge/copier/status")
        )
        mt5_account = await loop.run_in_executor(
            None, lambda: _fetch_json(f"{BRIDGE_URL}/api/v1/bridge/mt5/account")
        )
        mt5_positions = await loop.run_in_executor(
            None, lambda: _fetch_json(f"{BRIDGE_URL}/api/v1/bridge/mt5/positions")
        )
        health = await loop.run_in_executor(
            None, lambda: _fetch_json(f"{BRIDGE_URL}/health")
        )

        account = mt5_account or {}
        balance = account.get("balance", 0)
        equity = account.get("equity", 0)
        margin = account.get("margin", 0)
        margin_free = account.get("margin_free", 0)
        pnl = account.get("profit", 0)

        positions = mt5_positions or []
        pos_count = len(positions)

        channels = bridge_cfg.get("channels_data", []) if bridge_cfg else []
        channels_active = sum(1 for c in channels if c.get("enabled", True))

        risk = (bridge_cfg or {}).get("risk_management", {})
        trailing = (bridge_cfg or {}).get("trailing_stop", {})

        mt5_ok = bool(account)
        ts_active = trailing.get("enabled", False)
        be_active = risk.get("breakeven_enabled", False)
        be_pips = risk.get("breakeven_pips", 8.0)
        corr_active = risk.get("correlation_guard", False)
        max_hold = risk.get("max_hold_hours", 48)
        close_fri = risk.get("close_on_friday", False)
        max_pos = risk.get("max_open_positions", 5)

        emoji_mt5 = "🟢" if mt5_ok else "🔴"
        emoji_ts = "✅" if ts_active else "❌"
        emoji_be = "✅" if be_active else "❌"
        emoji_corr = "✅" if corr_active else "❌"
        emoji_fri = "✅" if close_fri else "❌"
        pnl_emoji = "🟢" if pnl >= 0 else "🔴"

        now_art = datetime.now(ART).strftime("%H:%M")

        texto = (
            f"📊 *TERMINAL STATUS*  🕐 {now_art} ART\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💳 *Balance:* `${balance:,.2f}`\n"
            f"💰 *Equity:* `${equity:,.2f}`\n"
            f"📊 *Margen:* `${margin:,.2f}` / Libre: `${margin_free:,.2f}`\n"
            f"💵 *P&L Flotante:* {pnl_emoji} `${pnl:+,.2f}`\n\n"
            f"📍 *Posiciones:* {pos_count} abiertas (max {max_pos})\n"
            f"📡 *Canales:* {channels_active}/{len(channels)} activos\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 MT5: {emoji_mt5} {'Conectado' if mt5_ok else 'Desconectado'}\n"
            f"🔄 Trailing: {emoji_ts} "
            f"{'activo' if ts_active else 'apagado'}"
        )

        if ts_active:
            ts_start = trailing.get("start_pips", 5)
            ts_step = trailing.get("step_pips", 2)
            texto += f" (start={ts_start}, step={ts_step})"

        texto += (
            f"\n🛡️ BE: {emoji_be} "
            f"{'activo' if be_active else 'apagado'}"
            f"{f' ({be_pips}pips)' if be_active else ''}\n"
            f"🧩 Correlacion: {emoji_corr} "
            f"{'activo' if corr_active else 'apagado'}\n"
            f"⏰ Max Hold: {max_hold}h | Cierre viernes: {emoji_fri}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━"
        )

        keyboard = [
            [
                InlineKeyboardButton("🔄 Actualizar", callback_data="cmd:status"),
                InlineKeyboardButton("📍 Posiciones", callback_data="cmd:positions"),
            ],
            [
                InlineKeyboardButton("🔴 Cerrar Todo", callback_data="close:all"),
            ],
            [
                InlineKeyboardButton("💼 Menu Principal", callback_data="cmd:menu"),
            ],
        ]

        await update.message.reply_text(
            texto,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    except Exception as e:
        logger.error(f"Error en /status: {e}", exc_info=True)
        await update.message.reply_text("⚠️ Error al obtener estado del sistema.")
