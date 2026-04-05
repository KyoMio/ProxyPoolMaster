"""collectors_v2 调度器。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from src.collectors_v2.run_status import (
    resolve_error_summary as _resolve_error_summary,
    resolve_run_status as _resolve_run_status,
)


class CollectorV2Scheduler:
    """V2 Worker 调度实现。"""

    def __init__(
        self,
        repository,
        run_execution,
        timeout_seconds: int,
        stdout_limit_kb: int,
        logger=None,
        worker_id: str = "collector-worker-1",
        heartbeat_update=None,
    ):
        self.repository = repository
        self.run_execution = run_execution
        self.timeout_seconds = max(1, int(timeout_seconds))
        self.stdout_limit_kb = max(1, int(stdout_limit_kb))
        self.logger = logger
        self.worker_id = worker_id
        self.heartbeat_update = heartbeat_update

    def list_due_collectors(self, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        current = now or datetime.now()
        due_collectors: List[Dict[str, Any]] = []
        for definition in self.repository.list_definitions():
            if not isinstance(definition, dict):
                continue
            if not bool(definition.get("enabled", True)):
                continue
            if str(definition.get("lifecycle", "draft")) != "published":
                continue
            if self._is_due(definition, current):
                due_collectors.append(dict(definition))
        return due_collectors

    def tick(self, now: Optional[datetime] = None) -> int:
        current = now or datetime.now()
        due_collectors = self.list_due_collectors(current)
        self._update_heartbeat(active_jobs=0, queue_backlog=len(due_collectors))
        executed = 0
        remaining = len(due_collectors)
        for definition in due_collectors:
            self._update_heartbeat(active_jobs=1, queue_backlog=remaining)
            run_record = self._execute_definition(definition, current)
            self.repository.append_run_record(str(definition.get("id", "")), run_record)
            executed += 1
            remaining -= 1
            self._update_heartbeat(active_jobs=0, queue_backlog=remaining)
        return executed

    def _is_due(self, definition: Dict[str, Any], now: datetime) -> bool:
        interval_seconds = max(1, int(definition.get("interval_seconds", 300) or 300))
        last_schedule_run = self._get_last_schedule_run(str(definition.get("id", "")))
        if last_schedule_run is None:
            return True

        started_at = str(last_schedule_run.get("started_at", "")).strip()
        if not started_at:
            return True

        try:
            last_started = datetime.fromisoformat(started_at)
        except ValueError:
            return True

        return now >= last_started + timedelta(seconds=interval_seconds)

    def _get_last_schedule_run(self, collector_id: str) -> Optional[Dict[str, Any]]:
        runs = self.repository.get_runs(collector_id, limit=20)
        for run in runs:
            if str(run.get("trigger", "")) == "schedule":
                return dict(run)
        return None

    def _execute_definition(self, definition: Dict[str, Any], now: datetime) -> Dict[str, Any]:
        collector_id = str(definition.get("id", "")).strip()
        run_id = str(uuid4())
        started_at = now.isoformat()
        self._log(
            "info",
            "collector schedule run started",
            collector_id=collector_id,
            run_id=run_id,
            trigger="schedule",
        )
        exec_result = self.run_execution(
            {
                "run_id": run_id,
                "collector": definition,
                "trigger": "schedule",
            },
            timeout_seconds=self.timeout_seconds,
            stdout_limit_kb=self.stdout_limit_kb,
        )
        ended_at = datetime.now().isoformat()
        errors = list(exec_result.get("errors", []) or [])
        status = _resolve_run_status(exec_result, errors)
        error_summary = _resolve_error_summary(exec_result, errors, status)
        run_record = {
            "run_id": run_id,
            "collector_id": collector_id,
            "trigger": "schedule",
            "status": status,
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_ms": int(exec_result.get("execution_time_ms", 0) or 0),
            "metrics": {
                "raw_count": int(exec_result.get("raw_count", 0) or 0),
                "valid_count": int(exec_result.get("valid_count", 0) or 0),
                "stored_count": int(exec_result.get("stored_count", 0) or 0),
                "duplicate_count": int(exec_result.get("duplicate_count", 0) or 0),
                "cooldown_blocked_count": int(exec_result.get("cooldown_blocked_count", 0) or 0),
            },
            "error_summary": error_summary,
            "error_details": errors,
        }
        log_level = self._resolve_finished_log_level(run_record)
        self._log(
            log_level,
            "collector schedule run finished",
            collector_id=collector_id,
            run_id=run_id,
            trigger="schedule",
            status=run_record["status"],
            duration_ms=run_record["duration_ms"],
            raw_count=run_record["metrics"]["raw_count"],
            valid_count=run_record["metrics"]["valid_count"],
            stored_count=run_record["metrics"]["stored_count"],
            duplicate_count=run_record["metrics"]["duplicate_count"],
            cooldown_blocked_count=run_record["metrics"]["cooldown_blocked_count"],
            error_summary=run_record["error_summary"],
        )
        return run_record

    def _resolve_finished_log_level(self, run_record: Dict[str, Any]) -> str:
        status = str(run_record.get("status", "")).strip().lower()
        error_summary = str(run_record.get("error_summary") or "").strip()
        if status == "timeout":
            return "error"
        if status == "failed" and error_summary == "未提取到任何代理记录":
            return "warning"
        if status == "failed":
            return "error"
        if status == "partial_success":
            return "warning"
        return "info"

    def _log(self, level: str, message: str, **kwargs: Any) -> None:
        if self.logger is None:
            return
        error_summary = str(kwargs.get("error_summary") or "").strip()
        if error_summary:
            message = f"{message}: {error_summary}"
        extra = {
            "component": "COLLECTOR_WORKER",
            "worker_id": self.worker_id,
        }
        extra.update(kwargs)
        getattr(self.logger, level)(message, extra=extra)

    def _update_heartbeat(self, active_jobs: int, queue_backlog: int) -> None:
        if self.heartbeat_update is None:
            return
        self.heartbeat_update(
            active_jobs=max(0, int(active_jobs)),
            queue_backlog=max(0, int(queue_backlog)),
        )
