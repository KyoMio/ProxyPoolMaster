import logging
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.config import Config
from src.logger import FIXED_LOG_FILE_NAME, _clear_and_close_handlers, setup_logging


class TestBaseComponents(unittest.TestCase):
    def tearDown(self):
        for logger_name in ["TestBaseLogger", "TestBaseLoggerDebug"]:
            _clear_and_close_handlers(logging.getLogger(logger_name))

    def test_config_env_vars(self):
        with patch.dict(
            os.environ,
            {
                "REDIS_HOST": "test_redis_host",
                "REDIS_PORT": "6380",
                "LOG_LEVEL": "DEBUG",
                "API_TOKEN": "test_api_token",
            },
            clear=False,
        ):
            cfg = Config()
            self.assertEqual(cfg.REDIS_HOST, "test_redis_host")
            self.assertEqual(cfg.REDIS_PORT, 6380)
            self.assertEqual(cfg.LOG_LEVEL, "DEBUG")
            self.assertEqual(cfg.API_TOKEN, "test_api_token")

    def test_config_to_dict(self):
        cfg = Config()
        cfg_dict = cfg.to_dict()
        self.assertIsInstance(cfg_dict, dict)
        self.assertIn("REDIS_HOST", cfg_dict)
        self.assertEqual(cfg_dict["REDIS_HOST"], cfg.REDIS_HOST)
        self.assertNotIn("_file_config_cache", cfg_dict)

    def test_config_should_default_api_token_to_empty_when_unset(self):
        with patch.object(Config, "_load_from_file", return_value={}), patch.dict(os.environ, {}, clear=True):
            cfg = Config()

        self.assertEqual(cfg.API_TOKEN, "")

    def test_logger_setup_should_write_to_fixed_log_file(self):
        cfg = SimpleNamespace(
            LOG_LEVEL="INFO",
            LOG_MAX_BYTES=1024 * 1024,
            LOG_BACKUP_COUNT=2,
            TIMEZONE="Asia/Shanghai",
            LOG_FILE="ignored.log",
        )
        test_logger = setup_logging(cfg=cfg, logger_name="TestBaseLogger")
        test_logger.info("This is a test log message.")

        file_handlers = [h for h in test_logger.handlers if isinstance(h, logging.FileHandler)]
        self.assertTrue(file_handlers)
        self.assertTrue(all(h.baseFilename.endswith(FIXED_LOG_FILE_NAME) for h in file_handlers))

    def test_logger_level_change(self):
        cfg = SimpleNamespace(
            LOG_LEVEL="DEBUG",
            LOG_MAX_BYTES=1024 * 1024,
            LOG_BACKUP_COUNT=2,
            TIMEZONE="Asia/Shanghai",
        )
        debug_logger = setup_logging(cfg=cfg, logger_name="TestBaseLoggerDebug")
        self.assertEqual(debug_logger.level, logging.DEBUG)


if __name__ == "__main__":
    unittest.main()
