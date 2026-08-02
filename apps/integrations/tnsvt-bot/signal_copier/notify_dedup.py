"""
Dedup de notificaciones de trade bloqueado.

Logica extraida de main.py::_notify_bot para poder testearla sin
arrancar Telethon, MT5, ni el resto del bootstrap del signal_copier.

El estado se persiste en disco (JSON) para que la ventana de dedup
sobreviva reinicios del proceso: la misma (symbol, action, reason)
solo notifica una vez cada BLOCKED_NOTIF_DEDUP_SECS (default 24h).
"""
from __future__ import annotations

import json
import os
import time
from typing import Tuple

DEDUP_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "blocked_notif_dedup.json"
)


def _key_str(symbol: str, action: str, reason: str) -> str:
    return f"{symbol or ''}|{action or ''}|{reason or ''}"


def load_recent(path: str | None = None) -> dict:
    """Carga el estado de dedup persistido (dict {key_str: last_ts})."""
    path = path or DEDUP_FILE
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return {str(k): float(v) for k, v in data.items()}
    except Exception:
        return {}


def save_recent(recent: dict, path: str | None = None) -> None:
    """Persiste el estado de dedup (dict {key_str: last_ts})."""
    path = path or DEDUP_FILE
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(recent, f)
    except Exception:
        pass


def should_dedup_blocked_notif(
    recent: dict,
    symbol: str,
    action: str,
    reason: str,
    dedup_secs: int,
    now_ts: float | None = None,
) -> Tuple[bool, int]:
    """Devuelve (is_dedup, dedup_secs) para trade_blocked.

    Si el (symbol, action, reason) ya fue publicado dentro de la ventana
    dedup_secs, retorna (True, dedup_secs) y NO actualiza el timestamp
    (asi no extiende la ventana).

    Si no fue publicado, retorna (False, dedup_secs) y marca el timestamp.
    """
    if now_ts is None:
        now_ts = time.time()
    key = _key_str(symbol, action, reason)
    last_ts = recent.get(key)
    if last_ts and (now_ts - last_ts) < dedup_secs:
        return True, dedup_secs
    recent[key] = now_ts
    return False, dedup_secs


def should_dedup_blocked_notif_persistent(
    symbol: str,
    action: str,
    reason: str,
    dedup_secs: int,
    now_ts: float | None = None,
    path: str | None = None,
) -> Tuple[bool, int]:
    """Igual que should_dedup_blocked_notif pero con estado persistido en disco.

    Carga el JSON, aplica la dedup y, si cambió (nuevo bloqueo), lo guarda.
    Asi un reinicio del signal_copier no resetea la ventana de 24h.
    """
    if now_ts is None:
        now_ts = time.time()
    recent = load_recent(path)
    is_dedup, secs = should_dedup_blocked_notif(
        recent, symbol, action, reason, dedup_secs, now_ts
    )
    save_recent(recent, path)
    return is_dedup, secs


def get_dedup_secs() -> int:
    """Lee el override de env o devuelve default (24h).

    La ventana es de 24h para que la misma (symbol, action, reason)
    solo notifique una vez (el loop time_exit reintenta cada 60s y no
    debe re-spamear el mismo bloqueo).
    """
    try:
        return int(os.getenv("BLOCKED_NOTIF_DEDUP_SECS", "86400"))
    except (TypeError, ValueError):
        return 86400
