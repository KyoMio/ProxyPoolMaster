import json
import os
import tempfile
import unittest
from unittest.mock import patch

from src.config import Config


class TestConfigFilePath(unittest.TestCase):
    def test_config_should_load_from_config_file_env_override(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, "custom-config.json")
            with open(config_path, "w", encoding="utf-8") as file_handle:
                json.dump(
                    {
                        "RATE_LIMIT_PROXY_MINUTE": "88/minute",
                        "TEST_BATCH_SIZE": 321,
                    },
                    file_handle,
                )

            with patch.dict(os.environ, {"CONFIG_FILE": config_path}, clear=False):
                cfg = Config()

            self.assertEqual(cfg.RATE_LIMIT_PROXY_MINUTE, "88/minute")
            self.assertEqual(cfg.TEST_BATCH_SIZE, 321)


if __name__ == "__main__":
    unittest.main()
