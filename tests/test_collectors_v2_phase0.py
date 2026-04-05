import unittest
from unittest.mock import patch

import os

from src.config import Config


class TestCollectorsV2Phase0(unittest.TestCase):
    def test_collectors_v2_models_should_be_importable(self):
        from src.collectors_v2.models import (
            CollectorDefinition,
            CollectorRunRecord,
            WorkerHeartbeat,
        )

        self.assertIsNotNone(CollectorDefinition)
        self.assertIsNotNone(CollectorRunRecord)
        self.assertIsNotNone(WorkerHeartbeat)

    def test_config_should_expose_collector_v2_feature_flags(self):
        with patch.object(Config, "_load_from_file", return_value={}):
            cfg = Config()
        cfg_dict = cfg.to_dict()

        self.assertEqual(cfg.COLLECTOR_RUNTIME_MODE, "v2")
        self.assertEqual(cfg.COLLECTOR_V2_ENABLED, 1)
        self.assertEqual(cfg.COLLECTOR_V2_UI_ENABLED, 1)
        self.assertEqual(cfg.COLLECTOR_V2_MIGRATION_AUTO, 1)
        self.assertNotIn("COLLECTOR_V2_COMPAT_MODE", cfg_dict)
        self.assertNotIn("COLLECTOR_V2_LEGACY_ROUTE_MOUNT", cfg_dict)

    def test_runtime_mode_v2_should_enable_v2_related_flags(self):
        with patch.dict(os.environ, {"COLLECTOR_RUNTIME_MODE": "v2"}, clear=False):
            with patch.object(Config, "_load_from_file", return_value={}):
                cfg = Config()

        self.assertEqual(cfg.COLLECTOR_RUNTIME_MODE, "v2")
        self.assertEqual(cfg.COLLECTOR_V2_ENABLED, 1)
        self.assertEqual(cfg.COLLECTOR_V2_UI_ENABLED, 1)
        self.assertEqual(cfg.COLLECTOR_V2_MIGRATION_AUTO, 1)

    def test_runtime_mode_legacy_should_disable_v2_related_flags(self):
        with patch.dict(
            os.environ,
            {
                "COLLECTOR_RUNTIME_MODE": "legacy",
                "COLLECTOR_V2_ENABLED": "1",
                "COLLECTOR_V2_UI_ENABLED": "1",
                "COLLECTOR_V2_MIGRATION_AUTO": "1",
            },
            clear=False,
        ):
            with patch.object(Config, "_load_from_file", return_value={}):
                cfg = Config()

        self.assertEqual(cfg.COLLECTOR_RUNTIME_MODE, "legacy")
        self.assertEqual(cfg.COLLECTOR_V2_ENABLED, 0)
        self.assertEqual(cfg.COLLECTOR_V2_UI_ENABLED, 0)
        self.assertEqual(cfg.COLLECTOR_V2_MIGRATION_AUTO, 0)


if __name__ == "__main__":
    unittest.main()
