import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.collectors_v2 import runtime


class TestCollectorWorkerRuntime(unittest.TestCase):
    def test_runtime_mode_should_disable_legacy_scheduler_when_v2_selected(self):
        config = SimpleNamespace(
            COLLECTOR_RUNTIME_MODE="v2",
            COLLECTOR_V2_ENABLED=1,
            COLLECTOR_WORKER_ENABLED=1,
        )

        self.assertFalse(runtime.should_start_legacy_collector(config))
        self.assertTrue(runtime.is_collector_worker_enabled(config))

    def test_runtime_mode_should_disable_v2_worker_when_legacy_selected(self):
        config = SimpleNamespace(
            COLLECTOR_RUNTIME_MODE="legacy",
            COLLECTOR_V2_ENABLED=1,
            COLLECTOR_WORKER_ENABLED=1,
        )

        self.assertTrue(runtime.should_start_legacy_collector(config))
        self.assertFalse(runtime.is_collector_worker_enabled(config))

    def test_start_should_create_task_when_v2_and_worker_enabled(self):
        config = SimpleNamespace(
            COLLECTOR_RUNTIME_MODE="v2",
            COLLECTOR_V2_ENABLED=1,
            COLLECTOR_WORKER_ENABLED=1,
        )
        logger = SimpleNamespace(info=lambda *args, **kwargs: None)
        redis_manager = object()
        created = {}

        def fake_create_task(coro):
            created["coro"] = coro
            coro.close()
            return "task"

        with patch("src.collectors_v2.runtime.CollectorV2Repository", return_value="repo"):
            task = runtime.start_collector_worker_task(
                config=config,
                logger=logger,
                redis_manager=redis_manager,
                create_task=fake_create_task,
            )

        self.assertEqual(task, "task")
        self.assertTrue(asyncio.iscoroutine(created["coro"]))

    def test_start_should_skip_task_when_v2_disabled(self):
        config = SimpleNamespace(
            COLLECTOR_RUNTIME_MODE="legacy",
            COLLECTOR_V2_ENABLED=0,
            COLLECTOR_WORKER_ENABLED=1,
        )

        task = runtime.start_collector_worker_task(
            config=config,
            logger=object(),
            redis_manager=object(),
        )

        self.assertIsNone(task)


if __name__ == "__main__":
    unittest.main()
