"""
Bridge API - Publisher worker.

Procesa la cola persistente y publica cada evento a TNSVT (gateway).
Si la publicación falla, el evento vuelve a la cola con backoff.
"""

import json
import logging
import os
import threading
import time
from typing import Optional

import requests

from outbox import Outbox

logger = logging.getLogger("bridge.publisher")


class Publisher:
    """Worker en background que sincroniza outbox → TNSVT."""

    def __init__(
        self,
        outbox: Outbox,
        gateway_url: str,
        api_key: Optional[str] = None,
        poll_interval: float = 2.0,
    ):
        self.outbox = outbox
        self.gateway_url = gateway_url.rstrip("/")
        self.api_key = api_key
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="bridge-publisher", daemon=True
        )
        self._thread.start()
        logger.info(f"Publisher started → {self.gateway_url}")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as e:
                logger.exception(f"Publisher tick error: {e}")
            self._stop_event.wait(self.poll_interval)

    def _tick(self) -> None:
        pending = self.outbox.fetch_pending(limit=10)
        for event in pending:
            if self._stop_event.is_set():
                break
            self._publish_one(event)

    def _publish_one(self, event: dict) -> None:
        event_id = event["id"]
        payload = json.loads(event["payload"])
        source = event["source"]
        attempt = event["attempts"] + 1

        # Mapear source → endpoint TNSVT
        endpoint = self._route(source, payload)

        try:
            r = requests.post(
                f"{self.gateway_url}{endpoint}",
                json=payload,
                headers=self._headers(),
                timeout=3,
            )
            if r.status_code < 500:
                self.outbox.mark_delivered(event_id)
                logger.info(
                    f"Delivered event {event_id} → {endpoint} "
                    f"(HTTP {r.status_code})"
                )
            else:
                err = f"HTTP {r.status_code}: {r.text[:200]}"
                self.outbox.mark_failed(event_id, err, attempt)
                logger.warning(
                    f"Failed event {event_id} → {endpoint}: {err} "
                    f"(attempt {attempt})"
                )
        except requests.RequestException as e:
            err = f"{type(e).__name__}: {e}"[:500]
            self.outbox.mark_failed(event_id, err, attempt)
            logger.warning(
                f"Network error event {event_id}: {err} (attempt {attempt})"
            )

    def _route(self, source: str, payload: dict) -> str:
        """Decide a qué endpoint de TNSVT enviar según el source."""
        if source == "mt5-bot":
            return "/api/v1/bridge/mt5/order"
        if source == "telegram-signal":
            return "/api/v1/bridge/telegram/signal"
        if source == "mt5-mobile":
            return "/api/v1/bridge/mt5/mobile"
        return "/api/v1/bridge/unknown"

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json", "X-Bridge-Source": "tnsvt-bridge"}
        if self.api_key:
            h["X-Bridge-Key"] = self.api_key
        return h
