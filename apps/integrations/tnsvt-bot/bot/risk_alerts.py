"""
Risk Alerts — Monitoreo de DD en tiempo real + resumenes periodicos al grupo.

Loop asincrono que cada 30 segundos:
1. Consulta risk state al bridge-api
2. Si DD > 8%, manda DM al admin con detalle
3. Si cruza multiples de 4h (boundary), publica resumen al grupo

Rate-limited: solo 1 DM por hora para evitar spam.
"""
import asyncio
import logging
from datetime import datetime, timedelta

import pytz
import requests

from config import settings

logger = logging.getLogger("Bot.RiskAlerts")

ART = pytz.timezone("America/Argentina/Buenos_Aires")
BRIDGE_URL = "http://localhost:8522"
POLL_INTERVAL = 30
DD_WARNING_PCT = 8.0
DM_COOLDOWN_SECONDS = 3600

_last_dm_sent_at: float = 0.0
_last_group_summary_hour: int = -1


async def _fetch_risk_state() -> dict | None:
    try:
        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(
            None,
            lambda: requests.get(
                f"{BRIDGE_URL}/api/v1/bridge/risk/state", timeout=5
            ),
        )
        if resp.status_code == 200:
            return resp.json()
        logger.debug(f"risk state HTTP {resp.status_code}")
    except Exception as e:
        logger.debug(f"fetch_risk_state error: {e}")
    return None


async def _notify_admin_dm(app, state: dict) -> None:
    """Envia DM al admin cuando DD cruza threshold."""
    global _last_dm_sent_at
    import time
    if time.time() - _last_dm_sent_at < DM_COOLDOWN_SECONDS:
        return

    admin_ids = settings.BOT_ADMIN_IDS
    if not admin_ids:
        return

    dd_pct = state.get("dd_pct", 0)
    equity = state.get("equity", 0)
    peak = state.get("peak_equity", 0)
    open_count = state.get("open_count", 0)
    daily_pnl = state.get("daily_pnl", 0)
    open_pnl = state.get("open_pnl", 0)

    text = (
        f"⚠️ *DD ALTO: {dd_pct:.1f}%*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Equity: `${equity:,.2f}`\n"
        f"📉 Peak: `${peak:,.2f}`\n"
        f"📊 Posiciones abiertas: {open_count}\n"
        f"📈 PnL diario: `${daily_pnl:+,.2f}`\n"
        f"💹 PnL flotante: `${open_pnl:+,.2f}`\n"
        f"🛑 Umbral alerta: {DD_WARNING_PCT}%\n\n"
        f"_Considerá cerrar posiciones o reducir exposición._"
    )

    sent = False
    for admin_id in admin_ids:
        try:
            await app.bot.send_message(
                chat_id=admin_id, text=text, parse_mode="Markdown"
            )
            sent = True
        except Exception as e:
            logger.error(f"risk_alerts: DM admin {admin_id} fallo: {e}")

    if sent:
        _last_dm_sent_at = time.time()


async def _publish_group_summary(app, state: dict) -> None:
    """Publica resumen cada 4h al grupo."""
    global _last_group_summary_hour
    now = datetime.now(ART)
    current_hour = now.hour
    current_block = current_hour // 4

    if current_block == _last_group_summary_hour:
        return
    if current_hour not in (0, 4, 8, 12, 16, 20):
        return

    _last_group_summary_hour = current_block

    target = settings.BOT_GROUP_ID
    if not target:
        return

    dd_pct = state.get("dd_pct", 0)
    open_count = state.get("open_count", 0)
    daily_pnl = state.get("daily_pnl", 0)
    open_pnl = state.get("open_pnl", 0)

    text = (
        f"📊 *Estado de Riesgo* ({now.strftime('%H:%M')} ART)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"DD: `{dd_pct:.1f}%` | "
        f"Posiciones: `{open_count}` | "
        f"PnL hoy: `${daily_pnl:+,.2f}` | "
        f"PnL flotante: `${open_pnl:+,.2f}`"
    )

    try:
        await app.bot.send_message(
            chat_id=target, text=text, parse_mode="Markdown"
        )
        logger.info("risk_alerts: resumen 4h publicado al grupo")
    except Exception as e:
        logger.error(f"risk_alerts: fallo publicando resumen: {e}")


async def risk_alerts_loop(app):
    """Loop principal: cada 30s chequea DD."""
    logger.info(
        f"risk_alerts arrancado (poll={POLL_INTERVAL}s, "
        f"DD_warning={DD_WARNING_PCT}%)"
    )
    await asyncio.sleep(20)

    while True:
        try:
            state = await _fetch_risk_state()
            if state:
                dd_pct = state.get("dd_pct", 0)
                if dd_pct >= DD_WARNING_PCT:
                    await _notify_admin_dm(app, state)
                await _publish_group_summary(app, state)
            else:
                logger.debug("risk_alerts: sin state, skip")

        except Exception as e:
            logger.error(f"risk_alerts tick error: {e}")

        await asyncio.sleep(POLL_INTERVAL)