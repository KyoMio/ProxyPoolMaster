import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from src.database.models import Proxy
from src.database.redis_client import RedisManager


class TestRedisManager(unittest.TestCase):
    def setUp(self):
        self.config = SimpleNamespace(
            REDIS_HOST="localhost",
            REDIS_PORT=6379,
            REDIS_DB=0,
            REDIS_PASSWORD="",
            TEST_SCHEDULE_ZSET_KEY="proxies:test_schedule",
        )
        self.logger = Mock()
        self.manager = RedisManager(self.config, self.logger)
        self.client = Mock()

    def test_add_proxy_should_write_hash_and_indexes(self):
        proxy = Proxy(ip="192.168.1.1", port=8080, protocol="http")
        self.client.exists.return_value = False

        with patch.object(self.manager, "get_redis_client", return_value=self.client), patch(
            "src.database.redis_client.time.time", return_value=1700000000
        ):
            result = self.manager.add_proxy(proxy)

        self.assertTrue(result)
        proxy_key = self.manager._get_proxy_key(proxy)
        self.client.sadd.assert_called_once_with("proxies:all", proxy_key)
        self.client.zadd.assert_any_call("proxies:score", {proxy_key: proxy.score})
        self.client.zadd.assert_any_call(
            self.config.TEST_SCHEDULE_ZSET_KEY,
            {proxy_key: 1700000000},
        )
        self.assertEqual(self.client.zadd.call_count, 2)
        self.assertGreaterEqual(self.client.hset.call_count, 1)

    def test_store_proxy_should_return_structured_result_for_new_proxy(self):
        proxy = Proxy(ip="192.168.1.12", port=8080, protocol="http")
        self.client.exists.return_value = False

        with patch.object(self.manager, "get_redis_client", return_value=self.client), patch(
            "src.database.redis_client.time.time", return_value=1700000000
        ):
            result = self.manager.store_proxy(proxy)

        proxy_key = self.manager._get_proxy_key(proxy)
        self.assertEqual(
            result,
            {
                "stored": True,
                "created": True,
                "proxy_key": proxy_key,
            },
        )
        self.client.zadd.assert_any_call(
            self.config.TEST_SCHEDULE_ZSET_KEY,
            {proxy_key: 1700000000},
        )

    def test_store_proxy_should_return_structured_result_for_existing_proxy(self):
        proxy = Proxy(ip="192.168.1.13", port=8080, protocol="http")
        self.client.exists.return_value = True
        self.client.hgetall.return_value = {
            "score": "7",
            "grade": "B",
            "success_count": "2",
            "fail_count": "0",
            "response_time": "0.8",
            "last_check_time": "1700000000",
        }

        with patch.object(self.manager, "get_redis_client", return_value=self.client), patch(
            "src.database.redis_client.time.time", return_value=1700000000
        ):
            result = self.manager.store_proxy(proxy)

        self.assertEqual(
            result,
            {
                "stored": True,
                "created": False,
                "proxy_key": self.manager._get_proxy_key(proxy),
            },
        )
        schedule_calls = [
            call for call in self.client.zadd.call_args_list if call.args and call.args[0] == self.config.TEST_SCHEDULE_ZSET_KEY
        ]
        self.assertEqual(schedule_calls, [])

    def test_store_proxy_should_skip_when_proxy_is_in_cooldown(self):
        proxy = Proxy(ip="192.168.1.14", port=8080, protocol="http")

        with patch.object(self.manager, "get_redis_client", return_value=self.client), patch.object(
            self.manager,
            "is_proxy_in_cooldown",
            return_value=True,
        ):
            result = self.manager.store_proxy(proxy)

        self.assertEqual(
            result,
            {
                "stored": False,
                "created": False,
                "proxy_key": self.manager._get_proxy_key(proxy),
                "cooldown_blocked": True,
            },
        )
        self.client.hset.assert_not_called()
        self.client.sadd.assert_not_called()
        self.client.zadd.assert_not_called()
        self.client.exists.assert_not_called()

    def test_store_proxy_should_only_fetch_redis_client_once_when_cooldown_blocks(self):
        proxy = Proxy(ip="192.168.1.18", port=8080, protocol="http")
        self.client.hgetall.return_value = {"cooldown_until": "1800000000"}

        with patch.object(self.manager, "get_redis_client", return_value=self.client) as mock_get_client, patch(
            "src.database.redis_client.time.time",
            return_value=1700000000,
        ):
            result = self.manager.store_proxy(proxy)

        self.assertEqual(result["cooldown_blocked"], True)
        self.assertEqual(mock_get_client.call_count, 1)

    def test_record_proxy_cooldown_should_write_hash_zset_and_ttl(self):
        proxy = Proxy(ip="192.168.1.15", port=8080, protocol="https")
        proxy_key = self.manager._get_proxy_key(proxy)

        self.client.hgetall.return_value = {}
        with patch.object(self.manager, "get_redis_client", return_value=self.client), patch(
            "src.database.redis_client.time.time",
            return_value=1700000000,
        ):
            result = self.manager.record_proxy_cooldown(
                proxy=proxy,
                removed_at=1700000000,
                strike_count=1,
                last_fail_count=5,
                reason="max_fail_count_reached",
            )

        self.assertEqual(result["proxy_key"], proxy_key)
        self.assertEqual(result["strike_count"], 1)
        self.assertEqual(result["cooldown_seconds"], 43200)
        self.assertEqual(result["cooldown_until"], 1700043200)
        self.client.hset.assert_any_call(
            self.manager._get_proxy_cooldown_key(proxy),
            "proxy_key",
            proxy_key,
        )
        self.client.zadd.assert_any_call(
            "proxies:cooldown",
            {self.manager._get_proxy_cooldown_key(proxy): 1700043200},
        )
        self.client.expire.assert_called_once_with(
            self.manager._get_proxy_cooldown_key(proxy),
            43260,
        )

    def test_is_proxy_in_cooldown_should_return_false_when_expired(self):
        proxy_key = "proxy:http:192.168.1.16:8080"
        cooldown_key = "proxy:cooldown:http:192.168.1.16:8080"
        self.client.exists.return_value = True
        self.client.hgetall.return_value = {
            "proxy_key": proxy_key,
            "cooldown_until": "1699999990",
        }
        self.client.zscore.return_value = 1699999990

        with patch.object(self.manager, "get_redis_client", return_value=self.client), patch(
            "src.database.redis_client.time.time",
            return_value=1700000000,
        ):
            result = self.manager.is_proxy_in_cooldown(proxy_key)

        self.assertFalse(result)
        self.client.delete.assert_any_call(cooldown_key)
        self.client.zrem.assert_any_call("proxies:cooldown", cooldown_key)

    def test_is_proxy_in_cooldown_should_cleanup_zset_when_hash_is_missing(self):
        proxy_key = "proxy:http:192.168.1.17:8080"
        cooldown_key = "proxy:cooldown:http:192.168.1.17:8080"
        self.client.hgetall.return_value = {}

        with patch.object(self.manager, "get_redis_client", return_value=self.client):
            result = self.manager.is_proxy_in_cooldown(proxy_key)

        self.assertFalse(result)
        self.client.delete.assert_not_called()
        self.client.zrem.assert_any_call("proxies:cooldown", cooldown_key)

    def test_get_all_non_cooldown_proxies_should_skip_cooldown_entries(self):
        active_proxy = Proxy(ip="192.168.1.20", port=8080, protocol="http")
        cooldown_proxy = Proxy(ip="192.168.1.21", port=8080, protocol="https")
        active_key = self.manager._get_proxy_key(active_proxy)
        cooldown_key = self.manager._get_proxy_key(cooldown_proxy)

        self.client.smembers.return_value = [active_key, cooldown_key]
        self.client.hgetall.side_effect = [
            active_proxy.to_dict(),
            cooldown_proxy.to_dict(),
        ]

        def fake_is_proxy_in_cooldown(proxy_key, client=None, now_ts=None):
            return proxy_key == cooldown_key

        with patch.object(self.manager, "get_redis_client", return_value=self.client), patch.object(
            self.manager,
            "is_proxy_in_cooldown",
            side_effect=fake_is_proxy_in_cooldown,
        ):
            result = self.manager.get_all_non_cooldown_proxies()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].ip, active_proxy.ip)
        self.client.hgetall.assert_called_once_with(active_key)

    def test_get_cooldown_proxy_count_should_count_active_entries_from_cooldown_zset(self):
        cooldown_proxy = Proxy(ip="192.168.1.23", port=8080, protocol="https")
        cooldown_key = self.manager._get_proxy_cooldown_key(cooldown_proxy)
        self.client.zrangebyscore.return_value = [cooldown_key]
        self.client.hgetall.return_value = {
            "proxy_key": self.manager._get_proxy_key(cooldown_proxy),
            "cooldown_until": "1700003600",
        }

        with patch.object(self.manager, "get_redis_client", return_value=self.client), patch(
            "src.database.redis_client.time.time",
            return_value=1700000000,
        ):
            result = self.manager.get_cooldown_proxy_count()

        self.assertEqual(result, 1)
        self.client.zrangebyscore.assert_called_once_with("proxies:cooldown", "(1700000000.0", "+inf")
        self.client.hgetall.assert_called_once_with(cooldown_key)

    def test_calculate_proxy_cooldown_seconds_should_map_12h_24h_72h(self):
        self.assertEqual(self.manager.calculate_proxy_cooldown_seconds(1), 43200)
        self.assertEqual(self.manager.calculate_proxy_cooldown_seconds(2), 86400)
        self.assertEqual(self.manager.calculate_proxy_cooldown_seconds(3), 259200)
        self.assertEqual(self.manager.calculate_proxy_cooldown_seconds(9), 259200)

    def test_add_proxy_should_preserve_existing_score_and_grade(self):
        proxy = Proxy(ip="192.168.1.2", port=8080, protocol="https")
        self.client.exists.return_value = True
        self.client.hgetall.return_value = {
            "score": "90",
            "grade": "A",
            "success_count": "10",
            "fail_count": "1",
            "response_time": "0.2",
            "last_check_time": "1700000000",
        }

        with patch.object(self.manager, "get_redis_client", return_value=self.client):
            result = self.manager.add_proxy(proxy)

        self.assertTrue(result)
        self.assertEqual(proxy.score, 90)
        self.assertEqual(proxy.grade, "A")
        self.assertEqual(proxy.success_count, 10)
        self.assertEqual(proxy.fail_count, 1)
        self.client.zadd.assert_called_once_with("proxies:score", {self.manager._get_proxy_key(proxy): 90})
        schedule_calls = [
            call for call in self.client.zadd.call_args_list if call.args and call.args[0] == self.config.TEST_SCHEDULE_ZSET_KEY
        ]
        self.assertEqual(schedule_calls, [])

    def test_update_proxy_should_return_false_when_not_exists(self):
        proxy = Proxy(ip="10.0.0.1", port=9000, protocol="http")
        self.client.exists.return_value = False

        with patch.object(self.manager, "get_redis_client", return_value=self.client):
            result = self.manager.update_proxy(proxy)

        self.assertFalse(result)

    def test_delete_proxy_should_remove_all_indexes(self):
        proxy = Proxy(ip="192.168.1.3", port=8080, protocol="http")

        with patch.object(self.manager, "get_redis_client", return_value=self.client):
            result = self.manager.delete_proxy(proxy)

        self.assertTrue(result)
        proxy_key = self.manager._get_proxy_key(proxy)
        self.client.delete.assert_called_once_with(proxy_key)
        self.client.srem.assert_any_call("proxies:all", proxy_key)
        self.client.srem.assert_any_call("proxies:available", proxy_key)
        self.client.zrem.assert_any_call("proxies:score", proxy_key)
        self.client.zrem.assert_any_call(self.config.TEST_SCHEDULE_ZSET_KEY, proxy_key)
        for grade in ["S", "A", "B", "C", "D"]:
            self.client.srem.assert_any_call(f"proxies:grade:{grade}", proxy_key)

    def test_delete_proxy_by_key_should_remove_all_indexes(self):
        proxy_key = "proxy:http:192.168.1.3:8080"

        with patch.object(self.manager, "get_redis_client", return_value=self.client):
            result = self.manager.delete_proxy_by_key(proxy_key)

        self.assertTrue(result)
        self.client.delete.assert_called_once_with(proxy_key)
        self.client.srem.assert_any_call("proxies:all", proxy_key)
        self.client.srem.assert_any_call("proxies:available", proxy_key)
        self.client.zrem.assert_any_call("proxies:score", proxy_key)
        self.client.zrem.assert_any_call(self.config.TEST_SCHEDULE_ZSET_KEY, proxy_key)
        for grade in ["S", "A", "B", "C", "D"]:
            self.client.srem.assert_any_call(f"proxies:grade:{grade}", proxy_key)

    def test_get_random_proxy_should_return_proxy_object(self):
        proxy = Proxy(ip="1.1.1.1", port=80, protocol="http")
        with patch.object(self.manager, "get_redis_client", return_value=self.client), patch.object(
            self.manager,
            "get_all_non_cooldown_proxies",
            return_value=[proxy],
        ):
            result = self.manager.get_random_proxy()

        self.assertIsNotNone(result)
        self.assertEqual(result.ip, "1.1.1.1")
        self.assertEqual(result.port, 80)

    def test_get_all_proxies_should_return_all_entries(self):
        self.client.smembers.return_value = {"proxy:http:1.1.1.1:80", "proxy:https:2.2.2.2:443"}
        self.client.hgetall.side_effect = [
            {"ip": "1.1.1.1", "port": "80", "protocol": "http"},
            {"ip": "2.2.2.2", "port": "443", "protocol": "https"},
        ]

        with patch.object(self.manager, "get_redis_client", return_value=self.client):
            result = self.manager.get_all_proxies()

        self.assertEqual(len(result), 2)
        ips = {p.ip for p in result}
        self.assertEqual(ips, {"1.1.1.1", "2.2.2.2"})

    def test_schedule_proxy_check_should_write_to_schedule_zset(self):
        proxy_key = "proxy:http:1.1.1.1:80"

        with patch.object(self.manager, "get_redis_client", return_value=self.client):
            self.manager.schedule_proxy_check(proxy_key, 1234567890)

        self.client.zadd.assert_called_once_with(
            self.config.TEST_SCHEDULE_ZSET_KEY,
            {proxy_key: 1234567890},
        )

    def test_get_due_proxy_keys_should_return_only_due_keys_and_respect_limit(self):
        self.client.zrangebyscore.return_value = [
            "proxy:http:1.1.1.1:80",
            "proxy:https:2.2.2.2:443",
        ]

        with patch.object(self.manager, "get_redis_client", return_value=self.client):
            result = self.manager.get_due_proxy_keys(limit=1, now_ts=1234567890)

        self.assertEqual(result, ["proxy:http:1.1.1.1:80"])
        self.client.zrangebyscore.assert_called_once_with(
            self.config.TEST_SCHEDULE_ZSET_KEY,
            min="-inf",
            max=1234567890,
            start=0,
            num=1,
        )

    def test_remove_from_test_schedule_should_remove_key(self):
        proxy_key = "proxy:http:1.1.1.1:80"

        with patch.object(self.manager, "get_redis_client", return_value=self.client):
            self.manager.remove_from_test_schedule(proxy_key)

        self.client.zrem.assert_called_once_with(
            self.config.TEST_SCHEDULE_ZSET_KEY,
            proxy_key,
        )

    def test_get_proxies_by_keys_should_return_proxies_and_missing_keys(self):
        keys = [
            "proxy:http:1.1.1.1:80",
            "proxy:https:2.2.2.2:443",
        ]
        pipeline = Mock()
        pipeline.execute.return_value = [
            {"ip": "1.1.1.1", "port": "80", "protocol": "http"},
            {},
        ]
        self.client.pipeline.return_value = pipeline

        with patch.object(self.manager, "get_redis_client", return_value=self.client):
            proxies, missing_keys = self.manager.get_proxies_by_keys(keys)

        self.assertEqual(len(proxies), 1)
        self.assertEqual(proxies[0].ip, "1.1.1.1")
        self.assertEqual(missing_keys, ["proxy:https:2.2.2.2:443"])
        self.client.pipeline.assert_called_once_with(transaction=False)
        self.assertEqual(pipeline.hgetall.call_args_list[0].args[0], keys[0])
        self.assertEqual(pipeline.hgetall.call_args_list[1].args[0], keys[1])
        pipeline.execute.assert_called_once_with()

    def test_get_proxies_by_keys_should_treat_corrupt_records_as_dirty_keys(self):
        keys = [
            "proxy:http:1.1.1.1:80",
            "proxy:https:2.2.2.2:443",
        ]
        pipeline = Mock()
        pipeline.execute.return_value = [
            {"ip": "1.1.1.1", "port": "80", "protocol": "http"},
            {"ip": "2.2.2.2", "port": "bad-port", "protocol": "https"},
        ]
        self.client.pipeline.return_value = pipeline

        with patch.object(self.manager, "get_redis_client", return_value=self.client):
            proxies, missing_keys = self.manager.get_proxies_by_keys(keys)

        self.assertEqual(len(proxies), 1)
        self.assertEqual(proxies[0].ip, "1.1.1.1")
        self.assertEqual(missing_keys, ["proxy:https:2.2.2.2:443"])
        self.logger.warning.assert_called()
        self.client.pipeline.assert_called_once_with(transaction=False)
        pipeline.execute.assert_called_once_with()

    def test_get_proxies_by_keys_should_raise_when_redis_read_fails(self):
        keys = ["proxy:http:1.1.1.1:80"]
        pipeline = Mock()
        pipeline.execute.side_effect = RuntimeError("redis read failed")
        self.client.pipeline.return_value = pipeline

        with patch.object(self.manager, "get_redis_client", return_value=self.client):
            with self.assertRaises(RuntimeError):
                self.manager.get_proxies_by_keys(keys)

        self.client.pipeline.assert_called_once_with(transaction=False)
        pipeline.hgetall.assert_called_once_with(keys[0])
        pipeline.execute.assert_called_once_with()

    def test_batch_update_test_results_should_update_indexes_and_schedule(self):
        proxy_a = Proxy(
            ip="1.1.1.1",
            port=80,
            protocol="http",
            score=88,
            grade="A",
            success_count=3,
            fail_count=0,
            response_time=0.4,
            last_check_time=1700000100,
        )
        proxy_d = Proxy(
            ip="2.2.2.2",
            port=443,
            protocol="https",
            score=12,
            grade="D",
            success_count=0,
            fail_count=4,
            response_time=9.9,
            last_check_time=1700000100,
        )
        pipeline = Mock()
        pipeline.execute.return_value = [None, None]
        self.client.pipeline.return_value = pipeline

        with patch.object(self.manager, "get_redis_client", return_value=self.client):
            result = self.manager.batch_update_test_results(
                [
                    {
                        "proxy": proxy_a,
                        "next_check_at": 1700000200,
                        "remove": False,
                    },
                    {
                        "proxy": proxy_d,
                        "next_check_at": 1700000300,
                        "remove": False,
                    },
                ]
            )

        self.assertEqual(result["updated"], 2)
        self.assertEqual(result["deleted"], 0)
        self.assertEqual(result["scheduled"], 2)
        self.client.pipeline.assert_called_once_with(transaction=False)
        proxy_a_key = self.manager._get_proxy_key(proxy_a)
        proxy_d_key = self.manager._get_proxy_key(proxy_d)
        pipeline = self.client.pipeline.return_value
        pipeline.hset.assert_any_call(proxy_a_key, "ip", "1.1.1.1")
        pipeline.hset.assert_any_call(proxy_d_key, "ip", "2.2.2.2")
        pipeline.zadd.assert_any_call("proxies:score", {proxy_a_key: 88})
        pipeline.zadd.assert_any_call("proxies:score", {proxy_d_key: 12})
        pipeline.zadd.assert_any_call(
            self.config.TEST_SCHEDULE_ZSET_KEY,
            {proxy_a_key: 1700000200},
        )
        pipeline.zadd.assert_any_call(
            self.config.TEST_SCHEDULE_ZSET_KEY,
            {proxy_d_key: 1700000300},
        )
        pipeline.sadd.assert_any_call("proxies:available", proxy_a_key)
        pipeline.srem.assert_any_call("proxies:available", proxy_d_key)
        pipeline.sadd.assert_any_call("proxies:grade:A", proxy_a_key)
        pipeline.sadd.assert_any_call("proxies:grade:D", proxy_d_key)
        self.assertGreaterEqual(pipeline.hset.call_count, 2)
        pipeline.execute.assert_called_once_with()

    def test_batch_update_test_results_should_record_cooldown_before_delete(self):
        proxy = Proxy(
            ip="3.3.3.3",
            port=8080,
            protocol="http",
            score=0,
            grade="D",
            success_count=0,
            fail_count=5,
        )
        self.client.hgetall.return_value = {
            "strike_count": "1",
            "cooldown_until": "1700043200",
        }
        pipeline = Mock()
        pipeline.execute.return_value = [None]
        self.client.pipeline.return_value = pipeline

        with patch.object(self.manager, "get_redis_client", return_value=self.client), patch(
            "src.database.redis_client.time.time",
            return_value=1700000000,
        ):
            result = self.manager.batch_update_test_results(
                [
                    {
                        "proxy": proxy,
                        "remove": True,
                        "removed_at": 1700000000,
                        "last_fail_count": 5,
                    }
                ]
            )

        self.assertEqual(result["updated"], 0)
        self.assertEqual(result["deleted"], 1)
        self.assertEqual(result["scheduled"], 0)
        proxy_key = self.manager._get_proxy_key(proxy)
        cooldown_key = self.manager._get_proxy_cooldown_key(proxy)
        self.client.hset.assert_any_call(cooldown_key, "proxy_key", proxy_key)
        self.client.hset.assert_any_call(cooldown_key, "strike_count", "2")
        self.client.zadd.assert_any_call(
            "proxies:cooldown",
            {cooldown_key: 1700086400},
        )
        self.client.expire.assert_any_call(cooldown_key, 86460)
        pipeline.delete.assert_called_once_with(proxy_key)
        pipeline.zrem.assert_any_call(self.config.TEST_SCHEDULE_ZSET_KEY, proxy_key)
        pipeline.execute.assert_called_once_with()

    def test_batch_update_test_results_should_delete_proxy_and_unschedule_it(self):
        proxy = Proxy(
            ip="3.3.3.3",
            port=8080,
            protocol="http",
            score=0,
            grade="D",
            success_count=0,
            fail_count=5,
        )
        pipeline = Mock()
        pipeline.execute.return_value = [None]
        self.client.pipeline.return_value = pipeline

        with patch.object(self.manager, "get_redis_client", return_value=self.client):
            result = self.manager.batch_update_test_results(
                [
                    {
                        "proxy": proxy,
                        "next_check_at": 1700000400,
                        "remove": True,
                    }
                ]
            )

        self.assertEqual(result["updated"], 0)
        self.assertEqual(result["deleted"], 1)
        self.assertEqual(result["scheduled"], 0)
        proxy_key = self.manager._get_proxy_key(proxy)
        self.client.pipeline.assert_called_once_with(transaction=False)
        pipeline = self.client.pipeline.return_value
        pipeline.delete.assert_called_once_with(proxy_key)
        pipeline.srem.assert_any_call("proxies:all", proxy_key)
        pipeline.zrem.assert_any_call("proxies:score", proxy_key)
        pipeline.zrem.assert_any_call(self.config.TEST_SCHEDULE_ZSET_KEY, proxy_key)
        pipeline.execute.assert_called_once_with()

    def test_get_random_available_proxy_should_fallback_to_pending(self):
        self.client.smembers.return_value = {"proxy:http:1.1.1.1:80"}
        self.client.hgetall.return_value = {
            "ip": "1.1.1.1",
            "port": "80",
            "protocol": "http",
            "success_count": "0",
            "fail_count": "0",
        }

        with patch.object(self.manager, "get_redis_client", return_value=self.client):
            result = self.manager.get_random_available_proxy(max_fail_count=5)

        self.assertIsNotNone(result)
        self.assertEqual(result.ip, "1.1.1.1")

    def test_add_proxy_should_schedule_new_proxy_first_check(self):
        proxy = Proxy(ip="192.168.1.10", port=8080, protocol="http")
        self.client.exists.return_value = False

        with patch.object(self.manager, "get_redis_client", return_value=self.client), patch(
            "src.database.redis_client.time.time", return_value=1700000000
        ):
            result = self.manager.add_proxy(proxy)

        self.assertTrue(result)
        proxy_key = self.manager._get_proxy_key(proxy)
        self.client.zadd.assert_any_call(
            self.config.TEST_SCHEDULE_ZSET_KEY,
            {proxy_key: 1700000000},
        )

    def test_add_proxy_should_not_reschedule_existing_proxy_by_default(self):
        proxy = Proxy(ip="192.168.1.11", port=8080, protocol="http")
        self.client.exists.return_value = True
        self.client.hgetall.return_value = {
            "score": "5",
            "grade": "C",
            "success_count": "1",
            "fail_count": "0",
            "response_time": "1.0",
            "last_check_time": "1700000000",
        }

        with patch.object(self.manager, "get_redis_client", return_value=self.client), patch(
            "src.database.redis_client.time.time", return_value=1700000000
        ):
            result = self.manager.add_proxy(proxy)

        self.assertTrue(result)
        schedule_calls = [
            call for call in self.client.zadd.call_args_list if call.args and call.args[0] == self.config.TEST_SCHEDULE_ZSET_KEY
        ]
        self.assertEqual(schedule_calls, [])


if __name__ == "__main__":
    unittest.main()
