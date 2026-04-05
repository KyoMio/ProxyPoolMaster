import unittest
from unittest.mock import Mock, patch

from src.collectors_v2.execution.runner import run_execution
from src.database.redis_client import RedisManager


class TestCollectorsV2ExecutionRunner(unittest.TestCase):
    def test_runner_should_validate_simple_spec_proxies(self):
        payload = {
            "run_id": "run-1",
            "trigger": "test",
            "collector": {
                "id": "demo",
                "mode": "simple",
                "spec": {
                    "proxies": [
                        {"ip": "1.1.1.1", "port": 80, "protocol": "http"},
                        {"ip": "2.2.2.2", "port": "bad", "protocol": "http"},
                    ]
                },
            },
        }

        mock_redis_manager = Mock(spec=RedisManager)
        mock_redis_manager.store_proxy.return_value = {
            "stored": True,
            "created": True,
            "proxy_key": "proxy:http:1.1.1.1:80",
        }

        with patch(
            "src.collectors_v2.execution.runner._get_redis_manager",
            return_value=mock_redis_manager,
            create=True,
        ), patch("src.collectors_v2.execution.runner.time.time", return_value=1700000000):
            result = run_execution(payload)

        self.assertTrue(result["success"])
        self.assertEqual(result["raw_count"], 2)
        self.assertEqual(result["valid_count"], 1)
        self.assertEqual(result["stored_count"], 1)
        self.assertGreaterEqual(len(result["errors"]), 1)
        mock_redis_manager.store_proxy.assert_called_once()
        mock_redis_manager.get_redis_client.assert_not_called()
        mock_redis_manager._get_proxy_key.assert_not_called()

    def test_runner_should_store_valid_proxies_into_redis(self):
        payload = {
            "run_id": "run-store-1",
            "trigger": "test",
            "collector": {
                "id": "demo-store",
                "mode": "simple",
                "spec": {
                    "proxies": [
                        {"ip": "3.3.3.3", "port": 8080, "protocol": "http"},
                        {"ip": "4.4.4.4", "port": 8081, "protocol": "https"},
                    ]
                },
            },
        }

        mock_redis_manager = Mock(spec=RedisManager)
        mock_redis_manager.store_proxy.side_effect = [
            {
                "stored": True,
                "created": True,
                "proxy_key": "proxy:http:3.3.3.3:8080",
            },
            {
                "stored": True,
                "created": False,
                "proxy_key": "proxy:https:4.4.4.4:8081",
            },
        ]

        with patch(
            "src.collectors_v2.execution.runner._get_redis_manager",
            return_value=mock_redis_manager,
            create=True,
        ), patch("src.collectors_v2.execution.runner.time.time", return_value=1700000000):
            result = run_execution(payload)

        self.assertTrue(result["success"])
        self.assertEqual(result["valid_count"], 2)
        self.assertEqual(result["stored_count"], 1)
        self.assertEqual(result["duplicate_count"], 1)
        self.assertEqual(mock_redis_manager.store_proxy.call_count, 2)
        mock_redis_manager.get_redis_client.assert_not_called()
        mock_redis_manager._get_proxy_key.assert_not_called()

    def test_runner_should_use_structured_store_result_without_key_lookup(self):
        payload = {
            "run_id": "run-schedule-1",
            "trigger": "test",
            "collector": {
                "id": "demo-schedule",
                "mode": "simple",
                "spec": {
                    "proxies": [
                        {"ip": "5.5.5.5", "port": 8080, "protocol": "http"},
                    ]
                },
            },
        }

        mock_redis_manager = Mock(spec=RedisManager)
        mock_redis_manager.store_proxy.return_value = {
            "stored": True,
            "created": True,
            "proxy_key": "proxy:http:5.5.5.5:8080",
        }

        with patch(
            "src.collectors_v2.execution.runner._get_redis_manager",
            return_value=mock_redis_manager,
            create=True,
        ), patch("src.collectors_v2.execution.runner.time.time", return_value=1700000000):
            result = run_execution(payload)

        self.assertTrue(result["success"])
        self.assertEqual(result["stored_count"], 1)
        self.assertEqual(result["duplicate_count"], 0)
        mock_redis_manager.store_proxy.assert_called_once()
        mock_redis_manager.get_redis_client.assert_not_called()
        mock_redis_manager._get_proxy_key.assert_not_called()

    def test_runner_should_skip_cooldown_blocked_proxy_without_counting_as_storage_error(self):
        payload = {
            "run_id": "run-cooldown-1",
            "trigger": "test",
            "collector": {
                "id": "demo-cooldown",
                "mode": "simple",
                "spec": {
                    "proxies": [
                        {"ip": "6.6.6.6", "port": 8080, "protocol": "http"},
                    ]
                },
            },
        }

        mock_redis_manager = Mock(spec=RedisManager)
        mock_redis_manager.store_proxy.return_value = {
            "stored": False,
            "created": False,
            "proxy_key": "proxy:http:6.6.6.6:8080",
            "cooldown_blocked": True,
        }

        with patch(
            "src.collectors_v2.execution.runner._get_redis_manager",
            return_value=mock_redis_manager,
            create=True,
        ), patch("src.collectors_v2.execution.runner.time.time", return_value=1700000000):
            result = run_execution(payload)

        self.assertTrue(result["success"])
        self.assertEqual(result["raw_count"], 1)
        self.assertEqual(result["valid_count"], 1)
        self.assertEqual(result["stored_count"], 0)
        self.assertEqual(result["duplicate_count"], 0)
        self.assertEqual(result.get("cooldown_blocked_count"), 1)
        self.assertEqual(result["errors"], [])
        mock_redis_manager.store_proxy.assert_called_once()
        mock_redis_manager.get_redis_client.assert_not_called()
        mock_redis_manager._get_proxy_key.assert_not_called()

    def test_runner_should_fail_when_collector_missing(self):
        result = run_execution({"run_id": "run-2", "trigger": "test"})
        self.assertFalse(result["success"])
        self.assertGreaterEqual(len(result["errors"]), 1)

    def test_runner_should_surface_api_response_error_message(self):
        payload = {
            "run_id": "run-3",
            "trigger": "test",
            "collector": {
                "id": "demo",
                "mode": "simple",
                "spec": {
                    "request": {"url": "https://example.test/api"},
                    "extract": {"type": "jsonpath", "expression": "$.data.proxy_list[*]"},
                    "field_mapping": {"ip": "ip", "port": "port"},
                },
            },
        }

        with patch("src.collectors_v2.execution.engines.simple_engine.requests.request") as mock_request:
            class _FakeResponse:
                def raise_for_status(self):
                    return None

                def json(self):
                    return {"code": "10002", "msg": "akey invalid", "data": {"proxy_list": []}}

            mock_request.return_value = _FakeResponse()
            with patch("src.collectors_v2.execution.runner._get_redis_manager", return_value=Mock(spec=RedisManager), create=True):
                result = run_execution(payload)

        self.assertFalse(result["success"])
        self.assertTrue(any("akey invalid" in err for err in result["errors"]))


if __name__ == "__main__":
    unittest.main()
