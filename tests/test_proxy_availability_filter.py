"""
测试代理可用性过滤功能
"""
import unittest
from unittest.mock import MagicMock, patch
import logging
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.models import Proxy
from src.database.redis_client import RedisManager
from src.config import Config


class TestProxyAvailabilityFilter(unittest.TestCase):
    """测试代理可用性过滤功能"""

    def setUp(self):
        """测试前的设置"""
        self.mock_config = MagicMock(spec=Config)
        self.mock_config.MAX_FAIL_COUNT = 5
        self.mock_config.LOG_LEVEL = "INFO"
        self.mock_config.LOG_FILE = "/tmp/test.log"
        self.mock_logger = logging.getLogger("test")
        self.mock_logger.setLevel(logging.DEBUG)
        self.redis_manager = RedisManager(self.mock_config, self.mock_logger)

    def test_get_random_available_proxy_with_available_proxy(self):
        """测试 get_random_available_proxy 方法正确返回可用代理"""
        # 创建测试数据
        available_proxy = Proxy(
            ip="1.1.1.1", port=8080, protocol="http",
            success_count=1, fail_count=0, grade="B"
        )
        unavailable_proxy_fail = Proxy(
            ip="2.2.2.2", port=8080, protocol="http",
            success_count=1, fail_count=5, grade="D"
        )
        unavailable_proxy_c_grade = Proxy(
            ip="3.3.3.3", port=8080, protocol="http",
            success_count=1, fail_count=0, grade="C"
        )

        with patch.object(
            self.redis_manager,
            'get_all_non_cooldown_proxies',
            return_value=[available_proxy, unavailable_proxy_fail, unavailable_proxy_c_grade],
        ):
            result = self.redis_manager.get_random_available_proxy(max_fail_count=5)
            # 应该只返回 B 级及以上代理
            self.assertIsNotNone(result)
            self.assertEqual(result.ip, "1.1.1.1")

    def test_get_random_available_proxy_no_verified_but_pending(self):
        """测试当没有已验证代理但有待测试代理时，降级返回待测试代理"""
        # 创建测试数据 - 没有已验证的，但有待测试的
        unavailable_proxy_fail = Proxy(
            ip="2.2.2.2", port=8080, protocol="http",
            success_count=1, fail_count=5, grade="D"  # 已失败，不可用
        )
        pending_proxy = Proxy(
            ip="3.3.3.3", port=8080, protocol="http",
            success_count=0, fail_count=0, grade=""  # 待测试（测试期间状态）
        )

        with patch.object(
            self.redis_manager,
            'get_all_non_cooldown_proxies',
            return_value=[unavailable_proxy_fail, pending_proxy],
        ):
            result = self.redis_manager.get_random_available_proxy(max_fail_count=5)
            # 应该降级返回待测试代理
            self.assertIsNotNone(result)
            self.assertEqual(result.ip, "3.3.3.3")

    def test_get_random_available_proxy_all_failed(self):
        """测试当所有代理都失败时返回 None"""
        # 创建测试数据 - 所有代理都已失败
        unavailable_proxy_fail1 = Proxy(
            ip="2.2.2.2", port=8080, protocol="http",
            success_count=1, fail_count=5, grade="D"
        )
        unavailable_proxy_fail2 = Proxy(
            ip="3.3.3.3", port=8080, protocol="http",
            success_count=0, fail_count=5, grade="D"
        )

        with patch.object(
            self.redis_manager,
            'get_all_non_cooldown_proxies',
            return_value=[unavailable_proxy_fail1, unavailable_proxy_fail2],
        ):
            result = self.redis_manager.get_random_available_proxy(max_fail_count=5)
            # 所有代理都已失败，应该返回 None
            self.assertIsNone(result)

    def test_get_all_available_proxies_returns_only_available(self):
        """测试 get_all_available_proxies 方法只返回 B 级及以上代理"""
        available_proxy1 = Proxy(ip="1.1.1.1", port=8080, protocol="http", success_count=1, fail_count=0, grade="B")
        available_proxy2 = Proxy(ip="2.2.2.2", port=8080, protocol="http", success_count=1, fail_count=2, grade="S")
        unavailable_proxy = Proxy(ip="3.3.3.3", port=8080, protocol="http", success_count=1, fail_count=0, grade="C")

        with patch.object(
            self.redis_manager,
            'get_all_non_cooldown_proxies',
            return_value=[available_proxy1, available_proxy2, unavailable_proxy],
        ):
            result = self.redis_manager.get_all_available_proxies(max_fail_count=5)
            self.assertEqual(len(result), 2)
            ips = [p.ip for p in result]
            self.assertIn("1.1.1.1", ips)
            self.assertIn("2.2.2.2", ips)
            self.assertNotIn("3.3.3.3", ips)

    def test_get_all_available_proxies_empty(self):
        """测试当没有代理时返回空列表"""
        with patch.object(self.redis_manager, 'get_all_non_cooldown_proxies', return_value=[]):
            result = self.redis_manager.get_all_available_proxies(max_fail_count=5)
            self.assertEqual(len(result), 0)
            self.assertIsInstance(result, list)

    def test_proxy_availability_with_different_fail_counts(self):
        """测试不同 fail_count 值的可用性判断"""
        # 测试边界值
        proxy_fail_4 = Proxy(ip="1.1.1.1", port=8080, protocol="http", success_count=1, fail_count=4, grade="B")  # 可用
        proxy_fail_5 = Proxy(ip="2.2.2.2", port=8080, protocol="http", success_count=1, fail_count=5, grade="A")  # 不可用
        proxy_fail_0 = Proxy(ip="3.3.3.3", port=8080, protocol="http", success_count=1, fail_count=0, grade="C")  # 不可用

        with patch.object(
            self.redis_manager,
            'get_all_non_cooldown_proxies',
            return_value=[proxy_fail_4, proxy_fail_5, proxy_fail_0],
        ):
            result = self.redis_manager.get_all_available_proxies(max_fail_count=5)
            self.assertEqual(len(result), 1)
            ips = [p.ip for p in result]
            self.assertIn("1.1.1.1", ips)  # fail_count=4 < 5，可用
            self.assertNotIn("2.2.2.2", ips)  # fail_count=5，不可用
            self.assertNotIn("3.3.3.3", ips)  # C级不再属于可用代理


class TestProxyIsAvailableLogic(unittest.TestCase):
    """测试代理可用性判断逻辑"""

    def test_proxy_is_available_c_grade_should_be_false(self):
        """测试 C 级代理不属于可用代理"""
        proxy = Proxy(ip="1.1.1.1", port=8080, protocol="http", success_count=1, fail_count=0, grade="C")
        is_available = proxy.grade in {"S", "A", "B"} and proxy.fail_count < 5
        self.assertFalse(is_available)

    def test_proxy_is_available_b_grade_should_be_true(self):
        """测试 B 级及以上且 fail_count<5 的代理可用"""
        proxy = Proxy(ip="1.1.1.1", port=8080, protocol="http", success_count=1, fail_count=0, grade="B")
        is_available = proxy.grade in {"S", "A", "B"} and proxy.fail_count < 5
        self.assertTrue(is_available)

    def test_proxy_is_available_fail_count_at_limit(self):
        """测试 fail_count=5 的代理不可用"""
        proxy = Proxy(ip="1.1.1.1", port=8080, protocol="http", success_count=5, fail_count=5, grade="S")
        is_available = proxy.grade in {"S", "A", "B"} and proxy.fail_count < 5
        self.assertFalse(is_available)

    def test_proxy_is_available_fail_count_over_limit(self):
        """测试 fail_count>5 的代理不可用"""
        proxy = Proxy(ip="1.1.1.1", port=8080, protocol="http", success_count=10, fail_count=6, grade="A")
        is_available = proxy.grade in {"S", "A", "B"} and proxy.fail_count < 5
        self.assertFalse(is_available)


if __name__ == "__main__":
    unittest.main()
