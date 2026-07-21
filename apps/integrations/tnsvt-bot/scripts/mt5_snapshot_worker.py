"""
MT5 Snapshot Worker — Lee account info y posiciones del MT5 cada 3s.

Escribe dos archivos JSON que el bridge (:8522) expone vía API:
  - account_snapshot.json  → balance, equity, margin, margin_level, etc.
  - positions_snapshot.json → todas las posiciones abiertas (bot + manual)

Esto permite que el frontend React muestre datos en vivo de la cuenta MT5
sin depender del historial de trades del bot.
"""

import json
import logging
import os
import threading
import time

import MetaTrader5 as mt5

logger = logging.getLogger("bot.snapshot")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ACCOUNT_PATH = os.path.join(BASE_DIR, "account_snapshot.json")
POSITIONS_PATH = os.path.join(BASE_DIR, "positions_snapshot.json")

POLL_INTERVAL = 3.0

TYPE_MAP = {mt5.ORDER_TYPE_BUY: "BUY", mt5.ORDER_TYPE_SELL: "SELL"}
POSITION_FIELDS = [
    "ticket", "symbol", "type", "volume", "price_open",
    "sl", "tp", "price_current", "profit", "swap", "commission",
    "magic", "comment", "time",
]


def _serialize_position(pos) -> dict:
    d = {"type": TYPE_MAP.get(pos.type, "UNKNOWN")}
    for field in POSITION_FIELDS:
        if field == "type":
            continue
        val = getattr(pos, field, None)
        if isinstance(val, (int, float)):
            d[field] = val
        elif val is not None:
            d[field] = str(val)
    return d


class MTSnapshotWorker(threading.Thread):
    daemon = True

    def __init__(self):
        super().__init__(name="bot-snapshot")
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()
        self.join(timeout=3)

    def run(self):
        logger.info("MTSnapshotWorker started (poll %ds)", POLL_INTERVAL)
        if not mt5.initialize():
            logger.warning("MT5 no disponible, snapshot worker espera")
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as e:
                logger.exception("snapshot tick error: %s", e)
            self._stop_event.wait(POLL_INTERVAL)
        logger.info("MTSnapshotWorker stopped")

    def _tick(self):
        account = mt5.account_info()
        if account:
            snap = {
                "login": account.login,
                "balance": round(account.balance, 2),
                "equity": round(account.equity, 2),
                "margin": round(account.margin, 2),
                "margin_free": round(account.margin_free, 2),
                "margin_level": round(account.margin_level, 2) if account.margin_level else None,
                "profit": round(account.profit, 2),
                "leverage": account.leverage,
                "currency": account.currency,
                "server": account.server,
                "name": account.name,
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            self._write_json(ACCOUNT_PATH, snap)
        else:
            logger.debug("account_info() returned None")

        positions = mt5.positions_get()
        rows = []
        if positions:
            rows = [_serialize_position(p) for p in positions]
        self._write_json(POSITIONS_PATH, rows)

    @staticmethod
    def _write_json(path: str, data):
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, path)
        except OSError as e:
            logger.warning("no se pudo escribir %s: %s", path, e)
