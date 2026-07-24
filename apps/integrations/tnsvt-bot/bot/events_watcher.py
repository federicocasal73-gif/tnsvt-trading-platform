"""
Events Watcher — Polling al bridge-api para publicar eventos de trade al grupo.

El signal_copier NO puede mandar mensajes por el bot (no tiene BOT_TOKEN).
En lugar de eso, hace POST /api/v1/bridge/events con cada trade abierto/cerrado/bloqueado.

Este módulo hace GET /api/v1/bridge/events cada 2s, publica los pendientes
al BOT_GROUP_ID como mensaje de Telegram con botones inline (Cerrar, Soporte, etc),
y marca cada evento como delivered.
"""
import asyncio
import logging
from datetime import datetime

import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import settings

logger = logging.getLogger("Bot.EventsWatcher")

BRIDGE_URL = "http://localhost:8522"
POLL_INTERVAL_SEC = 2

_last_ts: float = 0.0
_initialized: bool = False


def _fmt_price(val) -> str:
    if val is None or val == 0:
        return "—"
    return f"{float(val):.5f}".rstrip("0").rstrip(".")


def _fmt_tp(tp_val) -> str:
    if tp_val is None:
        return "—"
    if isinstance(tp_val, (list, tuple)):
        if not tp_val:
            return "—"
        return ", ".join(_fmt_price(v) for v in tp_val if v)
    return _fmt_price(tp_val)


def _action_emoji(action: str) -> str:
    a = (action or "").upper()
    if a in ("BUY", "LONG", "COMPRA"):
        return "🟢"
    if a in ("SELL", "SHORT", "VENTA"):
        return "🔴"
    if a in ("CLOSE",):
        return "⚪"
    return "🟡"


def _result_emoji(result: str) -> str:
    r = (result or "").upper()
    if r in ("WIN", "TP", "TAKE_PROFIT", "TP1", "TP2", "TP3", "FULL_TP", "PARCIAL"):
        return "✅"
    if r in ("LOSS", "SL", "STOP_LOSS"):
        return "❌"
    if r in ("BREAKEVEN", "CLOSED"):
        return "⚪"
    return "🔔"


def _tradingview_url(symbol: str) -> str:
    """Devuelve una URL de TradingView en español para el símbolo dado."""
    sym = (symbol or "").upper().replace("/", "").replace("_", "").strip()
    if not sym:
        return "https://es.tradingview.com/"
    if sym in ("XAUUSD", "GOLD", "XAU"):
        return "https://es.tradingview.com/chart/?symbol=OANDA:XAUUSD"
    if sym in ("XAGUSD", "SILVER", "XAG"):
        return "https://es.tradingview.com/chart/?symbol=OANDA:XAGUSD"
    if sym in ("BTCUSD", "BTC"):
        return "https://es.tradingview.com/chart/?symbol=BINANCE:BTCUSDT"
    if sym in ("ETHUSD", "ETH"):
        return "https://es.tradingview.com/chart/?symbol=BINANCE:ETHUSDT"
    if sym in ("US30", "DJ30", "DOW"):
        return "https://es.tradingview.com/chart/?symbol=TVC:DJI"
    if sym in ("US100", "NAS100", "NASDAQ"):
        return "https://es.tradingview.com/chart/?symbol=TVC:NDX"
    if sym in ("US500", "SP500"):
        return "https://es.tradingview.com/chart/?symbol=TVC:SPX"
    if len(sym) == 6 and sym.isalpha():
        return f"https://es.tradingview.com/chart/?symbol=OANDA:{sym}"
    return "https://es.tradingview.com/"


def _keyboard_for_event(evt: dict) -> InlineKeyboardMarkup:
    """Teclado inline según el tipo de evento."""
    symbol = evt.get("symbol", "")
    rows = []

    if evt.get("type") == "trade_open":
        tv_url = _tradingview_url(symbol)
        rows.append([
            InlineKeyboardButton("📈 Ver Chart", url=tv_url),
            InlineKeyboardButton("📊 Stats", callback_data="cmd:stats"),
        ])
        rows.append([
            InlineKeyboardButton(f"❌ Cerrar {symbol}", callback_data=f"close:symbol:{symbol}"),
        ])

    elif evt.get("type") == "trade_close":
        rows.append([
            InlineKeyboardButton("📊 Stats hoy", callback_data="cmd:stats"),
            InlineKeyboardButton("📡 Canales", callback_data="cmd:canales"),
        ])

    elif evt.get("type") == "trade_blocked":
        rows.append([
            InlineKeyboardButton("📡 Canales", callback_data="cmd:canales"),
            InlineKeyboardButton("📅 Calendario", callback_data="cmd:calendario"),
        ])

    rows.append([
        InlineKeyboardButton("🆘 Soporte", callback_data="cmd:soporte"),
    ])
    return InlineKeyboardMarkup(rows)


def _format_trade_open(evt: dict) -> str:
    sym = evt.get("symbol", "")
    action = evt.get("action", "")
    ticket = evt.get("ticket", "")
    channel = evt.get("channel", "")
    time_str = datetime.now().strftime("%H:%M")
    return (
        f"Terminal Financiera Pro TNSVT                    [Soporte]\n"
        f"{_action_emoji(action)} *TRADE EJECUTADO*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 *{sym}* — {action.upper()} {_action_emoji(action)}\n"
        f"💰 Entry: `{_fmt_price(evt.get('price'))}`\n"
        f"🛑 SL: `{_fmt_price(evt.get('sl'))}`\n"
        f"🎯 TPs: `{_fmt_tp(evt.get('tp'))}`\n"
        f"💼 Lot: `_`\n"
        f"🎫 Ticket: `#{ticket}`\n"
        f"📡 Canal: _{channel}_   {time_str}\n"
    )


def _format_trade_close(evt: dict) -> str:
    sym = evt.get("symbol", "")
    action = evt.get("action", "")
    pnl = float(evt.get("pnl", 0) or 0)
    result = evt.get("result", "")
    channel = evt.get("channel", "")
    time_str = datetime.now().strftime("%H:%M")

    return (
        f"Terminal Financiera Pro TNSVT                    [Soporte]\n"
        f"{_result_emoji(result)} *TRADE CERRADO*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 *{sym}* — {action.upper()}\n"
        f"💰 PnL: `${pnl:+.2f}`\n"
        f"🏷 Resultado: *{result}*\n"
        f"📡 Canal: _{channel}_   {time_str}\n"
    )


def _format_trade_blocked(evt: dict) -> str:
    sym = evt.get("symbol", "")
    action = evt.get("action", "")
    reason = evt.get("reason", "")
    return (
        f"Terminal Financiera Pro TNSVT                    [Soporte]\n"
        f"🚫 *TRADE BLOQUEADO*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 *{sym}* — {action.upper()}\n"
        f"📝 Razón: _{reason or 'Sin razón'}_\n"
    )


def _format_event(evt: dict) -> str:
    evt_type = evt.get("type", "")
    if evt_type == "trade_open":
        return _format_trade_open(evt)
    if evt_type == "trade_close":
        return _format_trade_close(evt)
    if evt_type == "trade_blocked":
        return _format_trade_blocked(evt)
    return f"📨 Evento: {evt_type} {evt.get('symbol', '')}"


async def events_watcher_loop(app):
    """Loop asincrono que arranca al init del bot y hace polling cada POLL_INTERVAL_SEC.

    Acepta el `app` de python-telegram-bot y por dentro usa `context.application.bot`
    para mandar mensajes. Mantiene last_ts entre llamadas para no duplicar.
    """
    global _initialized
    if not _initialized:
        _initialized = True
        logger.info(
            f"events_watcher arrancado (poll={POLL_INTERVAL_SEC}s, "
            f"target_chat={settings.BOT_GROUP_ID})"
        )

    context = type("Ctx", (), {"bot": app.bot})()
    context.application = app

    while True:
        try:
            events = await _poll_once()
            for evt in events:
                await _publish_event(context, evt)
        except Exception as e:
            logger.error(f"events_watcher_loop error: {e}")
        await asyncio.sleep(POLL_INTERVAL_SEC)


async def _publish_event(context: ContextTypes.DEFAULT_TYPE, evt: dict) -> None:
    """Publica un evento al grupo y marca como delivered."""
    target_chat = settings.BOT_GROUP_ID
    if not target_chat:
        logger.warning("events_watcher: BOT_GROUP_ID no configurado, no publico nada")
        return

    text = _format_event(evt)
    keyboard = _keyboard_for_event(evt)

    try:
        msg = await context.bot.send_message(
            chat_id=target_chat,
            text=text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
        logger.info(
            f"events_watcher: publicado {evt.get('type')} {evt.get('symbol')} "
            f"-> msg_id={msg.message_id} en grupo {target_chat}"
        )
    except Exception as e:
        logger.error(f"events_watcher: fallo publicando al grupo {target_chat}: {e}")
        return

    try:
        requests.post(
            f"{BRIDGE_URL}/api/v1/bridge/events/{evt.get('event_id')}/delivered",
            timeout=3,
        )
    except Exception as e:
        logger.debug(f"events_watcher: fallo marcando delivered: {e}")


async def _poll_once() -> list:
    """Hace un GET /api/v1/bridge/events con el último timestamp procesado."""
    global _last_ts
    try:
        r = requests.get(
            f"{BRIDGE_URL}/api/v1/bridge/events",
            params={"delim": _last_ts},
            timeout=5,
        )
        r.raise_for_status()
        events = r.json().get("events", [])
        if events:
            _last_ts = max(e.get("ts", _last_ts) for e in events)
        return events
    except Exception as e:
        logger.debug(f"events_watcher poll error: {e}")
        return []


async def events_watcher_job(context: ContextTypes.DEFAULT_TYPE):
    """Job que se ejecuta cada POLL_INTERVAL_SEC segundos para publicar eventos."""
    global _initialized
    if not _initialized:
        _initialized = True
        logger.info(
            f"events_watcher arrancado (poll={POLL_INTERVAL_SEC}s, "
            f"target_chat={settings.BOT_GROUP_ID})"
        )

    events = await _poll_once()
    for evt in events:
        await _publish_event(context, evt)
