"""
NATS client para el orchestrator.

- Se suscribe a tnsvt.lst.signal (señal cruda del liquidity-engine)
- Publica en trading.signal.validated (formato SignalInput para execution-engine)
- Se suscribe a trading.control.pause / trading.control.resume
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Awaitable, Callable, Optional

import nats
from nats.aio.client import Client as NATSClient

from app.models import LSTSignalIn, SignalInput

logger = logging.getLogger(__name__)

SignalCallback = Callable[[LSTSignalIn], Awaitable[None]]
ControlCallback = Callable[[str], Awaitable[None]]


class NATSClient:
    def __init__(
        self,
        url: str,
        stream: str,
        subject_in: str,
        subject_out: str,
        control_subject: str = "trading.control",
    ) -> None:
        self._url = url
        self._stream = stream
        self._subject_in = subject_in
        self._subject_out = subject_out
        self._control_subject = control_subject
        self._nc: Optional[NATSClient] = None
        self._lock = asyncio.Lock()
        self._input_stream: str = stream
        self._output_stream: str = stream
        self._control_callback: Optional[ControlCallback] = None

    async def connect(self) -> None:
        async with self._lock:
            if self._nc and self._nc.is_connected:
                return
            self._nc = await nats.connect(self._url, max_reconnect_attempts=10)
            js = self._nc.jetstream()

            try:
                info_lst = await js.find_stream_name_by_subject(self._subject_in)
                logger.info("Stream for %s: %s", self._subject_in, info_lst)
                self._input_stream = info_lst
            except Exception as e:
                logger.warning("Could not find stream for %s: %s", self._subject_in, e)
                self._input_stream = self._stream

            try:
                info_out = await js.find_stream_name_by_subject(self._subject_out)
                logger.info("Stream for %s: %s", self._subject_out, info_out)
                self._output_stream = info_out
            except Exception as e:
                logger.warning("Could not find stream for %s: %s", self._subject_out, e)
                self._output_stream = self._stream

            logger.info("Connected to NATS at %s (in=%s, out=%s)", self._url, self._input_stream, self._output_stream)

    async def close(self) -> None:
        if self._nc:
            await self._nc.drain()
            self._nc = None

    def set_control_callback(self, callback: ControlCallback) -> None:
        self._control_callback = callback

    async def subscribe_signals(self, callback: SignalCallback) -> None:
        if not self._nc:
            await self.connect()
        assert self._nc is not None
        logger.info("Subscribing to %s (NATS core, queue group for load balancing)", self._subject_in)

        async def handler(msg):
            try:
                data = json.loads(msg.data.decode())
                signal = LSTSignalIn.model_validate(data)
                await callback(signal)
            except Exception as e:
                logger.error("Error processing signal: %s", e, exc_info=True)

        await self._nc.subscribe(self._subject_in, cb=handler)

    async def subscribe_control(self) -> None:
        if not self._nc:
            await self.connect()
        assert self._nc is not None

        async def handler(msg):
            try:
                data = json.loads(msg.data.decode())
                action = data.get("action", "")
                logger.info("Control message received: %s", action)
                if self._control_callback:
                    await self._control_callback(action)
            except Exception as e:
                logger.error("Error processing control message: %s", e, exc_info=True)

        await self._nc.subscribe(f"{self._control_subject}.>", cb=handler)
        logger.info("Subscribed to %s.> for control messages", self._control_subject)

    async def publish_signal(self, signal: SignalInput) -> int:
        if not self._nc:
            await self.connect()
        assert self._nc is not None
        payload = signal.to_json_bytes()
        await self._nc.publish(self._subject_out, payload)
        logger.info(
            "Published SignalInput (NATS core) symbol=%s action=%s conf=%.2f",
            signal.symbol, signal.action, signal.confidence,
        )
        return 0