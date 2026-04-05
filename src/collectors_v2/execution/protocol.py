"""collectors_v2 父子进程通信协议（阶段 0 骨架）。"""

from typing import Any, TypedDict


class ExecutionInput(TypedDict, total=False):
    run_id: str
    collector: dict[str, Any]
    trigger: str


class ExecutionResult(TypedDict, total=False):
    success: bool
    raw_count: int
    valid_count: int
    stored_count: int
    duplicate_count: int
    cooldown_blocked_count: int
    execution_time_ms: int
    errors: list[str]
