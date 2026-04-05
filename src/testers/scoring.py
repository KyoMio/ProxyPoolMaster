"""
代理评分算法模块
实现基于测试目标通过率的分级与可用性判定
"""

from dataclasses import dataclass
from typing import List, Dict

from src.utils.proxy_availability import grade_from_pass_rate, is_grade_available


@dataclass
class TargetResult:
    """单个测试目标的结果"""
    target: str
    success: bool
    response_time: float
    status_code: int = 0
    error: str = ""


@dataclass
class MultiTargetTestResult:
    """多目标测试结果聚合"""
    target_results: List[TargetResult]
    total_time: float

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.target_results if r.success)

    @property
    def total_targets(self) -> int:
        return len(self.target_results)

    @property
    def avg_response_time(self) -> float:
        success_times = [r.response_time for r in self.target_results if
                         r.success and r.response_time > 0]
        return sum(success_times) / len(success_times) if success_times else 0.0


class ProxyScorer:
    """
    代理评分器。

    当前等级只由本轮测试目标通过率决定：
    - S: >= 90
    - A: >= 75
    - B: >= 50
    - C: > 0 且 < 50
    - D: = 0
    """

    def __init__(self, logger):
        self.logger = logger

    def calculate_score(
            self,
            test_result: MultiTargetTestResult,
            success_count: int = 0,
            total_checks: int = 0
    ) -> Dict:
        """
        计算代理综合评分。
        """
        success_targets = test_result.success_count
        avg_time = test_result.avg_response_time
        total_targets = max(test_result.total_targets, 1)
        pass_rate = (success_targets / total_targets) * 100
        total_score = int(round(pass_rate))
        grade = self._get_grade(total_score, success_targets)
        is_available = is_grade_available(grade)

        result = {
            "total_score": total_score,
            "grade": grade,
            "availability_score": total_score,
            "speed_score": 0,
            "stability_score": 0,
            "coverage_score": total_score,
            "is_available": is_available,
            "success_targets": success_targets,
            "avg_response_time": avg_time,
            "pass_rate": pass_rate,
        }

        self.logger.debug(f"Score calculated: {result}")
        return result

    def _get_grade(self, total_score: int, success_targets: int) -> str:
        """
        根据当前通过率得分判定等级。
        """
        return grade_from_pass_rate(float(total_score))

    def calculate_test_interval_multiplier(self, grade: str, fail_count: int) -> float:
        """
        计算测试间隔倍数
        """
        if fail_count > 0:
            return 0.3

        multipliers = {
            'S': 2.0,
            'A': 1.5,
            'B': 1.0,
            'C': 0.5,  # C级代理加快检测
            'D': 0.3
        }
        return multipliers.get(grade, 1.0)
