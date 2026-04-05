import unittest
from unittest.mock import Mock, MagicMock, patch
from src.collectors.safe_executor import SafeCollectorExecutor
from src.database.models import Proxy


class TestSafeCollectorExecutor(unittest.TestCase):
    
    def setUp(self):
        """设置测试环境"""
        self.mock_collector = Mock()
        self.mock_config = Mock()
        self.mock_config.COLLECTOR_EXEC_TIMEOUT = 5
        self.mock_logger = Mock()
        self.mock_redis = Mock()
        self.mock_redis.store_proxy = Mock(
            return_value={
                "stored": True,
                "created": True,
                "proxy_key": "proxy:http:192.168.1.1:8080",
            }
        )
        self.mock_redis.add_proxy = Mock(return_value=True)
        
        self.executor = SafeCollectorExecutor(
            self.mock_collector,
            "test_collector",
            self.mock_config,
            self.mock_logger,
            self.mock_redis
        )
    
    def test_execute_success(self):
        """测试成功执行"""
        # 模拟返回有效代理
        self.mock_collector.fetch_proxies.return_value = [
            Proxy(ip="192.168.1.1", port=8080),
            Proxy(ip="192.168.1.2", port=8081),
        ]
        
        report = self.executor.execute()
        
        self.assertTrue(report["success"])
        self.assertEqual(report["raw_count"], 2)
        self.assertEqual(report["valid_count"], 2)
        self.assertEqual(report["stored_count"], 2)
        self.assertEqual(len(report["validation_errors"]), 0)
    
    def test_execute_with_invalid_data(self):
        """测试包含无效数据的执行"""
        self.mock_collector.fetch_proxies.return_value = [
            Proxy(ip="192.168.1.1", port=8080),
            {"ip": "192.168.1.2"},  # 缺少 port
            Proxy(ip="192.168.1.3", port=99999),  # 无效端口
        ]
        
        report = self.executor.execute()
        
        self.assertTrue(report["success"])  # 整体成功（部分有效）
        self.assertEqual(report["raw_count"], 3)
        self.assertEqual(report["valid_count"], 1)
        self.assertEqual(report["invalid"], 2)
        self.assertEqual(len(report["validation_errors"]), 2)
    
    def test_execute_returns_non_list(self):
        """测试返回非列表"""
        self.mock_collector.fetch_proxies.return_value = "not a list"
        
        report = self.executor.execute()
        
        self.assertFalse(report["success"])
        self.assertIn("列表", report["exception"])
    
    def test_execute_returns_none(self):
        """测试返回 None"""
        self.mock_collector.fetch_proxies.return_value = None
        
        report = self.executor.execute()
        
        self.assertFalse(report["success"])
        self.assertIn("列表", report["exception"])
    
    def test_execute_with_exception(self):
        """测试执行抛出异常"""
        self.mock_collector.fetch_proxies.side_effect = Exception("Test error")
        
        report = self.executor.execute()
        
        self.assertFalse(report["success"])
        self.assertIn("Test error", report["exception"])
    
    def test_execute_with_storage_error(self):
        """测试存储错误"""
        self.mock_collector.fetch_proxies.return_value = [
            Proxy(ip="192.168.1.1", port=8080),
        ]
        self.mock_redis.store_proxy.side_effect = Exception("Redis error")

        report = self.executor.execute()
        
        self.assertFalse(report["success"])
        self.assertEqual(len(report["storage_errors"]), 1)
        self.assertIn("Redis error", report["storage_errors"][0])
    
    def test_duplicate_detection(self):
        """测试重复检测"""
        self.mock_collector.fetch_proxies.return_value = [
            Proxy(ip="192.168.1.1", port=8080),
        ]
        self.mock_redis.store_proxy.return_value = {
            "stored": False,
            "created": False,
            "proxy_key": "proxy:http:192.168.1.1:8080",
        }

        report = self.executor.execute()
        
        self.assertEqual(report["stored_count"], 0)
        self.assertEqual(report["duplicate_count"], 1)

    def test_execute_should_skip_cooldown_blocked_proxy_without_counting_duplicate_or_failure(self):
        """测试冷却代理会被跳过，不计入重复或失败"""
        self.mock_collector.fetch_proxies.return_value = [
            Proxy(ip="192.168.1.3", port=8082),
        ]
        self.mock_redis.store_proxy.return_value = {
            "stored": False,
            "created": False,
            "proxy_key": "proxy:http:192.168.1.3:8082",
            "cooldown_blocked": True,
        }

        report = self.executor.execute()

        self.assertTrue(report["success"])
        self.assertEqual(report["stored_count"], 0)
        self.assertEqual(report["duplicate_count"], 0)
        self.assertEqual(report["cooldown_blocked_count"], 1)
        self.mock_redis.store_proxy.assert_called_once()
        self.mock_redis.add_proxy.assert_not_called()

    def test_execute_should_use_shared_cooldown_helper(self):
        """测试执行器通过共享 helper 处理冷却感知存储"""
        proxy = Proxy(ip="192.168.1.4", port=8083)
        self.mock_collector.fetch_proxies.return_value = [proxy]

        with patch(
            "src.collectors.safe_executor.store_proxy_with_cooldown_awareness",
            return_value={
                "stored": False,
                "created": False,
                "proxy_key": "proxy:http:192.168.1.4:8083",
                "cooldown_blocked": True,
            },
        ) as mock_helper:
            report = self.executor.execute()

        mock_helper.assert_called_once_with(self.mock_redis, proxy)
        self.assertEqual(report["cooldown_blocked_count"], 1)
        self.assertEqual(report["stored_count"], 0)
        self.assertEqual(report["duplicate_count"], 0)
        self.mock_redis.store_proxy.assert_not_called()
        self.mock_redis.add_proxy.assert_not_called()


if __name__ == "__main__":
    unittest.main()
