"""
Registra el primer admin + tenant en auth-service.

Uso:
    python scripts/register_admin.py

Variables de entorno:
    AUTH_SERVICE_URL    (default: http://localhost:8001)
    ADMIN_EMAIL         (default: admin@tnsvt.io)
    ADMIN_USERNAME      (default: admin)
    ADMIN_PASSWORD      (default: Admin123!Pass)
    ADMIN_TENANT_NAME   (default: TNSVT)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def _request(method: str, url: str, body: dict | None = None, timeout: int = 10) -> tuple[int, dict | str]:
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"} if body else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8")
            return resp.status, json.loads(text) if text else {}
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", errors="ignore")
        try:
            return e.code, json.loads(text)
        except Exception:
            return e.code, text
    except Exception as e:
        return 0, str(e)


def wait_for_auth(base_url: str, timeout_s: int = 60) -> bool:
    import time
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        status, _ = _request("GET", f"{base_url}/health", timeout=3)
        if status == 200:
            return True
        time.sleep(1.5)
    return False


def main() -> int:
    base_url = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001")
    email = os.getenv("ADMIN_EMAIL", "admin@tnsvt.io")
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD", "Admin123!Pass")
    tenant_name = os.getenv("ADMIN_TENANT_NAME", "TNSVT")

    print(f"target: {base_url}")
    print(f"email:   {email}")
    print(f"user:    {username}")

    if not wait_for_auth(base_url):
        print(f"ERROR: auth-service no responde en {base_url}")
        return 1

    body = {
        "tenant_name": tenant_name,
        "email": email,
        "username": username,
        "password": password,
    }

    status, resp = _request("POST", f"{base_url}/api/v1/auth/register", body)

    if status == 201:
        print(f"OK: usuario registrado")
        print(f"  user_id:    {resp.get('user', {}).get('id')}")
        print(f"  tenant_id:  {resp.get('tenant', {}).get('id')}")
        print(f"  role:       {resp.get('user', {}).get('role')}")
        token = resp.get("access_token", "")
        if token:
            print(f"  token:      {token[:30]}...")
        return 0

    if status == 400:
        error_body = resp.get("error", "") if isinstance(resp, dict) else str(resp)
        if "already" in str(error_body).lower() or "exists" in str(error_body).lower():
            print(f"INFO: usuario ya registrado. Probando login...")
            status2, resp2 = _request("POST", f"{base_url}/api/v1/auth/login",
                                      {"email": email, "password": password})
            if status2 == 200:
                print(f"OK: login funciona")
                print(f"  token: {resp2.get('access_token', '')[:30]}...")
                return 0
            print(f"login fallo: {status2} {resp2}")
            return 1
        print(f"register fallo: {status} {error_body}")
        return 1

    print(f"register fallo: {status} {resp}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
