import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.database.models import Proxy
from src.testers.manager import TesterManager
from src.testers.scoring import MultiTargetTestResult, TargetResult


async def _run_inline(func, *args, **kwargs):
    return func(*args, **kwargs)


class FakeTester:
    def __init__(self, config, logger):
        self._result = MultiTargetTestResult(
            target_results=[
                TargetResult(target="http://a", success=False, response_time=0.1, error="x"),
                TargetResult(target="http://b", success=False, response_time=0.2, error="x"),
            ],
            total_time=0.3,
        )

    async def test_proxy_async(self, proxy_ip, proxy_port, proxy_protocol=None):
        return self._result


class FakePassTester:
    def __init__(self, config, logger):
        self._result = MultiTargetTestResult(
            target_results=[
                TargetResult(target="http://a", success=True, response_time=0.1),
                TargetResult(target="http://b", success=True, response_time=0.2),
            ],
            total_time=0.3,
        )

    async def test_proxy_async(self, proxy_ip, proxy_port, proxy_protocol=None):
        return self._result


class TestTesterLoggingPolicy(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.config = SimpleNamespace(
            TEST_INTERVAL_SECONDS=60,
            MAX_FAIL_COUNT=3,
            TEST_MAX_CONCURRENT=10,
            TESTER_LOG_EACH_PROXY=False,
        )
        self.logger = Mock()
        self.redis_manager = Mock()
        self.redis_client = Mock()
        self.redis_manager.get_redis_client.return_value = self.redis_client
        self.manager = TesterManager(
            config=self.config,
            logger=self.logger,
            redis_manager=self.redis_manager,
            tester_class=FakeTester,
        )
        self.logger.reset_mock()

    @patch("src.testers.manager.asyncio.to_thread", side_effect=_run_inline)
    async def test_per_proxy_failure_should_not_log_warning_before_threshold(self, _mock_to_thread):
        proxy = Proxy(ip="1.1.1.1", port=8080, protocol="http", fail_count=0)

        result = await self.manager._test_single_proxy(proxy)

        self.assertIsNotNone(result)
        self.assertEqual(proxy.fail_count, 1)
        self.assertFalse(self.logger.warning.called)

    @patch("src.testers.manager.asyncio.to_thread", side_effect=_run_inline)
    async def test_reaching_delete_threshold_should_only_emit_removal_debug(self, _mock_to_thread):
        proxy = Proxy(ip="2.2.2.2", port=8080, protocol="http", fail_count=2)

        result = await self.manager._test_single_proxy(proxy)

        self.assertIsInstance(result, dict)
        self.assertTrue(result["remove"])
        self.assertEqual(self.logger.warning.call_count, 0)
        debug_messages = [call.args[0] for call in self.logger.debug.call_args_list if call.args]
        self.assertTrue(any("Removing proxy" in msg for msg in debug_messages))

    @patch("src.testers.manager.asyncio.to_thread", side_effect=_run_inline)
    async def test_tester_should_emit_per_proxy_info_when_flag_enabled(self, _mock_to_thread):
        info_config = SimpleNamespace(
            TEST_INTERVAL_SECONDS=60,
            MAX_FAIL_COUNT=3,
            TEST_MAX_CONCURRENT=10,
            TESTER_LOG_EACH_PROXY=True,
        )
        manager = TesterManager(
            config=info_config,
            logger=self.logger,
            redis_manager=self.redis_manager,
            tester_class=FakePassTester,
        )
        self.logger.reset_mock()
        proxy = Proxy(ip="3.3.3.3", port=8080, protocol="http", fail_count=0)

        result = await manager._test_single_proxy(proxy)

        self.assertIsNotNone(result)
        info_messages = [call.args[0] for call in self.logger.info.call_args_list if call.args]
        self.assertTrue(any("passed" in msg for msg in info_messages))


if __name__ == "__main__":
    unittest.main()
