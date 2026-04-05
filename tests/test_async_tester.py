import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.testers.scoring import ProxyScorer, TargetResult, MultiTargetTestResult
from src.testers.async_tester import AsyncHttpTester
from src.testers.baseline import BaselineFingerprint


class TestProxyScorer(unittest.TestCase):
    """测试评分算法 - 针对免费代理优化版本"""

    def setUp(self):
        self.logger = Mock()
        self.scorer = ProxyScorer(self.logger)

    def test_perfect_proxy(self):
        """测试完美代理（S级）- 4目标快速响应"""
        results = [
            TargetResult("http://test1.com", True, 0.5, 200),
            TargetResult("http://test2.com", True, 0.6, 200),
            TargetResult("http://test3.com", True, 0.4, 200),
            TargetResult("http://test4.com", True, 0.7, 200),
        ]
        test_result = MultiTargetTestResult(results, 2.2)

        score = self.scorer.calculate_score(test_result, success_count=10,
                                            total_checks=10)

        self.assertEqual(score["grade"], "S")
        self.assertTrue(score["is_available"])
        self.assertEqual(score["success_targets"], 4)

    def test_excellent_proxy(self):
        """测试优秀代理（A级）- 3目标成功"""
        results = [
            TargetResult("http://test1.com", True, 1.5, 200),
            TargetResult("http://test2.com", True, 2.0, 200),
            TargetResult("http://test3.com", True, 1.8, 200),
            TargetResult("http://test4.com", False, 0, error="Timeout"),
        ]
        test_result = MultiTargetTestResult(results, 5.3)

        score = self.scorer.calculate_score(test_result, success_count=5,
                                            total_checks=6)

        self.assertEqual(score["grade"], "A")
        self.assertTrue(score["is_available"])
        self.assertEqual(score["success_targets"], 3)

    def test_good_proxy_two_targets(self):
        """测试良好代理（B级）- 2目标成功"""
        results = [
            TargetResult("http://test1.com", True, 2.5, 200),
            TargetResult("http://test2.com", True, 3.5, 200),
            TargetResult("http://test3.com", False, 0, error="Timeout"),
            TargetResult("http://test4.com", False, 0, error="Timeout"),
        ]
        test_result = MultiTargetTestResult(results, 6.0)

        score = self.scorer.calculate_score(test_result, success_count=3,
                                            total_checks=5)

        # 2目标成功(30) + 速度25分(2-5秒) + 稳定性12分 + 覆盖度6分 = 73分
        self.assertEqual(score["grade"], "B")
        self.assertTrue(score["is_available"])
        self.assertEqual(score["success_targets"], 2)

    def test_single_target_good_quality(self):
        """测试单目标高质量代理（C级）- 不再视为可用代理"""
        results = [
            TargetResult("http://test1.com", True, 1.5, 200),
            TargetResult("http://test2.com", False, 0, error="Timeout"),
            TargetResult("http://test3.com", False, 0, error="Timeout"),
            TargetResult("http://test4.com", False, 0, error="Timeout"),
        ]
        test_result = MultiTargetTestResult(results, 1.5)

        score = self.scorer.calculate_score(test_result, success_count=2,
                                            total_checks=3)

        # 按通过率等级规则：单目标成功固定为 C 级
        self.assertEqual(score["grade"], "C")
        self.assertFalse(score["is_available"])
        self.assertEqual(score["success_targets"], 1)

    def test_single_target_poor_quality(self):
        """测试单目标低质量代理（C级）不算可用"""
        results = [
            TargetResult("http://test1.com", True, 12.0, 200),  # 很慢
            TargetResult("http://test2.com", False, 0, error="Timeout"),
            TargetResult("http://test3.com", False, 0, error="Timeout"),
            TargetResult("http://test4.com", False, 0, error="Timeout"),
        ]
        test_result = MultiTargetTestResult(results, 12.0)

        score = self.scorer.calculate_score(test_result, success_count=1,
                                            total_checks=5)

        self.assertEqual(score["grade"], "C")
        self.assertFalse(score["is_available"])
        self.assertEqual(score["success_targets"], 1)

    def test_new_proxy_single_target(self):
        """测试新代理首次成功单目标 - C级但不算可用"""
        results = [
            TargetResult("http://test1.com", True, 3.0, 200),
            TargetResult("http://test2.com", False, 0, error="Timeout"),
            TargetResult("http://test3.com", False, 0, error="Timeout"),
            TargetResult("http://test4.com", False, 0, error="Timeout"),
        ]
        test_result = MultiTargetTestResult(results, 3.0)

        score = self.scorer.calculate_score(test_result, success_count=0,
                                            total_checks=0)

        self.assertEqual(score["grade"], "C")
        self.assertFalse(score["is_available"])

    def test_slow_but_working_proxy(self):
        """测试慢速但可用的代理 - 免费代理常见"""
        results = [
            TargetResult("http://test1.com", True, 8.0, 200),  # 较慢
            TargetResult("http://test2.com", True, 9.0, 200),  # 较慢
            TargetResult("http://test3.com", False, 0, error="Timeout"),
            TargetResult("http://test4.com", False, 0, error="Timeout"),
        ]
        test_result = MultiTargetTestResult(results, 17.0)

        score = self.scorer.calculate_score(test_result, success_count=3,
                                            total_checks=5)

        # 2目标成功(30) + 速度20分(5-10秒) + 稳定性12分 + 覆盖度6分 = 68分 → B级
        self.assertEqual(score["grade"], "B")
        self.assertTrue(score["is_available"])

    def test_failed_proxy(self):
        """测试完全失败的代理（D级）"""
        results = [
            TargetResult("http://test1.com", False, 0, error="Timeout"),
            TargetResult("http://test2.com", False, 0, error="Timeout"),
            TargetResult("http://test3.com", False, 0, error="Timeout"),
            TargetResult("http://test4.com", False, 0, error="Timeout"),
        ]
        test_result = MultiTargetTestResult(results, 0)

        score = self.scorer.calculate_score(test_result, success_count=0,
                                            total_checks=0)

        self.assertEqual(score["grade"], "D")
        self.assertFalse(score["is_available"])
        self.assertEqual(score["total_score"], 0)


class TestAsyncHttpTester(unittest.IsolatedAsyncioTestCase):
    """测试异步 HTTP 测试器"""

    async def asyncSetUp(self):
        self.config = Mock()
        self.config.TEST_TARGETS = ["https://www.baidu.com"]
        self.config.TEST_TIMEOUT_PER_TARGET = 5
        self.logger = Mock()

    async def test_initialization(self):
        """测试初始化"""
        tester = AsyncHttpTester(self.config, self.logger)
        self.assertEqual(len(tester.targets), 1)
        self.assertIsNotNone(tester.connector)
        await tester.close()

    async def test_test_single_target_with_session_should_use_baseline_validation(self):
        tester = AsyncHttpTester(self.config, self.logger)
        target = "https://example.com/welcome"
        tester._target_baselines[target] = BaselineFingerprint(
            host="example.com",
            title="Example Domain",
            content_type_prefix="text/html",
            median_body_length=1200,
            median_text_length=320,
            keywords=["Example Domain", "testing proxies"],
        )
        session = FakeSession(
            FakeResponse(
                status=200,
                url="https://example.com/welcome?from=proxy",
                content_type="text/html; charset=utf-8",
                body=(
                    "<html><head><title>Example Domain</title></head><body>"
                    "This proxy reached Example Domain successfully for testing proxies."
                    "</body></html>"
                ).encode("utf-8"),
            )
        )

        result = await tester._test_single_target_with_session(session, target, "http://1.1.1.1:8080")

        self.assertTrue(result.success)
        self.assertEqual(result.status_code, 200)
        self.assertTrue(session.last_kwargs["allow_redirects"])
        self.assertTrue(session.last_kwargs["ssl"])
        await tester.close()

    async def test_test_single_target_with_session_should_reject_intercept_page(self):
        tester = AsyncHttpTester(self.config, self.logger)
        target = "https://example.com/welcome"
        tester._target_baselines[target] = BaselineFingerprint(
            host="example.com",
            title="Example Domain",
            content_type_prefix="text/html",
            median_body_length=1200,
            median_text_length=320,
            keywords=["Example Domain"],
        )
        session = FakeSession(
            FakeResponse(
                status=200,
                url="https://blocked.invalid/firewall",
                content_type="text/html; charset=utf-8",
                body=b"<html><head><title>Access Denied</title></head><body>blocked</body></html>",
            )
        )

        result = await tester._test_single_target_with_session(session, target, "http://1.1.1.1:8080")

        self.assertFalse(result.success)
        self.assertIn("host_mismatch", result.error)
        self.assertIn("keyword_miss", result.error)
        await tester.close()

    async def test_test_proxy_async_should_skip_targets_without_baseline(self):
        self.config.TEST_TARGETS = ["https://target-a.example", "https://target-b.example"]
        tester = AsyncHttpTester(self.config, self.logger)
        tester._target_baselines = {
            "https://target-a.example": BaselineFingerprint(
                host="target-a.example",
                title="A",
                content_type_prefix="text/html",
                median_body_length=100,
                median_text_length=80,
                keywords=["A"],
            )
        }
        tester._ensure_target_baselines = AsyncMock()
        tester._test_single_target_with_session = AsyncMock(
            return_value=TargetResult(
                target="https://target-a.example",
                success=True,
                response_time=0.2,
                status_code=200,
            )
        )

        with patch("src.testers.async_tester.aiohttp.ClientSession", return_value=FakeClientSession()):
            result = await tester.test_proxy_async("1.1.1.1", 8080, "http")

        self.assertEqual(result.total_targets, 1)
        self.assertEqual(result.success_count, 1)
        tester._test_single_target_with_session.assert_awaited_once()
        self.assertEqual(
            tester._test_single_target_with_session.await_args_list[0].args[1],
            "https://target-a.example",
        )
        await tester.close()

    async def test_apply_runtime_config_should_clear_cached_baselines(self):
        tester = AsyncHttpTester(self.config, self.logger)
        tester._target_baselines = {
            "https://example.com": BaselineFingerprint(
                host="example.com",
                title="Example",
                content_type_prefix="text/html",
                median_body_length=100,
                median_text_length=80,
                keywords=["Example"],
            )
        }
        tester._unhealthy_targets = {"https://down.example"}
        self.config.TEST_TIMEOUT_PER_TARGET = 9
        self.config.TEST_TARGETS = ["https://new.example"]

        tester.apply_runtime_config(["TEST_TIMEOUT_PER_TARGET", "TEST_TARGETS"])

        self.assertEqual(tester.timeout.total, 9)
        self.assertEqual(tester.targets, ["https://new.example"])
        self.assertEqual(tester._target_baselines, {})
        self.assertEqual(tester._unhealthy_targets, set())
        await tester.close()

    async def test_test_proxy_should_require_b_grade_or_above(self):
        self.config.TEST_TARGETS = [
            "https://a.example",
            "https://b.example",
            "https://c.example",
            "https://d.example",
        ]
        tester = AsyncHttpTester(self.config, self.logger)
        tester.test_proxy_async = AsyncMock(
            return_value=MultiTargetTestResult(
                [
                    TargetResult("https://a.example", True, 0.2, 200),
                    TargetResult("https://b.example", False, 0, error="Timeout"),
                    TargetResult("https://c.example", False, 0, error="Timeout"),
                    TargetResult("https://d.example", False, 0, error="Timeout"),
                ],
                0.2,
            )
        )
        result = await asyncio.to_thread(tester.test_proxy, "1.1.1.1", 8080, "http")

        self.assertFalse(result["success"])
        self.assertIn("B级及以上", result["error_message"])
        await tester.close()


class FakeResponse:
    def __init__(self, *, status: int, url: str, content_type: str, body: bytes, charset: str = "utf-8"):
        self.status = status
        self.url = url
        self.headers = {"Content-Type": content_type}
        self.charset = charset
        self._body = body

    async def read(self):
        return self._body


class FakeRequestContextManager:
    def __init__(self, response: FakeResponse):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeSession:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.last_kwargs = {}

    def get(self, *args, **kwargs):
        self.last_kwargs = kwargs
        return FakeRequestContextManager(self.response)


class FakeClientSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


if __name__ == "__main__":
    unittest.main()
