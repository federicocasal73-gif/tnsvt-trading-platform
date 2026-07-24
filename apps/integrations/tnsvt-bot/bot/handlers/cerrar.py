"""
Handler: /cerrar SYMBOL — Cierra posiciones abiertas.

Modos:
  /cerrar XAUUSD     → cierra posiciones de XAUUSD
  /cerrar all        → cierra TODAS las posiciones abiertas
  /cerrar            → muestra menu inline de opciones

Flujo:
  1. User escribe comando (solo admin via @admin_only + @dm_only)
  2. Bot llama a bridge-api POST /api/v1/bridge/copier/close
  3. bridge-api escribe comando a D:\\TradingBotMT5\\cmd_requests.json
  4. El signal_copier poll lee el comando y cierra las posiciones
  5. Bot hace polling de cmd_responses.json cada 1s hasta 10s para confirmar
"""
import asyncio
import json
import logging
import requests
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.handlers.admin_check import dm_only, admin_only
from config import settings

logger = logging.getLogger("Bot.Handlers.Cerrar")

BASE_URL = "http://localhost:8522"
CMD_RESPONSES_PATH = Path(r"D:\TradingBotMT5\cmd_responses.json")


@admin_only
@dm_only
async def cerrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cierra posiciones del símbolo especificado."""
    try:
        user = update.effective_user
        if not context.args:
            await _show_close_menu(update)
            return

        raw = context.args[0].upper().strip()
        logger.info(f"Comando /cerrar {raw} desde {user.username or user.id}")

        # Si es "ALL", cerrar todo
        if raw == "ALL":
            await _close_all(update, context, user)
            return

        symbol = raw
        status_msg = await update.message.reply_text(
            f"🔒 Cerrando posiciones de *{symbol}*...\n_Esperando confirmación..._",
            parse_mode="Markdown",
        )

        loop = asyncio.get_event_loop()

        def _do_close():
            return requests.post(
                f"{BASE_URL}/api/v1/bridge/copier/close",
                json={"action": "close", "symbol": symbol, "by_user": str(user.id)},
                timeout=5,
            )

        resp = await loop.run_in_executor(None, _do_close)

        if resp.status_code != 200:
            await status_msg.edit_text(
                f"⚠️ Error del bridge-api: HTTP {resp.status_code}"
            )
            return

        data = resp.json()
        if not data.get("ok"):
            await status_msg.edit_text(
                f"⚠️ {data.get('detail', 'No se pudo cerrar')}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Volver", callback_data="senales:menu")],
                ]),
            )
            return

        request_id = data.get("request_id")
        open_positions = data.get("open_positions", "?")

        await status_msg.edit_text(
            f"⏳ Cerrando *{symbol}*...\n"
            f"Posiciones abiertas: {open_positions}\n"
            f"_Esperando confirmación del signal_copier..._",
            parse_mode="Markdown",
        )

        confirmation = await _poll_for_response(request_id, timeout=10.0)

        if confirmation:
            status = confirmation.get("status", "?")
            closed = confirmation.get("closed", 0)
            if status == "ok":
                await status_msg.edit_text(
                    f"✅ *{symbol}* cerrado correctamente.\n"
                    f"Posiciones cerradas: {closed}\n"
                    f"Status: `{status}`",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📊 Stats hoy", callback_data="cmd:stats")],
                        [InlineKeyboardButton("📋 Menú principal", callback_data="cmd:refresh")],
                    ]),
                )
            elif status == "no_positions":
                await status_msg.edit_text(
                    f"⚠️ Sin posiciones abiertas para *{symbol}* en el momento del cierre.",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📋 Menú principal", callback_data="cmd:refresh")],
                    ]),
                )
            elif status == "skipped":
                reason = confirmation.get("reason", "sin razón")
                await status_msg.edit_text(
                    f"⚠️ Cierre skipped: {reason}",
                    parse_mode="Markdown",
                )
            else:
                error = confirmation.get("error", "?")
                await status_msg.edit_text(
                    f"❌ Error cerrando *{symbol}*: {error}",
                    parse_mode="Markdown",
                )
        else:
            await status_msg.edit_text(
                f"⚠️ Comando enviado para cerrar *{symbol}* (id={request_id[:18]})\n\n"
                f"Posiciones objetivo: {open_positions}\n"
                f"_El signal_copier no confirmó en 10s. Verificá con `/statshoy`._",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Refrescar", callback_data="senales:menu")],
                    [InlineKeyboardButton("📋 Menú principal", callback_data="cmd:refresh")],
                ]),
            )
    except Exception as e:
        logger.error(f"Error en /cerrar: {e}")
        await update.message.reply_text("⚠️ Error al ejecutar el cierre.")


async def _show_close_menu(update: Update):
    """Muestra menu inline con opciones de cierre."""
    from telegram import Update
    text = (
        "❌ *Cerrar posiciones*\n\n"
        "Elegí una opción o usá:\n"
        "• `/cerrar all` — Cerrar TODO\n"
        "• `/cerrar SYMBOL` — Cerrar un símbolo\n"
        "• `/cerrar canal NOMBRE` — Cerrar por canal\n\n"
        "Ej: `/cerrar XAUUSD`, `/cerrar all`"
    )
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔴 Cerrar TODO", callback_data="close:all")],
            [InlineKeyboardButton("🔴 Cerrar XAUUSD", callback_data="close:symbol:XAUUSD")],
            [InlineKeyboardButton("🔴 Cerrar EURUSD", callback_data="close:symbol:EURUSD")],
            [InlineKeyboardButton("📋 Menú principal", callback_data="cmd:refresh")],
        ]),
    )


async def _close_all(update: Update, context, user):
    """Cierra todas las posiciones abiertas."""
    try:
        loop = asyncio.get_event_loop()

        def _fetch_open_positions():
            r = requests.get(f"{BASE_URL}/api/v1/bridge/mt5/positions", timeout=5)
            if r.status_code == 200:
                return r.json()
            return []

        all_positions = await loop.run_in_executor(None, _fetch_open_positions)
        symbols = list(set(p.get("symbol") for p in all_positions if p.get("symbol")))
        if not symbols:
            await update.message.reply_text("✅ No hay posiciones abiertas para cerrar.")
            return

        # Close symbol by symbol
        status_msg = await update.message.reply_text(
            f"🔴 Cerrando TODAS las posiciones ({len(symbols)} símbolos)...",
            parse_mode="Markdown",
        )

        results = []
        for sym in symbols:
            def _close_sym(s=sym):
                return requests.post(
                    f"{BASE_URL}/api/v1/bridge/copier/close",
                    json={"action": "close", "symbol": s, "by_user": str(user.id)},
                    timeout=5,
                )
            resp = await loop.run_in_executor(None, _close_sym)
            ok = resp.status_code == 200 and resp.json().get("ok", False)
            results.append((sym, ok))

        ok_count = sum(1 for _, ok in results if ok)
        fail_count = sum(1 for _, ok in results if not ok)

        lines = [f"🔴 *Cierre masivo completado*"]
        lines.append(f"✅ Cerrados: {ok_count} | ❌ Fallos: {fail_count}")
        for sym, ok in results:
            lines.append(f"  {'✅' if ok else '❌'} `{sym}`")

        await status_msg.edit_text(
            "\n".join(lines),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 /status", callback_data="cmd:status")],
                [InlineKeyboardButton("📋 Menú principal", callback_data="cmd:refresh")],
            ]),
        )
    except Exception as e:
        logger.error(f"Error en _close_all: {e}")
        await update.message.reply_text("⚠️ Error cerrando todas las posiciones.")


async def _poll_for_response(request_id: str, timeout: float = 10.0) -> dict | None:
    """Polls cmd_responses.json cada 1s hasta encontrar el request_id o timeout."""
    if not request_id:
        return None

    loop = asyncio.get_event_loop()

    async def _check_once() -> dict | None:
        def _read():
            if not CMD_RESPONSES_PATH.exists():
                return None
            try:
                with open(CMD_RESPONSES_PATH, encoding="utf-8") as f:
                    responses = json.load(f)
                if not isinstance(responses, list):
                    return None
                for r in responses:
                    if (
                        isinstance(r, dict)
                        and r.get("request_id") == request_id
                        and r.get("status") != "pending"
                    ):
                        return r
            except Exception:
                return None
            return None

        return await loop.run_in_executor(None, _read)

    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        result = await _check_once()
        if result is not None:
            return result
        await asyncio.sleep(1.0)

    return None
