"""
Pool de workers para mt5-connector (Sprint 2.1).

Sprint 1 asumía 1 sola instancia de mt5-connector (un único login MT5).
Para 12-24 cuentas con 1-10 cuentas por instancia MT5, levantamos N
instancias de mt5-connector (cada una en su puerto, ej. 8007, 8008, 8009, 8010)
y round-robin entre ellas.

Este módulo expone:
- MT5WorkerPool: round-robin stateful
- call_mt5_connector(): helper que toma un path, hace POST/GET, retorna
  respuesta del primer worker que responda 2xx
- get_metrics(): contadores para /metrics (requests, errors, latency p50/p99)
"""
import os
import time
import threading
import logging
from collections import deque
from typing import Optional

import requests

logger = logging.getLogger("bridge.mt5_pool")


class MT5WorkerPool:
    """Round-robin pool sobre N instancias de mt5-connector."""

    def __init__(self, urls: list[str], timeout: int = 15):
        self.urls = urls
        self.timeout = timeout
        self._lock = threading.Lock()
        self._idx = 0  # round-robin counter
        # Métricas: ring buffer de las últimas N latencias
        self._latencies: deque[float] = deque(maxlen=500)
        self._requests = 0
        self._errors = 0
        self._retries = 0

    def _next_url(self) -> str:
        with self._lock:
            url = self.urls[self._idx % len(self.urls)]
            self._idx += 1
            return url

    def call(self, method: str, path: str, json_body: Optional[dict] = None,
             timeout: Optional[int] = None) -> tuple[Optional[requests.Response], str | None]:
        """Round-robin call. Si el primero falla, intenta el siguiente.

        Returns (response, last_error_url). Si todos fallan, response=None
        y el caller puede decidir el fallback.
        """
        attempts = len(self.urls)
        last_error: str | None = None
        for i in range(attempts):
            url = self._next_url()
            full = f"{url.rstrip('/')}{path}"
            start = time.time()
            try:
                resp = requests.request(
                    method=method,
                    url=full,
                    json=json_body,
                    timeout=timeout or self.timeout,
                )
                latency = time.time() - start
                with self._lock:
                    self._requests += 1
                    self._latencies.append(latency)
                if resp.status_code < 500:
                    # 2xx/3xx/4xx: success del upstream (4xx es "input error",
                    # no es culpa del worker)
                    if resp.status_code >= 400:
                        logger.debug("mt5_pool %s %s → %d (input error)", method, path, resp.status_code)
                    return resp, None
                # 5xx: rotar al siguiente
                last_error = f"{full} → {resp.status_code}"
                with self._lock:
                    self._retries += 1
                logger.warning("mt5_pool retry %s (5xx from %s)", path, url)
            except requests.exceptions.ConnectionError as e:
                latency = time.time() - start
                with self._lock:
                    self._requests += 1
                    self._errors += 1
                    self._latencies.append(latency)
                last_error = f"{full} → connection refused: {e}"
                logger.warning("mt5_pool connection error: %s", url)
            except Exception as e:
                latency = time.time() - start
                with self._lock:
                    self._requests += 1
                    self._errors += 1
                    self._latencies.append(latency)
                last_error = f"{full} → {type(e).__name__}: {e}"
                logger.warning("mt5_pool error: %s: %s", url, e)
        return None, last_error

    def metrics(self) -> dict:
        with self._lock:
            lats = sorted(self._latencies)
            n = len(lats)
            p50 = lats[n // 2] if n else 0.0
            p95 = lats[int(n * 0.95)] if n else 0.0
            p99 = lats[min(int(n * 0.99), n - 1)] if n else 0.0
            return {
                "urls": self.urls,
                "size": len(self.urls),
                "requests": self._requests,
                "errors": self._errors,
                "retries": self._retries,
                "p50_ms": round(p50 * 1000, 2),
                "p95_ms": round(p95 * 1000, 2),
                "p99_ms": round(p99 * 1000, 2),
                "samples": n,
            }


# Singleton lazy-init
_pool: MT5WorkerPool | None = None
_pool_lock = threading.Lock()


def get_pool() -> MT5WorkerPool:
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is not None:
            return _pool
        urls_env = os.getenv(
            "MT5_CONNECTOR_URLS",
            os.getenv("MT5_CONNECTOR_URL", "http://localhost:8007"),
        )
        urls = [u.strip() for u in urls_env.split(",") if u.strip()]
        if not urls:
            urls = ["http://localhost:8007"]
        _pool = MT5WorkerPool(urls=urls, timeout=15)
        logger.info("MT5WorkerPool inicializado con %d worker(s): %s", len(urls), urls)
        return _pool
