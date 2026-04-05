import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import main as backend_main


class TestLegacyBootstrap(unittest.IsolatedAsyncioTestCase):
    async def test_legacy_mode_should_not_create_default_collectors_when_config_empty(self):
        fake_config = SimpleNamespace(
            COLLECTORS=[],
            COLLECT_INTERVAL_SECONDS=300,
            ZDAYE_COLLECT_INTERVAL=300,
            ZDAYE_OVERSEAS_COLLECT_INTERVAL=300,
            COLLECTOR_RUNTIME_MODE="legacy",
            save_to_file=Mock(),
        )
        fake_logger = Mock()
        fake_redis_manager = Mock()
        fake_collector_manager = Mock()
        fake_tester_manager = SimpleNamespace(
            start=AsyncMock(),
            stop=AsyncMock(),
        )

        async def stop_main_loop(_seconds: float):
            raise KeyboardInterrupt()

        with patch.object(backend_main, "config", fake_config), \
             patch.object(backend_main, "app_logger", fake_logger), \
             patch.object(backend_main, "redis_manager", fake_redis_manager), \
             patch.object(backend_main, "CollectorManager", return_value=fake_collector_manager) as collector_manager_cls, \
             patch.object(backend_main, "TesterManager", return_value=fake_tester_manager), \
             patch.object(backend_main, "start_collector_worker_task", return_value=None), \
             patch.object(backend_main, "stop_collector_worker_task", new=AsyncMock()), \
             patch.object(backend_main.asyncio, "sleep", side_effect=stop_main_loop):
            await backend_main.main()

        collector_manager_cls.assert_called_once()
        args, kwargs = collector_manager_cls.call_args
        self.assertEqual(args, (fake_config, fake_logger, fake_redis_manager))
        self.assertEqual(kwargs["collectors_with_intervals"], [])
        fake_config.save_to_file.assert_not_called()
        self.assertEqual(fake_config.COLLECTORS, [])


if __name__ == "__main__":
    unittest.main()
