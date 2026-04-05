import unittest
from src.collectors.base_collector import BaseCollector
from src.database.models import Proxy
from typing import List


class MockCollector(BaseCollector):
    """测试用的模拟收集器"""
    
    def fetch_proxies(self) -> List[Proxy]:
        return [Proxy(ip="192.168.1.1", port=8080)]


class TestBaseCollector(unittest.TestCase):
    
    def test_set_env_vars(self):
        """测试设置环境变量"""
        collector = MockCollector()
        
        env_vars = {
            "API_KEY": {"value": "secret123", "is_secret": True},
            "ENDPOINT": {"value": "https://api.com", "is_secret": False}
        }
        
        collector.set_env_vars(env_vars)
        
        self.assertEqual(collector.env["API_KEY"], "secret123")
        self.assertEqual(collector.env["ENDPOINT"], "https://api.com")
    
    def test_get_env_with_default(self):
        """测试获取环境变量带默认值"""
        collector = MockCollector()
        collector.set_env_vars({"EXISTING": {"value": "value"}})
        
        self.assertEqual(collector.get_env("EXISTING"), "value")
        self.assertEqual(collector.get_env("MISSING"), "")
        self.assertEqual(collector.get_env("MISSING", "default"), "default")
    
    def test_env_empty_dict(self):
        """测试空环境变量"""
        collector = MockCollector()
        collector.set_env_vars({})
        
        self.assertEqual(collector.env, {})
        self.assertEqual(collector.get_env("ANY"), "")


if __name__ == "__main__":
    unittest.main()
