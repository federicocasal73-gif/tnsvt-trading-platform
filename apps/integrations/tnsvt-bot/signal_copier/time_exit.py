"""
Time-Based Exit — Cierra posiciones por tiempo maximo, cierre pre-feriado,
y bloquea apertura despues de cierta hora.
"""
import logging
from datetime import datetime, timezone, timedelta

import MetaTrader5 as mt5
import pytz

logger = logging.getLogger("SignalCopier.TimeExit")

ART = pytz.timezone("America/Argentina/Buenos_Aires")
MAGIC = 20260706


def get_positions_to_close_by_hold(cfg: dict) -> list[dict]:
    """Retorna posiciones que excedieron RISK_MAX_HOLD_HOURS."""
    max_hours = cfg.get("max_hold_hours", 48)
    if max_hours <= 0:
        return []

    now = datetime.now(timezone.utc)
    to_close = []

    try:
        positions = mt5.positions_get(magic=MAGIC) or []
    except Exception as e:
        logger.error(f"time_exit get_positions error: {e}")
        return []

    for pos in positions:
        opened = datetime.fromtimestamp(pos.time, tz=timezone.utc)
        elapsed = (now - opened).total_seconds() / 3600
        if elapsed >= max_hours:
            to_close.append({
                "ticket": pos.ticket,
                "symbol": pos.symbol,
                "reason": f"max_hold_{max_hours}h (lleva {elapsed:.1f}h)",
                "profit": pos.profit,
            })
            logger.info(
                f"time_exit: {pos.symbol} #{pos.ticket} abierto hace "
                f"{elapsed:.1f}h, supero maximo {max_hours}h"
            )

    return to_close


def get_positions_to_close_friday(cfg: dict) -> list[dict]:
    """Retorna posiciones a cerrar por cierre de semana (viernes >= 17:00 ART)."""
    if not cfg.get("close_on_friday"):
        return []

    now_art = datetime.now(ART)
    if now_art.weekday() != 4:  # 4 = viernes
        return []
    if now_art.hour < 17:
        return []

    to_close = []
    try:
        positions = mt5.positions_get(magic=MAGIC) or []
    except Exception as e:
        logger.error(f"time_exit friday error: {e}")
        return []

    for pos in positions:
        to_close.append({
            "ticket": pos.ticket,
            "symbol": pos.symbol,
            "reason": "cierre_viernes_17h",
            "profit": pos.profit,
        })

    if to_close:
        logger.info(f"time_exit: {len(to_close)} posiciones a cerrar por cierre viernes")

    return to_close


def can_open_now(cfg: dict) -> tuple[bool, str]:
    """Verifica si se pueden abrir nuevas posiciones segun la hora."""
    no_open_after = cfg.get("no_open_after", "")
    if not no_open_after:
        return True, ""

    try:
        hh, mm = no_open_after.split(":")
        limit_hour = int(hh)
        limit_min = int(mm)
    except (ValueError, AttributeError):
        return True, ""

    now_art = datetime.now(ART)
    limit = now_art.replace(hour=limit_hour, minute=limit_min, second=0, microsecond=0)

    if now_art >= limit:
        return False, f"Bloqueado por horario: no se abren posiciones despues de las {no_open_after} ART"

    return True, ""
