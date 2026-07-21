"""
Mini MT5 snapshot writer — Cada 3s escribe account_snapshot.json y
positions_snapshot.json. El bridge-api :8522 los lee directamente.

Loguea a mt5_snapshot_debug.log para diagnosticar.
"""
import json
import logging
import os
import sys
import time

import MetaTrader5 as mt5

BASE_DIR = r"D:\TradingBotMT5"
ACCOUNT_PATH = os.path.join(BASE_DIR, "account_snapshot.json")
POSITIONS_PATH = os.path.join(BASE_DIR, "positions_snapshot.json")
LOG_PATH = os.path.join(BASE_DIR, "mt5_snapshot_debug.log")

POLL_INTERVAL = 3.0

TYPE_MAP = {mt5.ORDER_TYPE_BUY: "BUY", mt5.ORDER_TYPE_SELL: "SELL"}
POSITION_FIELDS = [
    "ticket", "symbol", "type", "volume", "price_open",
    "sl", "tp", "price_current", "profit", "swap", "commission",
    "magic", "comment", "time",
]

logging.basicConfig(
    filename=LOG_PATH,
    filemode="a",
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("mt5-mini")


def write_atomic(path, data):
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
        return True
    except OSError as e:
        log.warning("write %s failed: %s", path, e)
        return False


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


def tick():
    try:
        account = mt5.account_info()
    except Exception as e:
        log.warning("account_info error: %s", e)
        return

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
        if write_atomic(ACCOUNT_PATH, snap):
            log.info("account: bal=%.2f equity=%.2f margin=%.2f profit=%.2f lev=%d",
                     snap["balance"], snap["equity"], snap["margin"],
                     snap["profit"], snap["leverage"])
    else:
        log.warning("account_info() retornó None")

    try:
        positions = mt5.positions_get()
    except Exception as e:
        log.warning("positions_get error: %s", e)
        positions = None

    rows = []
    if positions:
        rows = [_serialize_position(p) for p in positions]
    if write_atomic(POSITIONS_PATH, rows):
        log.info("positions: %d abiertas", len(rows))


def main():
    log.info("=== mini mt5_snapshot arrancado ===")
    if not mt5.initialize():
        log.warning("mt5.initialize() falló; reintento en cada tick")
    else:
        log.info("mt5 inicializado OK; cuenta=%s",
                 mt5.account_info().login if mt5.account_info() else "?")

    while True:
        tick()
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("interrumpido")
    except Exception as e:
        log.exception("fatal: %s", e)
        sys.exit(1)
