"""
Smoke test E2E: copy-enabled separation (Dashboard vs Copy Trading).

Nota: el gateway filtra por JWT tenant. Para este test usamos llamadas
directas a account-manager (puerto 8510) y a bridge-api (puerto 8522)
con el tenant donde estan registradas las cuentas por lst-account-bootstrap.
"""
import json
import sys
import urllib.error
import urllib.request


BASE_ACCT = "http://127.0.0.1:8510"
BASE_BRIDGE = "http://127.0.0.1:8522"
# Tenant donde estan las cuentas (registrado por lst-account-bootstrap)
TENANT = "d028c9ec-6257-4d38-8a55-7ba6dd4f2b9b"


def http(method, url, body=None, headers=None, timeout=10):
    h = dict(headers or {})
    if body is not None and "Content-Type" not in h:
        h["Content-Type"] = "application/json"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode()
            return resp.status, json.loads(text) if text else {}
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", errors="ignore")
        try:
            return e.code, json.loads(text)
        except Exception:
            return e.code, text
    except Exception as e:
        return 0, str(e)


def http(method, url, body=None, headers=None, timeout=10):
    h = dict(headers or {})
    if body is not None and "Content-Type" not in h:
        h["Content-Type"] = "application/json"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode()
            return resp.status, json.loads(text) if text else {}
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", errors="ignore")
        try:
            return e.code, json.loads(text)
        except Exception:
            return e.code, text
    except Exception as e:
        return 0, str(e)


def login():
    status, resp = http("POST", f"{BASE_GATEWAY}/api/v1/auth/login",
                         body={"email": "admin@tnsvt.io", "password": "Admin123!Pass"})
    if status != 200:
        # Plan B: usar /api/v1/auth/register que crea admin
        status, resp = http("POST", f"{BASE_GATEWAY}/api/v1/auth/register",
                             body={"tenant_name": "TNSVT_LST",
                                   "email": f"smoke-{TENANT[:8]}@tnsvt.io",
                                   "username": f"smoke{TENANT[:6]}",
                                   "password": "Smoke!Pass1"})
        if status != 201:
            print(f"login/register failed: {status} {resp}")
            sys.exit(1)
    return resp["access_token"], resp.get("user", {}).get("tenant_id", TENANT)


def get_token_tenant(headers):
    """Lee tenant_id del JWT (ya validado por el gateway)."""
    return headers.get("X-Tenant-ID", TENANT)


def main():
    print("=== Smoke test E2E: copy-separation (llamadas directas) ===\n")
    h = {"X-Tenant-ID": TENANT}

    print("[1] GET /api/v1/accounts (Dashboard: todas)")
    status, data = http("GET", f"{BASE_ACCT}/api/v1/accounts", headers=h)
    accounts = data.get("accounts", []) if isinstance(data, dict) else []
    print(f"  HTTP {status}, total: {len(accounts)}")
    for a in accounts:
        print(f"  - {a.get('alias') or a.get('login')} login={a.get('login')} copy_enabled={a.get('copy_enabled')}")

    if not accounts:
        print("  sin cuentas, fin del test")
        return

    print(f"\n[2] GET /bridge/mt5/accounts?tenant_id={TENANT} (bridge-api)")
    status, data = http("GET", f"{BASE_BRIDGE}/api/v1/bridge/mt5/accounts?tenant_id={TENANT}")
    bridge_accts = data.get("accounts", []) if isinstance(data, dict) else []
    print(f"  HTTP {status}, total: {len(bridge_accts)}")
    if bridge_accts:
        print(f"  bridge expone copy_enabled: {[a.get('copy_enabled') for a in bridge_accts]}")

    print(f"\n[3] GET /api/v1/accounts/replicators (deberia estar vacio)")
    status, data = http("GET", f"{BASE_ACCT}/api/v1/accounts/replicators", headers=h)
    replicators = data.get("accounts", []) if isinstance(data, dict) else []
    print(f"  HTTP {status}, replicators: {len(replicators)}")

    target = accounts[0]
    target_id = target["id"]
    print(f"\n[4] PATCH copy_enabled=true en {target.get('alias') or target_id}")
    status, _ = http("PUT", f"{BASE_ACCT}/api/v1/accounts/{target_id}",
                     body={"copy_enabled": True}, headers=h)
    print(f"  HTTP {status}")

    print(f"\n[5] GET /api/v1/accounts/replicators (ahora 1)")
    status, data = http("GET", f"{BASE_ACCT}/api/v1/accounts/replicators", headers=h)
    replicators = data.get("accounts", []) if isinstance(data, dict) else []
    print(f"  HTTP {status}, replicators: {len(replicators)}")
    for r in replicators:
        print(f"  - {r.get('alias') or r.get('login')} login={r.get('login')} copy_enabled={r.get('copy_enabled')}")

    print(f"\n[6] GET /bridge/replicators?tenant_id={TENANT} (live data)")
    status, data = http("GET", f"{BASE_BRIDGE}/api/v1/bridge/replicators?tenant_id={TENANT}")
    bridge_repl = data.get("accounts", []) if isinstance(data, dict) else []
    print(f"  HTTP {status}, replicators: {len(bridge_repl)}")

    print(f"\n[7] PATCH copy_enabled=false (rollback)")
    status, _ = http("PUT", f"{BASE_ACCT}/api/v1/accounts/{target_id}",
                     body={"copy_enabled": False}, headers=h)
    print(f"  HTTP {status}")

    print(f"\n[8] GET /api/v1/accounts/replicators (deberia volver a 0)")
    status, data = http("GET", f"{BASE_ACCT}/api/v1/accounts/replicators", headers=h)
    replicators = data.get("accounts", []) if isinstance(data, dict) else []
    print(f"  HTTP {status}, replicators: {len(replicators)}")

    print("\n[OK] smoke test E2E completo")


if __name__ == "__main__":
    main()
