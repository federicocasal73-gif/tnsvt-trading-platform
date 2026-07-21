"""
Handler: /cuentas — Lista cuentas MT5 disponibles (multi-cuenta).

Las cuentas se leen de `D:\\TradingBotMT5\\accounts.json` si existe,
sino se muestran las cuentas que el bridge-api ha indexado.
"""
import asyncio
import json
import logging
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.handlers.admin_check import dm_only
import requests

logger = logging.getLogger("Bot.Handlers.Cuentas")

ACCOUNTS_PATH = Path(r"D:\TradingBotMT5\accounts.json")


def _load_accounts():
    """Lee accounts.json o devuelve lista vacia."""
    try:
        if ACCOUNTS_PATH.exists():
            data = json.loads(ACCOUNTS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
    except Exception as e:
        logger.warning(f"No pude leer accounts.json: {e}")
    return []


async def _fetch_snapshots(base_url: str, timeout: int = 4):
    """Snapshot individual por cuenta via /api/v1/bridge/mt5/account?login=..."""
    out: dict = {}
    try:
        # Bridge-api: account por defecto si no se pasa login
        r = requests.get(f"{base_url}/api/v1/bridge/mt5/account", timeout=timeout)
        if r.status_code == 200:
            data = r.json().get("data", {})
            if data and data.get("login"):
                out[data["login"]] = data

        # Lista de cuentas adicionales: leer accounts.json
        accounts = _load_accounts()
        for acc in accounts:
            login = acc.get("login")
            if not login or login in out:
                continue
            snap_path = ACCOUNTS_PATH.parent / f"account_snapshot_{login}.json"
            if snap_path.exists():
                try:
                    out[login] = json.loads(snap_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"fetch_snapshots error: {e}")
    return out


@dm_only
async def cuentas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra todas las cuentas MT5 con snapshots actuales."""
    try:
        user = update.effective_user
        logger.info(f"Comando /cuentas desde {user.username or user.id}")

        loop = asyncio.get_event_loop()
        accounts = await loop.run_in_executor(None, _load_accounts)
        snaps = await loop.run_in_executor(None, lambda: _fetch_snapshots_sync())

        if not accounts and not snaps:
            await update.message.reply_text(
                "⚠️ No hay cuentas configuradas.\n\n"
                "Editá `D:\\TradingBotMT5\\accounts.json` y agregá tus cuentas MT5.\n\n"
                "Formato:\n"
                "```\n"
                "[\n"
                '  {"login": 10011629660, "password": "xxx", "server": "MetaQuotes-Demo", "name": "Demo 1", "alias": "demo1"}\n'
                "]\n"
                "```",
                parse_mode="Markdown",
            )
            return

        # Si accounts.json existe, usar esa lista. Si no, derivar de snaps.
        if not accounts:
            seen = set()
            accounts = []
            for login, snap in snaps.items():
                if login in seen:
                    continue
                seen.add(login)
                accounts.append({
                    "login": snap.get("login", login),
                    "name": snap.get("name", "?"),
                    "server": snap.get("server", "?"),
                    "alias": f"account_{login}",
                })

        lines = [f"🏦 *Cuentas MT5* ({len(accounts)})\n"]
        keyboard_rows = []

        for i, acc in enumerate(accounts, 1):
            login = acc.get("login")
            alias = acc.get("alias", "?")
            name = acc.get("name", "?")
            server = acc.get("server", "?")

            snap = snaps.get(login, {})
            balance = snap.get("balance", 0)
            equity = snap.get("equity", 0)
            pnl = snap.get("profit", 0)
            open_pos = snap.get("open_positions", 0)

            lines.append(
                f"*{i}. {name}* (`{alias}`)\n"
                f"   Login: `{login}` · {server}\n"
                f"   Balance: `${balance:,.2f}` · Equity: `${equity:,.2f}`\n"
                f"   PnL: {'🟢' if pnl > 0 else ('🔴' if pnl < 0 else '⚪')} `${pnl:+,.2f}` · Open: {open_pos}\n"
            )

            keyboard_rows.append([
                InlineKeyboardButton(
                    f"📊 Stats {alias}",
                    callback_data=f"cuenta_stats:{login}",
                )
            ])

        lines.append(f"\n_Total agregado: balance=${sum(snaps.get(a.get('login'), {}).get('balance', 0) for a in accounts):,.2f}_")
        lines.append("\n_Para más detalle de una cuenta, tocá el botón._")

        keyboard_rows.append([
            InlineKeyboardButton("🔄 Refrescar", callback_data="cuenta_refresh"),
            InlineKeyboardButton("✏️ Editar accounts.json", callback_data="cuenta_edit"),
        ])

        await update.message.reply_text(
            "\n".join(lines),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard_rows),
        )
    except Exception as e:
        logger.error(f"Error en /cuentas: {e}")
        await update.message.reply_text("⚠️ Error al listar cuentas.")


def _fetch_snapshots_sync():
    """Version sync para run_in_executor."""
    base = "http://localhost:8522"
    out: dict = {}
    try:
        r = requests.get(f"{base}/api/v1/bridge/mt5/account", timeout=4)
        if r.status_code == 200:
            data = r.json().get("data", {})
            if data and data.get("login"):
                out[data["login"]] = data
    except Exception:
        pass

    try:
        accounts = _load_accounts()
        for acc in accounts:
            login = acc.get("login")
            if not login or login in out:
                continue
            snap_path = ACCOUNTS_PATH.parent / f"account_snapshot_{login}.json"
            if snap_path.exists():
                try:
                    out[login] = json.loads(snap_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
    except Exception:
        pass
    return out
