import asyncio
import unittest
from unittest.mock import patch

from src.api import system_endpoints


class _FakeCollectorRepo:
    def list_definitions(self):
        return [
            {
                "id": "collector-a",
                "name": "Alpha",
                "enabled": True,
                "lifecycle": "published",
            },
            {
                "id": "collector-b",
                "name": "Beta",
                "enabled": True,
                "lifecycle": "paused",
            },
        ]

    def get_last_run(self, collector_id):
        if collector_id == "collector-a":
            return {
                "run_id": "run-a",
                "collector_id": "collector-a",
                "trigger": "schedule",
                "status": "success",
                "started_at": "2026-03-19T10:00:00",
                "ended_at": "2026-03-19T10:01:00",
                "duration_ms": 60000,
                "metrics": {
                    "raw_count": 10,
                    "valid_count": 8,
                    "stored_count": 6,
                    "duplicate_count": 2,
                },
            }
        if collector_id == "collector-b":
            return {
                "run_id": "run-b",
                "collector_id": "collector-b",
                "trigger": "manual",
                "status": "failed",
                "started_at": "2026-03-19T10:00:00",
                "ended_at": "2026-03-19T10:01:00",
                "duration_ms": 60000,
                "metrics": {
                    "raw_count": 3,
                    "valid_count": 0,
                    "stored_count": 4,
                    "duplicate_count": 0,
                },
            }
        return None


class _FakeRedisManager:
    def __init__(self, cooldown_proxy_count=0):
        self._cooldown_proxy_count = cooldown_proxy_count

    def get_cooldown_proxy_count(self):
        return self._cooldown_proxy_count


class _BrokenRedisManager:
    def get_cooldown_proxy_count(self):
        raise RuntimeError("redis unavailable")


class TestCollectorRealtimePayload(unittest.TestCase):
    def test_get_collector_realtime_payload_should_include_worker_summary_overview_and_collectors(self):
        with patch("src.api.system_endpoints.CollectorV2Repository", return_value=_FakeCollectorRepo()), \
             patch(
                 "src.api.system_endpoints._get_collector_module_status",
                 return_value={
                     "moduleName": "Collector",
                     "status": "Running",
                     "lastHeartbeat": "2026-03-19T10:00:00",
                     "performance": {
                         "active_jobs": 2,
                         "queue_backlog": 4,
                     },
                 },
             ), \
             patch("src.api.system_endpoints._get_redis_manager", return_value=_FakeRedisManager()):
            payload = asyncio.run(system_endpoints.get_collector_realtime_payload())

        self.assertIn("worker_summary", payload)
        self.assertIn("overview", payload)
        self.assertIn("collectors", payload)
        self.assertEqual(payload["worker_summary"]["status"], "running")
        self.assertEqual(payload["worker_summary"]["activeJobs"], 2)
        self.assertEqual(payload["worker_summary"]["queueBacklog"], 4)
        self.assertEqual(payload["overview"]["total"], 2)
        self.assertEqual(payload["overview"]["published"], 1)
        self.assertEqual(payload["overview"]["paused"], 1)
        self.assertEqual(payload["overview"]["draft"], 0)
        self.assertEqual(payload["overview"]["recentStoredCount"], 10)
        self.assertEqual(payload["overview"]["cooldownPoolCount"], 0)
        self.assertIn("recentStoredCount", payload["overview"])
        self.assertIn("successRate", payload["overview"])
        self.assertEqual(payload["collectors"][0]["last_run"]["run_id"], "run-a")

    def test_get_collector_realtime_payload_should_include_cooldown_pool_count(self):
        with patch("src.api.system_endpoints.CollectorV2Repository", return_value=_FakeCollectorRepo()), \
             patch(
                 "src.api.system_endpoints._get_collector_module_status",
                 return_value={
                     "moduleName": "Collector",
                     "status": "Running",
                     "lastHeartbeat": "2026-03-19T10:00:00",
                     "performance": {
                         "active_jobs": 0,
                         "queue_backlog": 0,
                     },
                 },
             ), \
             patch("src.api.system_endpoints._get_redis_manager", return_value=_FakeRedisManager(cooldown_proxy_count=7)):
            payload = asyncio.run(system_endpoints.get_collector_realtime_payload())

        self.assertEqual(payload["overview"]["cooldownPoolCount"], 7)

    def test_get_collector_realtime_payload_should_fall_back_to_zero_when_cooldown_counter_fails(self):
        with patch("src.api.system_endpoints.CollectorV2Repository", return_value=_FakeCollectorRepo()), \
             patch(
                 "src.api.system_endpoints._get_collector_module_status",
                 return_value={
                     "moduleName": "Collector",
                     "status": "Running",
                     "lastHeartbeat": "2026-03-19T10:00:00",
                     "performance": {
                         "active_jobs": 0,
                         "queue_backlog": 0,
                     },
                 },
             ), \
             patch("src.api.system_endpoints._get_redis_manager", return_value=_BrokenRedisManager()):
            payload = asyncio.run(system_endpoints.get_collector_realtime_payload())

        self.assertEqual(payload["overview"]["cooldownPoolCount"], 0)
