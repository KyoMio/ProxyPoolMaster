import unittest
from pathlib import Path

from src.api.system_endpoints import merge_connection_metrics


class TestMergeConnectionMetrics(unittest.TestCase):
    def test_merge_connection_metrics_includes_ws_count(self):
        api_metrics = {
            "avg_response_time_ms": 10,
            "qps": 1.2,
            "error_rate": 0.0,
            "concurrent_connections": 2,
        }

        merged = merge_connection_metrics(api_metrics, dashboard_ws_connections=3, log_ws_connections=4)

        self.assertEqual(merged["http_inflight_requests"], 2)
        self.assertEqual(merged["websocket_connections"], 7)
        self.assertEqual(merged["concurrent_connections"], 9)

    def test_entrypoint_should_not_start_backend_main_scheduler(self):
        project_root = Path(__file__).resolve().parent.parent
        entrypoint = (project_root / "entrypoint.sh").read_text(encoding="utf-8")
        self.assertNotIn("nohup python /app/backend/main.py", entrypoint)

    def test_api_runtime_should_not_expose_embedded_collector_switch(self):
        project_root = Path(__file__).resolve().parent.parent
        api_main = (project_root / "src" / "api" / "main.py").read_text(encoding="utf-8")
        self.assertNotIn("DISABLE_API_COLLECTOR", api_main)
        self.assertNotIn("Starting Collector V2 worker in API process", api_main)


if __name__ == "__main__":
    unittest.main()
