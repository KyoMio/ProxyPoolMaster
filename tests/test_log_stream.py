import unittest

from src.api.log_stream import LogClientState, matches_filters


class TestLogStreamFilters(unittest.TestCase):
    def test_matches_filters_by_level_component_keyword(self):
        entry = {
            "level": "INFO",
            "component": "API",
            "message": "Collector round completed",
            "source": "ProxyPoolMaster",
        }

        self.assertTrue(matches_filters(entry, {"level": "INFO"}))
        self.assertFalse(matches_filters(entry, {"level": "ERROR"}))
        self.assertTrue(matches_filters(entry, {"component": "api"}))
        self.assertFalse(matches_filters(entry, {"component": "tester"}))
        self.assertTrue(matches_filters(entry, {"keyword": "completed"}))
        self.assertTrue(matches_filters(entry, {"keyword": "proxypool"}))
        self.assertFalse(matches_filters(entry, {"keyword": "timeout"}))

    def test_matches_filters_by_min_level(self):
        warning_entry = {
            "level": "WARNING",
            "component": "TESTER",
            "message": "Removing proxy 1.1.1.1:80",
            "source": "ProxyPoolMaster",
        }
        info_entry = {
            "level": "INFO",
            "component": "APP",
            "message": "Service started",
            "source": "ProxyPoolMaster",
        }

        self.assertTrue(matches_filters(warning_entry, {"min_level": "WARNING"}))
        self.assertTrue(matches_filters(warning_entry, {"min_level": "INFO"}))
        self.assertFalse(matches_filters(info_entry, {"min_level": "WARNING"}))

    def test_matches_filters_by_exclude_components(self):
        tester_entry = {
            "level": "WARNING",
            "component": "TESTER",
            "message": "Removing proxy 1.1.1.1:80",
            "source": "ProxyPoolMaster",
        }
        api_entry = {
            "level": "INFO",
            "component": "API",
            "message": "Request handled",
            "source": "ProxyPoolMaster",
        }

        self.assertFalse(matches_filters(tester_entry, {"exclude_components": "TESTER,REDIS"}))
        self.assertTrue(matches_filters(api_entry, {"exclude_components": "TESTER,REDIS"}))

    def test_matches_filters_by_collector_and_run_id(self):
        entry = {
            "level": "INFO",
            "component": "COLLECTOR_WORKER",
            "message": "collector run completed",
            "source": "ProxyPoolMaster",
            "context": {
                "collector_id": "demo_collector",
                "run_id": "run-123",
            },
        }

        self.assertTrue(matches_filters(entry, {"collector_id": "demo_collector"}))
        self.assertFalse(matches_filters(entry, {"collector_id": "another_collector"}))
        self.assertTrue(matches_filters(entry, {"run_id": "run-123"}))
        self.assertFalse(matches_filters(entry, {"run_id": "run-456"}))


class TestLogClientState(unittest.TestCase):
    def test_queue_overflow_tracks_dropped(self):
        state = LogClientState(max_queue_size=3)
        state.enqueue({"id": 1})
        state.enqueue({"id": 2})
        state.enqueue({"id": 3})
        state.enqueue({"id": 4})
        state.enqueue({"id": 5})

        self.assertEqual(state.dropped_count, 2)
        self.assertEqual([item["id"] for item in list(state.queue)], [3, 4, 5])


class TestJsonFormatterContext(unittest.TestCase):
    def test_json_formatter_should_include_collector_and_run_identifiers(self):
        import json
        import logging

        from src.logger import JSONFormatter

        formatter = JSONFormatter(component="COLLECTOR_WORKER", timezone_str="Asia/Shanghai")
        record = logging.LogRecord(
            name="ProxyPoolMaster",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="collector run completed",
            args=(),
            exc_info=None,
        )
        record.component = "COLLECTOR_WORKER"
        record.collector_id = "demo_collector"
        record.run_id = "run-123"
        record.worker_id = "collector-worker-1"
        record.error_summary = "JSON 解析失败"

        payload = json.loads(formatter.format(record))

        self.assertEqual(payload["context"]["collector_id"], "demo_collector")
        self.assertEqual(payload["context"]["run_id"], "run-123")
        self.assertEqual(payload["context"]["worker_id"], "collector-worker-1")
        self.assertEqual(payload["context"]["error_summary"], "JSON 解析失败")


if __name__ == "__main__":
    unittest.main()
