import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from src.database.models import Proxy
from src.database.redis_client import RedisManager
from src.testers.manager import TesterManager


class DummyTester:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.applied_keys = []

    def apply_runtime_config(self, updated_keys):
        self.applied_keys.extend(updated_keys)

    async def close(self):
        return None


class TestTesterManager(unittest.TestCase):
    def setUp(self):
        self.config = SimpleNamespace(
            TEST_INTERVAL_SECONDS=300,
            TEST_BATCH_SIZE=2,
            TEST_IDLE_SLEEP_SECONDS=2,
            TEST_SCHEDULE_ZSET_KEY="proxies:test_schedule",
            MAX_FAIL_COUNT=5,
            TEST_MAX_CONCURRENT=10,
            TESTER_LOG_EACH_PROXY=False,
            TEST_TIMEOUT_PER_TARGET=5,
            TEST_TARGETS=["http://example.com"],
        )
        self.logger = Mock()
        self.redis_manager = Mock(spec=RedisManager)
        self.manager = TesterManager(
            self.config,
            self.logger,
            self.redis_manager,
            tester_class=DummyTester
        )

    def test_apply_runtime_config_should_update_tester_runtime_fields(self):
        self.config.TEST_INTERVAL_SECONDS = 60
        self.config.MAX_FAIL_COUNT = 8
        self.config.TEST_MAX_CONCURRENT = 32
        self.config.TESTER_LOG_EACH_PROXY = True

        result = self.manager.apply_runtime_config(
            ["TEST_INTERVAL_SECONDS", "MAX_FAIL_COUNT", "TEST_MAX_CONCURRENT", "TESTER_LOG_EACH_PROXY"]
        )

        self.assertEqual(self.manager.base_interval, 60)
        self.assertEqual(self.manager.max_fail_count, 8)
        self.assertEqual(self.manager.max_concurrent, 32)
        self.assertTrue(self.manager.log_each_proxy)
        self.assertEqual(self.manager.semaphore._value, 32)
        self.assertIn("TEST_INTERVAL_SECONDS", result)
        self.assertIn("MAX_FAIL_COUNT", result)
        self.assertIn("TEST_MAX_CONCURRENT", result)
        self.assertIn("TESTER_LOG_EACH_PROXY", result)

    def test_test_single_proxy_should_build_batch_payload_and_next_check_time(self):
        proxy = Proxy(
            ip="1.1.1.1",
            port=80,
            protocol="http",
            success_count=1,
            fail_count=0,
            grade="B",
        )
        self.manager.tester.test_proxy_async = AsyncMock(
            return_value=SimpleNamespace(
                success_count=1,
                total_targets=1,
                avg_response_time=0.5,
            )
        )

        with patch("src.testers.manager.time.time", return_value=1700000000):
            result = asyncio.run(self.manager._test_single_proxy(proxy))

        self.assertIsInstance(result, dict)
        self.assertEqual(result["proxy"].last_check_time, 1700000000)
        self.assertFalse(result["remove"])
        self.assertAlmostEqual(result["next_check_at"], 1700000600.0)
        self.assertEqual(result["proxy"].grade, "S")
        self.assertEqual(result["proxy"].fail_count, 0)

    def test_test_single_proxy_should_mark_remove_when_fail_count_reaches_limit(self):
        proxy = Proxy(
            ip="2.2.2.2",
            port=443,
            protocol="https",
            success_count=0,
            fail_count=4,
            grade="D",
        )
        self.manager.tester.test_proxy_async = AsyncMock(
            return_value=SimpleNamespace(
                success_count=0,
                total_targets=1,
                avg_response_time=1.0,
            )
        )

        with patch("src.testers.manager.time.time", return_value=1700000000):
            result = asyncio.run(self.manager._test_single_proxy(proxy))

        self.assertIsInstance(result, dict)
        self.assertTrue(result["remove"])
        self.assertEqual(result["proxy"].fail_count, 5)
        self.assertAlmostEqual(result["next_check_at"], 1700000090.0)

    def test_test_new_proxy_should_persist_success_result(self):
        proxy = Proxy(
            ip="3.3.3.3",
            port=8080,
            protocol="http",
            success_count=0,
            fail_count=0,
            grade="B",
        )
        tested_proxy = Proxy(
            ip="3.3.3.3",
            port=8080,
            protocol="http",
            success_count=1,
            fail_count=0,
            grade="C",
        )
        self.manager._test_single_proxy = AsyncMock(
            return_value={
                "proxy": tested_proxy,
                "remove": False,
                "passed": True,
                "next_check_at": 1700000200,
            }
        )
        self.manager._save_stats_to_redis = AsyncMock()
        self.manager._broadcast_update = AsyncMock()

        with patch("src.testers.manager.time.time", side_effect=[1700000000, 1700000001]):
            result = asyncio.run(self.manager.test_new_proxy(proxy))

        self.assertIs(result, tested_proxy)
        self.manager._test_single_proxy.assert_awaited_once_with(proxy)
        self.redis_manager.batch_update_test_results.assert_called_once_with(
            [
                {
                    "proxy": tested_proxy,
                    "remove": False,
                    "next_check_at": 1700000200,
                }
            ]
        )
        self.assertEqual(self.manager._stats["total_tested"], 1)
        self.assertEqual(self.manager._stats["total_passed"], 1)
        self.assertEqual(self.manager._stats["total_failed"], 0)
        self.assertEqual(self.manager._stats["total_removed"], 0)
        self.assertEqual(self.manager._stats["test_rounds"], 1)
        self.assertEqual(self.manager._stats["last_batch_tested"], 1)
        self.assertEqual(self.manager._stats["batch_throughput_per_min"], 60.0)
        self.manager._save_stats_to_redis.assert_awaited_once()
        self.manager._broadcast_update.assert_awaited_once()

    def test_test_new_proxy_should_delete_when_fail_count_reaches_limit(self):
        proxy = Proxy(
            ip="4.4.4.4",
            port=9090,
            protocol="https",
            success_count=0,
            fail_count=4,
            grade="D",
        )
        tested_proxy = Proxy(
            ip="4.4.4.4",
            port=9090,
            protocol="https",
            success_count=0,
            fail_count=5,
            grade="D",
        )
        self.manager._test_single_proxy = AsyncMock(
            return_value={
                "proxy": tested_proxy,
                "remove": True,
                "passed": False,
                "removed_at": 1700000000,
                "next_check_at": 1700000300,
            }
        )
        self.manager._save_stats_to_redis = AsyncMock()
        self.manager._broadcast_update = AsyncMock()

        with patch("src.testers.manager.time.time", side_effect=[1700000000, 1700000002]):
            result = asyncio.run(self.manager.test_new_proxy(proxy))

        self.assertIs(result, tested_proxy)
        self.manager._test_single_proxy.assert_awaited_once_with(proxy)
        self.redis_manager.batch_update_test_results.assert_called_once_with(
            [
                {
                    "proxy": tested_proxy,
                    "remove": True,
                    "removed_at": 1700000000,
                    "last_fail_count": 5,
                    "next_check_at": 1700000300,
                }
            ]
        )
        self.assertEqual(self.manager._stats["total_tested"], 1)
        self.assertEqual(self.manager._stats["total_passed"], 0)
        self.assertEqual(self.manager._stats["total_failed"], 0)
        self.assertEqual(self.manager._stats["total_removed"], 1)
        self.assertEqual(self.manager._stats["test_rounds"], 1)
        self.assertEqual(self.manager._stats["last_batch_tested"], 1)
        self.assertEqual(self.manager._stats["batch_throughput_per_min"], 30.0)
        self.manager._save_stats_to_redis.assert_awaited_once()
        self.manager._broadcast_update.assert_awaited_once()

    def test_drain_due_proxies_should_batch_write_due_results_and_cleanup_missing_keys(self):
        proxy_a = Proxy(ip="1.1.1.1", port=80, protocol="http", grade="C", success_count=1, fail_count=0)
        proxy_b = Proxy(ip="2.2.2.2", port=443, protocol="https", grade="D", success_count=0, fail_count=1)
        self.redis_manager.get_due_proxy_keys.return_value = [
            "proxy:http:1.1.1.1:80",
            "proxy:https:2.2.2.2:443",
            "proxy:http:9.9.9.9:8080",
        ]
        self.redis_manager.get_redis_client.return_value.zcount.return_value = 3
        self.redis_manager.get_proxies_by_keys.return_value = ([proxy_a, proxy_b], ["proxy:http:9.9.9.9:8080"])
        self.redis_manager.batch_update_test_results.return_value = {
            "updated": 2,
            "deleted": 0,
            "scheduled": 2,
        }
        self.manager._test_single_proxy = AsyncMock(
            side_effect=[
                {"proxy": proxy_a, "remove": False, "passed": True, "next_check_at": 1700000200},
                {
                    "proxy": proxy_b,
                    "remove": True,
                    "passed": False,
                    "removed_at": 1700000000,
                    "next_check_at": 1700000300,
                },
            ]
        )
        self.manager._broadcast_update = AsyncMock()

        with patch("src.testers.manager.time.time", return_value=1700000000):
            result = asyncio.run(self.manager._drain_due_proxies())

        self.assertEqual(result, 2)
        self.redis_manager.get_due_proxy_keys.assert_called_once_with(limit=2, now_ts=1700000000)
        self.redis_manager.get_proxies_by_keys.assert_called_once_with(self.redis_manager.get_due_proxy_keys.return_value)
        self.redis_manager.delete_proxy_by_key.assert_called_once_with("proxy:http:9.9.9.9:8080")
        self.redis_manager.batch_update_test_results.assert_called_once_with(
            [
                {"proxy": proxy_a, "remove": False, "next_check_at": 1700000200},
                {
                    "proxy": proxy_b,
                    "remove": True,
                    "removed_at": 1700000000,
                    "last_fail_count": 1,
                    "next_check_at": 1700000300,
                },
            ]
        )
        self.assertEqual(self.manager._stats["total_tested"], 2)
        self.assertEqual(self.manager._stats["total_passed"], 1)
        self.assertEqual(self.manager._stats["total_removed"], 1)
        self.assertEqual(self.manager._stats["test_rounds"], 1)
        self.manager._broadcast_update.assert_awaited_once()

    def test_run_tests_periodically_should_sleep_when_queue_empty(self):
        async def fake_sleep(seconds):
            self.assertEqual(seconds, 2)
            self.manager._running = False

        self.manager._drain_due_proxies = AsyncMock(return_value=0)
        self.manager._update_running_status = AsyncMock()
        self.manager._clear_running_status = AsyncMock()

        with patch("src.testers.manager.asyncio.sleep", new=AsyncMock(side_effect=fake_sleep)) as mock_sleep:
            asyncio.run(self.manager.run_tests_periodically())

        self.manager._drain_due_proxies.assert_called_once()
        mock_sleep.assert_called_once_with(2)
        self.manager._clear_running_status.assert_awaited()

    def test_repair_missing_schedule_entries_should_enqueue_untested_and_keep_limit(self):
        untested_key = "proxy:http:1.1.1.1:80"
        tested_key = "proxy:https:2.2.2.2:443"
        already_scheduled_key = "proxy:http:3.3.3.3:8080"

        client = Mock()
        client.smembers.return_value = {untested_key, tested_key, already_scheduled_key}
        client.zscore.side_effect = lambda schedule_key, proxy_key: 1700000500 if proxy_key == already_scheduled_key else None
        client.hgetall.side_effect = lambda proxy_key: {
            untested_key: {
                "ip": "1.1.1.1",
                "port": "80",
                "protocol": "http",
                "last_check_time": "0",
                "success_count": "0",
                "fail_count": "0",
                "grade": "",
                "score": "0",
            },
            tested_key: {
                "ip": "2.2.2.2",
                "port": "443",
                "protocol": "https",
                "last_check_time": "1699999900",
                "success_count": "1",
                "fail_count": "0",
                "grade": "A",
                "score": "50",
            },
            already_scheduled_key: {
                "ip": "3.3.3.3",
                "port": "8080",
                "protocol": "http",
                "last_check_time": "1699999800",
                "success_count": "1",
                "fail_count": "0",
                "grade": "B",
                "score": "30",
            },
        }[proxy_key]
        self.redis_manager.get_redis_client.return_value = client

        with patch.object(self.manager.scorer, "calculate_test_interval_multiplier", return_value=1.0):
            repaired = self.manager._repair_missing_schedule_entries(limit=2, now_ts=1700000000)

        self.assertEqual(repaired, 2)
        client.zadd.assert_any_call(self.config.TEST_SCHEDULE_ZSET_KEY, {untested_key: 1700000000.0})
        client.zadd.assert_any_call(self.config.TEST_SCHEDULE_ZSET_KEY, {tested_key: 1700000200.0})
        self.assertEqual(client.zadd.call_count, 2)


if __name__ == "__main__":
    unittest.main()
