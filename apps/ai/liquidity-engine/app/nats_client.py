import json
import logging

import nats

from app.models import LSTSignal

logger = logging.getLogger(__name__)


class NATSPublisher:
    def __init__(self, url: str, stream: str, subject: str):
        self._url = url
        self._stream = stream
        self._subject = subject
        self._nc: nats.NATS | None = None

    async def connect(self):
        self._nc = await nats.connect(self._url)
        js = self._nc.jetstream()
        try:
            await js.add_stream(name=self._stream, subjects=[self._subject])
        except Exception:
            logger.info("Stream %s already exists", self._stream)
        logger.info("Connected to NATS at %s", self._url)

    async def publish(self, signal: LSTSignal):
        if not self._nc:
            raise RuntimeError("NATS not connected")
        data = signal.model_dump_json().encode()
        ack = await self._nc.jetstream().publish(self._subject, data)
        logger.debug("Published LST signal (seq=%d)", ack.seq)

    async def close(self):
        if self._nc:
            await self._nc.drain()
