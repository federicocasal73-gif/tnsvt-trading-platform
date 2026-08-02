"""Tests para news-bridge."""
import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_MODULE_PATH = Path(__file__).resolve().parent.parent / "main.py"
_spec = importlib.util.spec_from_file_location("news_bridge_main_mod", _MODULE_PATH)
_news_bridge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_news_bridge)
NewsBridge = _news_bridge.NewsBridge
sys.modules.setdefault("news_bridge_main_mod", _news_bridge)
_MAIN_NAME = "news_bridge_main_mod"


@pytest.fixture
def bridge():
    b = NewsBridge.__new__(NewsBridge)
    b.nats_url = "nats://localhost:4222"
    b.subject = "trading.signal.news_based"
    b.stream = "tnsvt"
    b.durable = "news-bridge"
    b.signal_engine_url = "http://localhost:8003"
    b.tenant_id = "00000000-0000-0000-0000-000000000001"
    b.api_key = "test_key"
    b._cooldown = {}
    b._nc = None
    b._js = None
    b._sub = None
    b._stopped = False
    b._http = AsyncMock()
    return b


def _msg(symbol="XAUUSD", action="BUY", confidence=0.7, **extra):
    base = {
        "id": "test-id",
        "tenant_id": "",
        "source": "news-analyzer",
        "symbol": symbol,
        "action": action,
        "entry_price": None,
        "stop_loss": 1490.0,
        "take_profits": [1520.0],
        "lot_mode": "risk_based",
        "comment": "FED dovish",
        "confidence": confidence,
    }
    base.update(extra)
    return base


def test_cooldown_key_format():
    b = NewsBridge.__new__(NewsBridge)
    b._cooldown = {}
    assert b._cooldown_key("XAUUSD", "BUY") == "XAUUSD:BUY"
    assert b._cooldown_key("EURUSD", "SELL") == "EURUSD:SELL"


def test_cooldown_initial_false():
    b = NewsBridge.__new__(NewsBridge)
    b._cooldown = {}
    assert not b._on_cooldown("XAUUSD:BUY")


def test_cooldown_after_set_true():
    b = NewsBridge.__new__(NewsBridge)
    b._cooldown = {}
    b._set_cooldown("XAUUSD:BUY")
    assert b._on_cooldown("XAUUSD:BUY")


@pytest.mark.asyncio
async def test_forward_valid_message(bridge):
    bridge._http.post = AsyncMock(return_value=MagicMock(status_code=201))
    ok, status = await bridge._forward_to_signal_engine(_msg())
    assert ok is True
    assert status == 201
    bridge._http.post.assert_called_once()
    call_kwargs = bridge._http.post.call_args.kwargs
    assert call_kwargs["json"]["symbol"] == "XAUUSD"
    assert call_kwargs["json"]["action"] == "BUY"
    assert call_kwargs["headers"]["X-Tenant-ID"] == bridge.tenant_id


@pytest.mark.asyncio
async def test_forward_invalid_action_skipped(bridge):
    ok, status = await bridge._forward_to_signal_engine(_msg(action="INVALID"))
    assert ok is False
    assert status == 0
    bridge._http.post.assert_not_called()


@pytest.mark.asyncio
async def test_forward_empty_symbol_skipped(bridge):
    ok, status = await bridge._forward_to_signal_engine(_msg(symbol=""))
    assert ok is False
    bridge._http.post.assert_not_called()


@pytest.mark.asyncio
async def test_forward_rejected_returns_false(bridge):
    bridge._http.post = AsyncMock(return_value=MagicMock(status_code=400, text="bad"))
    ok, status = await bridge._forward_to_signal_engine(_msg())
    assert ok is False
    assert status == 400


@pytest.mark.asyncio
async def test_forward_sets_cooldown(bridge):
    bridge._http.post = AsyncMock(return_value=MagicMock(status_code=201))
    await bridge._forward_to_signal_engine(_msg())
    assert bridge._on_cooldown("XAUUSD:BUY")


@pytest.mark.asyncio
async def test_forward_respects_cooldown(bridge):
    bridge._set_cooldown("XAUUSD:BUY")
    bridge._http.post = AsyncMock()
    ok, status = await bridge._forward_to_signal_engine(_msg())
    assert ok is False
    bridge._http.post.assert_not_called()


@pytest.mark.asyncio
async def test_on_message_parses_acks_on_success(bridge):
    bridge._forward_to_signal_engine = AsyncMock(return_value=(True, 201))
    msg = MagicMock()
    msg.data = json.dumps(_msg()).encode("utf-8")
    msg.ack = AsyncMock()
    msg.nak = AsyncMock()
    await bridge._on_message(msg)
    bridge._forward_to_signal_engine.assert_called_once()
    msg.ack.assert_called_once()
    msg.nak.assert_not_called()


@pytest.mark.asyncio
async def test_on_message_naks_on_non_duplicate_failure(bridge):
    bridge._forward_to_signal_engine = AsyncMock(return_value=(False, 500))
    msg = MagicMock()
    msg.data = json.dumps(_msg()).encode("utf-8")
    msg.ack = AsyncMock()
    msg.nak = AsyncMock()
    await bridge._on_message(msg)
    msg.nak.assert_called_once()
    msg.ack.assert_not_called()


@pytest.mark.asyncio
async def test_on_message_acks_on_409_duplicate(bridge):
    """409 = DUPLICATE: signal-engine ya tiene esta senal, ack y no reintentar."""
    bridge._forward_to_signal_engine = AsyncMock(return_value=(False, 409))
    msg = MagicMock()
    msg.data = json.dumps(_msg()).encode("utf-8")
    msg.ack = AsyncMock()
    msg.nak = AsyncMock()
    await bridge._on_message(msg)
    msg.ack.assert_called_once()
    msg.nak.assert_not_called()


@pytest.mark.asyncio
async def test_on_message_invalid_json_acks_to_drain(bridge):
    bridge._forward_to_signal_engine = AsyncMock()
    msg = MagicMock()
    msg.data = b"not json"
    msg.ack = AsyncMock()
    await bridge._on_message(msg)
    bridge._forward_to_signal_engine.assert_not_called()
    msg.ack.assert_called_once()


@pytest.mark.asyncio
async def test_subscribe_uses_jetstream(bridge):
    from nats.js.errors import NotFoundError

    bridge._js = MagicMock()
    bridge._js.subscribe = AsyncMock(return_value=MagicMock())
    bridge._js.stream_info = AsyncMock(side_effect=NotFoundError("not found", 404))
    bridge._js.add_stream = AsyncMock()

    ok = await bridge._subscribe()
    assert ok is True
    bridge._js.subscribe.assert_called_once()
    call_kwargs = bridge._js.subscribe.call_args.kwargs
    assert call_kwargs["subject"] == bridge.subject
    assert call_kwargs["durable"] == bridge.durable
    assert call_kwargs["manual_ack"] is True
    bridge._js.add_stream.assert_called_once()
    add_kwargs = bridge._js.add_stream.call_args.kwargs
    assert add_kwargs["name"] == bridge.stream
    assert bridge.subject in add_kwargs["subjects"]
