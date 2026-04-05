"""collectors_v2 数据结构定义。"""

from typing import Any, Literal, Optional, TypedDict


class CollectorDefinition(TypedDict, total=False):
    id: str
    name: str
    mode: Literal["simple", "code"]
    source: Literal["api", "scrape"]
    enabled: bool
    lifecycle: Literal["draft", "published", "paused"]
    interval_seconds: int
    spec: dict[str, Any]
    code_ref: Optional[dict[str, Any]]
    env_vars: dict[str, dict[str, Any]]
    meta: dict[str, Any]


class CollectorRunRecord(TypedDict, total=False):
    run_id: str
    collector_id: str
    trigger: Literal["schedule", "manual", "test"]
    status: Literal["success", "partial_success", "failed", "timeout"]
    started_at: str
    ended_at: str
    duration_ms: int
    metrics: dict[str, int]
    error_summary: Optional[str]
    error_details: list[str]


class WorkerHeartbeat(TypedDict, total=False):
    worker_id: str
    status: Literal["running", "degraded", "stopped"]
    last_heartbeat: str
    active_jobs: int
    queue_backlog: int
    version: str
