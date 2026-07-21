"""
callbacks.py — Router central para todos los botones inline del bot.

Cuando el usuario aprieta un boton, Telegram envia un CallbackQuery.
Aca decidimos que comando ejecutar en funcion del callback_data.
"""
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.handlers import start, signals, admin, historial, statshoy, canales, cuentas
from signal_copier.database import get_stats_today, get_stats_since

logger = logging.getLogger("Bot.Callbacks")


async def _answer(query, text: str = ""):
    """Acknowledge el callback (sin notificación visible)."""
    try:
        await query.answer(text or None)
    except Exception:
        pass


async def _edit(query, text: str, parse_mode: str = "Markdown", reply_markup=None):
    """Edita el mensaje original con nuevo texto."""
    try:
        await query.edit_message_text(text=text, parse_mode=parse_mode, reply_markup=reply_markup)
    except Exception as e:
        logger.debug(f"edit_message_text fallback: {e}")


def main_menu_keyboard():
    """Botonera principal del /start."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Panorama", callback_data="cmd:analisis"),
            InlineKeyboardButton("📈 Equity", callback_data="cmd:grafico"),
            InlineKeyboardButton("💱 Cripto", callback_data="cmd:cripto"),
        ],
        [
            InlineKeyboardButton("📰 Noticias", callback_data="cmd:noticias"),
            InlineKeyboardButton("📅 Calendario", callback_data="cmd:calendario"),
            InlineKeyboardButton("📡 Señales", callback_data="cmd:senales"),
        ],
        [
            InlineKeyboardButton("📈 Historial", callback_data="cmd:historial"),
            InlineKeyboardButton("📊 Stats", callback_data="cmd:stats"),
            InlineKeyboardButton("🏦 Cuentas", callback_data="cmd:cuentas"),
        ],
        [
            InlineKeyboardButton("💼 Bot MT5", callback_data="cmd:bot"),
            InlineKeyboardButton("🆘 Ayuda", callback_data="cmd:ayuda"),
        ],
        [
            InlineKeyboardButton("🔄 Refrescar", callback_data="cmd:refresh"),
        ],
    ])


async def button_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """CallbackQuery router principal."""
    query = update.callback_query
    data = (query.data or "").strip()
    if not data:
        await _answer(query)
        return

    await _answer(query)

    # Comandos principales del /start
    if data.startswith("cmd:"):
        cmd = data.split(":", 1)[1]
        if cmd == "refresh":
            text, kbd = start.MENU_TEXT, main_menu_keyboard()
            await query.edit_message_text(text=text, parse_mode="Markdown", reply_markup=kbd)
            return

        if cmd == "ayuda":
            text, kbd = _help_text(), _help_keyboard()
            await query.edit_message_text(text=text, parse_mode="Markdown", reply_markup=kbd)
            return

        if cmd == "bot":
            text, kbd = _bot_status_text(), _bot_keyboard()
            await query.edit_message_text(text=text, parse_mode="Markdown", reply_markup=kbd)
            return

        # Redirigir a comandos existentes
        if cmd in ("senales", "stats", "historial", "cripto", "noticias", "calendario"):
            # Borrar el menú y forzar /cmd — dejamos el user tipear el comando
            # para mantener consistencia con el flujo /start.
            await query.edit_message_text(
                text=f"💬 Escribí *{cmd}* o tocá `/menu`.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 Volver al menú", callback_data="cmd:refresh")],
                ]),
            )
            return
        if cmd in ("analisis", "grafico"):
            await query.edit_message_text(
                text=f"📊 Para *{cmd}* abrir la Terminal Vite: http://localhost:5180/{cmd}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 Volver al menú", callback_data="cmd:refresh")],
                ]),
            )
            return

    # Submenú señales
    if data == "senales:menu":
        await _submenu_senales(query)
        return
    if data == "senales:stats_hoy":
        stats = await asyncio.get_event_loop().run_in_executor(None, get_stats_today)
        await _show_stats_hoy(query, stats)
        return
    if data == "senales:canales":
        await _show_canales(query)
        return
    if data == "senales:close":
        await query.edit_message_text(
            text="❌ *Cerrar posición*\n\n"
                 "Para cerrar una posición, usá `/cerrar SYMBOL`.\n"
                 "Ejemplo: `/cerrar XAUUSD`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Volver", callback_data="senales:menu")],
                [InlineKeyboardButton("📋 Menú principal", callback_data="cmd:refresh")],
            ]),
        )
        return

    # Historial: elegir período
    if data.startswith("historial:"):
        period = data.split(":", 1)[1]  # "semana" | "mes"
        days = 30 if period == "mes" else 7
        await _show_historial(query, days, period)
        return

    # Cuentas: detalle individual
    if data.startswith("cuenta_stats:"):
        login = int(data.split(":", 1)[1])
        snap = _read_account_snapshot(login)
        if snap:
            pnl = snap.get("profit", 0)
            emoji = "🟢" if pnl > 0 else ("🔴" if pnl < 0 else "⚪")
            text = (
                f"📊 *Cuenta {login}*\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"Balance: `${snap.get('balance', 0):,.2f}`\n"
                f"Equity: `${snap.get('equity', 0):,.2f}`\n"
                f"Margen: `${snap.get('margin', 0):,.2f}`\n"
                f"Margen Libre: `${snap.get('free_margin', 0):,.2f}`\n"
                f"PnL Flotante: {emoji} `${pnl:+,.2f}`\n"
                f"Leverage: 1:{snap.get('leverage', '?')}\n"
                f"Open Positions: {snap.get('open_positions', 0)}\n"
                f"Server: {snap.get('server', '?')}\n"
                f"Name: {snap.get('name', '?')}\n"
            )
        else:
            text = f"⚠️ No hay snapshot reciente para cuenta `{login}`"
        await query.edit_message_text(
            text=text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Volver a /cuentas", callback_data="cmd:cuentas")],
                [InlineKeyboardButton("📋 Menú principal", callback_data="cmd:refresh")],
            ]),
        )
        return

    if data == "cuenta_refresh":
        await query.edit_message_text("🔄 Refrescando...")
        await cuentas.cuentas(update, context)  # re-render
        return

    if data == "cuenta_edit":
        await query.edit_message_text(
            text="✏️ *Editá `D:\\\\TradingBotMT5\\\\accounts.json`*\n\n"
                 "Cada cuenta tiene:\n"
                 "```json\n"
                 "{\n"
                 '  "login": 10011629660,\n'
                 '  "password": "tu_password",\n'
                 '  "server": "MetaQuotes-Demo",\n'
                 '  "name": "Mi cuenta Demo",\n'
                 '  "alias": "demo_main"\n'
                 "}\n"
                 "```\n"
                 "Después de editar, reiniciá `mt5_multi_snapshot.py`.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Volver", callback_data="cmd:cuentas")],
            ]),
        )
        return


def _read_account_snapshot(login: int):
    try:
        import json
        from pathlib import Path
        snap_path = Path(r"D:\TradingBotMT5") / f"account_snapshot_{login}.json"
        if snap_path.exists():
            return json.loads(snap_path.read_text(encoding="utf-8"))
        # Fallback al archivo global
        global_path = Path(r"D:\TradingBotMT5") / "account_snapshot.json"
        if global_path.exists():
            data = json.loads(global_path.read_text(encoding="utf-8"))
            if data.get("login") == login:
                return data
    except Exception:
        pass
    return None


async def _submenu_senales(query):
    text = (
        "📡 *Estadísticas del Copiador*\n\n"
        "Elegí qué querés ver:"
    )
    kbd = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Stats hoy", callback_data="senales:stats_hoy")],
        [InlineKeyboardButton("📡 Canales", callback_data="senales:canales")],
        [InlineKeyboardButton("🔒 Cerrar posición", callback_data="senales:close")],
        [InlineKeyboardButton("🔙 Volver al menú", callback_data="cmd:refresh")],
    ])
    await query.edit_message_text(text=text, parse_mode="Markdown", reply_markup=kbd)


async def _show_stats_hoy(query, stats):
    executed = stats.get("executed", 0)
    wins = stats.get("wins", 0)
    losses = stats.get("losses", 0)
    blocked = stats.get("blocked", 0)
    wr = stats.get("win_rate", 0)
    pnl = stats.get("total_pnl", 0)
    emoji = "🟢" if pnl > 0 else ("🔴" if pnl < 0 else "⚪")
    text = (
        f"📊 *Stats de Hoy*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"✅ Ejecutadas: {executed}\n"
        f"🟢 Ganadas: {wins}\n"
        f"🔴 Perdidas: {losses}\n"
        f"🚫 Bloqueadas: {blocked}\n"
        f"📈 Win rate: {wr}%\n"
        f"💵 PnL: {emoji} `${pnl:+,.2f}`"
    )
    kbd = InlineKeyboardMarkup([
        [InlineKeyboardButton("📈 Historial esta semana", callback_data="historial:semana")],
        [InlineKeyboardButton("📈 Historial este mes", callback_data="historial:mes")],
        [InlineKeyboardButton("🔙 Volver a Señales", callback_data="senales:menu")],
        [InlineKeyboardButton("📋 Menú principal", callback_data="cmd:refresh")],
    ])
    await query.edit_message_text(text=text, parse_mode="Markdown", reply_markup=kbd)


async def _show_canales(query):
    from bot.handlers.canales import _read_config
    loop = asyncio.get_event_loop()
    cfg = await loop.run_in_executor(None, _read_config)
    channels_data = cfg.get("channels_data", []) or []

    if not channels_data:
        text = "⚠️ Sin canales configurados"
        kbd = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="senales:menu")]])
    else:
        lines = [f"📡 *Canales Monitoreados* ({len(channels_data)})\n"]
        for i, ch in enumerate(channels_data, 1):
            name = ch.get("name", "?")
            cid = ch.get("id", "?")
            tid = ch.get("topic_id")
            line = f"{i}. `{name}`"
            if tid is not None:
                line += f" · topic={tid}"
            line += f"\n   ID: `{cid}`"
            lines.append(line)
        text = "\n".join(lines)
        kbd = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Volver a Señales", callback_data="senales:menu")],
            [InlineKeyboardButton("📋 Menú principal", callback_data="cmd:refresh")],
        ])
    await query.edit_message_text(text=text, parse_mode="Markdown", reply_markup=kbd)


async def _show_historial(query, days: int, label: str):
    loop = asyncio.get_event_loop()
    trades = await loop.run_in_executor(None, get_stats_since, days)
    stats = await loop.run_in_executor(None, get_stats_since, days)
    wins = stats.get("wins", 0)
    pnl = stats.get("total_pnl", 0)
    emoji = "🟢" if pnl > 0 else ("🔴" if pnl < 0 else "⚪")
    text = (
        f"📈 *Historial última {label}*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 Win rate: {stats.get('win_rate', 0)}%\n"
        f"💰 Total PnL: {emoji} `${pnl:+,.2f}`\n"
        f"📊 Trades: {stats.get('total', 0)}\n"
        f"🟢 Ganados: {wins}  🔴 Perdidos: {stats.get('losses', 0)}\n"
    )
    if stats.get("pnl_wins") is not None:
        text += (
            f"Ganancias: ${stats['pnl_wins']:+,.2f}\n"
            f"Pérdidas: ${stats.get('pnl_losses', 0):+,.2f}\n"
        )
    text += f"\n_Ver detalle completo en la Terminal Vite → http://localhost:5180/history_"

    kbd = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Última semana", callback_data="historial:semana")],
        [InlineKeyboardButton("📅 Último mes", callback_data="historial:mes")],
        [InlineKeyboardButton("🔙 Volver a Señales", callback_data="senales:menu")],
        [InlineKeyboardButton("📋 Menú principal", callback_data="cmd:refresh")],
    ])
    await query.edit_message_text(text=text, parse_mode="Markdown", reply_markup=kbd)


def _help_text():
    return (
        "🆘 *Comandos disponibles*\n\n"
        "*Análisis técnico*\n"
        "• `/reporte SIMBOLO` — Multi-timeframe\n"
        "• `/r SIMBOLO` — Atajo rápido\n"
        "• `/analisis` — Panorama 5 pares\n"
        "• `/grafico` — Equity curve\n\n"
        "*Mercados*\n"
        "• `/mercados` — Resumen global\n"
        "• `/cripto` — Criptomonedas\n"
        "• `/calendario` — Calendario económico\n"
        "• `/noticias` — Últimas noticias\n\n"
        "*Señales*\n"
        "• `/senales` — Señales copiadas (con botones)\n"
        "• `/statshoy` — Estadísticas del día\n"
        "• `/historial` — Trades 7 días\n"
        "• `/canales` — Canales Telegram configurados\n\n"
        "*Cuentas MT5*\n"
        "• `/cuentas` — Lista de cuentas (multi-cuenta)\n\n"
        "*Admin*\n"
        "• `/resumen` — Resumen diario\n"
        "• `/stats` — Estadísticas detalladas\n"
    )


def _help_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📡 Señales", callback_data="senales:menu")],
        [InlineKeyboardButton("🏦 Cuentas", callback_data="cmd:cuentas")],
        [InlineKeyboardButton("🔙 Volver al menú", callback_data="cmd:refresh")],
    ])


def _bot_status_text():
    return (
        "💼 *Estado del Bot MT5*\n\n"
        "El signal_copier escucha canales de Telegram y ejecuta trades\n"
        "automaticamente en MT5 con las reglas de riesgo configuradas.\n\n"
        "Para configurar canales: `/canales`\n"
        "Para ver cuentas: `/cuentas`\n"
        "Para cerrar posiciones: `/cerrar SYMBOL`\n"
    )


def _bot_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📡 Canales", callback_data="senales:canales")],
        [InlineKeyboardButton("🏦 Cuentas", callback_data="cmd:cuentas")],
        [InlineKeyboardButton("🔙 Volver al menú", callback_data="cmd:refresh")],
    ])
