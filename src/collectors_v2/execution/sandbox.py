"""collectors_v2 执行沙箱辅助工具。"""

from typing import Dict, List


def apply_sandbox_limits() -> None:
    """阶段 2 占位：后续在子进程内接入内存/CPU 限额。"""
    return None


def truncate_output(value: str, limit_kb: int) -> str:
    """限制 stdout/stderr 大小，避免日志爆炸。"""
    limit_bytes = max(1, int(limit_kb)) * 1024
    encoded = (value or "").encode("utf-8", errors="ignore")
    if len(encoded) <= limit_bytes:
        return value or ""
    truncated = encoded[:limit_bytes].decode("utf-8", errors="ignore")
    return f"{truncated}...[truncated]"


def build_timeout_result(timeout_seconds: int) -> Dict[str, object]:
    return {
        "success": False,
        "raw_count": 0,
        "valid_count": 0,
        "stored_count": 0,
        "duplicate_count": 0,
        "cooldown_blocked_count": 0,
        "execution_time_ms": max(0, int(timeout_seconds) * 1000),
        "errors": [f"execution timeout after {timeout_seconds}s"],
    }
