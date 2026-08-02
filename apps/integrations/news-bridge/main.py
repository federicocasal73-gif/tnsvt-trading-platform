"""News Bridge — consume trading.signal.news_based y la inyecta al signal-engine.

Decisión del usuario: news → ejecución vía signal-engine.

Reglas:
- Suscribe NATS JetStream subject `trading.signal.news_based` con durable
  consumer "news-bridge" y manual_ack para no perder mensajes.
- Convierte cada mensaje a SubmitSignalRequest del signal-engine.
- POST /api/v1/signals (signal-engine) con X-Tenant-ID desde env.
- Cooldown 5 min por (symbol, action) para evitar spam.
- ack en éxito; nak tras error de forward para reintento.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Optional

import httpx
import nats
from nats.errors import TimeoutError as NatsTimeoutError
from nats.js.errors import NotFoundError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("NewsBridge")


class NewsBridge:
    COOLDOWN_SECONDS = 300

    def __init__(self) -> None:
        self.nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
        self.subject = os.getenv("NEWS_SUBJECT", "trading.signal.news_based")
        self.stream = os.getenv("NATS_STREAM", "tnsvt")
        self.durable = os.getenv("NEWS_BRIDGE_DURABLE", "news-bridge")
        self.signal_engine_url = os.getenv("SIGNAL_ENGINE_URL", "http://localhost:8003")
        self.tenant_id = os.getenv("DEFAULT_TENANT_ID", "")
        self.api_key = os.getenv("SIGNAL_INGEST_API_KEY", "")

        self._cooldown: dict[str, float] = {}
        self._nc: Optional[nats.NATS] = None
        self._js = None
        self._sub = None
        self._http = httpx.AsyncClient(timeout=10)
        self._stopped = False

    async def connect(self) -> bool:
        try:
            self._nc = await asyncio.wait_for(
                nats.connect(self.nats_url, connect_timeout=3),
                timeout=5,
            )
            self._js = self._nc.jetstream()
            logger.info("NATS connected (JetStream ready): %s", self.nats_url)
            return True
        except (NatsTimeoutError, OSError, Exception) as e:
            logger.warning("NATS unavailable: %s. News-bridge will retry.", e)
            self._nc = None
            self._js = None
            return False

    async def close(self) -> None:
        self._stopped = True
        if self._sub is not None:
            try:
                await self._sub.unsubscribe()
            except Exception:
                pass
            self._sub = None
        if self._nc:
            try:
                await self._nc.drain()
            except Exception:
                pass
            self._nc = None
            self._js = None
        await self._http.aclose()

    def _cooldown_key(self, symbol: str, action: str) -> str:
        return f"{symbol}:{action}"

    def _on_cooldown(self, key: str) -> bool:
        last = self._cooldown.get(key, 0)
        return (time.time() - last) < self.COOLDOWN_SECONDS

    def _set_cooldown(self, key: str) -> None:
        self._cooldown[key] = time.time()

    async def _forward_to_signal_engine(self, msg: dict) -> tuple[bool, int]:
        symbol = (msg.get("symbol") or "").upper()
        action = msg.get("action") or ""
        if not symbol or action not in ("BUY", "SELL"):
            logger.debug("Skipping news signal: invalid symbol/action %s/%s", symbol, action)
            return False, 0

        key = self._cooldown_key(symbol, action)
        if self._on_cooldown(key):
            logger.debug("news cooldown: %s", key)
            return False, 0

        body = {
            "symbol": symbol,
            "action": action,
            "entry_price": msg.get("entry_price"),
            "stop_loss": msg.get("stop_loss"),
            "take_profits": msg.get("take_profits") or [],
            "lot_mode": msg.get("lot_mode") or "risk_based",
            "comment": (msg.get("comment") or "")[:200],
            "source": "news-analyzer",
            "tenant_id": self.tenant_id or msg.get("tenant_id") or "",
            "confidence": float(msg.get("confidence", 0.5)),
        }

        headers = {"Content-Type": "application/json"}
        if self.tenant_id:
            headers["X-Tenant-ID"] = self.tenant_id
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        try:
            resp = await self._http.post(
                f"{self.signal_engine_url}/api/v1/signals",
                json=body,
                headers=headers,
            )
        except Exception as e:
            logger.warning("forward to signal-engine failed: %s", e)
            return False, 0

        status = resp.status_code
        if status in (200, 201):
            self._set_cooldown(key)
            logger.info(
                "news-bridge forwarded: %s %s conf=%.2f status=%d",
                symbol, action, body["confidence"], status,
            )
            return True, status

        logger.warning(
            "news-bridge forward rejected: status=%d body=%s",
            status, resp.text[:200],
        )
        return False, status

    async def _on_message(self, msg) -> None:
        try:
            data = json.loads(msg.data.decode("utf-8"))
        except Exception as e:
            logger.warning("invalid json in news message: %s", e)
            try:
                await msg.ack()
            except Exception:
                pass
            return

        ok, status = await self._forward_to_signal_engine(data)
        try:
            if ok:
                await msg.ack()
            elif status == 409:
                # 409 = DUPLICATE. signal-engine ya tiene esta senal. ack y drop.
                logger.debug("duplicate signal (409), ack to drop")
                await msg.ack()
            else:
                await msg.nak()
        except Exception as e:
            logger.debug("ack/nak failed: %s", e)

    async def _ensure_stream(self) -> bool:
        """Crea el stream si no existe (best-effort)."""
        if self._js is None:
            return False
        try:
            await self._js.stream_info(self.stream)
            return True
        except NotFoundError:
            pass
        except Exception as e:
            logger.warning("stream_info failed: %s", e)
            return False
        try:
            await self._js.add_stream(
                name=self.stream,
                subjects=[self.subject],
            )
            logger.info("created stream %s for subject %s", self.stream, self.subject)
            return True
        except Exception as e:
            logger.warning("add_stream failed (may already exist or no permission): %s", e)
            return False

    async def _subscribe(self) -> bool:
        if self._js is None:
            return False
        if not await self._ensure_stream():
            pass

        try:
            self._sub = await self._js.subscribe(
                subject=self.subject,
                cb=self._on_message,
                durable=self.durable,
                manual_ack=True,
            )
            logger.info("JetStream subscribed: subject=%s durable=%s", self.subject, self.durable)
            return True
        except Exception as e:
            logger.warning("js.subscribe failed: %s", e)
            return False

    async def run(self) -> None:
        backoff = 1
        while not self._stopped:
            if self._nc is None or self._js is None:
                ok = await self.connect()
                if not ok:
                    await asyncio.sleep(min(backoff, 30))
                    backoff *= 2
                    continue
                backoff = 1

            if self._sub is None:
                if not await self._subscribe():
                    await asyncio.sleep(5)
                    continue

            try:
                while not self._stopped:
                    await asyncio.sleep(1)
                if self._sub is not None:
                    await self._sub.unsubscribe()
                    self._sub = None
            except Exception as e:
                logger.warning("subscription error: %s. Reconnecting...", e)
                try:
                    if self._sub is not None:
                        await self._sub.unsubscribe()
                except Exception:
                    pass
                self._sub = None
                if self._nc:
                    try:
                        await self._nc.close()
                    except Exception:
                        pass
                    self._nc = None
                    self._js = None
                await asyncio.sleep(2)


async def main() -> None:
    bridge = NewsBridge()
    try:
        await bridge.run()
    finally:
        await bridge.close()


if __name__ == "__main__":
    asyncio.run(main())
