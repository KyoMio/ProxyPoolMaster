import unittest
from unittest.mock import patch

from src.middleware import metrics as metrics_module


class TestRecordMetricsSnapshotConnections(unittest.TestCase):
    def setUp(self):
        metrics_module.reset_metrics()
        for history in metrics_module._metrics_history.values():
            history.clear()
        metrics_module._last_snapshot_time = 0

    def test_record_snapshot_uses_merged_concurrent_connections(self):
        api_metrics = {
            "avg_response_time_ms": 12.5,
            "qps": 2.1,
            "error_rate": 0.01,
            "concurrent_connections": 3,
        }

        with patch("src.middleware.metrics.time.time", return_value=1000):
            metrics_module.record_metrics_snapshot(api_metrics=api_metrics)

        history = list(metrics_module._metrics_history["concurrent_connections"])
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0][1], 3)

    def test_get_metrics_history_should_convert_ratio_metrics_to_percent_values(self):
        with patch("src.middleware.metrics.time.time", return_value=1000):
            metrics_module.record_metrics_snapshot(
                collector_stats={
                    "collect_rate_per_min": 2.0,
                    "success_rate": 0.5,
                },
                api_metrics={
                    "avg_response_time_ms": 12.5,
                    "qps": 2.1,
                    "error_rate": 0.25,
                    "concurrent_connections": 3,
                },
            )

        with patch("src.middleware.metrics.time.time", return_value=1001):
            success_rate_history = metrics_module.get_metrics_history("success_rate", "1h")
            error_rate_history = metrics_module.get_metrics_history("error_rate", "1h")

        self.assertEqual(success_rate_history["values"], [50.0])
        self.assertEqual(error_rate_history["values"], [25.0])


if __name__ == "__main__":
    unittest.main()
