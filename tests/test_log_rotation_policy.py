import glob
import logging
import os
import unittest
from types import SimpleNamespace

from src.logger import FIXED_LOG_FILE_NAME, USE_CONCURRENT_HANDLER, _clear_and_close_handlers, setup_logging


class TestLogRotationPolicy(unittest.TestCase):
    def setUp(self):
        self.log_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "logs",
        )
        os.makedirs(self.log_dir, exist_ok=True)
        for path in glob.glob(os.path.join(self.log_dir, f"{FIXED_LOG_FILE_NAME}*")):
            os.remove(path)

    def tearDown(self):
        _clear_and_close_handlers(logging.getLogger("RotationPolicyTest"))
        for path in glob.glob(os.path.join(self.log_dir, f"{FIXED_LOG_FILE_NAME}*")):
            os.remove(path)

    def test_log_should_rotate_and_keep_max_backup_count(self):
        cfg = SimpleNamespace(
            LOG_LEVEL="INFO",
            LOG_MAX_BYTES=256,
            LOG_BACKUP_COUNT=2,
            TIMEZONE="Asia/Shanghai",
            LOG_FILE="ignored.log",
        )
        logger = setup_logging(cfg, logger_name="RotationPolicyTest")

        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                handler.setLevel(logging.CRITICAL + 1)

        for _ in range(200):
            logger.info("X" * 300)

        _clear_and_close_handlers(logger)
        all_files = sorted(glob.glob(os.path.join(self.log_dir, f"{FIXED_LOG_FILE_NAME}*")))
        backup_files = [
            f for f in all_files
            if os.path.basename(f) != FIXED_LOG_FILE_NAME and not f.endswith(".lock")
        ]

        self.assertGreaterEqual(len(backup_files), 1)
        self.assertLessEqual(len(backup_files), 2)
        if USE_CONCURRENT_HANDLER:
            self.assertTrue(any(name.endswith(".gz") for name in backup_files))


if __name__ == "__main__":
    unittest.main()
