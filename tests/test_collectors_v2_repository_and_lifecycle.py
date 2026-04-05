import unittest

from src.collectors_v2.repository import CollectorV2Repository
from src.collectors_v2.service import apply_lifecycle_action


class _FakeRedisClient:
    def __init__(self):
        self.kv = {}
        self.sets = {}
        self.lists = {}

    def set(self, key, value):
        self.kv[key] = value

    def get(self, key):
        return self.kv.get(key)

    def delete(self, key):
        self.kv.pop(key, None)
        self.lists.pop(key, None)

    def sadd(self, key, value):
        self.sets.setdefault(key, set()).add(value)

    def srem(self, key, value):
        self.sets.setdefault(key, set()).discard(value)

    def smembers(self, key):
        return self.sets.get(key, set())

    def lpush(self, key, value):
        self.lists.setdefault(key, [])
        self.lists[key].insert(0, value)

    def ltrim(self, key, start, end):
        data = self.lists.get(key, [])
        self.lists[key] = data[start:end + 1] if end >= 0 else data[start:]

    def lrange(self, key, start, end):
        data = self.lists.get(key, [])
        if end < 0:
            return data[start:]
        return data[start:end + 1]

    def setex(self, key, _ttl, value):
        self.kv[key] = value


class _FakeRedisManager:
    def __init__(self):
        self.client = _FakeRedisClient()

    def get_redis_client(self):
        return self.client


class TestCollectorsV2RepositoryAndLifecycle(unittest.TestCase):
    def test_definition_crud_and_run_history(self):
        repo = CollectorV2Repository(_FakeRedisManager())

        definition = {
            "id": "demo_collector",
            "name": "Demo",
            "mode": "simple",
            "source": "api",
            "enabled": True,
            "lifecycle": "draft",
            "interval_seconds": 300,
            "spec": {},
            "env_vars": {},
            "meta": {"version": 1},
        }

        repo.upsert_definition(definition)
        self.assertEqual(repo.get_definition("demo_collector")["name"], "Demo")
        self.assertEqual(len(repo.list_definitions()), 1)

        for idx in range(5):
            repo.append_run_record(
                "demo_collector",
                {
                    "run_id": f"run-{idx}",
                    "collector_id": "demo_collector",
                    "trigger": "test",
                    "status": "success",
                },
                history_limit=3,
            )

        runs = repo.get_runs("demo_collector", limit=10)
        self.assertEqual(len(runs), 3)
        self.assertEqual(runs[0]["run_id"], "run-4")

        repo.delete_definition("demo_collector")
        self.assertIsNone(repo.get_definition("demo_collector"))

    def test_apply_lifecycle_action_should_follow_state_machine(self):
        self.assertEqual(apply_lifecycle_action("draft", "publish"), "published")
        self.assertEqual(apply_lifecycle_action("published", "pause"), "paused")
        self.assertEqual(apply_lifecycle_action("paused", "resume"), "published")

        with self.assertRaises(ValueError):
            apply_lifecycle_action("draft", "resume")


if __name__ == "__main__":
    unittest.main()
