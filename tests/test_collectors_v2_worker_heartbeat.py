import asyncio
import unittest
from unittest.mock import patch

from src.collectors_v2.repository import CollectorV2Repository
from src.api import system_endpoints


class _FakeRedisClient:
    def __init__(self):
        self._store = {}

    def setex(self, key, _ttl, value):
        self._store[key] = value

    def get(self, key):
        return self._store.get(key)


class _FakeRedisManager:
    def __init__(self):
        self.client = _FakeRedisClient()

    def get_redis_client(self):
        return self.client


class TestCollectorWorkerHeartbeat(unittest.TestCase):
    def test_repository_should_save_and_load_worker_heartbeat(self):
        repo = CollectorV2Repository(_FakeRedisManager())

        repo.upsert_worker_heartbeat(
            worker_id="collector-worker-1",
            status="running",
            active_jobs=2,
            queue_backlog=3,
            version="v2",
            ttl_seconds=30,
        )

        heartbeat = repo.get_worker_heartbeat("collector-worker-1")
        self.assertIsNotNone(heartbeat)
        self.assertEqual(heartbeat["worker_id"], "collector-worker-1")
        self.assertEqual(heartbeat["status"], "running")
        self.assertEqual(heartbeat["active_jobs"], 2)
        self.assertEqual(heartbeat["queue_backlog"], 3)


class TestCollectorWorkerSystemLink(unittest.TestCase):
    def test_get_module_status_should_use_legacy_collector_module_when_runtime_mode_is_legacy(self):
        collector_status = {
            "running": True,
            "uptime_formatted": "1h",
            "collectors": [],
            "collectors_count": 0,
            "stats": {},
        }

        with patch("src.api.system_endpoints.global_collector_manager") as mock_collector_manager, \
             patch("src.api.system_endpoints._get_tester_module_status") as mock_tester_status, \
             patch.object(system_endpoints.config, "COLLECTOR_RUNTIME_MODE", "legacy"), \
             patch.object(system_endpoints.config, "COLLECTOR_V2_ENABLED", 0):
            mock_collector_manager.get_status.return_value = collector_status
            mock_tester_status.return_value = {
                "moduleName": "Tester Manager",
                "status": "Stopped",
                "lastHeartbeat": "2026-03-08T22:00:01",
                "uptime": "1h",
                "performance": {},
            }

            modules = asyncio.run(system_endpoints.get_module_status(token=""))

        collector = next(module for module in modules if module["moduleName"] == "Collector")
        self.assertEqual(collector["status"], "Running")
        self.assertEqual(collector["details"]["version"], "legacy")
        self.assertFalse(any(module["moduleName"] == "Collector Manager" for module in modules))
        self.assertFalse(any(module["moduleName"] == "Collector Worker" for module in modules))

    def test_should_build_v2_collector_module_status(self):
        heartbeat = {
            "worker_id": "collector-worker-1",
            "status": "running",
            "last_heartbeat": "2026-03-08T22:00:00",
            "active_jobs": 1,
            "queue_backlog": 0,
            "version": "v2",
        }
        with patch("src.api.system_endpoints._get_collector_worker_heartbeat", return_value=heartbeat), \
             patch.object(system_endpoints.config, "COLLECTOR_RUNTIME_MODE", "v2"), \
             patch.object(system_endpoints.config, "COLLECTOR_V2_ENABLED", 1):
            module = system_endpoints._get_collector_module_status(
                now_str="2026-03-08T22:00:01",
                uptime="1h",
            )

        self.assertEqual(module["moduleName"], "Collector")
        self.assertEqual(module["status"], "Running")
        self.assertEqual(module["details"]["worker_id"], "collector-worker-1")

    def test_get_module_status_should_include_single_collector_module_when_runtime_mode_is_v2(self):
        collector_status = {
            "running": False,
            "uptime_formatted": "1h",
            "collectors": [],
            "collectors_count": 0,
            "stats": {},
        }

        heartbeat = {
            "worker_id": "collector-worker-1",
            "status": "running",
            "last_heartbeat": "2026-03-08T22:00:00",
            "active_jobs": 1,
            "queue_backlog": 0,
            "version": "v2",
        }

        with patch("src.api.system_endpoints.global_collector_manager") as mock_collector_manager, \
             patch("src.api.system_endpoints._get_tester_module_status") as mock_tester_status, \
             patch.object(system_endpoints.config, "COLLECTOR_RUNTIME_MODE", "v2"), \
             patch.object(system_endpoints.config, "COLLECTOR_V2_ENABLED", 1), \
             patch("src.api.system_endpoints._get_collector_worker_heartbeat", return_value=heartbeat):
            mock_collector_manager.get_status.return_value = collector_status
            mock_tester_status.return_value = {
                "moduleName": "Tester Manager",
                "status": "Stopped",
                "lastHeartbeat": "2026-03-08T22:00:01",
                "uptime": "1h",
                "performance": {},
            }

            modules = asyncio.run(system_endpoints.get_module_status(token=""))

        collector = next(module for module in modules if module["moduleName"] == "Collector")
        self.assertEqual(collector["status"], "Running")
        self.assertEqual(collector["details"]["version"], "v2")
        self.assertFalse(any(module["moduleName"] == "Collector Manager" for module in modules))
        self.assertFalse(any(module["moduleName"] == "Collector Worker" for module in modules))

    def test_get_system_status_should_expose_collector_runtime_version(self):
        collector_status = {
            "running": False,
            "uptime_formatted": "1h",
            "collectors": [],
            "collectors_count": 0,
            "stats": {},
        }

        with patch("src.api.system_endpoints.global_collector_manager") as mock_collector_manager, \
             patch.object(system_endpoints.config, "COLLECTOR_RUNTIME_MODE", "v2"), \
             patch("src.api.system_endpoints._get_collector_module_status", return_value={
                 "moduleName": "Collector",
                 "status": "Running",
                 "lastHeartbeat": "2026-03-08T22:00:01",
                 "uptime": "1h",
                 "details": {"version": "v2"},
                 "performance": {},
             }), \
             patch.object(system_endpoints.app_globals, "global_redis_manager") as mock_redis_manager, \
             patch("src.api.system_endpoints._can_connect_tcp_endpoint", return_value=(True, None)):
            mock_collector_manager.get_status.return_value = collector_status
            mock_redis_manager.get_redis_client.return_value.ping.return_value = True
            mock_redis_manager.get_redis_client.return_value.info.return_value = {}

            status_payload = asyncio.run(system_endpoints.get_system_status())

        self.assertEqual(status_payload["collector_runtime_mode"], "v2")
        self.assertEqual(status_payload["collector_version"], "v2")


if __name__ == "__main__":
    unittest.main()
