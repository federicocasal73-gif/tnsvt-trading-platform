"""
Watchdog — Monitorea el ecosistema TNSVT V2 y publica alertas
en Telegram cuando detecta caidas o restauraciones.

Componentes verificados:
  1. Bridge-api FastAPI :8522 (salud general del ecosistema)
  2. Signal Copier Python (file mt5_status.json via bridge-api)
  3. MT5 snapshot worker (que el bridge-api tenga datos frescos)

Cada 60s chequea. Si un componente falla 2 veces seguidas,
publica un mensaje al chat admin (BOT_ADMIN_CHAT_ID).
"""
import asyncio
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import requests

logger = logging.getLogger("Bot.Watchdog")


def check_bridge_api(base_url: str, timeout: int = 5) -> dict:
    """Devuelve dict con status y diagnóstico del bridge-api."""
    result = {"name": "bridge-api", "healthy": False, "detail": ""}
    try:
        r = requests.get(f"{base_url}/health", timeout=timeout)
        if r.status_code == 200:
            data = r.json()
            result["healthy"] = True
            result["detail"] = f"v{data.get('version', '?')} gateway={data.get('gateway', '?')}"
        else:
            result["detail"] = f"HTTP {r.status_code}"
    except requests.exceptions.ConnectionError:
        result["detail"] = "connection refused"
    except Exception as e:
        result["detail"] = str(e)[:120]
    return result


def check_signal_copier(base_url: str, timeout: int = 5) -> dict:
    """Verifica que el signal_copier Python este vivo (connected=True)."""
    result = {"name": "signal_copier", "healthy": False, "detail": ""}
    try:
        r = requests.get(f"{base_url}/api/v1/bridge/mt5/signal_copier_status", timeout=timeout)
        if r.status_code == 200:
            data = r.json()
            if data.get("ok") and data.get("data", {}).get("connected"):
                balance = data["data"].get("balance", 0)
                equity = data["data"].get("equity", 0)
                open_pos = data["data"].get("open_positions", 0)
                result["healthy"] = True
                result["detail"] = f"balance={balance:.2f} equity={equity:.2f} open={open_pos}"
            else:
                result["detail"] = f"signal_copier disconnected"
        else:
            result["detail"] = f"HTTP {r.status_code}"
    except Exception as e:
        result["detail"] = str(e)[:120]
    return result


def check_mt5_snapshot(base_url: str, max_age_seconds: int = 30, timeout: int = 5) -> dict:
    """Verifica que el MT5 snapshot worker este escribiendo datos frescos."""
    result = {"name": "mt5_snapshot", "healthy": False, "detail": ""}
    try:
        r = requests.get(f"{base_url}/api/v1/bridge/mt5/account", timeout=timeout)
        if r.status_code == 200:
            data = r.json().get("data", {})
            updated_at = data.get("updated_at", "")
            if not updated_at:
                result["detail"] = "account sin timestamp"
                return result
            ts = datetime.strptime(updated_at, "%Y-%m-%dT%H:%M:%SZ")
            age = (datetime.utcnow() - ts).total_seconds()
            if age <= max_age_seconds:
                result["healthy"] = True
                result["detail"] = f"actualizado hace {age:.1f}s"
            else:
                result["detail"] = f"stale ({age:.0f}s)"
        else:
            result["detail"] = f"HTTP {r.status_code}"
    except Exception as e:
        result["detail"] = str(e)[:120]
    return result


class WatchdogState:
    """Trackea estado previo de cada componente para detectar flapping."""

    def __init__(self):
        self.last_state: dict = {}      # name -> "up" | "down"
        self.last_alert_ts: dict = {}   # name -> ultimo timestamp de alerta
        self.bootstrapped: bool = False

    def should_alert(self, component: str, status: str, cooldown: int = 300) -> bool:
        """Devuelve True si el cambio de estado merece alerta (con cooldown 5min)."""
        prev = self.last_state.get(component)
        if prev is None:
            self.last_state[component] = status
            return False
        if prev == status:
            return False
        # Cambio de estado — aplicar cooldown
        now = time.time()
        last = self.last_alert_ts.get(component, 0)
        if now - last < cooldown:
            self.last_state[component] = status  # actualizamos estado igualmente
            return False
        self.last_state[component] = status
        self.last_alert_ts[component] = now
        return True


def fmt_alert_status_icon(healthy: bool) -> str:
    return "🟢" if healthy else "🔴"


async def watchdog_loop(bot_app, check_interval: int = 60):
    """Loop principal del watchdog.

    Publica mensajes al chat admin sobre los componentes
    del ecosistema TNSVT V2 (bridge-api, signal_copier, MT5).
    """
    base_url = os.getenv("TNSVT_URL", "http://localhost:8522")
    admin_chat_id_str = os.getenv("BOT_ADMIN_CHAT_ID", "").strip()
    admin_chat_id = int(admin_chat_id_str) if admin_chat_id_str.isdigit() else None

    if not admin_chat_id:
        logger.warning("BOT_ADMIN_CHAT_ID no configurado; watchdog seguira sin publicar alertas")
    else:
        try:
            await bot_app.bot.send_message(
                chat_id=admin_chat_id,
                text=(
                    "🤖 *Watchdog TNSVT activo*\n"
                    f"Chequeando cada {check_interval}s\n"
                    f"Bridge: {base_url}\n"
                    f"Admin chat: `{admin_chat_id}`"
                ),
                parse_mode="Markdown",
            )
            logger.info(f"Watchdog inicializado, admin_chat_id={admin_chat_id}")
        except Exception as e:
            logger.warning(f"No pude notificar al admin en /watchdog start: {e}")

    state = WatchdogState()
    await asyncio.sleep(10)  # warm-up

    while True:
        try:
            checks = [
                check_bridge_api(base_url),
                check_signal_copier(base_url),
                check_mt5_snapshot(base_url),
            ]

            up_count = sum(1 for c in checks if c["healthy"])
            total = len(checks)
            overall = "UP" if up_count == total else f"DEGRADED ({up_count}/{total})"

            for check in checks:
                is_now_up = check["healthy"]
                target_state = "up" if is_now_up else "down"
                prev_state = state.last_state.get(check["name"], "up" if check["healthy"] else "down")

                # Solo alertar en cambios de estado (con cooldown)
                if prev_state != target_state and admin_chat_id:
                    try:
                        icon = fmt_alert_status_icon(is_now_up)
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        if is_now_up:
                            title = f"ℹ️ SERVICE_RESTORED · {check['name']}"
                        else:
                            title = f"🚨 SERVICE_DOWN · {check['name']}"
                        text = (
                            f"{title}\n\n"
                            f"Detalle: `{check['detail']}`\n"
                            f"Time: {timestamp}\n"
                            f"Overall: {overall}"
                        )
                        await bot_app.bot.send_message(
                            chat_id=admin_chat_id,
                            text=text,
                        )
                        logger.info(f"Watchdog alert: {check['name']} → {target_state}")
                    except Exception as e:
                        logger.warning(f"Error publicando alerta: {e}")
                state.last_state[check["name"]] = target_state

            # Reporte periodico cada 10 checkeos (10 min)
            checks_count = sum(1 for _ in checks)
            if not hasattr(watchdog_loop, "_counter"):
                watchdog_loop._counter = 0
            watchdog_loop._counter += 1
            if watchdog_loop._counter % 10 == 0 and admin_chat_id:
                try:
                    icon = "🟢" if up_count == total else "🟡"
                    text_lines = [f"{icon} *Reporte Watchdog* ({overall})\n"]
                    for c in checks:
                        c_icon = fmt_alert_status_icon(c["healthy"])
                        text_lines.append(f"{c_icon} `{c['name']}`: {c['detail']}")
                    text = "\n".join(text_lines)
                    await bot_app.bot.send_message(
                        chat_id=admin_chat_id,
                        text=text,
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    logger.warning(f"Error en reporte periodico: {e}")

            logger.debug(f"Watchdog tick: {up_count}/{total} up")

        except Exception as e:
            logger.warning(f"Watchdog tick error: {e}")

        await asyncio.sleep(check_interval)
