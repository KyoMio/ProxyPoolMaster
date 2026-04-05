"""代理等级与可用性规则。"""

from __future__ import annotations


AVAILABLE_GRADES = {"S", "A", "B"}


def grade_from_pass_rate(pass_rate: float) -> str:
    """根据测试目标通过率计算代理等级。"""
    if pass_rate <= 0:
        return "D"
    if pass_rate < 50:
        return "C"
    if pass_rate < 75:
        return "B"
    if pass_rate < 90:
        return "A"
    return "S"


def is_grade_available(grade: str) -> bool:
    """只有 B 级及以上代理属于可用代理。"""
    return (grade or "").upper() in AVAILABLE_GRADES
