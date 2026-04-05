import unittest
from pathlib import Path
import re
import os
from unittest.mock import patch

from src.config import Config


class TestEnvAlignment(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(__file__).resolve().parent.parent
        self.env_file = self.project_root / ".env"
        self.env_example_file = self.project_root / "env.example"

    @staticmethod
    def _parse_keys(content: str) -> set[str]:
        pattern = re.compile(r"^\s*#?\s*([A-Z][A-Z0-9_]*)\s*=", re.MULTILINE)
        return set(pattern.findall(content))

    def test_env_and_env_example_should_include_supported_keys(self):
        expected_keys = {
            "API_TOKEN",
            "ZDAYE_APP_ID",
            "ZDAYE_AKEY",
            "REDIS_HOST",
            "REDIS_PORT",
            "REDIS_DB",
            "REDIS_PASSWORD",
            "LOG_LEVEL",
            "LOG_MAX_BYTES",
            "LOG_BACKUP_COUNT",
            "TIMEZONE",
            "REQUEST_TIMEOUT",
            "COLLECT_INTERVAL_SECONDS",
            "ZDAYE_COLLECT_INTERVAL",
            "ZDAYE_OVERSEAS_COLLECT_INTERVAL",
            "COLLECTORS",
            "TEST_INTERVAL_SECONDS",
            "MAX_FAIL_COUNT",
            "TESTER_LOG_EACH_PROXY",
            "TEST_MAX_CONCURRENT",
            "TEST_TIMEOUT_PER_TARGET",
            "TEST_BATCH_SIZE",
            "TEST_IDLE_SLEEP_SECONDS",
            "TEST_SCHEDULE_ZSET_KEY",
            "TEST_MIGRATION_BATCH_SIZE",
            "RATE_LIMIT_PROXY_MINUTE",
            "RATE_LIMIT_HEALTH_MINUTE",
            "API_HOST",
            "API_PORT",
            "DASHBOARD_WS_BROADCAST_INTERVAL_SECONDS",
            "SYSTEM_WS_BROADCAST_INTERVAL_SECONDS",
            "DISABLE_API_TESTER",
            "COLLECTOR_RUNTIME_MODE",
            "COLLECTOR_WORKER_ENABLED",
            "COLLECTOR_WORKER_ID",
            "COLLECTOR_WORKER_TICK_SECONDS",
            "COLLECTOR_WORKER_MAX_CONCURRENT",
            "COLLECTOR_EXEC_TIMEOUT",
            "COLLECTOR_EXEC_MAX_MEMORY_MB",
            "COLLECTOR_EXEC_STDOUT_LIMIT_KB",
            "COLLECTOR_RUN_HISTORY_LIMIT",
            "APP_RELEASE_VERSION",
            "APP_GIT_SHA",
            "APP_IMAGE_TAG",
        }

        env_example_keys = self._parse_keys(self.env_example_file.read_text(encoding="utf-8"))

        if self.env_file.exists():
            env_keys = self._parse_keys(self.env_file.read_text(encoding="utf-8"))
            allowed_local_keys = expected_keys | {
                "APP_COLLECTOR_WORKER_ENABLED",
                "COLLECTOR_V2_ENABLED",
                "COLLECTOR_V2_UI_ENABLED",
                "COLLECTOR_V2_MIGRATION_AUTO",
                "DISABLE_API_COLLECTOR",
            }
            self.assertTrue(
                env_keys <= allowed_local_keys,
                f".env 存在未识别键: {sorted(env_keys - allowed_local_keys)}"
            )
        self.assertTrue(
            expected_keys.issubset(env_example_keys),
            f"env.example 缺失键: {sorted(expected_keys - env_example_keys)}"
        )

    def test_dead_keys_should_not_exist(self):
        dead_keys = {
            "LOG_FILE",
            "AVAILABLE_MIN_SCORE",
            "FREE_PROXY_LIST_COLLECT_INTERVAL",
            "APP_COLLECTOR_WORKER_ENABLED",
            "COLLECTOR_V2_COMPAT_MODE",
            "COLLECTOR_V2_LEGACY_ROUTE_MOUNT",
            "DISABLE_API_COLLECTOR",
        }

        env_example_content = self.env_example_file.read_text(encoding="utf-8")
        for key in dead_keys:
            self.assertNotIn(key, env_example_content)

    def test_tester_schedule_config_keys_should_exist_in_config(self):
        with patch.object(Config, "_load_from_file", return_value={}):
            cfg = Config()

        expected_defaults = {
            "TEST_BATCH_SIZE": 200,
            "TEST_IDLE_SLEEP_SECONDS": 2,
            "TEST_SCHEDULE_ZSET_KEY": "proxies:test_schedule",
            "TEST_MIGRATION_BATCH_SIZE": 500,
        }

        for key, expected_value in expected_defaults.items():
            self.assertIn(key, cfg.to_dict())
            self.assertEqual(getattr(cfg, key), expected_value)

    def test_tester_schedule_config_keys_should_be_overridable_from_env(self):
        env_patch = {
            "TEST_BATCH_SIZE": "123",
            "TEST_IDLE_SLEEP_SECONDS": "7",
            "TEST_SCHEDULE_ZSET_KEY": "custom:test_schedule",
            "TEST_MIGRATION_BATCH_SIZE": "999",
        }

        with patch.object(Config, "_load_from_file", return_value={}), patch.dict(os.environ, env_patch, clear=False):
            cfg = Config()

        self.assertEqual(cfg.TEST_BATCH_SIZE, 123)
        self.assertEqual(cfg.TEST_IDLE_SLEEP_SECONDS, 7)
        self.assertEqual(cfg.TEST_SCHEDULE_ZSET_KEY, "custom:test_schedule")
        self.assertEqual(cfg.TEST_MIGRATION_BATCH_SIZE, 999)

    def test_docker_compose_should_propagate_timezone_and_use_dedicated_worker(self):
        compose_file = self.project_root / "docker-compose.yml"
        compose_content = compose_file.read_text(encoding="utf-8")

        self.assertIn("collector-worker:", compose_content)
        self.assertIn("TZ: ${TIMEZONE:-Asia/Shanghai}", compose_content)
        self.assertNotIn("APP_COLLECTOR_WORKER_ENABLED", compose_content)

    def test_runtime_config_template_should_exist(self):
        config_default_file = self.project_root / "config.default.json"
        self.assertTrue(config_default_file.exists(), "config.default.json should exist")

    def test_gitignore_should_exclude_runtime_state_files(self):
        gitignore_content = (self.project_root / ".gitignore").read_text(encoding="utf-8")

        self.assertIn("config.json", gitignore_content)
        self.assertIn(".omx/", gitignore_content)

    def test_docker_should_use_runtime_config_directory_and_default_template(self):
        dockerfile_content = (self.project_root / "Dockerfile").read_text(encoding="utf-8")
        compose_content = (self.project_root / "docker-compose.yml").read_text(encoding="utf-8")
        compose_dev_content = (self.project_root / "docker-compose.dev.yml").read_text(encoding="utf-8")

        self.assertIn("COPY config.default.json ./config.default.json", dockerfile_content)
        self.assertNotIn("COPY config.json ./config.json", dockerfile_content)

        self.assertIn("./data/config:/app/data/config", compose_content)
        self.assertIn("CONFIG_FILE: /app/data/config/config.json", compose_content)
        self.assertNotIn("./config.json:/app/config.json", compose_content)

        self.assertIn("./data/config:/app/data/config", compose_dev_content)
        self.assertIn("CONFIG_FILE: /app/data/config/config.json", compose_dev_content)
        self.assertNotIn("./config.json:/app/config.json", compose_dev_content)

    def test_github_workflow_should_inject_runtime_build_metadata(self):
        workflow_content = (
            self.project_root / ".github" / "workflows" / "docker-image.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("APP_RELEASE_VERSION", workflow_content)
        self.assertIn("APP_GIT_SHA", workflow_content)
        self.assertIn("APP_IMAGE_TAG", workflow_content)
        self.assertIn("ghcr.io/${GITHUB_REPOSITORY,,}", workflow_content)


if __name__ == "__main__":
    unittest.main()
