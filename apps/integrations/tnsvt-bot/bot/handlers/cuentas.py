"""
Handler: /cuentas — Lista cuentas MT5 gestionadas por el account-manager.

Las cuentas y credenciales ahora viven en el servicio account-manager (:8510).
Este handler consume /api/v1/accounts (vía gateway :8000) y los snapshots
vivos via /api/v1/bridge/mt5/accounts (que el bridge-api proxy desde
account-manager).

Antes leía `<MT5_DATA_DIR>/accounts.json` — ese archivo legacy se conserva
sólo como fallback si account-manager está caído.
"""
import asyncio
import json
import logging
import os
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.handlers.admin_check import dm_only
from bot.bridge_auth import bridge_headers
import requests

logger = logging.getLogger("Bot.Handlers.Cuentas")

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000")
BRIDGE_URL = os.getenv("BRIDGE_URL", "http://localhost:8522")
MT5_DATA_DIR = Path(os.getenv("MT5_DATA_DIR", r"D:\TradingBotMT5"))
ACCOUNTS_PATH = MT5_DATA_DIR / "accounts.json"  # legacy fallback


def _gateway_headers() -> dict:
    """Headers con X-Tenant-ID para multi-tenant."""
    h = {"Content-Type": "application/json"}
    tid = os.getenv("DEFAULT_TENANT_ID")
    if tid:
        h["X-Tenant-ID"] = tid
    return h


def _load_accounts_from_account_manager() -> list[dict] | None:
    """Lee cuentas del account-manager vía gateway. None si falla."""
    try:
        r = requests.get(
            f"{GATEWAY_URL}/api/v1/accounts",
            headers=_gateway_headers(),
            timeout=5,
        )
        if r.status_code == 200:
            data = r.json()
            accs = data.get("accounts", [])
            # Normalizar a la shape que el resto del handler espera
            return [
                {
                    "id": a.get("id"),
                    "login": a.get("login"),
                    "name": a.get("name") or f"Account {a.get('login')}",
                    "alias": a.get("alias") or f"acc_{a.get('login')}",
                    "server": a.get("server"),
                    "broker": a.get("broker"),
                    "status": a.get("status"),
                }
                for a in accs
            ]
    except Exception as e:
        logger.warning(f"account-manager unreachable via gateway: {e}")
    return None


def _load_accounts_legacy() -> list[dict]:
    """Fallback: leer accounts.json del filesystem."""
    try:
        if ACCOUNTS_PATH.exists():
            data = json.loads(ACCOUNTS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
    except Exception as e:
        logger.warning(f"No pude leer accounts.json (legacy): {e}")
    return []


def _load_accounts() -> list[dict]:
    """Primero intenta account-manager; fallback al archivo legacy."""
    accs = _load_accounts_from_account_manager()
    if accs is not None:
        return accs
    logger.warning("Usando accounts.json (legacy fallback)")
    return _load_accounts_legacy()


def _fetch_snapshots_from_bridge() -> dict:
    """Snapshot por cuenta via /api/v1/bridge/mt5/accounts (proxies account-manager)."""
    out: dict = {}
    try:
        r = requests.get(f"{BRIDGE_URL}/api/v1/bridge/mt5/accounts", headers=bridge_headers(), timeout=4)
        if r.status_code == 200:
            data = r.json()
            for a in data.get("accounts", []):
                login = a.get("login")
                if login:
                    out[login] = {
                        "login": login,
                        "balance": a.get("balance"),
                        "equity": a.get("equity"),
                        "profit": a.get("profit"),
                        "open_positions": a.get("open_positions", 0),
                        "server": a.get("server"),
                        "name": a.get("name"),
                    }
    except Exception as e:
        logger.warning(f"fetch_snapshots_from_bridge error: {e}")
    return out


def _fetch_snapshots_legacy() -> dict:
    """Legacy: leer de archivos locales en MT5_DATA_DIR."""
    out: dict = {}
    try:
        r = requests.get(f"{BRIDGE_URL}/api/v1/bridge/mt5/account", headers=bridge_headers(), timeout=4)
        if r.status_code == 200:
            data = r.json().get("data", {})
            if data and data.get("login"):
                out[data["login"]] = data
    except Exception:
        pass
    try:
        for acc in _load_accounts_legacy():
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


def _fetch_snapshots() -> dict:
    """Snapshots via bridge (que proxia account-manager)."""
    snaps = _fetch_snapshots_from_bridge()
    if snaps:
        return snaps
    return _fetch_snapshots_legacy()


@dm_only
async def cuentas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra todas las cuentas MT5 con snapshots actuales."""
    try:
        user = update.effective_user
        logger.info(f"Comando /cuentas desde {user.username or user.id}")

        loop = asyncio.get_event_loop()
        accounts = await loop.run_in_executor(None, _load_accounts)
        snaps = await loop.run_in_executor(None, _fetch_snapshots)

        if not accounts and not snaps:
            await update.message.reply_text(
                "⚠️ No hay cuentas configuradas en el account-manager.\n\n"
                "Para agregar una cuenta, usá el panel web → *Cuentas MT5* "
                "o POST a /api/v1/accounts con login/password/server.",
                parse_mode="Markdown",
            )
            return

        # Si no hay accounts (caso legacy puro), derivar de snaps
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
                    "status": "active",
                })

        lines = [f"🏦 *Cuentas MT5* ({len(accounts)})\n"]
        keyboard_rows = []

        for i, acc in enumerate(accounts, 1):
            login = acc.get("login")
            alias = acc.get("alias", "?")
            name = acc.get("name", "?")
            server = acc.get("server", "?")
            status = acc.get("status", "active")

            snap = snaps.get(login, {})
            balance = snap.get("balance") or 0
            equity = snap.get("equity") or 0
            pnl = snap.get("profit") or 0
            open_pos = snap.get("open_positions") or 0

            status_emoji = "🟢" if status == "active" else "🟡" if status == "paused" else "⚫"
            lines.append(
                f"*{i}. {name}* (`{alias}`) {status_emoji}\n"
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

        total_balance = sum((snaps.get(a.get("login"), {}).get("balance") or 0) for a in accounts)
        lines.append(f"\n_Total agregado: balance=`${total_balance:,.2f}`_")
        lines.append("\n_Administrá cuentas vía panel web → Cuentas MT5_")

        keyboard_rows.append([
            InlineKeyboardButton("🔄 Refrescar", callback_data="cuenta_refresh"),
        ])

        await update.message.reply_text(
            "\n".join(lines),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard_rows),
        )
    except Exception as e:
        logger.error(f"Error en /cuentas: {e}", exc_info=True)
        await update.message.reply_text("⚠️ Error al listar cuentas.")
