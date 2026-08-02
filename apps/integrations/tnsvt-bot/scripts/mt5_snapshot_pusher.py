"""
mt5_snapshot_pusher.py — Push live MT5 data to account-manager.

Este script NO abre instancias de MT5. Solo lee el estado de la sesión
MT5 que ya está corriendo (mantenida por signal_copier) y publica los
snapshots al account-manager (PostgreSQL) vía API REST.

Por qué existe: el account-manager es la única fuente de verdad de las
cuentas MT5. El frontend lee siempre desde account-manager, no desde
archivos en D:\\TradingBotMT5. Este pusher mantiene los snapshots
en account-manager frescos sin necesidad de mantener el legacy
mt5_multi_snapshot.py (que abría N terminales y competía con signal_copier).

Frecuencia: cada 5 segundos (configurable vía MT5_SNAPSHOT_INTERVAL).
"""
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# ─── Config ────────────────────────────────────────────────────────
ACCOUNT_MANAGER_URL = os.getenv("ACCOUNT_MANAGER_URL", "http://localhost:8510")
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000")
SERVICE_TOKEN = os.getenv("ACCOUNT_MGR_SERVICE_TOKEN", "")
MT5_DATA_DIR = Path(os.getenv("MT5_DATA_DIR", r"D:\TradingBotMT5"))
MT5_STATUS_PATH = Path(os.getenv("MT5_STATUS_PATH", str(MT5_DATA_DIR / "var" / "mt5_status.json")))
POSITIONS_SNAPSHOT_PATH = MT5_DATA_DIR / "positions_snapshot.json"
POLL_INTERVAL = float(os.getenv("MT5_SNAPSHOT_INTERVAL", "5"))

# ─── Logging ───────────────────────────────────────────────────────
LOG_PATH = MT5_DATA_DIR / "mt5_snapshot_pusher.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(LOG_PATH),
    filemode="a",
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("mt5-snapshot-pusher")
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
log.addHandler(_handler)


# ─── Helpers ───────────────────────────────────────────────────────

def _headers(tenant_id: str | None = None) -> dict:
    h = {
        "Content-Type": "application/json",
        "X-Service-Token": SERVICE_TOKEN,
    }
    if tenant_id:
        h["X-Tenant-ID"] = tenant_id
    return h


def _tenant_id() -> str:
    return os.getenv("DEFAULT_TENANT_ID", "")


def _read_mt5_status() -> dict | None:
    """Lee el estado escrito por signal_copier en mt5_status.json."""
    try:
        if not MT5_STATUS_PATH.exists():
            return None
        return json.loads(MT5_STATUS_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        log.debug(f"read mt5_status.json: {e}")
        return None


def _read_positions() -> list:
    """Lee positions_snapshot.json (escrito por signal_copier)."""
    try:
        if not POSITIONS_SNAPSHOT_PATH.exists():
            return []
        data = json.loads(POSITIONS_SNAPSHOT_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception as e:
        log.debug(f"read positions_snapshot.json: {e}")
        return []


def _list_accounts() -> list[dict]:
    """Lista las cuentas del tenant vía gateway (proxies account-manager)."""
    try:
        r = requests.get(
            f"{GATEWAY_URL}/api/v1/accounts",
            headers=_headers(_tenant_id()),
            timeout=5,
        )
        if r.status_code == 200:
            return r.json().get("accounts", [])
    except Exception as e:
        log.warning(f"list_accounts: {e}")
    return []


def _find_account_by_login(accounts: list[dict], login: int) -> dict | None:
    for a in accounts:
        if a.get("login") == login:
            return a
    return None


def _push_snapshot(account_id: str, snap: dict) -> bool:
    """POST snapshot al account-manager (vía gateway)."""
    try:
        r = requests.post(
            f"{GATEWAY_URL}/api/v1/accounts/{account_id}/snapshot",
            headers=_headers(_tenant_id()),
            json=snap,
            timeout=5,
        )
        return r.status_code == 200
    except Exception as e:
        log.warning(f"push_snapshot({account_id}): {e}")
        return False


def _build_snapshot_from_status(status: dict, open_positions: int) -> dict:
    """Convierte mt5_status.json + positions a la shape del account-manager."""
    return {
        "balance": float(status.get("balance", 0) or 0),
        "equity": float(status.get("equity", 0) or 0),
        "margin": float(status.get("margin", 0) or 0),
        "free_margin": float(status.get("free_margin", 0) or 0),
        "profit": float(status.get("profit", 0) or 0),
        "open_positions": int(open_positions),
        "connected": bool(status.get("connected", False)),
    }


def main():
    log.info("=" * 50)
    log.info("mt5_snapshot_pusher iniciado (no abre MT5)")
    log.info(f"  account_manager: {ACCOUNT_MANAGER_URL}")
    log.info(f"  status source:  {MT5_STATUS_PATH}")
    log.info(f"  positions src:  {POSITIONS_SNAPSHOT_PATH}")
    log.info(f"  poll interval:  {POLL_INTERVAL}s")
    log.info("=" * 50)

    if not SERVICE_TOKEN:
        log.error("ACCOUNT_MGR_SERVICE_TOKEN not set in .env; cannot authenticate")
        sys.exit(1)

    last_pushed: dict[int, float] = {}  # login → epoch
    min_interval = max(POLL_INTERVAL, 2)

    while True:
        try:
            status = _read_mt5_status()
            if not status:
                log.debug("no mt5_status.json yet")
                time.sleep(min_interval)
                continue

            login = status.get("login")
            if not login:
                log.debug("status without login")
                time.sleep(min_interval)
                continue

            connected = bool(status.get("connected", False))
            if not connected:
                log.debug("MT5 disconnected, waiting")
                time.sleep(min_interval)
                continue

            # Rate-limit per account
            now = time.time()
            if now - last_pushed.get(login, 0) < min_interval:
                time.sleep(1)
                continue

            positions = _read_positions()
            snap = _build_snapshot_from_status(status, len(positions))

            # Look up account_id from account-manager
            accounts = _list_accounts()
            acc = _find_account_by_login(accounts, int(login))
            if not acc:
                log.debug(f"login {login} not in account-manager; skipping push")
                time.sleep(min_interval)
                continue

            ok = _push_snapshot(acc["id"], snap)
            if ok:
                last_pushed[login] = now
                log.info(
                    f"pushed snap login={login} bal=${snap['balance']:.2f} "
                    f"equity=${snap['equity']:.2f} open={snap['open_positions']}"
                )
            else:
                log.warning(f"push snap failed for login={login}")
        except Exception as e:
            log.exception(f"loop error: {e}")
        time.sleep(min_interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("interrupted")
    except Exception as e:
        log.exception(f"fatal: {e}")
        sys.exit(1)
