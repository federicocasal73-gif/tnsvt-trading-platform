"""
Cliente para obtener rates del mt5-connector.
"""
from __future__ import annotations

import logging
from typing import List, Optional

import httpx

logger = logging.getLogger(__name__)


class PriceFeedClient:
    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None
        self._timeout = timeout

    async def start(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_rates(self, symbol: str, timeframe: str, limit: int = 100) -> List[dict]:
        if self._client is None:
            await self.start()
        assert self._client is not None
        try:
            resp = await self._client.get(
                f"{self._base_url}/rates",
                params={"symbol": symbol, "timeframe": timeframe, "limit": limit},
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("rates") or data.get("data") or []
            return []
        except Exception as e:
            logger.warning("get_rates(%s, %s) failed: %s", symbol, timeframe, e)
            return []

    async def get_account_info(self) -> dict:
        if self._client is None:
            await self.start()
        assert self._client is not None
        try:
            resp = await self._client.get(f"{self._base_url}/api/v1/brokers/accounts/default")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning("get_account_info failed: %s", e)
            return {}