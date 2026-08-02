"""
lst-account-bootstrap — registra la cuenta LST en account-manager.

Idempotente: si la cuenta ya existe para (login, server) bajo el tenant,
recupera su UUID en vez de crear duplicado.

Uso:
    Espera variables:
        ACCOUNT_MANAGER_URL      (default: http://localhost:8510)
        LST_TENANT_ID            (default: 00000000-0000-0000-0000-000000000001)
        LST_LOGIN                (requerido)
        LST_SERVER               (requerido)
        LST_PASSWORD             (requerido)
        LST_BROKER               (default: mt5)
        LST_ALIAS                (default: LST-Trading)
        LST_ACCOUNT_ID_FILE      (default: /var/run/tnsvt/secrets/lst_account_id)

Exit codes:
    0  registrado / UUID escrito
    1  error fatal (no se pudo conectar a account-manager tras reintentos)
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("lst-account-bootstrap")


def _get(url: str, headers: dict, timeout: int = 10) -> tuple[int, dict | str]:
    req = urllib.request.Request(url, method="GET", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, body
    except Exception as e:
        return 0, str(e)


def _post(url: str, payload: dict, headers: dict, timeout: int = 10) -> tuple[int, dict | str]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={**headers, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, body
    except Exception as e:
        return 0, str(e)


def wait_for_account_manager(base_url: str, headers: dict, retries: int = 60, delay: float = 2.0) -> bool:
    for attempt in range(1, retries + 1):
        status, body = _get(f"{base_url}/health", headers, timeout=3)
        if status == 200:
            logger.info("account-manager ready (%d/%d)", attempt, retries)
            return True
        logger.info("waiting account-manager (attempt %d/%d, status=%s)", attempt, retries, status)
        time.sleep(delay)
    return False


def find_existing_account(base_url: str, headers: dict, tenant_id: str, login: int, server: str) -> str | None:
    status, body = _get(f"{base_url}/api/v1/accounts", headers, timeout=10)
    if status != 200 or not isinstance(body, dict):
        return None
    for acc in body.get("accounts", []) or []:
        try:
            if int(acc.get("login", -1)) == login and acc.get("server") == server:
                return acc.get("id")
        except Exception:
            continue
    return None


def main() -> int:
    base_url = os.getenv("ACCOUNT_MANAGER_URL", "http://localhost:8510")
    tenant_id = os.getenv("LST_TENANT_ID", "00000000-0000-0000-0000-000000000001")

    login_str = os.getenv("LST_LOGIN", "")
    server = os.getenv("LST_SERVER", "")
    password = os.getenv("LST_PASSWORD", "")
    broker = os.getenv("LST_BROKER", "mt5")
    alias = os.getenv("LST_ALIAS", "LST-Trading")
    out_file = os.getenv("LST_ACCOUNT_ID_FILE", "/var/run/tnsvt/secrets/lst_account_id")

    if not login_str or not server or not password:
        logger.error("LST_LOGIN, LST_SERVER and LST_PASSWORD are required")
        return 1

    try:
        login = int(login_str)
    except ValueError:
        logger.error("LST_LOGIN must be integer, got %r", login_str)
        return 1

    headers = {"X-Tenant-ID": tenant_id}

    if not wait_for_account_manager(base_url, headers):
        logger.error("account-manager not reachable after retries: %s", base_url)
        return 1

    logger.info("checking if account already exists (login=%s server=%s tenant=%s)", login, server, tenant_id)
    existing = find_existing_account(base_url, headers, tenant_id, login, server)
    if existing:
        logger.info("account already exists: id=%s", existing)
        account_id = existing
    else:
        logger.info("creating new account")
        status, body = _post(
            f"{base_url}/api/v1/accounts",
            {
                "login": login,
                "server": server,
                "password": password,
                "broker": broker,
                "alias": alias,
            },
            headers,
        )
        if status == 201 and isinstance(body, dict) and body.get("id"):
            account_id = body["id"]
            logger.info("account created: id=%s login=%s server=%s", account_id, login, server)
        else:
            logger.error("failed to create account: status=%s body=%s", status, body)
            return 1

    try:
        os.makedirs(os.path.dirname(out_file), exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(account_id)
        logger.info("wrote %s to %s", account_id, out_file)
    except OSError as e:
        logger.error("cannot write %s: %s", out_file, e)
        return 1

    print(account_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
