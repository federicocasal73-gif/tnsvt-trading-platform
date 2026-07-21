"""
ScanWorker — daemon thread que vigila cmd_requests.json en D:\\TradingBotMT5
y ejecuta scans de Telegram cuando el bridge lo solicita.

Flujo:
  1. Bridge escribe {"action": "scan_channels", "request_id": "abc123"} a
     cmd_requests.json
  2. ScanWorker (este thread) lo detecta, carga api_id/api_hash desde
     config.json, llama telegram_scan.scan_channels()
  3. Escribe resultado a cmd_responses.json con el mismo request_id
  4. Bridge lee cmd_responses.json y lo expone vía GET
     /api/v1/bridge/telegram/channels

Polling cada 2s. Atómico: solo un proceso procesa cada request (delete
después de leer).
"""

import json
import logging
import os
import threading
import time

logger = logging.getLogger("bot.scan")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CMD_REQ_PATH = os.path.join(BASE_DIR, "cmd_requests.json")
CMD_RESP_PATH = os.path.join(BASE_DIR, "cmd_responses.json")
POLL_INTERVAL = 2.0


def _load_config() -> dict:
    cfg_path = os.path.join(BASE_DIR, "config.json")
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"config.json read failed: {e}")
        return {}


class ScanWorker(threading.Thread):
    """Worker daemon que ejecuta scans de Telegram cuando se lo pide el bridge."""

    def __init__(self) -> None:
        super().__init__(name="bot-scan-worker", daemon=True)
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()
        self.join(timeout=3)

    def run(self) -> None:
        logger.info(f"ScanWorker started (watching {CMD_REQ_PATH})")
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as e:
                logger.exception(f"ScanWorker tick error: {e}")
            self._stop_event.wait(POLL_INTERVAL)

    def _tick(self) -> None:
        if not os.path.exists(CMD_REQ_PATH):
            return
        try:
            with open(CMD_REQ_PATH, "r", encoding="utf-8") as f:
                req = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"cmd_requests.json read failed: {e}")
            return

        action = req.get("action")
        request_id = req.get("request_id", "unknown")

        # consume el request atómicamente: rename a .processing
        processing_path = CMD_REQ_PATH + ".processing"
        try:
            os.replace(CMD_REQ_PATH, processing_path)
        except OSError:
            return

        if action == "scan_channels":
            self._handle_scan(request_id)
        else:
            self._write_response(request_id, {"error": f"unknown action: {action}"})

        try:
            os.remove(processing_path)
        except OSError:
            pass

    def _handle_scan(self, request_id: str) -> None:
        cfg = _load_config()
        api_id = cfg.get("api_id", "")
        api_hash = cfg.get("api_hash", "")

        if not api_id or not api_hash:
            self._write_response(
                request_id,
                {"error": "config.json sin api_id/api_hash"},
            )
            return

        if not self._check_session_exists():
            self._write_response(
                request_id,
                {"error": "Sesión Telethon no encontrada. Reautenticar."},
            )
            return

        logger.info(f"scan_channels request_id={request_id}")
        from telegram_scan import scan_channels

        result = scan_channels(api_id, api_hash)
        self._write_response(request_id, result)
        logger.info(
            f"scan_channels done request_id={request_id} "
            f"(channels={len(result.get('data', []))})"
        )

    @staticmethod
    def _check_session_exists() -> bool:
        return os.path.exists(
            os.path.join(BASE_DIR, "mitradingbot_session.session")
        )

    @staticmethod
    def _write_response(request_id: str, payload: dict) -> None:
        body = {
            "request_id": request_id,
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            **payload,
        }
        tmp = CMD_RESP_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(body, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CMD_RESP_PATH)
