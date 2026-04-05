import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock

from src.collectors_v2.scheduler import CollectorV2Scheduler


class _FakeRepo:
    def __init__(self, definitions=None, runs=None):
        self.definitions = list(definitions or [])
        self.runs = {key: list(value) for key, value in (runs or {}).items()}
        self.saved_runs = []

    def list_definitions(self):
        return list(self.definitions)

    def get_runs(self, collector_id, limit=20):
        return list(self.runs.get(collector_id, []))[:limit]

    def append_run_record(self, collector_id, run_record, history_limit=200):
        self.saved_runs.append((collector_id, run_record))
        self.runs.setdefault(collector_id, [])
        self.runs[collector_id].insert(0, run_record)
        self.runs[collector_id] = self.runs[collector_id][:history_limit]
        return run_record


class TestCollectorV2Scheduler(unittest.TestCase):
    def test_tick_should_run_published_enabled_collector_without_schedule_history(self):
        repo = _FakeRepo(definitions=[
            {
                "id": "zdaye_v2",
                "name": "站大爷",
                "mode": "simple",
                "source": "api",
                "enabled": True,
                "lifecycle": "published",
                "interval_seconds": 300,
                "spec": {},
            }
        ])
        execution_calls = []

        def fake_runner(payload, timeout_seconds, stdout_limit_kb):
            execution_calls.append((payload, timeout_seconds, stdout_limit_kb))
            return {
                "success": True,
                "raw_count": 1,
                "valid_count": 1,
                "stored_count": 1,
                "duplicate_count": 0,
                "execution_time_ms": 120,
                "errors": [],
            }

        scheduler = CollectorV2Scheduler(
            repository=repo,
            run_execution=fake_runner,
            timeout_seconds=60,
            stdout_limit_kb=256,
        )

        executed = scheduler.tick(now=datetime(2026, 3, 17, 20, 45, 0))

        self.assertEqual(executed, 1)
        self.assertEqual(len(execution_calls), 1)
        self.assertEqual(repo.saved_runs[0][0], "zdaye_v2")
        self.assertEqual(repo.saved_runs[0][1]["trigger"], "schedule")
        self.assertEqual(repo.saved_runs[0][1]["status"], "success")

    def test_tick_should_skip_collector_when_interval_not_elapsed(self):
        last_schedule_time = datetime(2026, 3, 17, 20, 45, 0)
        repo = _FakeRepo(
            definitions=[
                {
                    "id": "zdaye_v2",
                    "name": "站大爷",
                    "mode": "simple",
                    "source": "api",
                    "enabled": True,
                    "lifecycle": "published",
                    "interval_seconds": 300,
                    "spec": {},
                }
            ],
            runs={
                "zdaye_v2": [
                    {
                        "run_id": "r-1",
                        "collector_id": "zdaye_v2",
                        "trigger": "schedule",
                        "status": "success",
                        "started_at": last_schedule_time.isoformat(),
                        "ended_at": (last_schedule_time + timedelta(seconds=1)).isoformat(),
                        "duration_ms": 100,
                        "metrics": {
                            "raw_count": 1,
                            "valid_count": 1,
                            "stored_count": 1,
                            "duplicate_count": 0,
                        },
                        "error_summary": None,
                        "error_details": [],
                    }
                ]
            },
        )

        scheduler = CollectorV2Scheduler(
            repository=repo,
            run_execution=lambda payload, timeout_seconds, stdout_limit_kb: {
                "success": True,
                "raw_count": 1,
                "valid_count": 1,
                "stored_count": 1,
                "duplicate_count": 0,
                "execution_time_ms": 100,
                "errors": [],
            },
            timeout_seconds=60,
            stdout_limit_kb=256,
        )

        executed = scheduler.tick(now=last_schedule_time + timedelta(seconds=120))

        self.assertEqual(executed, 0)
        self.assertEqual(repo.saved_runs, [])

    def test_tick_should_log_collector_and_run_context(self):
        repo = _FakeRepo(definitions=[
            {
                "id": "zdaye_v2",
                "name": "站大爷",
                "mode": "simple",
                "source": "api",
                "enabled": True,
                "lifecycle": "published",
                "interval_seconds": 300,
                "spec": {},
            }
        ])
        logger = Mock()

        scheduler = CollectorV2Scheduler(
            repository=repo,
            run_execution=lambda payload, timeout_seconds, stdout_limit_kb: {
                "success": False,
                "raw_count": 0,
                "valid_count": 0,
                "stored_count": 0,
                "duplicate_count": 0,
                "execution_time_ms": 80,
                "errors": ["JSON 解析失败"],
            },
            timeout_seconds=60,
            stdout_limit_kb=256,
            logger=logger,
            worker_id="collector-worker-1",
        )

        scheduler.tick(now=datetime(2026, 3, 17, 20, 45, 0))

        logged_extras = [call.kwargs.get("extra", {}) for call in logger.info.call_args_list + logger.error.call_args_list]
        self.assertTrue(any(extra.get("collector_id") == "zdaye_v2" for extra in logged_extras))
        self.assertTrue(any(extra.get("run_id") for extra in logged_extras))
        self.assertTrue(any(extra.get("worker_id") == "collector-worker-1" for extra in logged_extras))
        self.assertTrue(any(extra.get("status") == "failed" for extra in logged_extras))
        self.assertTrue(any(extra.get("error_summary") == "JSON 解析失败" for extra in logged_extras))
        error_messages = [call.args[0] for call in logger.error.call_args_list]
        self.assertTrue(any("JSON 解析失败" in message for message in error_messages))

    def test_tick_should_not_treat_cooldown_only_result_as_failed(self):
        repo = _FakeRepo(definitions=[
            {
                "id": "zdaye_v2",
                "name": "站大爷",
                "mode": "simple",
                "source": "api",
                "enabled": True,
                "lifecycle": "published",
                "interval_seconds": 300,
                "spec": {},
            }
        ])
        logger = Mock()

        scheduler = CollectorV2Scheduler(
            repository=repo,
            run_execution=lambda payload, timeout_seconds, stdout_limit_kb: {
                "success": True,
                "raw_count": 3,
                "valid_count": 3,
                "stored_count": 0,
                "duplicate_count": 0,
                "cooldown_blocked_count": 3,
                "execution_time_ms": 80,
                "errors": [],
            },
            timeout_seconds=60,
            stdout_limit_kb=256,
            logger=logger,
            worker_id="collector-worker-1",
        )

        scheduler.tick(now=datetime(2026, 3, 17, 20, 45, 0))

        saved_run = repo.saved_runs[0][1]
        self.assertEqual(saved_run["status"], "success")
        self.assertEqual(saved_run["metrics"]["cooldown_blocked_count"], 3)
        self.assertIsNone(saved_run["error_summary"])
        logger.error.assert_not_called()

    def test_tick_should_update_worker_metrics_during_execution(self):
        repo = _FakeRepo(definitions=[
            {
                "id": "collector_a",
                "name": "A",
                "mode": "simple",
                "source": "api",
                "enabled": True,
                "lifecycle": "published",
                "interval_seconds": 300,
                "spec": {},
            },
            {
                "id": "collector_b",
                "name": "B",
                "mode": "simple",
                "source": "api",
                "enabled": True,
                "lifecycle": "published",
                "interval_seconds": 300,
                "spec": {},
            },
        ])
        heartbeat_events = []

        def fake_runner(payload, timeout_seconds, stdout_limit_kb):
            return {
                "success": True,
                "raw_count": 1,
                "valid_count": 1,
                "stored_count": 1,
                "duplicate_count": 0,
                "execution_time_ms": 50,
                "errors": [],
            }

        scheduler = CollectorV2Scheduler(
            repository=repo,
            run_execution=fake_runner,
            timeout_seconds=60,
            stdout_limit_kb=256,
            heartbeat_update=lambda active_jobs, queue_backlog: heartbeat_events.append((active_jobs, queue_backlog)),
        )

        executed = scheduler.tick(now=datetime(2026, 3, 17, 20, 45, 0))

        self.assertEqual(executed, 2)
        self.assertEqual(
            heartbeat_events,
            [
                (0, 2),
                (1, 2),
                (0, 1),
                (1, 1),
                (0, 0),
            ],
        )

    def test_tick_should_derive_error_summary_when_execution_returns_empty_result(self):
        repo = _FakeRepo(definitions=[
            {
                "id": "zdaye_v2",
                "name": "站大爷",
                "mode": "simple",
                "source": "api",
                "enabled": True,
                "lifecycle": "published",
                "interval_seconds": 300,
                "spec": {},
            }
        ])
        logger = Mock()

        scheduler = CollectorV2Scheduler(
            repository=repo,
            run_execution=lambda payload, timeout_seconds, stdout_limit_kb: {
                "success": True,
                "raw_count": 0,
                "valid_count": 0,
                "stored_count": 0,
                "duplicate_count": 0,
                "execution_time_ms": 23,
                "errors": [],
            },
            timeout_seconds=60,
            stdout_limit_kb=256,
            logger=logger,
            worker_id="collector-worker-1",
        )

        scheduler.tick(now=datetime(2026, 3, 17, 20, 45, 0))

        saved_run = repo.saved_runs[0][1]
        self.assertEqual(saved_run["error_summary"], "未提取到任何代理记录")
        warning_messages = [call.args[0] for call in logger.warning.call_args_list]
        self.assertTrue(any("未提取到任何代理记录" in message for message in warning_messages))
        logger.error.assert_not_called()


if __name__ == "__main__":
    unittest.main()
