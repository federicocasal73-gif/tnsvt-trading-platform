"""
bot/services/tnsvt_status.py
=============================
Wrapper ligero sobre TNSVTClient para handlers del bot.
Provee funciones de alto nivel con cache + fallback graceful.
"""
import logging
import time
import threading
from typing import Optional

from tnsvt_client import TNSVTClient

logger = logging.getLogger("Bot.Services.TNSVTStatus")

_client: Optional[TNSVTClient] = None
_cache = {}
_cache_ttl = 15
_lock = threading.Lock()


def get_client() -> TNSVTClient:
    global _client
    if _client is None:
        _client = TNSVTClient()
    return _client


def _cached(key: str, fetcher, ttl: int = None):
    ttl = ttl or _cache_ttl
    now = time.time()
    with _lock:
        if key in _cache:
            ts, value = _cache[key]
            if now - ts < ttl:
                return value
        try:
            value = fetcher()
            _cache[key] = (now, value)
            return value
        except Exception as e:
            logger.debug(f"Cache fetch failed for {key}: {e}")
            return _cache.get(key, (0, None))[1]


def invalidate_cache():
    with _lock:
        _cache.clear()


def get_copier_status_from_tnsvt() -> Optional[dict]:
    """Retorna el status del signal_copier desde TNSVT, o None si no accesible."""
    client = get_client()
    if not client.enabled:
        return None
    return _cached("status", lambda: _fetch_status(client))


def _fetch_status(client: TNSVTClient) -> Optional[dict]:
    dashboard = client.get_dashboard()
    if dashboard and dashboard.get("success"):
        return dashboard.get("status") or {}
    return None


def get_copier_stats_from_tnsvt() -> dict:
    """Retorna stats consolidadas del copiador (balance, pnl, winrate, etc.)."""
    client = get_client()
    empty = {
        "balance": 0,
        "daily_pnl": 0,
        "weekly_pnl": 0,
        "total_trades": 0,
        "win_rate": 0,
        "mt5_connected": False,
    }
    if not client.enabled:
        return empty
    return _cached("stats", lambda: _fetch_stats(client), ttl=10) or empty


def _fetch_stats(client: TNSVTClient) -> dict:
    dashboard = client.get_dashboard()
    if not dashboard or not dashboard.get("success"):
        return {
            "balance": 0,
            "daily_pnl": 0,
            "weekly_pnl": 0,
            "total_trades": 0,
            "win_rate": 0,
            "mt5_connected": False,
        }
    s = dashboard.get("status", {}) or {}
    return {
        "balance": s.get("balance", 0),
        "daily_pnl": s.get("daily_pnl", 0),
        "weekly_pnl": s.get("weekly_pnl", 0),
        "total_trades": s.get("total_trades", 0),
        "win_rate": s.get("win_rate", 0),
        "mt5_connected": s.get("mt5_connected", False),
    }


def get_recent_trades_from_tnsvt(limit: int = 50) -> list:
    """Retorna trades recientes desde TNSVT journal."""
    client = get_client()
    if not client.enabled:
        return []
    return _cached(f"trades_{limit}", lambda: client.get_recent_trades(limit), ttl=30) or []


def get_dashboard_full() -> Optional[dict]:
    """Retorna el dashboard completo (status + config + recent_trades)."""
    client = get_client()
    if not client.enabled:
        return None
    return _cached("dashboard_full", lambda: client.get_dashboard(), ttl=10)


def send_bot_heartbeat(bot_username: str = "telegram_bot") -> bool:
    """Marca el bot como vivo en el status de TNSVT."""
    client = get_client()
    if not client.enabled or not client.admin_password:
        return False
    try:
        return client.update_status_field(
            telegram_bot=True,
            bot_username=bot_username,
        )
    except Exception as e:
        logger.debug(f"send_bot_heartbeat error: {e}")
        return False