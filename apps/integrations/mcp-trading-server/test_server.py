import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_httpx():
    with patch("server.httpx.AsyncClient") as mock:
        client = AsyncMock()
        mock.return_value.__aenter__.return_value = client
        yield client


@pytest.fixture
def mock_nats():
    with patch("server.nats.connect") as mock_connect:
        nc = AsyncMock()
        nc.is_connected = True
        js = MagicMock()
        js.publish = AsyncMock()
        nc.jetstream = MagicMock(return_value=js)
        mock_connect.return_value = nc
        yield nc, js


class TestHelpers:
    @pytest.mark.asyncio
    async def test_api_get_success(self, mock_httpx):
        mock_httpx.get.return_value = MagicMock(status_code=200, json=lambda: {"key": "value"})
        import server
        result = await server._api_get("http://localhost:8060", "/api/v1/orchestrator/health")
        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_api_get_failure(self, mock_httpx):
        mock_httpx.get.side_effect = Exception("timeout")
        import server
        with pytest.raises(Exception, match="timeout"):
            await server._api_get("http://localhost:8060", "/health")


class TestGetSignal:
    @pytest.mark.asyncio
    async def test_get_signal_found(self, mock_httpx):
        mock_httpx.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"items": [{"symbol": "XAUUSD", "action": "BUY"}]},
        )
        import server
        result = await server.get_signal("XAUUSD")
        assert "XAUUSD" in result

    @pytest.mark.asyncio
    async def test_get_signal_no_results(self, mock_httpx):
        mock_httpx.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"items": []},
        )
        import server
        result = await server.get_signal("BTCUSD")
        assert "No signals found" in result

    @pytest.mark.asyncio
    async def test_get_signal_error(self, mock_httpx):
        mock_httpx.get.side_effect = Exception("connection refused")
        import server
        result = await server.get_signal("XAUUSD")
        assert "Error" in result


class TestPauseResume:
    @pytest.mark.asyncio
    async def test_pause_bot(self, mock_nats):
        nc, _ = mock_nats
        import server
        server._nc = None
        result = await server.pause_bot()
        assert "paused" in result.lower()
        nc.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_resume_bot(self, mock_nats):
        nc, _ = mock_nats
        import server
        server._nc = None
        result = await server.resume_bot()
        assert "resumed" in result.lower()
        nc.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_pause_bot_error(self, mock_nats):
        nc, _ = mock_nats
        nc.publish.side_effect = Exception("NATS down")
        import server
        server._nc = nc
        result = await server.pause_bot()
        assert "Error" in result


class TestSendManualSignal:
    @pytest.mark.asyncio
    async def test_send_manual_signal(self, mock_nats):
        nc, js = mock_nats
        ack = MagicMock(spec=["seq"])
        ack.seq = 42
        js.publish.return_value = ack
        import server
        server._nc = nc
        result = await server.send_manual_signal("XAUUSD", "BUY", 0.85, 0.1)
        assert "seq=42" in result
        js.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_manual_signal_no_lot(self, mock_nats):
        nc, js = mock_nats
        ack = MagicMock(spec=["seq"])
        ack.seq = 1
        js.publish.return_value = ack
        import server
        server._nc = nc
        result = await server.send_manual_signal("EURUSD", "SELL", 0.70)
        assert "seq=1" in result
        js.publish.assert_called_once()


class TestGetPositions:
    @pytest.mark.asyncio
    async def test_get_positions_success(self, mock_httpx):
        mock_httpx.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"count": 2, "positions": [{"ticket": "1"}, {"ticket": "2"}]},
        )
        import server
        result = await server.get_positions()
        data = json.loads(result)
        assert data["count"] == 2

    @pytest.mark.asyncio
    async def test_get_positions_error(self, mock_httpx):
        mock_httpx.get.side_effect = Exception("down")
        import server
        result = await server.get_positions()
        assert "Error" in result


class TestRunBacktest:
    @pytest.mark.asyncio
    async def test_backtest_stub(self):
        import server
        result = await server.run_backtest("lst", 30)
        data = json.loads(result)
        assert data["status"] == "not_implemented"


class TestGetBotStatus:
    @pytest.mark.asyncio
    async def test_bot_status_all_ok(self, mock_httpx):
        mock_httpx.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"status": "ok", "portfolio": {"balance": 10000}, "count": 1, "positions": [{"ticket": "1"}]},
        )
        import server
        result = await server.get_bot_status()
        data = json.loads(result)
        assert "portfolio" in data

    @pytest.mark.asyncio
    async def test_bot_status_partial_failure(self, mock_httpx):
        def side_effect(url: str, **kwargs):
            if "health" in url:
                return MagicMock(status_code=200, json=lambda: {"status": "ok"})
            raise Exception("down")
        mock_httpx.get.side_effect = side_effect
        import server
        result = await server.get_bot_status()
        data = json.loads(result)
        assert "orchestrator" in data
