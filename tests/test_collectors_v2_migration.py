import unittest

from src.collectors_v2.migration import auto_migrate_collectors_to_v2, migrate_collectors_to_v2


class _FakeRepo:
    def __init__(self, existing_ids=None):
        self.existing_ids = set(existing_ids or [])
        self.saved = []

    def get_definition(self, collector_id):
        if collector_id in self.existing_ids:
            return {"id": collector_id}
        return None

    def upsert_definition(self, definition):
        self.saved.append(definition)
        self.existing_ids.add(definition["id"])
        return definition


class _FakeConfig:
    def __init__(self, collectors, default_interval=300, v2_enabled=1, migration_auto=1):
        self.COLLECTORS = collectors
        self.COLLECT_INTERVAL_SECONDS = default_interval
        self.COLLECTOR_V2_ENABLED = v2_enabled
        self.COLLECTOR_V2_MIGRATION_AUTO = migration_auto


class _FakeLogger:
    def __init__(self):
        self.infos = []
        self.warnings = []
        self.errors = []

    def info(self, msg, *args, **kwargs):
        self.infos.append(str(msg))

    def warning(self, msg, *args, **kwargs):
        self.warnings.append(str(msg))

    def error(self, msg, *args, **kwargs):
        self.errors.append(str(msg))


class TestCollectorsV2Migration(unittest.TestCase):
    def test_migrate_should_convert_legacy_collectors_to_v2_definitions(self):
        config = _FakeConfig([
            {
                "id": "legacy_api",
                "name": "Legacy API",
                "type": "api",
                "enabled": True,
                "interval": 120,
                "params": {"request": {"url": "https://example.com"}},
                "env_vars": {
                    "TOKEN": {"value": "abc", "is_secret": True}
                },
            },
            {
                "id": "legacy_code",
                "name": "Legacy Code",
                "type": "code",
                "source": "scrape",
                "enabled": False,
                "interval_seconds": 45,
                "module_path": "collectors.custom_demo",
                "class_name": "CustomDemoCollector",
                "env_vars": {},
            },
        ])
        repo = _FakeRepo()

        report = migrate_collectors_to_v2(
            config_instance=config,
            repository=repo,
            logger_instance=_FakeLogger(),
        )

        self.assertEqual(report["total"], 2)
        self.assertEqual(report["migrated"], 2)
        self.assertEqual(report["skipped"], 0)
        self.assertEqual(report["failed"], 0)

        first = repo.saved[0]
        self.assertEqual(first["id"], "legacy_api")
        self.assertEqual(first["mode"], "simple")
        self.assertEqual(first["source"], "api")
        self.assertEqual(first["lifecycle"], "published")
        self.assertEqual(first["interval_seconds"], 120)
        self.assertEqual(first["spec"], {"request": {"url": "https://example.com"}})
        self.assertIsNone(first["code_ref"])

        second = repo.saved[1]
        self.assertEqual(second["id"], "legacy_code")
        self.assertEqual(second["mode"], "code")
        self.assertEqual(second["source"], "scrape")
        self.assertEqual(second["lifecycle"], "paused")
        self.assertEqual(second["interval_seconds"], 45)
        self.assertEqual(second["code_ref"]["module_path"], "collectors.custom_demo")
        self.assertEqual(second["code_ref"]["class_name"], "CustomDemoCollector")

    def test_migrate_should_skip_existing_collectors_by_default(self):
        config = _FakeConfig([
            {
                "id": "already_migrated",
                "name": "Already Migrated",
                "type": "api",
                "enabled": True,
            }
        ])
        repo = _FakeRepo(existing_ids={"already_migrated"})

        report = migrate_collectors_to_v2(
            config_instance=config,
            repository=repo,
            logger_instance=_FakeLogger(),
        )

        self.assertEqual(report["total"], 1)
        self.assertEqual(report["migrated"], 0)
        self.assertEqual(report["skipped"], 1)
        self.assertEqual(report["failed"], 0)
        self.assertEqual(len(repo.saved), 0)

    def test_auto_migrate_should_be_noop_when_flags_disabled(self):
        config = _FakeConfig(
            collectors=[{"id": "legacy_api", "name": "Legacy API"}],
            v2_enabled=0,
            migration_auto=1,
        )
        repo = _FakeRepo()
        logger = _FakeLogger()

        report = auto_migrate_collectors_to_v2(
            config_instance=config,
            repository=repo,
            logger_instance=logger,
        )

        self.assertFalse(report["executed"])
        self.assertEqual(report["migrated"], 0)
        self.assertEqual(len(repo.saved), 0)

    def test_auto_migrate_should_run_when_flags_enabled(self):
        config = _FakeConfig(
            collectors=[{"id": "legacy_api", "name": "Legacy API"}],
            v2_enabled=1,
            migration_auto=1,
        )
        repo = _FakeRepo()
        logger = _FakeLogger()

        report = auto_migrate_collectors_to_v2(
            config_instance=config,
            repository=repo,
            logger_instance=logger,
        )

        self.assertTrue(report["executed"])
        self.assertEqual(report["migrated"], 1)
        self.assertEqual(len(repo.saved), 1)


if __name__ == "__main__":
    unittest.main()
