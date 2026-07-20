"""
BotSyncer — Daemon que sincroniza trades del SQLite del bot MT5 al bridge.

Cada 30 segundos lee trades del bot_data.db (D:\TradingBotMT5) y los
upsert a la tabla trades del bridge para mantener analytics actualizados
aunque el bot no publique vía POST.
"""

import logging
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta

from db import TradesDB

logger = logging.getLogger("bridge.syncer")

SYNC_INTERVAL = 30
BOT_DB_PATH = os.getenv("BOT_SQLITE_PATH", r"D:\TradingBotMT5\bot_data.db")
# Solo sincronizamos trades con no mas de N dias de antiguedad para
# evitar que datos viejos del bot_data.db inunden la analytics del bridge.
# Por defecto: ultimos 90 dias, configurable via env.
SYNC_DAYS_BACK = int(os.getenv("BOT_SYNC_DAYS_BACK", "90"))


class BotSyncer(threading.Thread):
    daemon = True

    def __init__(self, bridge_db: TradesDB):
        super().__init__(name="bridge-syncer")
        self.bridge_db = bridge_db
        self._stop_event = threading.Event()

    def run(self):
        logger.info(
            "BotSyncer iniciado → %s (cada %ds, ventana=%dd)",
            BOT_DB_PATH, SYNC_INTERVAL, SYNC_DAYS_BACK,
        )
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as e:
                logger.warning("syncer tick error: %s", e)
            self._stop_event.wait(SYNC_INTERVAL)

    def stop(self):
        self._stop_event.set()

    def _tick(self):
        if not os.path.exists(BOT_DB_PATH):
            logger.debug("syncer: bot DB no encontrada en %s", BOT_DB_PATH)
            return

        cutoff = (datetime.now() - timedelta(days=SYNC_DAYS_BACK)).strftime("%Y-%m-%d %H:%M:%S")

        try:
            with sqlite3.connect(BOT_DB_PATH, timeout=5) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """SELECT ticket, symbol, action, price AS open_price,
                              sl, tp, pnl, close_price, commission, swap,
                              channel_id, channel_title, topic_id,
                              status, closed_at, date AS opened_at
                       FROM trades
                       WHERE ticket > 0
                         AND date >= ?
                       ORDER BY id DESC""",
                    (cutoff,),
                ).fetchall()
        except Exception as e:
            logger.warning("syncer: error leyendo bot DB: %s", e)
            return

        count = 0
        for row in rows:
            payload = dict(row)
            payload["received_at"] = payload.get("opened_at") or time.strftime(
                "%Y-%m-%dT%H:%M:%S", time.gmtime()
            )
            payload["volume"] = 0  # el bot no guarda volumen en trades; puede no estar
            try:
                self.bridge_db.upsert_trade(payload)
                count += 1
            except Exception as e:
                logger.warning("syncer: error upsert ticket=%s: %s", payload.get("ticket"), e)

        if count:
            logger.info("syncer: %d trade(s) sincronizado(s) (ultimos %d dias)", count, SYNC_DAYS_BACK)
