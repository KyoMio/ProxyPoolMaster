import asyncio
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException

from src.api import collector_v2_endpoints as endpoints


class _FakeRepo:
    def __init__(self):
        self.definitions = {}
        self.runs = {}

    def list_definitions(self):
        return list(self.definitions.values())

    def upsert_definition(self, definition):
        self.definitions[definition["id"]] = definition
        return definition

    def get_definition(self, collector_id):
        return self.definitions.get(collector_id)

    def delete_definition(self, collector_id):
        self.definitions.pop(collector_id, None)

    def append_run_record(self, collector_id, run, history_limit=200):
        self.runs.setdefault(collector_id, [])
        self.runs[collector_id].insert(0, run)
        self.runs[collector_id] = self.runs[collector_id][:history_limit]

    def get_runs(self, collector_id, limit=20):
        return self.runs.get(collector_id, [])[:limit]

    def get_last_run(self, collector_id):
        runs = self.runs.get(collector_id, [])
        return runs[0] if runs else None


class TestCollectorsV2Endpoints(unittest.TestCase):
    def test_test_run_should_log_collector_and_run_context(self):
        repo = _FakeRepo()
        repo.upsert_definition({
            "id": "demo_loggable",
            "name": "demo_loggable",
            "mode": "simple",
            "source": "api",
            "enabled": True,
            "lifecycle": "draft",
            "interval_seconds": 300,
            "spec": {},
            "env_vars": {},
            "meta": {"version": 1},
        })
        mock_logger = Mock()

        with patch("src.api.collector_v2_endpoints._get_v2_repository", return_value=repo), \
             patch("src.api.collector_v2_endpoints.app_globals.global_logger", mock_logger), \
             patch("src.api.collector_v2_endpoints.run_execution_subprocess", return_value={
                 "success": False,
                 "raw_count": 0,
                 "valid_count": 0,
                 "stored_count": 0,
                 "duplicate_count": 0,
                 "execution_time_ms": 100,
                 "errors": ["JSON 解析失败"],
             }):
            run_result = asyncio.run(endpoints.test_run_collector_v2(collector_id="demo_loggable", token=""))

        self.assertEqual(run_result["status"], "failed")
        self.assertGreaterEqual(mock_logger.info.call_count, 1)
        logged_extras = [call.kwargs.get("extra", {}) for call in mock_logger.info.call_args_list + mock_logger.error.call_args_list]
        self.assertTrue(any(extra.get("collector_id") == "demo_loggable" for extra in logged_extras))
        self.assertTrue(any(extra.get("run_id") == run_result["run_id"] for extra in logged_extras))
        self.assertTrue(any(extra.get("error_summary") == "JSON 解析失败" for extra in logged_extras))
        error_messages = [call.args[0] for call in mock_logger.error.call_args_list]
        self.assertTrue(any("JSON 解析失败" in message for message in error_messages))

    def test_create_test_run_publish_pause_resume_flow(self):
        repo = _FakeRepo()

        with patch("src.api.collector_v2_endpoints._get_v2_repository", return_value=repo), \
             patch("src.api.collector_v2_endpoints.run_execution_subprocess", return_value={
                 "success": True,
                 "raw_count": 2,
                 "valid_count": 1,
                 "stored_count": 1,
                 "duplicate_count": 0,
                 "cooldown_blocked_count": 0,
                 "execution_time_ms": 41,
                 "errors": ["第 2 项: 字段类型转换失败: invalid literal for int() with base 10: 'bad'"],
             }):
            created = asyncio.run(endpoints.create_collector_v2(
                endpoints.CollectorV2Create(
                    name="DemoV2",
                    spec={
                        "proxies": [
                            {"ip": "1.1.1.1", "port": 80, "protocol": "http"},
                            {"ip": "2.2.2.2", "port": "bad", "protocol": "http"},
                        ]
                    },
                ),
                token="",
            ))
            collector_id = created["id"]

            run_result = asyncio.run(endpoints.test_run_collector_v2(collector_id=collector_id, token=""))
            self.assertEqual(run_result["status"], "partial_success")
            self.assertEqual(run_result["metrics"]["raw_count"], 2)
            self.assertEqual(run_result["metrics"]["valid_count"], 1)
            self.assertGreaterEqual(len(run_result["error_details"]), 1)

            published = asyncio.run(endpoints.publish_collector_v2(
                collector_id=collector_id,
                data=endpoints.PublishRequest(skip_test_validation=False),
                token="",
            ))
            self.assertEqual(published["lifecycle"], "published")

            paused = asyncio.run(endpoints.pause_collector_v2(collector_id=collector_id, token=""))
            self.assertEqual(paused["lifecycle"], "paused")

            resumed = asyncio.run(endpoints.resume_collector_v2(collector_id=collector_id, token=""))
            self.assertEqual(resumed["lifecycle"], "published")

    def test_publish_without_successful_test_run_should_fail(self):
        repo = _FakeRepo()
        repo.upsert_definition({
            "id": "demo_no_test",
            "name": "demo_no_test",
            "mode": "simple",
            "source": "api",
            "enabled": True,
            "lifecycle": "draft",
            "interval_seconds": 300,
            "spec": {},
            "env_vars": {},
            "meta": {"version": 1},
        })

        with patch("src.api.collector_v2_endpoints._get_v2_repository", return_value=repo):
            with self.assertRaises(HTTPException):
                asyncio.run(endpoints.publish_collector_v2(
                    collector_id="demo_no_test",
                    data=endpoints.PublishRequest(skip_test_validation=False),
                    token="",
                ))

    def test_test_run_should_map_timeout_status(self):
        repo = _FakeRepo()
        repo.upsert_definition({
            "id": "demo_timeout",
            "name": "demo_timeout",
            "mode": "simple",
            "source": "api",
            "enabled": True,
            "lifecycle": "draft",
            "interval_seconds": 300,
            "spec": {},
            "env_vars": {},
            "meta": {"version": 1},
        })

        with patch("src.api.collector_v2_endpoints._get_v2_repository", return_value=repo), \
             patch("src.api.collector_v2_endpoints.run_execution_subprocess", return_value={
                 "success": False,
                 "raw_count": 0,
                 "valid_count": 0,
                 "stored_count": 0,
                 "duplicate_count": 0,
                 "execution_time_ms": 1000,
                 "errors": ["execution timeout after 1s"],
             }):
            run_result = asyncio.run(endpoints.test_run_collector_v2(collector_id="demo_timeout", token=""))

        self.assertEqual(run_result["status"], "timeout")

    def test_test_run_should_map_empty_result_to_failed(self):
        repo = _FakeRepo()
        repo.upsert_definition({
            "id": "demo_empty",
            "name": "demo_empty",
            "mode": "simple",
            "source": "api",
            "enabled": True,
            "lifecycle": "draft",
            "interval_seconds": 300,
            "spec": {},
            "env_vars": {},
            "meta": {"version": 1},
        })

        with patch("src.api.collector_v2_endpoints._get_v2_repository", return_value=repo), \
             patch("src.api.collector_v2_endpoints.run_execution_subprocess", return_value={
                 "success": True,
                 "raw_count": 0,
                 "valid_count": 0,
                 "stored_count": 0,
                 "duplicate_count": 0,
                 "execution_time_ms": 100,
                 "errors": [],
             }):
            run_result = asyncio.run(endpoints.test_run_collector_v2(collector_id="demo_empty", token=""))

        self.assertEqual(run_result["status"], "failed")
        self.assertEqual(run_result["error_summary"], "未提取到任何代理记录")

    def test_test_run_should_not_treat_cooldown_only_result_as_failed(self):
        repo = _FakeRepo()
        repo.upsert_definition({
            "id": "demo_cooldown_only",
            "name": "demo_cooldown_only",
            "mode": "simple",
            "source": "api",
            "enabled": True,
            "lifecycle": "draft",
            "interval_seconds": 300,
            "spec": {},
            "env_vars": {},
            "meta": {"version": 1},
        })
        mock_logger = Mock()

        with patch("src.api.collector_v2_endpoints._get_v2_repository", return_value=repo), \
             patch("src.api.collector_v2_endpoints.app_globals.global_logger", mock_logger), \
             patch("src.api.collector_v2_endpoints.run_execution_subprocess", return_value={
                 "success": True,
                 "raw_count": 3,
                 "valid_count": 3,
                 "stored_count": 0,
                 "duplicate_count": 0,
                 "cooldown_blocked_count": 3,
                 "execution_time_ms": 100,
                 "errors": [],
             }):
            run_result = asyncio.run(endpoints.test_run_collector_v2(collector_id="demo_cooldown_only", token=""))

        self.assertEqual(run_result["status"], "success")
        self.assertIsNone(run_result["error_summary"])
        self.assertEqual(run_result["metrics"]["cooldown_blocked_count"], 3)
        mock_logger.error.assert_not_called()

    def test_test_run_should_derive_error_summary_when_no_explicit_errors(self):
        repo = _FakeRepo()
        repo.upsert_definition({
            "id": "demo_no_reason",
            "name": "demo_no_reason",
            "mode": "simple",
            "source": "api",
            "enabled": True,
            "lifecycle": "draft",
            "interval_seconds": 300,
            "spec": {},
            "env_vars": {},
            "meta": {"version": 1},
        })
        mock_logger = Mock()

        with patch("src.api.collector_v2_endpoints._get_v2_repository", return_value=repo), \
             patch("src.api.collector_v2_endpoints.app_globals.global_logger", mock_logger), \
             patch("src.api.collector_v2_endpoints.run_execution_subprocess", return_value={
                 "success": True,
                 "raw_count": 0,
                 "valid_count": 0,
                 "stored_count": 0,
                 "duplicate_count": 0,
                 "execution_time_ms": 88,
                 "errors": [],
             }):
            run_result = asyncio.run(endpoints.test_run_collector_v2(collector_id="demo_no_reason", token=""))

        self.assertEqual(run_result["error_summary"], "未提取到任何代理记录")
        error_messages = [call.args[0] for call in mock_logger.error.call_args_list]
        self.assertTrue(any("未提取到任何代理记录" in message for message in error_messages))

    def test_test_run_should_map_all_invalid_to_failed(self):
        repo = _FakeRepo()
        repo.upsert_definition({
            "id": "demo_all_invalid",
            "name": "demo_all_invalid",
            "mode": "simple",
            "source": "api",
            "enabled": True,
            "lifecycle": "draft",
            "interval_seconds": 300,
            "spec": {},
            "env_vars": {},
            "meta": {"version": 1},
        })

        with patch("src.api.collector_v2_endpoints._get_v2_repository", return_value=repo), \
             patch("src.api.collector_v2_endpoints.run_execution_subprocess", return_value={
                 "success": True,
                 "raw_count": 2,
                 "valid_count": 0,
                 "stored_count": 0,
                 "duplicate_count": 0,
                 "execution_time_ms": 100,
                 "errors": ["第 1 项: 字段类型转换失败"],
             }):
            run_result = asyncio.run(endpoints.test_run_collector_v2(collector_id="demo_all_invalid", token=""))

        self.assertEqual(run_result["status"], "failed")

    def test_test_run_should_map_parse_exception_to_failed(self):
        repo = _FakeRepo()
        repo.upsert_definition({
            "id": "demo_parse_error",
            "name": "demo_parse_error",
            "mode": "simple",
            "source": "api",
            "enabled": True,
            "lifecycle": "draft",
            "interval_seconds": 300,
            "spec": {},
            "env_vars": {},
            "meta": {"version": 1},
        })

        with patch("src.api.collector_v2_endpoints._get_v2_repository", return_value=repo), \
             patch("src.api.collector_v2_endpoints.run_execution_subprocess", return_value={
                 "success": False,
                 "raw_count": 0,
                 "valid_count": 0,
                 "stored_count": 0,
                 "duplicate_count": 0,
                 "execution_time_ms": 100,
                 "errors": ["JSON 解析失败: Expecting value"],
             }):
            run_result = asyncio.run(endpoints.test_run_collector_v2(collector_id="demo_parse_error", token=""))

        self.assertEqual(run_result["status"], "failed")


if __name__ == "__main__":
    unittest.main()
