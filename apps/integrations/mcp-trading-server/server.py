#!/usr/bin/env python3
"""
MCP Trading Server — permite a agentes de IA (Claude, etc.) controlar TNSVT V2.

Tools:
  get_signal(symbol)       → última señal del orchestrator
  get_bot_status()         → state + posiciones + balance
  pause_bot()              → pausa el orchestrator vía NATS
  resume_bot()             → reanuda el orchestrator vía NATS
  send_manual_signal(...)  → publica señal manual en NATS
  get_positions()          → posiciones abiertas desde MT5
  run_backtest(...)        → stub (no implementado)

Transport: SSE (HTTP) en :8100
"""
from __future__ import annotations

import json
import logging
import os
import uuid

import httpx
import nats

from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("mcp-trading")

NATS_URL = os.getenv("MCP_NATS_URL", "nats://localhost:4222")
NATS_STREAM = os.getenv("MCP_NATS_STREAM", "tnsvt")
LST_SIGNAL_SUBJECT = os.getenv("MCP_LST_SIGNAL_SUBJECT", "tnsvt.lst.signal")
CONTROL_SUBJECT = os.getenv("MCP_CONTROL_SUBJECT", "trading.control")

ORCHESTRATOR_URL = os.getenv("MCP_ORCHESTRATOR_URL", "http://localhost:8060")
GATEWAY_URL = os.getenv("MCP_GATEWAY_URL", "http://localhost:8000")
MT5_CONNECTOR_URL = os.getenv("MCP_MT5_CONNECTOR_URL", "http://localhost:8007")

HTTP_TIMEOUT = 10
_nc: nats.NATS | None = None


async def get_nats() -> nats.NATS:
    global _nc
    if _nc is None or not _nc.is_connected:
        _nc = await nats.connect(NATS_URL, max_reconnect_attempts=3)
    return _nc


mcp = FastMCP(
    "tnsvt-trading",
    instructions="TNSVT V2 Trading Bot — controla posiciones, señales y estado del bot multi-activo.",
    host="0.0.0.0",
    port=8100,
)


# ─── Helpers ────────────────────────────────────────────────────


async def _api_get(base: str, path: str) -> dict:
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as c:
        r = await c.get(f"{base}{path}")
        r.raise_for_status()
        return r.json()


# ─── Tools ──────────────────────────────────────────────────────


@mcp.tool(
    name="get_signal",
    description="Obtiene la última señal generada por el orchestrator para un símbolo (o la más reciente si no se especifica).",
)
async def get_signal(symbol: str = "") -> str:
    path = f"/api/v1/orchestrator/signals?limit=1"
    if symbol:
        path += f"&symbol={symbol}"
    try:
        data = await _api_get(ORCHESTRATOR_URL, path)
        items = data.get("items", [])
        if not items:
            return "No signals found."
        return json.dumps(items[0], indent=2, default=str)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool(
    name="get_bot_status",
    description="Estado completo del bot: si está running/paused, posiciones abiertas, balance, equity, drawdown.",
)
async def get_bot_status() -> str:
    result = {}
    try:
        result["orchestrator"] = await _api_get(ORCHESTRATOR_URL, "/api/v1/orchestrator/health")
    except Exception as e:
        result["orchestrator_error"] = str(e)
    try:
        orchestator_stats = await _api_get(ORCHESTRATOR_URL, "/api/v1/orchestrator/stats")
        result["portfolio"] = orchestator_stats.get("portfolio")
        result["pending_signals"] = orchestator_stats.get("pending_signals", 0)
    except Exception as e:
        result["stats_error"] = str(e)
    try:
        account = await _api_get(MT5_CONNECTOR_URL, "/api/v1/brokers/accounts/default")
        result["account"] = account
    except Exception as e:
        result["account_error"] = str(e)
    try:
        positions = await _api_get(MT5_CONNECTOR_URL, "/api/v1/brokers/accounts/default/positions")
        result["positions"] = positions.get("positions", [])
        result["positions_count"] = positions.get("count", 0)
    except Exception as e:
        result["positions_error"] = str(e)
    return json.dumps(result, indent=2, default=str)


@mcp.tool(
    name="pause_bot",
    description="Pausa el orchestrator. No se procesarán nuevas señales hasta que se reanude.",
)
async def pause_bot() -> str:
    try:
        nc = await get_nats()
        msg = json.dumps({"action": "pause", "source": "mcp", "id": str(uuid.uuid4())[:8]})
        await nc.publish(f"{CONTROL_SUBJECT}.pause", msg.encode())
        logger.info("Published pause control (core NATS)")
        return "Bot paused. New signals will not be processed."
    except Exception as e:
        return f"Error pausing bot: {e}"


@mcp.tool(
    name="resume_bot",
    description="Reanuda el orchestrator después de una pausa.",
)
async def resume_bot() -> str:
    try:
        nc = await get_nats()
        msg = json.dumps({"action": "resume", "source": "mcp", "id": str(uuid.uuid4())[:8]})
        await nc.publish(f"{CONTROL_SUBJECT}.resume", msg.encode())
        logger.info("Published resume control (core NATS)")
        return "Bot resumed. Signal processing is active."
    except Exception as e:
        return f"Error resuming bot: {e}"


@mcp.tool(
    name="send_manual_signal",
    description="Publica una señal manual en NATS para que el orchestrator la procese. Ejemplo: send_manual_signal('XAUUSD', 'BUY', 0.78, 0.1)",
)
async def send_manual_signal(symbol: str, action: str, confidence: float, lot_size: float | None = None) -> str:
    try:
        nc = await get_nats()
        js = nc.jetstream()
        signal = {
            "symbol": symbol,
            "action": action.upper(),
            "confidence": confidence,
            "signal_type": "manual",
            "source": "mcp",
            "timestamp": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(),
            "metrics": {"manual": True},
        }
        if lot_size:
            signal["lot_size"] = lot_size
        ack = await js.publish(LST_SIGNAL_SUBJECT, json.dumps(signal).encode())
        logger.info("Published manual signal for %s %s, seq=%d", symbol, action, ack.seq)
        return f"Manual signal published: {symbol} {action} conf={confidence} seq={ack.seq}"
    except Exception as e:
        return f"Error publishing signal: {e}"


@mcp.tool(
    name="get_positions",
    description="Retorna todas las posiciones abiertas actualmente en MT5.",
)
async def get_positions() -> str:
    try:
        data = await _api_get(MT5_CONNECTOR_URL, "/api/v1/brokers/accounts/default/positions")
        count = data.get("count", 0)
        positions = data.get("positions", []) or []
        result = {"count": count, "positions": positions}
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool(
    name="run_backtest",
    description="Ejecuta un backtest simulado (stub). strategy_options: 'lst', 'lst+correlation'. days: número de días.",
)
async def run_backtest(strategy: str = "lst", days: int = 30) -> str:
    return json.dumps(
        {
            "status": "not_implemented",
            "message": "Backtesting engine not yet implemented. Coming in Semana 1.",
            "strategy": strategy,
            "days": days,
        },
        indent=2,
    )


# ─── Main ───────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("Starting MCP Trading Server on :8100 (SSE transport)")
    mcp.run(transport="sse")
