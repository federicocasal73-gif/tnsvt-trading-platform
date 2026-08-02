"""
Registra la cuenta LST en account-manager.

Uso:
    python scripts/register_lst_account.py

Variables de entorno:
    ACCOUNT_MANAGER_URL  (default: http://localhost:8510)
    LST_TENANT_ID       (default: 00000000-0000-0000-0000-000000000001)
    LST_LOGIN           (default: 98891135)
    LST_SERVER          (default: TopOneTrader-MT5)
    LST_PASSWORD        (default: )fxG$G(B4D)
    LST_BROKER          (default: TopOneTrader)
    LST_ALIAS           (default: LST-Trading)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request


def main() -> int:
    url = os.getenv("ACCOUNT_MANAGER_URL", "http://localhost:8510")
    tenant_id = os.getenv("LST_TENANT_ID", "00000000-0000-0000-0000-000000000001")

    body = {
        "login": int(os.getenv("LST_LOGIN", "98891135")),
        "server": os.getenv("LST_SERVER", "TopOneTrader-MT5"),
        "password": os.getenv("LST_PASSWORD", ")fxG$G(B4D"),
        "broker": os.getenv("LST_BROKER", "TopOneTrader"),
        "alias": os.getenv("LST_ALIAS", "LST-Trading"),
    }

    req = urllib.request.Request(
        f"{url}/api/v1/accounts",
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Tenant-ID": tenant_id,
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="ignore")
        print(f"ERROR {e.code}: {body_text}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if "id" not in data:
        print(f"Respuesta inesperada: {data}", file=sys.stderr)
        return 1

    print(f"LST account registrada:")
    print(f"  id     = {data['id']}")
    print(f"  login  = {data.get('login')}")
    print(f"  server = {data.get('server')}")
    print(f"  alias  = {data.get('alias')}")
    print()
    print("Para activar LST en execution-engine:")
    print(f"  export LST_ACCOUNT_ID={data['id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
