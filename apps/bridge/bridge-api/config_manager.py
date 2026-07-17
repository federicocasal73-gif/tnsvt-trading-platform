"""
ConfigManager — Lee/escribe config.json del bot MT5 desde el bridge.

Asume el bridge corre en la misma máquina que el bot (mismo path D:\\TradingBotMT5
configurable vía env BOT_DATA_DIR). Escritura atómica via write-then-rename.

También gestiona los archivos cmd_requests.json / cmd_responses.json que el
ScanWorker del bot consume para devolver resultados de scan Telegram.
"""

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger("bridge.config")

BASE_DIR = Path(
    os.getenv("BOT_DATA_DIR", r"D:\TradingBotMT5")
)
CONFIG_PATH = BASE_DIR / "config.json"
STATE_PATH = BASE_DIR / "bot_state.json"
CMD_REQ_PATH = BASE_DIR / "cmd_requests.json"
CMD_RESP_PATH = BASE_DIR / "cmd_responses.json"

_SCAN_RESULT_TTL_S = 600  # 10 minutos


class ConfigManager:
    """Acceso a config.json del bot + signal files para ScanWorker."""

    def read_config(self) -> dict:
        """Lee config.json del bot. Devuelve {} si no existe."""
        if not CONFIG_PATH.exists():
            return {}
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"config.json read failed: {e}")
            return {}

    def update_config(self, updates: dict) -> tuple[bool, str]:
        """Merge atómico de updates en config.json.

        Returns (success, message). Si BOT_DATA_DIR no existe o config.json
        no se puede leer, devuelve (False, "...").
        """
        if not BASE_DIR.exists():
            return False, f"BOT_DATA_DIR no existe: {BASE_DIR}"

        if not CONFIG_PATH.exists():
            current = {}
        else:
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    current = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                return False, f"No pude leer config.json: {e}"

        merged = {**current, **updates}
        tmp = CONFIG_PATH.with_suffix(".json.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(merged, f, indent=4, ensure_ascii=False)
            os.replace(tmp, CONFIG_PATH)
        except OSError as e:
            return False, f"No pude escribir config.json: {e}"

        logger.info(
            f"config.json updated keys={[k for k in updates.keys()]}"
        )
        return True, "ok"

    def request_scan(self) -> str:
        """Escribe cmd_requests.json pidiendo scan Telegram. Devuelve request_id."""
        request_id = f"scan_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        payload = {"action": "scan_channels", "request_id": request_id}
        tmp = CMD_REQ_PATH.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        os.replace(tmp, CMD_REQ_PATH)
        logger.info(f"scan requested id={request_id}")
        return request_id

    def read_scan_result(self) -> Optional[dict]:
        """Lee cmd_responses.json si existe y no está expirado.

        Returns None si no hay resultado, o el dict con 'data' / 'error'.
        """
        if not CMD_RESP_PATH.exists():
            return None
        try:
            with open(CMD_RESP_PATH, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"cmd_responses.json read failed: {e}")
            return None

        completed_at = payload.get("completed_at", "")
        try:
            ts = time.mktime(time.strptime(completed_at, "%Y-%m-%dT%H:%M:%SZ"))
            if time.time() - ts > _SCAN_RESULT_TTL_S:
                logger.info("scan result expired")
                return None
        except ValueError:
            pass

        return payload

    def scan_in_progress(self) -> bool:
        """Detecta si hay un scan corriendo (request sin response aún)."""
        if CMD_REQ_PATH.exists():
            return True
        if not CONFIG_PATH.exists():
            return False
        return False

    # ─── Bot control (start/stop via bot_state.json) ────────────────────

    def read_state(self) -> dict:
        """Lee bot_state.json (status, optional last_change, etc).

        Devuelve {"status": "UNKNOWN"} si no existe o no se puede leer.
        """
        if not STATE_PATH.exists():
            return {"status": "UNKNOWN", "_missing": True}
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"bot_state.json read failed: {e}")
            return {"status": "UNKNOWN", "_error": str(e)}

    def write_state(self, status: str) -> tuple[bool, str]:
        """Sobrescribe bot_state.json con {status: status}.

        Valores válidos según el bot: DEPLOYED | STOPPED | WAITING_CONFIG.
        """
        if status not in ("DEPLOYED", "STOPPED", "WAITING_CONFIG"):
            return False, f"status inválido: {status}"

        body = {"status": status, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        tmp = STATE_PATH.with_suffix(".json.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(body, f, ensure_ascii=False, indent=2)
            os.replace(tmp, STATE_PATH)
        except OSError as e:
            return False, f"No pude escribir bot_state.json: {e}"
        logger.info(f"bot_state.json set to {status}")
        return True, "ok"
