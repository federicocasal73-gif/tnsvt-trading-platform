"""Thin async HTTP client for the Ollama inference server."""
from __future__ import annotations

from typing import Any

import httpx
import structlog

log = structlog.get_logger("ai-core.ollama")

_DEFAULT_GENERATE_BODY = {
    "options": {
        "temperature": 0.2,
        "top_p": 0.9,
        "num_predict": 256,
    }
}


class OllamaClient:
    def __init__(self, settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.ollama_url,
            timeout=httpx.Timeout(settings.ollama_timeout_sec, connect=5.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )

    async def generate(self, prompt: str, *, model: str | None = None, system: str | None = None) -> dict[str, Any]:
        if not self._settings.ollama_enabled:
            return {"available": False, "error": "disabled"}

        body = {**_DEFAULT_GENERATE_BODY, "model": model or self._settings.ollama_model, "prompt": prompt, "stream": False}
        if system:
            body["system"] = system

        try:
            resp = await self._client.post("/api/generate", json=body)
            resp.raise_for_status()
            data = resp.json()
            return {
                "available": True,
                "response": data.get("response", "").strip(),
                "model": data.get("model", body["model"]),
                "eval_count": data.get("eval_count"),
                "eval_duration_ns": data.get("eval_duration"),
            }
        except httpx.TimeoutException:
            log.warning("ollama.timeout")
            return {"available": False, "error": "timeout"}
        except Exception as e:
            log.warning("ollama.error", error=str(e))
            return {"available": False, "error": str(e)}

    async def ping(self) -> bool:
        try:
            resp = await self._client.get("/api/tags", timeout=2.0)
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        await self._client.aclose()