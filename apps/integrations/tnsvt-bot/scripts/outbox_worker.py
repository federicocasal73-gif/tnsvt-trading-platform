"""
TNSVT Bridge Outbox Worker — corre como thread daemon dentro del bot MT5.

Cuando el bot ejecuta una orden, la inserta en SQLite (bridge_pending).
Este worker reintenta publicarla al bridge :8522 con backoff exponencial.
Funciona aunque el bridge esté caído: las órdenes se acumulan y se publican
cuando vuelva.
"""

import json
import threading
import time
import logging

import requests

import database

logger = logging.getLogger("bot.outbox")

DEFAULT_BRIDGE_URL = "http://localhost:8522"
POLL_INTERVAL = 5.0
HTTP_TIMEOUT = 3.0


class OutboxWorker(threading.Thread):
    """Worker daemon que sincroniza bridge_pending → bridge :8522."""

    def __init__(self, bridge_url: str = DEFAULT_BRIDGE_URL):
        super().__init__(name="bot-bridge-outbox", daemon=True)
        self.bridge_url = bridge_url.rstrip("/")
        self._stop_event = threading.Event()

    def run(self):
        logger.info(f"OutboxWorker started → {self.bridge_url}")
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as e:
                logger.exception(f"OutboxWorker tick error: {e}")
            self._stop_event.wait(POLL_INTERVAL)

    def stop(self):
        self._stop_event.set()
        self.join(timeout=3)

    def _tick(self):
        pending = database.fetch_pending_bridge(limit=10)
        for event in pending:
            if self._stop_event.is_set():
                break
            self._publish_one(event)

    def _publish_one(self, event: dict):
        event_id = event["id"]
        payload = json.loads(event["payload"])
        source = event["source"]
        attempt = event["attempts"] + 1

        endpoint = self._route(source)
        url = f"{self.bridge_url}{endpoint}"

        try:
            r = requests.post(url, json=payload, timeout=HTTP_TIMEOUT)
            if r.status_code < 500:
                database.mark_bridge_delivered(event_id)
                logger.info(
                    f"Delivered event {event_id} → {endpoint} "
                    f"(HTTP {r.status_code})"
                )
            else:
                err = f"HTTP {r.status_code}: {r.text[:200]}"
                database.mark_bridge_failed(event_id, err, attempt)
                logger.warning(
                    f"Failed event {event_id} → {endpoint}: {err} "
                    f"(attempt {attempt})"
                )
        except requests.RequestException as e:
            err = f"{type(e).__name__}: {e}"[:500]
            database.mark_bridge_failed(event_id, err, attempt)
            logger.warning(
                f"Network error event {event_id}: {err} (attempt {attempt})"
            )

    @staticmethod
    def _route(source: str) -> str:
        return {
            "mt5-bot": "/api/v1/bridge/mt5/order",
            "telegram-signal": "/api/v1/bridge/telegram/signal",
            "mt5-mobile": "/api/v1/bridge/mt5/mobile",
        }.get(source, "/api/v1/bridge/unknown")
