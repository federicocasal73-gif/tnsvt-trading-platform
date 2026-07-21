"""
TNSVT Client — Cliente HTTP para comunicar el copiador y el bot de Telegram
con el **bridge-api FastAPI** unificado dentro del monorepo TNSVT V2.

Compatibilidad histórica
------------------------
El primer endpoint era TNSVT Symphony (PHP). Ahora todo pasa por
`apps/bridge/bridge-api/` (FastAPI). Esta clase mantiene el mismo
contrato de métodos que la versión original (`log_trade`, `update_trade`,
`update_status_field`, `get_dashboard`, etc.) pero los URLs apuntan al
nuevo bridge-api (paths `/api/v1/bridge/copier/...`).
"""
import os
import logging
import requests
from typing import Optional

logger = logging.getLogger("TNSVTClient")


class TNSVTClient:
    """Cliente HTTP que habla con el bridge-api FastAPI del V2."""

    def __init__(
        self,
        base_url: str = None,
        user_code: str = None,
        admin_password: str = None,
    ):
        # Default: bridge-api del V2 corriendo en localhost:8522
        # (env BRIDGE_PORT del apps/bridge/bridge-api/.env o docker-compose).
        self.base_url = (
            base_url or os.getenv("TNSVT_URL", "http://localhost:8522")
        ).rstrip("/")
        self.user_code = user_code or os.getenv("TNSVT_USER_CODE", "DEMO")
        # TNSVT_ADMIN_PASSWORD se mantiene por retrocompatibilidad pero ya
        # no se usa: el bridge-api no requiere auth en estos endpoints.
        self.admin_password = (
            admin_password or os.getenv("TNSVT_ADMIN_PASSWORD", "")
        ) or os.getenv("TNSVT_ADMIN_USER_CODE", "")
        self._enabled = bool(self.base_url and self.user_code)
        self._timeout = 10

        if self._enabled:
            logger.info(
                f"TNSVT Client initialized: {self.base_url} | user={self.user_code}"
            )
        else:
            logger.warning("TNSVT Client disabled (no URL or user_code)")

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _headers(self) -> dict:
        # El bridge-api unificado no requiere auth en /api/v1/bridge/copier/*
        # pero conservamos headers para futuro cuando pongamos auth.
        headers = {
            "Content-Type": "application/json",
            "X-User-Code": self.user_code,
        }
        if self.admin_password:
            headers["X-Admin-Password"] = self.admin_password
        return headers

    def log_trade(
        self,
        symbol: str,
        action: str,
        price=None,
        sl=None,
        tp=None,
        result="OPEN",
        pnl=0.0,
        channel="",
        account_id=None,
    ) -> Optional[int]:
        """POST /api/v1/bridge/copier/trades — Registra un trade en el journal.

        Compat: era `POST /api/copier/trades` en Symphony PHP.
        """
        if not self._enabled:
            return None

        payload = {
            "symbol": symbol,
            "action": action,
            "price": float(price) if price is not None else None,
            "sl": float(sl) if sl is not None else None,
            "tp": float(tp) if tp is not None else None,
            "result": result,
            "pnl": float(pnl),
            "channel_title": channel or None,
            "notes": f"Auto-copied from: {channel}" if channel else None,
        }
        if account_id is not None:
            payload["tenant_id"] = str(account_id)

        try:
            resp = requests.post(
                f"{self.base_url}/api/v1/bridge/copier/trades",
                json=payload,
                headers=self._headers(),
                timeout=self._timeout,
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                trade_id = data.get("id") or data.get("ticket")
                logger.info(
                    f"Trade logged to TNSVT: #{trade_id} {symbol} {action}"
                )
                return trade_id
            else:
                logger.error(
                    f"TNSVT log_trade failed [{resp.status_code}]: {resp.text[:200]}"
                )
                return None
        except requests.exceptions.ConnectionError:
            logger.warning("TNSVT no disponible (connection refused)")
            return None
        except Exception as e:
            logger.error(f"TNSVT log_trade error: {e}")
            return None

    def update_trade(self, trade_id: int, result=None, pnl=None, sl=None, tp=None) -> bool:
        """PUT /api/v1/bridge/copier/trades/{id} — Actualiza un trade existente."""
        if not self._enabled or not trade_id:
            return False

        payload = {}
        if result is not None:
            payload["result"] = result
        if pnl is not None:
            payload["pnl"] = float(pnl)
        if sl is not None:
            payload["sl"] = float(sl)
        if tp is not None:
            payload["tp"] = float(tp)
        if not payload:
            return False

        try:
            resp = requests.put(
                f"{self.base_url}/api/v1/bridge/copier/trades/{trade_id}",
                json=payload,
                headers=self._headers(),
                timeout=self._timeout,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"TNSVT update_trade error: {e}")
            return False

    def send_heartbeat(self, status_data: dict):
        """POST /api/v1/bridge/copier/status — Envia heartbeat al servidor.

        El endpoint hace merge con el status actual y guarda cada key como row.
        """
        if not self._enabled:
            return None
        try:
            resp = requests.post(
                f"{self.base_url}/api/v1/bridge/copier/status",
                json=status_data or {},
                headers=self._headers(),
                timeout=self._timeout,
            )
            return resp.json() if resp.status_code == 200 else None
        except Exception as e:
            logger.debug(f"TNSVT heartbeat error: {e}")
            return None

    def get_config(self) -> Optional[dict]:
        """GET /api/v1/bridge/config — Config del bot MT5 (channels/lot/risk)."""
        if not self._enabled:
            return None
        try:
            resp = requests.get(
                f"{self.base_url}/api/v1/bridge/config",
                headers=self._headers(),
                timeout=self._timeout,
            )
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            logger.debug(f"TNSVT get_config error: {e}")
            return None

    def test_connection(self) -> bool:
        """Verifica que el bridge-api este accesible (/health)."""
        if not self._enabled:
            return False
        try:
            resp = requests.get(f"{self.base_url}/health", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def get_dashboard(self) -> Optional[dict]:
        """GET /api/v1/bridge/copier/dashboard — Snapshot consolidado del copier."""
        if not self._enabled:
            return None
        try:
            resp = requests.get(
                f"{self.base_url}/api/v1/bridge/copier/dashboard",
                headers=self._headers(),
                timeout=self._timeout,
            )
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            logger.debug(f"TNSVT get_dashboard error: {e}")
            return None

    def get_recent_trades(self, limit: int = 50) -> list:
        """GET /api/v1/bridge/analytics/trades — Trades recientes del journal."""
        if not self._enabled:
            return []
        try:
            resp = requests.get(
                f"{self.base_url}/api/v1/bridge/analytics/trades",
                params={"limit": limit},
                headers=self._headers(),
                timeout=self._timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return data
                return data.get("trades", []) or data.get("data", []) or []
            return []
        except Exception as e:
            logger.debug(f"TNSVT get_recent_trades error: {e}")
            return []

    def update_status_field(self, **fields) -> bool:
        """POST /api/v1/bridge/copier/status — Merge con status actual."""
        if not self._enabled:
            return False
        try:
            resp = requests.post(
                f"{self.base_url}/api/v1/bridge/copier/status",
                json=fields,
                headers=self._headers(),
                timeout=self._timeout,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.debug(f"TNSVT update_status_field error: {e}")
            return False
