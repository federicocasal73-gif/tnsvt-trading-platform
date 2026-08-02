"""
NATS publisher para news-analyzer (Sprint 3.3).

Publica a NATS JetStream cuando llega una noticia de alto impacto (FED,
NFP, CPI, etc.) con un símbolo afectado claro. Esto entra en el
mismo pipeline que las señales manuales/webhook/telegram, pasando por
signal-engine → risk-engine → execution-engine.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import nats
from nats.errors import TimeoutError as NatsTimeoutError

logger = logging.getLogger("NewsAnalyzer.Nats")


class NewsNatsPublisher:
    """Publica eventos de news a NATS JetStream subject 'trading.signal.news_based'."""

    def __init__(self, nats_url: str, subject: str = "trading.signal.news_based"):
        self.nats_url = nats_url
        self.subject = subject
        self.nc: Optional[nats.NATS] = None
        self.js: Optional[nats.JetStreamContext] = None
        self._lock = asyncio.Lock()
        # Cooldown por símbolo+action para evitar spam (5 minutos)
        self._cooldown: dict[str, float] = {}
        self._cooldown_seconds = 300

    async def connect(self) -> bool:
        """Conecta a NATS. Devuelve True si OK, False si falla (sigue funcionando sin NATS)."""
        try:
            self.nc = await asyncio.wait_for(
                nats.connect(self.nats_url, connect_timeout=3),
                timeout=5,
            )
            self.js = self.nc.jetstream()
            logger.info(f"NATS connected: {self.nats_url}")
            return True
        except (NatsTimeoutError, OSError, Exception) as e:
            logger.warning(f"NATS unavailable: {e}. News will not publish signals.")
            self.nc = None
            self.js = None
            return False

    async def close(self):
        if self.nc:
            await self.nc.close()
            self.nc = None
            self.js = None

    def _cooldown_key(self, symbol: str, action: str) -> str:
        return f"{symbol}:{action}"

    def _on_cooldown(self, key: str) -> bool:
        last = self._cooldown.get(key, 0)
        import time as _t
        return (_t.time() - last) < self._cooldown_seconds

    def _set_cooldown(self, key: str) -> None:
        import time as _t
        self._cooldown[key] = _t.time()

    async def maybe_publish_signal(
        self,
        symbol: str,
        action: str,            # "BUY" / "SELL"
        confidence: float,
        reason: str,
        tenant_id: str = "",
        stop_loss: Optional[float] = None,
        take_profits: Optional[list] = None,
    ) -> Optional[str]:
        """Publica una señal news-based si no está en cooldown y NATS está vivo.

        Devuelve el signal_id publicado o None si no se publicó.
        """
        if not self.js:
            return None
        key = self._cooldown_key(symbol, action)
        if self._on_cooldown(key):
            logger.debug(f"news_signal cooldown: {key}")
            return None
        if action not in ("BUY", "SELL"):
            return None
        if confidence < 0.5:
            return None

        sig = {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "source": "news-analyzer",
            "symbol": symbol,
            "action": action,
            "entry_price": None,
            "stop_loss": stop_loss,
            "take_profits": take_profits or [],
            "lot_mode": "risk_based",
            "comment": f"news: {reason}"[:200],
            "confidence": round(confidence, 3),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            async with self._lock:
                payload = json.dumps(sig).encode()
                ack = await self.js.publish(self.subject, payload)
                # nats-py PubAck es truthy si se recibió ack del server.
                if ack:
                    self._set_cooldown(key)
                    logger.info(f"news_signal published: {symbol} {action} conf={confidence:.2f} reason={reason[:60]}")
                    return sig["id"]
                logger.warning(f"news_signal publish not acked: {ack}")
                return None
        except Exception as e:
            logger.warning(f"news_signal publish failed: {e}")
            return None
