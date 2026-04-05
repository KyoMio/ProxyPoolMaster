import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts.migrate_test_schedule import migrate_test_schedule


class FakePipeline:
    def __init__(self, client):
        self.client = client
        self.commands = []

    def hgetall(self, key):
        self.commands.append(("hgetall", key))
        return self

    def zscore(self, key, member):
        self.commands.append(("zscore", key, member))
        return self

    def zadd(self, key, mapping):
        self.commands.append(("zadd", key, mapping))
        return self

    def zrem(self, key, member):
        self.commands.append(("zrem", key, member))
        return self

    def execute(self):
        results = []
        for command in self.commands:
            if command[0] == "hgetall":
                results.append(self.client.records.get(command[1], {}))
            elif command[0] == "zscore":
                results.append(self.client.schedule_scores.get(command[2]))
            elif command[0] == "zadd":
                results.append(True)
                self.client.scheduled.append((command[1], command[2]))
            elif command[0] == "zrem":
                results.append(True)
                self.client.scheduled.append(("zrem", command[1], command[2]))
            else:
                results.append(True)
        self.client.pipeline_calls.append(list(self.commands))
        self.commands = []
        return results


class FakeRedisClient:
    def __init__(self, proxy_keys, records, schedule_scores=None):
        self.proxy_keys = proxy_keys
        self.records = records
        self.schedule_scores = schedule_scores or {}
        self.scheduled = []
        self.hgetall_calls = []
        self.zscore_calls = []
        self.pipeline_calls = []

    def smembers(self, key):
        self.last_smembers_key = key
        return set(self.proxy_keys)

    def hgetall(self, key):
        self.hgetall_calls.append(key)
        return self.records.get(key, {})

    def zscore(self, key, member):
        self.zscore_calls.append((key, member))
        return self.schedule_scores.get(member)

    def zadd(self, key, mapping):
        self.scheduled.append((key, mapping))

    def zrem(self, key, member):
        self.scheduled.append(("zrem", key, member))

    def pipeline(self, transaction=False):
        return FakePipeline(self)


class FakeRedisManager:
    def __init__(self, client):
        self.client = client
        self.scheduled_calls = []
        self.deleted_keys = []

    def get_redis_client(self):
        return self.client

    def schedule_proxy_check(self, proxy_key, next_check_at):
        self.scheduled_calls.append((proxy_key, next_check_at))
        self.client.zadd("proxies:test_schedule", {proxy_key: next_check_at})
        return True

    def delete_proxy_by_key(self, proxy_key):
        self.deleted_keys.append(proxy_key)
        return True


class TestMigrateTestSchedule(unittest.TestCase):
    def setUp(self):
        self.config = SimpleNamespace(
            TEST_INTERVAL_SECONDS=300,
            TEST_SCHEDULE_ZSET_KEY="proxies:test_schedule",
            TEST_MIGRATION_BATCH_SIZE=500,
        )
        self.logger = Mock()

    def test_migrate_should_not_write_when_dry_run(self):
        proxy_key = "proxy:http:1.1.1.1:80"
        client = FakeRedisClient(
            [proxy_key],
            {
                proxy_key: {
                    "ip": "1.1.1.1",
                    "port": "80",
                    "protocol": "http",
                    "last_check_time": "1700000000",
                    "success_count": "1",
                    "fail_count": "0",
                    "grade": "B",
                    "score": "10",
                }
            },
            {proxy_key: None},
        )
        manager = FakeRedisManager(client)

        with patch("scripts.migrate_test_schedule.time.time", return_value=1700000300), patch(
            "scripts.migrate_test_schedule.ProxyScorer.calculate_test_interval_multiplier",
            return_value=1.0,
        ):
            summary = migrate_test_schedule(
                manager,
                self.config,
                dry_run=True,
                force=False,
                batch_size=1,
                now_ts=1700000300,
            )

        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["added"], 1)
        self.assertEqual(summary["rebuilt"], 0)
        self.assertEqual(summary["dirty"], 0)
        self.assertEqual(client.scheduled, [])

    def test_migrate_should_fill_missing_schedule_records(self):
        first_key = "proxy:http:1.1.1.1:80"
        second_key = "proxy:https:2.2.2.2:443"
        client = FakeRedisClient(
            [first_key, second_key],
            {
                first_key: {
                    "ip": "1.1.1.1",
                    "port": "80",
                    "protocol": "http",
                    "last_check_time": "1700000000",
                    "success_count": "1",
                    "fail_count": "0",
                    "grade": "B",
                    "score": "10",
                },
                second_key: {
                    "ip": "2.2.2.2",
                    "port": "443",
                    "protocol": "https",
                    "last_check_time": "1700000200",
                    "success_count": "1",
                    "fail_count": "0",
                    "grade": "A",
                    "score": "20",
                },
            },
            {first_key: None, second_key: 1700000500},
        )
        manager = FakeRedisManager(client)

        with patch("scripts.migrate_test_schedule.time.time", return_value=1700000300), patch(
            "scripts.migrate_test_schedule.ProxyScorer.calculate_test_interval_multiplier",
            side_effect=[1.0, 1.5],
        ):
            summary = migrate_test_schedule(
                manager,
                self.config,
                dry_run=False,
                force=False,
                batch_size=2,
                now_ts=1700000300,
            )

        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["existing"], 1)
        self.assertEqual(summary["added"], 1)
        self.assertEqual(summary["rebuilt"], 0)
        self.assertEqual(summary["dirty"], 0)
        self.assertEqual(len(client.scheduled), 1)
        self.assertEqual(client.scheduled[0][0], "proxies:test_schedule")
        self.assertIn(first_key, client.scheduled[0][1])

    def test_migrate_should_rebuild_existing_schedule_when_force_enabled(self):
        proxy_key = "proxy:http:3.3.3.3:8080"
        client = FakeRedisClient(
            [proxy_key],
            {
                proxy_key: {
                    "ip": "3.3.3.3",
                    "port": "8080",
                    "protocol": "http",
                    "last_check_time": "1700000100",
                    "success_count": "2",
                    "fail_count": "1",
                    "grade": "C",
                    "score": "30",
                }
            },
            {proxy_key: 1700000400},
        )
        manager = FakeRedisManager(client)

        with patch("scripts.migrate_test_schedule.time.time", return_value=1700000300), patch(
            "scripts.migrate_test_schedule.ProxyScorer.calculate_test_interval_multiplier",
            return_value=0.5,
        ):
            summary = migrate_test_schedule(
                manager,
                self.config,
                dry_run=False,
                force=True,
                batch_size=1,
                now_ts=1700000300,
            )

        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["existing"], 0)
        self.assertEqual(summary["added"], 0)
        self.assertEqual(summary["rebuilt"], 1)
        self.assertEqual(summary["dirty"], 0)
        self.assertEqual(len(client.scheduled), 1)
        self.assertEqual(client.scheduled[0][0], "proxies:test_schedule")
        self.assertIn(proxy_key, client.scheduled[0][1])

    def test_migrate_should_count_missing_and_corrupt_records_as_dirty(self):
        missing_key = "proxy:http:missing:80"
        corrupt_key = "proxy:http:bad:80"
        valid_key = "proxy:http:4.4.4.4:80"
        client = FakeRedisClient(
            [missing_key, corrupt_key, valid_key],
            {
                corrupt_key: {
                    "port": "not-a-number",
                    "protocol": "http",
                },
                valid_key: {
                    "ip": "4.4.4.4",
                    "port": "80",
                    "protocol": "http",
                    "last_check_time": "1700000000",
                    "success_count": "1",
                    "fail_count": "0",
                    "grade": "B",
                    "score": "10",
                },
            },
            {valid_key: None},
        )
        manager = FakeRedisManager(client)

        with patch("scripts.migrate_test_schedule.time.time", return_value=1700000300), patch(
            "scripts.migrate_test_schedule.ProxyScorer.calculate_test_interval_multiplier",
            return_value=1.0,
        ):
            summary = migrate_test_schedule(
                manager,
                self.config,
                dry_run=False,
                force=False,
                batch_size=3,
                now_ts=1700000300,
            )

        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["added"], 1)
        self.assertEqual(summary["dirty"], 2)
        self.assertEqual(summary["existing"], 0)
        self.assertEqual(summary["rebuilt"], 0)

    def test_migrate_should_remove_dirty_schedule_entries_when_not_dry_run(self):
        missing_key = "proxy:http:missing:80"
        corrupt_key = "proxy:http:bad:80"
        valid_key = "proxy:http:4.4.4.4:80"
        client = FakeRedisClient(
            [missing_key, corrupt_key, valid_key],
            {
                corrupt_key: {
                    "port": "not-a-number",
                    "protocol": "http",
                },
                valid_key: {
                    "ip": "4.4.4.4",
                    "port": "80",
                    "protocol": "http",
                    "last_check_time": "1700000000",
                    "success_count": "1",
                    "fail_count": "0",
                    "grade": "B",
                    "score": "10",
                },
            },
            {
                missing_key: 1700000400,
                corrupt_key: 1700000500,
                valid_key: None,
            },
        )
        manager = FakeRedisManager(client)

        with patch("scripts.migrate_test_schedule.time.time", return_value=1700000300), patch(
            "scripts.migrate_test_schedule.ProxyScorer.calculate_test_interval_multiplier",
            return_value=1.0,
        ):
            summary = migrate_test_schedule(
                manager,
                self.config,
                dry_run=False,
                force=False,
                batch_size=3,
                now_ts=1700000300,
            )

        self.assertEqual(summary["dirty"], 2)
        self.assertEqual(summary["added"], 1)
        self.assertCountEqual(manager.deleted_keys, [missing_key, corrupt_key])

    def test_migrate_should_use_custom_schedule_key_and_batch_pipeline(self):
        custom_config = SimpleNamespace(
            TEST_INTERVAL_SECONDS=300,
            TEST_SCHEDULE_ZSET_KEY="custom:test_schedule",
            TEST_MIGRATION_BATCH_SIZE=2,
        )
        first_key = "proxy:http:1.1.1.1:80"
        second_key = "proxy:https:2.2.2.2:443"
        client = FakeRedisClient(
            [first_key, second_key],
            {
                first_key: {
                    "ip": "1.1.1.1",
                    "port": "80",
                    "protocol": "http",
                    "last_check_time": "1700000000",
                    "success_count": "1",
                    "fail_count": "0",
                    "grade": "B",
                    "score": "10",
                },
                second_key: {
                    "ip": "2.2.2.2",
                    "port": "443",
                    "protocol": "https",
                    "last_check_time": "1700000200",
                    "success_count": "1",
                    "fail_count": "0",
                    "grade": "A",
                    "score": "20",
                },
            },
            {first_key: None, second_key: None},
        )
        manager = FakeRedisManager(client)

        with patch("scripts.migrate_test_schedule.time.time", return_value=1700000300), patch(
            "scripts.migrate_test_schedule.ProxyScorer.calculate_test_interval_multiplier",
            side_effect=[1.0, 1.5],
        ):
            summary = migrate_test_schedule(
                manager,
                custom_config,
                dry_run=False,
                force=False,
                batch_size=2,
                now_ts=1700000300,
            )

        self.assertEqual(summary["total"], 2)
        self.assertEqual(len(client.pipeline_calls), 2)
        self.assertTrue(
            any(
                command[0] == "zadd" and command[1] == "custom:test_schedule"
                for command in client.pipeline_calls[1]
            )
        )


if __name__ == "__main__":
    unittest.main()
