"""Collector V2 运行结果状态判定。"""

from typing import Any, Dict, List, Optional


def resolve_run_status(result: Dict[str, Any], errors: List[str]) -> str:
    """根据执行结果与错误明细推导运行状态。"""
    if not bool(result.get("success", False)):
        if any("timeout" in str(err).lower() for err in errors):
            return "timeout"
        return "failed"

    raw_count = int(result.get("raw_count", 0) or 0)
    valid_count = int(result.get("valid_count", 0) or 0)
    stored_count = int(result.get("stored_count", 0) or 0)
    cooldown_blocked_count = int(result.get("cooldown_blocked_count", 0) or 0)

    if raw_count <= 0 or valid_count <= 0:
        return "failed"
    if stored_count <= 0 and cooldown_blocked_count <= 0:
        return "failed"
    if stored_count <= 0 and cooldown_blocked_count > 0:
        return "partial_success" if errors else "success"

    if errors:
        return "partial_success"
    return "success"


def resolve_error_summary(result: Dict[str, Any], errors: List[str], status: str) -> Optional[str]:
    """根据执行结果推导面向界面的摘要错误文案。"""
    if errors:
        return str(errors[0])

    raw_count = int(result.get("raw_count", 0) or 0)
    valid_count = int(result.get("valid_count", 0) or 0)
    stored_count = int(result.get("stored_count", 0) or 0)

    if status == "timeout":
        return "执行超时"
    if raw_count <= 0:
        return "未提取到任何代理记录"
    if valid_count <= 0:
        return "提取到代理记录，但全部校验失败"
    if stored_count <= 0:
        cooldown_blocked_count = int(result.get("cooldown_blocked_count", 0) or 0)
        if cooldown_blocked_count > 0:
            return None
        return "未产生可存储代理记录"
    return None
