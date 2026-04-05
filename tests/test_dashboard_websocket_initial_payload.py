import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from src.api import main


class _FakeWebSocket:
    def __init__(self, token: str):
        self.query_params = {"token": token}
        self.client = SimpleNamespace(host="127.0.0.1")
        self.sent_messages = []
        self.closed = None

    async def send_json(self, payload):
        self.sent_messages.append(payload)

    async def receive_text(self):
        raise RuntimeError("client disconnected")

    async def close(self, code: int, reason: str):
        self.closed = {"code": code, "reason": reason}


class TestDashboardWebsocketInitialPayload(unittest.TestCase):
    def test_dashboard_websocket_should_send_collector_snapshot_on_connect(self):
        websocket = _FakeWebSocket(token="test-token")

        with patch.object(main.config, "API_TOKEN", "test-token"), patch(
            "src.api.main.websocket_manager.connect",
            new=AsyncMock(),
        ), patch(
            "src.api.main.websocket_manager.disconnect",
            new=Mock(),
        ) as mock_disconnect, patch(
            "src.api.dashboard_endpoints.get_dashboard_overview",
            new=AsyncMock(return_value={"total": 10}),
        ), patch(
            "src.api.main.get_collector_realtime_payload",
            new=AsyncMock(return_value={"overview": {"cooldownPoolCount": 3}}),
        ):
            asyncio.run(main.dashboard_websocket(websocket))

        self.assertEqual(
            [message["type"] for message in websocket.sent_messages],
            ["initial", "collector_update"],
        )
        self.assertEqual(websocket.sent_messages[1]["data"]["overview"]["cooldownPoolCount"], 3)
        mock_disconnect.assert_called_once_with(websocket)


if __name__ == "__main__":
    unittest.main()
