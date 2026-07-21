"""
BackfillWorker — Daemon que cierra trades abiertos consultando MT5.

Cada 5 minutos:
1. Lee trades con status='OPEN' y ticket != 0 desde SQLite
2. Para cada uno, llama mt5.history_deals_get(ticket) para obtener
   close_price, pnl, commission, swap
3. Si el deal existe → actualiza y marca status='CLOSED'
"""

import threading
import time
import logging
import sqlite3
from datetime import datetime, timezone

import MetaTrader5 as mt5

import database

logger = logging.getLogger("bot.backfill")

INTERVAL = 300  # 5 segundos * 60 = 5 minutos


class BackfillWorker(threading.Thread):
    daemon = True

    def __init__(self):
        super().__init__(name="bot-backfill")
        self._stop_event = threading.Event()

    def run(self):
        logger.info("BackfillWorker iniciado (cada %ds)", INTERVAL)
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as e:
                logger.exception("backfill tick error: %s", e)
            self._stop_event.wait(INTERVAL)

    def stop(self):
        self._stop_event.set()

    def _tick(self):
        """Una iteración del backfill."""
        if not mt5.initialize():
            logger.warning("backfill: MT5 no disponible, skip")
            return

        try:
            conn = sqlite3.connect(database.DB_NAME, timeout=5)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            rows = c.execute(
                "SELECT id, ticket, symbol FROM trades WHERE status='OPEN' AND ticket != 0"
            ).fetchall()

            if not rows:
                return

            updated = 0
            for row in rows:
                ticket = row["ticket"]
                deals = mt5.history_deals_get(position=ticket)
                if not deals:
                    continue

                for deal in deals:
                    if deal.position != ticket:
                        continue
                    now = datetime.now(timezone.utc).isoformat()
                    c.execute(
                        """UPDATE trades SET
                            close_price=?, pnl=?, commission=?, swap=?,
                            closed_at=?, status='CLOSED'
                        WHERE id=?""",
                        (deal.price, deal.profit, deal.commission,
                         deal.swap, now, row["id"]),
                    )
                    updated += 1
                    break

            conn.commit()
            if updated:
                logger.info("backfill: %d trade(s) cerrado(s)", updated)

        except Exception as e:
            logger.warning("backfill tick error: %s", e)
        finally:
            try:
                conn.close()
            except Exception:
                pass