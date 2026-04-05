import asyncio
import json
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from src.config import Config
from src.database.redis_client import RedisManager
from src.testers.manager import TesterManager
from src.api import system_endpoints


class _FakeRepo:
    def __init__(self, now: datetime):
        self.now = now

    def list_definitions(self):
        return [
            {
                "id": "collector_v2_a",
                "enabled": True,
                "lifecycle": "published",
            },
            {
                "id": "collector_v2_b",
                "enabled": True,
                "lifecycle": "published",
            },
            {
                "id": "collector_v2_disabled",
                "enabled": False,
                "lifecycle": "published",
            },
        ]

    def get_runs(self, collector_id, limit=20):
        if collector_id == "collector_v2_a":
            return [
                {
                    "trigger": "schedule",
                    "ended_at": (self.now - timedelta(minutes=2)).isoformat(),
                    "metrics": {"stored_count": 6},
                },
                {
                    "trigger": "test",
                    "ended_at": (self.now - timedelta(minutes=1)).isoformat(),
                    "metrics": {"stored_count": 99},
                },
            ]
        if collector_id == "collector_v2_b":
            return [
                {
                    "trigger": "schedule",
                    "ended_at": (self.now - timedelta(minutes=1)).isoformat(),
                    "metrics": {"stored_count": 4},
                }
            ]
        return []


class TestSystemEndpointMetrics(unittest.TestCase):
    def test_build_proxy_pool_metrics_should_only_count_b_or_above_as_available(self):
        mock_redis_manager = Mock()
        mock_redis_manager.get_all_proxies.return_value = [
            SimpleNamespace(grade="A"),
            SimpleNamespace(grade="C"),
            SimpleNamespace(grade="D"),
        ]

        with patch.object(system_endpoints.app_globals, "global_redis_manager", mock_redis_manager):
            metrics = asyncio.run(system_endpoints._build_proxy_pool_metrics({}, {}))

        self.assertEqual(metrics["success_rate"], 0.33)

    def test_tester_manager_status_should_expose_batch_metrics(self):
        config = Config()
        logger = Mock()
        redis_manager = Mock(spec=RedisManager)
        tester_factory = lambda *args, **kwargs: Mock(close=Mock(), apply_runtime_config=Mock())
        tester_manager = TesterManager(
            config,
            logger,
            redis_manager,
            tester_class=tester_factory,
            stats_only_mode=True,
        )
        tester_manager._stats["queue_backlog"] = 12
        tester_manager._stats["last_batch_duration_seconds"] = 3.25
        tester_manager._stats["batch_throughput_per_min"] = 18.4
        tester_manager._stats["last_batch_tested"] = 8

        status = tester_manager.get_status()
        stats = status["stats"]

        self.assertIn("queue_backlog", stats)
        self.assertIn("last_batch_duration_seconds", stats)
        self.assertIn("batch_throughput_per_min", stats)
        self.assertIn("last_batch_tested", stats)
        self.assertEqual(stats["queue_backlog"], 12)
        self.assertEqual(stats["last_batch_duration_seconds"], 3.25)
        self.assertEqual(stats["batch_throughput_per_min"], 18.4)
        self.assertEqual(stats["last_batch_tested"], 8)

    def test_get_system_metrics_should_use_v2_run_records_for_collect_rate(self):
        now = datetime.now()
        mock_redis_manager = Mock()
        mock_redis_manager.get_all_proxies.return_value = []
        mock_redis_manager.get_redis_client.return_value = Mock()

        with patch("src.api.system_endpoints.get_metrics", return_value={
            "avg_response_time_ms": 1,
            "qps": 2,
            "error_rate": 0,
            "concurrent_connections": 0,
        }), \
             patch("src.api.system_endpoints.merge_connection_metrics", side_effect=lambda api_metrics, **kwargs: api_metrics), \
             patch("src.api.system_endpoints.get_collector_runtime_mode", return_value="v2"), \
             patch("src.api.system_endpoints.CollectorV2Repository", return_value=_FakeRepo(now)), \
             patch.object(system_endpoints, "global_collector_manager") as mock_collector_manager, \
             patch.object(system_endpoints.app_globals, "global_redis_manager", mock_redis_manager), \
             patch.object(system_endpoints.app_globals, "global_tester_manager", None):
            mock_collector_manager.get_status.return_value = {
                "stats": {
                    "collect_rate_per_min": 123,
                    "success_rate": 0.5,
                }
            }

            metrics = asyncio.run(system_endpoints.get_system_metrics(token=""))

        self.assertEqual(metrics["proxy_pool_metrics"]["collect_rate_per_min"], 2.0)

    def test_get_collector_manager_module_status_should_expose_split_collection_counts(self):
        collector_status = {
            "running": True,
            "collectors_count": 1,
            "collectors": [
                {
                    "name": "Test Collector",
                    "is_running": True,
                    "interval_seconds": 300,
                    "last_run": "2026-03-19T00:00:00",
                }
            ],
            "stats": {
                "collect_rate_per_min": 8.5,
                "success_rate": 0.75,
                "raw_count": 12,
                "stored_count": 7,
                "cooldown_blocked_count": 5,
                "queue_length": 7,
            },
        }

        with patch("src.api.system_endpoints.get_collector_runtime_mode", return_value="legacy"):
            module_status = system_endpoints._get_collector_manager_module_status(
                now_str="2026-03-19T00:00:00",
                uptime="00:10:00",
                collector_status=collector_status,
            )

        performance = module_status["performance"]
        self.assertEqual(performance["collect_rate"], 8.5)
        self.assertEqual(performance["success_rate"], 0.75)
        self.assertEqual(performance["raw_count"], 12)
        self.assertEqual(performance["stored_count"], 7)
        self.assertEqual(performance["cooldown_blocked_count"], 5)
        self.assertEqual(performance["queue_length"], 7)

    def test_get_system_metrics_should_expose_tester_batch_metrics(self):
        mock_redis_manager = Mock()
        mock_redis_manager.get_all_proxies.return_value = []
        mock_redis_manager.get_redis_client.return_value = Mock()

        mock_tester_manager = Mock()
        mock_tester_manager.get_status.return_value = {
            "stats": {
                "total_tested": 24,
                "total_passed": 18,
                "total_failed": 4,
                "total_removed": 2,
                "test_rounds": 3,
                "test_rate_per_min": 12.5,
                "cleanup_rate_per_min": 1.5,
                "queue_backlog": 7,
                "last_batch_duration_seconds": 4.2,
                "batch_throughput_per_min": 14.3,
                "last_batch_tested": 9,
            }
        }

        with patch("src.api.system_endpoints.get_metrics", return_value={
            "avg_response_time_ms": 1,
            "qps": 2,
            "error_rate": 0,
            "concurrent_connections": 0,
        }), \
             patch("src.api.system_endpoints.merge_connection_metrics", side_effect=lambda api_metrics, **kwargs: api_metrics), \
             patch("src.api.system_endpoints.get_collector_runtime_mode", return_value="legacy"), \
             patch.object(system_endpoints, "global_collector_manager") as mock_collector_manager, \
             patch.object(system_endpoints.app_globals, "global_redis_manager", mock_redis_manager), \
             patch.object(system_endpoints.app_globals, "global_tester_manager", mock_tester_manager):
            mock_collector_manager.get_status.return_value = {
                "stats": {
                    "collect_rate_per_min": 123,
                    "success_rate": 0.5,
                }
            }

            metrics = asyncio.run(system_endpoints.get_system_metrics(token=""))

        proxy_metrics = metrics["proxy_pool_metrics"]
        self.assertEqual(proxy_metrics["test_queue_backlog"], 7)
        self.assertEqual(proxy_metrics["last_test_batch_duration_seconds"], 4.2)
        self.assertEqual(proxy_metrics["batch_throughput_per_min"], 14.3)
        self.assertEqual(proxy_metrics["last_test_batch_size"], 9)

    def test_get_system_metrics_should_expose_tester_batch_metrics_from_redis_when_manager_missing(self):
        mock_redis_manager = Mock()
        redis_client = Mock()
        redis_client.exists.return_value = True
        redis_client.get.return_value = json.dumps({
            "total_tested": 24,
            "total_passed": 18,
            "total_failed": 4,
            "total_removed": 2,
            "test_rounds": 3,
            "start_time": datetime.now().timestamp() - 120,
            "test_rate_per_min": 12.5,
            "cleanup_rate_per_min": 1.5,
            "queue_backlog": 7,
            "last_batch_duration_seconds": 4.2,
            "batch_throughput_per_min": 14.3,
            "last_batch_tested": 9,
        })
        mock_redis_manager.get_redis_client.return_value = redis_client
        mock_redis_manager.get_all_proxies.return_value = []

        with patch("src.api.system_endpoints.get_metrics", return_value={
            "avg_response_time_ms": 1,
            "qps": 2,
            "error_rate": 0,
            "concurrent_connections": 0,
        }), \
             patch("src.api.system_endpoints.merge_connection_metrics", side_effect=lambda api_metrics, **kwargs: api_metrics), \
             patch("src.api.system_endpoints.get_collector_runtime_mode", return_value="legacy"), \
             patch.object(system_endpoints, "global_collector_manager") as mock_collector_manager, \
             patch.object(system_endpoints.app_globals, "global_redis_manager", mock_redis_manager), \
             patch.object(system_endpoints.app_globals, "global_tester_manager", None):
            mock_collector_manager.get_status.return_value = {
                "stats": {
                    "collect_rate_per_min": 123,
                    "success_rate": 0.5,
                }
            }

            metrics = asyncio.run(system_endpoints.get_system_metrics(token=""))

        proxy_metrics = metrics["proxy_pool_metrics"]
        self.assertEqual(proxy_metrics["test_queue_backlog"], 7)
        self.assertEqual(proxy_metrics["last_test_batch_duration_seconds"], 4.2)
        self.assertEqual(proxy_metrics["batch_throughput_per_min"], 14.3)
        self.assertEqual(proxy_metrics["last_test_batch_size"], 9)

    def test_metrics_snapshot_worker_should_record_v2_collect_rate_and_proxy_availability(self):
        now = datetime.now()
        mock_redis_manager = Mock()
        mock_redis_manager.get_all_proxies.return_value = [
            SimpleNamespace(grade="A"),
            SimpleNamespace(grade=None),
        ]
        redis_client = Mock()
        redis_client.exists.return_value = False
        redis_client.get.return_value = None
        mock_redis_manager.get_redis_client.return_value = redis_client

        sleep_mock = AsyncMock(side_effect=[None, asyncio.CancelledError()])
        captured = {}

        with patch("src.api.system_endpoints.asyncio.sleep", new=sleep_mock), \
             patch("src.api.system_endpoints.get_metrics", return_value={
                 "avg_response_time_ms": 1,
                 "qps": 2,
                 "error_rate": 0,
                 "concurrent_connections": 0,
             }), \
             patch("src.api.system_endpoints.merge_connection_metrics", side_effect=lambda api_metrics, **kwargs: api_metrics), \
             patch("src.api.system_endpoints.get_collector_runtime_mode", return_value="v2"), \
             patch("src.api.system_endpoints.CollectorV2Repository", return_value=_FakeRepo(now)), \
             patch("src.api.system_endpoints.record_metrics_snapshot", side_effect=lambda collector_stats, tester_stats, api_metrics=None: captured.update({
                 "collector_stats": collector_stats,
                 "tester_stats": tester_stats,
                 "api_metrics": api_metrics,
             })), \
             patch.object(system_endpoints, "global_collector_manager") as mock_collector_manager, \
             patch.object(system_endpoints.app_globals, "global_redis_manager", mock_redis_manager), \
             patch.object(system_endpoints.app_globals, "global_tester_manager", None):
            mock_collector_manager.get_status.return_value = {
                "stats": {
                    "collect_rate_per_min": 0,
                    "success_rate": 0.0,
                }
            }

            asyncio.run(system_endpoints._metrics_snapshot_worker())

        self.assertEqual(captured["collector_stats"]["collect_rate_per_min"], 2.0)
        self.assertEqual(captured["collector_stats"]["success_rate"], 0.5)

    def test_get_tester_module_status_should_expose_batch_metrics_from_redis_when_manager_missing(self):
        redis_stats = {
            "total_tested": 24,
            "total_removed": 2,
            "test_rate_per_min": 12.5,
            "cleanup_rate_per_min": 1.5,
            "queue_backlog": 7,
            "last_batch_duration_seconds": 4.2,
            "batch_throughput_per_min": 14.3,
            "last_batch_tested": 9,
        }

        with patch.object(system_endpoints.app_globals, "global_tester_manager", None), patch(
            "src.api.system_endpoints._get_tester_stats_from_redis",
            return_value=(redis_stats, True),
        ):
            module_status = system_endpoints._get_tester_module_status(
                now_str="2026-03-18T22:00:00",
                uptime="00:10:00",
            )

        performance = module_status["performance"]
        self.assertEqual(performance["queue_backlog"], 7)
        self.assertEqual(performance["last_batch_duration_seconds"], 4.2)
        self.assertEqual(performance["batch_throughput_per_min"], 14.3)
        self.assertEqual(performance["last_batch_tested"], 9)

    def test_get_system_status_should_reflect_tester_stopped_when_no_manager_and_no_backend(self):
        mock_redis_manager = Mock()
        redis_client = Mock()
        redis_client.ping.return_value = True
        redis_client.info.return_value = {}
        mock_redis_manager.get_redis_client.return_value = redis_client

        with patch.object(system_endpoints.app_globals, "global_redis_manager", mock_redis_manager), \
             patch.object(system_endpoints, "global_collector_manager") as mock_collector_manager, \
             patch.object(system_endpoints.app_globals, "global_tester_manager", None), \
             patch("src.api.system_endpoints._get_tester_stats_from_redis", return_value=({}, False)), \
             patch("src.api.system_endpoints._can_connect_tcp_endpoint", return_value=(True, None)):
            mock_collector_manager.get_status.return_value = {"uptime_formatted": "00:10:00"}

            status = asyncio.run(system_endpoints.get_system_status())

        self.assertEqual(status["tester_service_status"], "Stopped")


if __name__ == "__main__":
    unittest.main()
