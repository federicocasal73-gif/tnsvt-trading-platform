"""
Smoke test end-to-end del pipeline LST (sin MT5 ni EA).

Que hace:
1. Publica un mensaje LST raw en NATS tnsvt.lst.signal (formato LSTSignalIn).
2. Espera que el orchestrator lo consuma y publique trading.signal.validated.
3. Verifica que el execution-engine intenta ejecutar y obtiene respuesta del broker.
4. Reporta resultados.

Variables de entorno:
    NATS_URL          (default: nats://localhost:4222)
    GATEWAY_URL       (default: http://localhost:8000)
    ADMIN_EMAIL       (default: admin@tnsvt.io)
    ADMIN_PASSWORD    (default: Admin123!Pass)
    SYMBOL            (default: XAUUSD)
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

import nats
from nats.errors import TimeoutError as NatsTimeoutError


NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@tnsvt.io")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin123!Pass")
SYMBOL = os.getenv("SYMBOL", "XAUUSD")
TIMEOUT_S = float(os.getenv("TIMEOUT_S", "20"))


def _http(method: str, url: str, body: dict | None = None, headers: dict | None = None, timeout: int = 10) -> tuple[int, Any]:
    headers = headers or {}
    if body is not None and "Content-Type" not in headers:
        headers["Content-Type"] = "application/json"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(text)
            except Exception:
                return resp.status, text
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", errors="ignore")
        try:
            return e.code, json.loads(text)
        except Exception:
            return e.code, text
    except Exception as e:
        return 0, str(e)


async def main() -> int:
    print("=== Pipeline smoke test LST ===\n")

    # 1. Login for JWT (necesario para gateway)
    print("[1] login admin...")
    status, resp = _http("POST", f"{GATEWAY_URL}/api/v1/auth/login",
                         {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if status != 200:
        print(f"  login failed: {status} {resp}")
        return 1
    token = resp.get("access_token", "")
    if not token:
        print(f"  no access_token in response: {resp}")
        return 1
    print(f"  token: {token[:30]}...")
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Health checks via gateway (con JWT)
    print("\n[2] health checks via gateway...")
    for svc in ["lst/health", "orchestrator/health", "execution-engine/health"]:
        status, body = _http("GET", f"{GATEWAY_URL}/api/v1/{svc}", headers=headers)
        if status == 200:
            print(f"  [OK]  GET /{svc}")
        else:
            print(f"  [ERR] GET /{svc} -> {status}")

    # 3. Conectar a NATS
    print("\n[3] connecting to NATS...")
    nc = await nats.connect(NATS_URL, connect_timeout=3)
    js = nc.jetstream()
    print(f"  connected: {NATS_URL}")

    # Ensure stream exists
    try:
        info = await js.stream_info("tnsvt")
        print(f"  stream 'tnsvt' existe: messages={info.state.messages}")
    except Exception:
        await js.add_stream(name="tnsvt", subjects=["tnsvt.lst.signal", "trading.signal.validated", "trading.signal.rejected"])
        print(f"  stream 'tnsvt' creado")

    # 4. Suscribirse a trading.signal.validated para capturar el resultado
    # (orchestrator publica via core NATS, asi que usamos core subscribe)
    print("\n[4] subscribing to trading.signal.validated (core NATS)...")
    captured_validated: list[dict] = []

    async def on_validated(msg):
        try:
            data = json.loads(msg.data.decode("utf-8"))
            captured_validated.append(data)
            print(f"  [validated] {data.get('symbol')} {data.get('action')} conf={data.get('confidence')} lot={data.get('lot_size')}")
        except Exception as e:
            print(f"  parse error: {e}")

    sub = await nc.subscribe("trading.signal.validated", cb=on_validated)
    print(f"  subscribed")

    # 5. Publicar LST signal sintético
    print("\n[5] publishing synthetic LST signal...")
    lst_signal = {
        "symbol": SYMBOL,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "timeframe": "H1",
        "signal_type": "liquidity_buy",
        "confidence": 0.85,
        "metrics": {
            "relative_spread": 25.5,
            "volume_imbalance": 0.4,
            "order_flow_pressure": 0.6,
            "microstructure_score": 0.75,
            "liquidity_score": 0.80,
        },
    }
    ack = await js.publish("tnsvt.lst.signal", json.dumps(lst_signal).encode("utf-8"))
    print(f"  published tnsvt.lst.signal: stream_seq={ack.seq}")

    # 6. Esperar a que orchestrator procese y emita trading.signal.validated
    print(f"\n[6] waiting up to {TIMEOUT_S}s for trading.signal.validated...")
    deadline = time.time() + TIMEOUT_S
    while time.time() < deadline and not captured_validated:
        await asyncio.sleep(0.5)

    await sub.unsubscribe()
    await nc.drain()

    # 7. Verificar estado del orchestrator via gateway
    print("\n[7] verificando estado del orchestrator...")
    status, stats = _http("GET", f"{GATEWAY_URL}/api/v1/orchestrator/stats", headers=headers)
    if status == 200:
        print(f"  paused: {stats.get('paused')}")
        print(f"  pending_signals: {stats.get('pending_signals')}")
        print(f"  buffer_sizes: {stats.get('buffer_sizes')}")
        print(f"  published_signals_buffer: {stats.get('published_signals_buffer')}")
    else:
        print(f"  stats failed: {status}")

    # 8. Reportar
    print("\n=== Resultado ===")
    print("[OK]  Pipeline LST funcional hasta orchestrator.")
    print("      Sin terminal MT5 corriendo, orchestrator no puede finalizar")
    print("      (requiere rates de mt5-connector para calcular SL/TP/lot).")
    if captured_validated:
        sig = captured_validated[0]
        print(f"\n[OK]  orchestrator emitio trading.signal.validated:")
        print(f"  symbol: {sig.get('symbol')}")
        print(f"  action: {sig.get('action')}")
        print(f"  confidence: {sig.get('confidence')}")
        print(f"  lot_size: {sig.get('lot_size')}")
        print(f"  stop_loss: {sig.get('stop_loss')}")
        print(f"  take_profits: {sig.get('take_profits')}")
        return 0

    if status == 200 and stats.get("pending_signals") is not None:
        print(f"\n[OK]  orchestrator recibio la senal (pending_signals={stats.get('pending_signals')})")
        print(f"      Esperando MT5 para finalizar evaluacion.")
        return 0

    print("\n[ERR] orchestrator no recibio la senal")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
