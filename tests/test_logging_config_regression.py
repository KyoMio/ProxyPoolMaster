import logging
import os
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from src.config import Config
from src.database.redis_client import RedisManager
from src.logger import _clear_and_close_handlers, setup_logging


class TestLoggingConfigRegression(unittest.TestCase):
    def tearDown(self):
        _clear_and_close_handlers(logging.getLogger("ProxyPoolMaster"))

    def test_config_init_should_not_override_existing_logger_level(self):
        with patch.dict(os.environ, {"LOG_LEVEL": "ERROR"}, clear=False):
            cfg = Config()
            setup_logging(cfg, logger_name="ProxyPoolMaster")
            self.assertEqual(logging.getLogger("ProxyPoolMaster").level, logging.ERROR)
            _ = Config()
            self.assertEqual(logging.getLogger("ProxyPoolMaster").level, logging.ERROR)

    def test_tester_log_each_proxy_should_default_false(self):
        with patch.object(Config, "_load_from_file", return_value={}):
            cfg = Config()
            self.assertIn("TESTER_LOG_EACH_PROXY", cfg.to_dict())
            self.assertFalse(cfg.TESTER_LOG_EACH_PROXY)

    def test_tester_schedule_config_should_have_defaults_and_env_overrides(self):
        with patch.object(Config, "_load_from_file", return_value={}):
            cfg = Config()

        self.assertIn("TEST_BATCH_SIZE", cfg.to_dict())
        self.assertIn("TEST_IDLE_SLEEP_SECONDS", cfg.to_dict())
        self.assertIn("TEST_SCHEDULE_ZSET_KEY", cfg.to_dict())
        self.assertIn("TEST_MIGRATION_BATCH_SIZE", cfg.to_dict())

        self.assertEqual(cfg.TEST_BATCH_SIZE, 200)
        self.assertEqual(cfg.TEST_IDLE_SLEEP_SECONDS, 2)
        self.assertEqual(cfg.TEST_SCHEDULE_ZSET_KEY, "proxies:test_schedule")
        self.assertEqual(cfg.TEST_MIGRATION_BATCH_SIZE, 500)

        with patch.object(Config, "_load_from_file", return_value={}), patch.dict(
            os.environ,
            {
                "TEST_BATCH_SIZE": "321",
                "TEST_IDLE_SLEEP_SECONDS": "11",
                "TEST_SCHEDULE_ZSET_KEY": "custom:schedule",
                "TEST_MIGRATION_BATCH_SIZE": "777",
            },
            clear=False,
        ):
            cfg = Config()

        self.assertEqual(cfg.TEST_BATCH_SIZE, 321)
        self.assertEqual(cfg.TEST_IDLE_SLEEP_SECONDS, 11)
        self.assertEqual(cfg.TEST_SCHEDULE_ZSET_KEY, "custom:schedule")
        self.assertEqual(cfg.TEST_MIGRATION_BATCH_SIZE, 777)

    def test_setup_logging_should_reject_invalid_cfg_type(self):
        with self.assertRaises(TypeError):
            setup_logging("config")

    def test_log_file_should_not_be_configurable_via_env(self):
        with patch.dict(os.environ, {"LOG_FILE": "custom.log"}, clear=False):
            cfg = Config()
        self.assertNotIn("LOG_FILE", cfg.to_dict())

    def test_available_min_score_should_not_be_configurable(self):
        with patch.dict(os.environ, {"AVAILABLE_MIN_SCORE": "99"}, clear=False):
            cfg = Config()
        self.assertNotIn("AVAILABLE_MIN_SCORE", cfg.to_dict())

    def test_setup_logging_should_always_write_to_fixed_app_log(self):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        log_dir = os.path.join(project_root, "logs")
        fixed_log_path = os.path.join(log_dir, "app.log")
        custom_log_path = os.path.join(log_dir, "custom.log")

        os.makedirs(log_dir, exist_ok=True)
        for path in (fixed_log_path, custom_log_path):
            if os.path.exists(path):
                os.remove(path)

        cfg = SimpleNamespace(
            LOG_LEVEL="INFO",
            LOG_FILE="custom.log",
            LOG_MAX_BYTES=1024 * 1024,
            LOG_BACKUP_COUNT=1,
            TIMEZONE="Asia/Shanghai",
        )
        logger = setup_logging(cfg, logger_name="FixedLogFilePolicy")
        logger.info("fixed-log-path-check")
        _clear_and_close_handlers(logger)

        self.assertTrue(os.path.exists(fixed_log_path))
        self.assertFalse(os.path.exists(custom_log_path))

    def test_runtime_apply_should_refresh_logger_level(self):
        from src import app_globals
        from src.api.config_endpoints import apply_runtime_config

        original_config = app_globals.global_config
        original_logger = app_globals.global_logger
        original_redis_manager = app_globals.global_redis_manager
        original_collector_manager = app_globals.global_collector_manager
        original_tester_manager = app_globals.global_tester_manager

        cfg = SimpleNamespace(
            LOG_LEVEL="INFO",
            LOG_MAX_BYTES=1024 * 1024,
            LOG_BACKUP_COUNT=1,
            TIMEZONE="Asia/Shanghai",
            REDIS_HOST="localhost",
            REDIS_PORT=6379,
            REDIS_DB=0,
            REDIS_PASSWORD="",
        )
        logger = setup_logging(cfg, logger_name="RuntimeApplyLogger")

        try:
            app_globals.global_config = cfg
            app_globals.global_logger = logger
            app_globals.global_redis_manager = RedisManager(cfg, logger)
            app_globals.global_collector_manager = None
            app_globals.global_tester_manager = None

            cfg.LOG_LEVEL = "ERROR"
            result = apply_runtime_config(["LOG_LEVEL"])

            self.assertIn("LOG_LEVEL", result["applied_keys"])
            self.assertEqual(app_globals.global_logger.level, logging.ERROR)
        finally:
            _clear_and_close_handlers(logging.getLogger("RuntimeApplyLogger"))
            if hasattr(app_globals.global_redis_manager, "close_connection_pool"):
                app_globals.global_redis_manager.close_connection_pool()
            app_globals.global_config = original_config
            app_globals.global_logger = original_logger
            app_globals.global_redis_manager = original_redis_manager
            app_globals.global_collector_manager = original_collector_manager
            app_globals.global_tester_manager = original_tester_manager

    def test_runtime_apply_should_rebuild_redis_manager(self):
        from src import app_globals
        from src.api.config_endpoints import apply_runtime_config

        original_config = app_globals.global_config
        original_logger = app_globals.global_logger
        original_redis_manager = app_globals.global_redis_manager
        original_collector_manager = app_globals.global_collector_manager
        original_tester_manager = app_globals.global_tester_manager

        cfg = SimpleNamespace(
            LOG_LEVEL="INFO",
            LOG_MAX_BYTES=1024 * 1024,
            LOG_BACKUP_COUNT=1,
            TIMEZONE="Asia/Shanghai",
            REDIS_HOST="localhost",
            REDIS_PORT=6379,
            REDIS_DB=0,
            REDIS_PASSWORD="",
        )
        logger = setup_logging(cfg, logger_name="RuntimeApplyRedis")
        old_redis_manager = RedisManager(cfg, logger)

        try:
            app_globals.global_config = cfg
            app_globals.global_logger = logger
            app_globals.global_redis_manager = old_redis_manager
            app_globals.global_collector_manager = None
            app_globals.global_tester_manager = None

            cfg.REDIS_PORT = 6380
            result = apply_runtime_config(["REDIS_PORT"])

            self.assertIn("REDIS_PORT", result["applied_keys"])
            self.assertIsNot(app_globals.global_redis_manager, old_redis_manager)
        finally:
            _clear_and_close_handlers(logging.getLogger("RuntimeApplyRedis"))
            if hasattr(app_globals.global_redis_manager, "close_connection_pool"):
                app_globals.global_redis_manager.close_connection_pool()
            app_globals.global_config = original_config
            app_globals.global_logger = original_logger
            app_globals.global_redis_manager = original_redis_manager
            app_globals.global_collector_manager = original_collector_manager
            app_globals.global_tester_manager = original_tester_manager

    def test_dead_config_keys_should_not_exist_in_templates_and_docs(self):
        project_root = Path(__file__).resolve().parent.parent
        dead_keys = ["LOG_FILE", "AVAILABLE_MIN_SCORE", "FREE_PROXY_LIST_COLLECT_INTERVAL"]
        target_files = [
            project_root / "docker-compose.yml",
            project_root / "env.example",
            project_root / "README.md",
        ]

        for target_file in target_files:
            content = target_file.read_text(encoding="utf-8")
            for dead_key in dead_keys:
                self.assertNotIn(dead_key, content, f"{dead_key} should be removed from {target_file.name}")

        config_json = project_root / "config.json"
        if config_json.exists():
            content = config_json.read_text(encoding="utf-8")
            for dead_key in dead_keys:
                self.assertNotIn(dead_key, content, f"{dead_key} should be removed from config.json")
