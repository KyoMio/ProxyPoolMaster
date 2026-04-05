"""
测试 API 限流配置
"""
import unittest
from unittest.mock import patch
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import Config


class TestRateLimitConfig(unittest.TestCase):
    """测试限流配置"""

    def test_default_rate_limit_values(self):
        """测试默认限流配置值"""
        config = Config()
        
        # 检查默认值
        self.assertEqual(config.RATE_LIMIT_PROXY_MINUTE, "60/minute")
        self.assertEqual(config.RATE_LIMIT_HEALTH_MINUTE, "30/minute")

    @patch.dict(os.environ, {"RATE_LIMIT_PROXY_MINUTE": "120/minute"})
    def test_proxy_rate_limit_from_env(self):
        """测试从环境变量读取代理接口限流配置"""
        config = Config()
        self.assertEqual(config.RATE_LIMIT_PROXY_MINUTE, "120/minute")

    @patch.dict(os.environ, {"RATE_LIMIT_HEALTH_MINUTE": "10/minute"})
    def test_health_rate_limit_from_env(self):
        """测试从环境变量读取健康检查接口限流配置"""
        config = Config()
        self.assertEqual(config.RATE_LIMIT_HEALTH_MINUTE, "10/minute")

    @patch.dict(os.environ, {
        "RATE_LIMIT_PROXY_MINUTE": "100/minute",
        "RATE_LIMIT_HEALTH_MINUTE": "50/minute"
    })
    def test_all_rate_limits_from_env(self):
        """测试同时设置两个限流配置"""
        config = Config()
        self.assertEqual(config.RATE_LIMIT_PROXY_MINUTE, "100/minute")
        self.assertEqual(config.RATE_LIMIT_HEALTH_MINUTE, "50/minute")

    def test_rate_limit_format(self):
        """测试限流配置格式正确"""
        config = Config()
        
        # 验证格式为 "数字/单位"
        proxy_limit = config.RATE_LIMIT_PROXY_MINUTE
        health_limit = config.RATE_LIMIT_HEALTH_MINUTE
        
        # 检查包含斜杠
        self.assertIn("/", proxy_limit)
        self.assertIn("/", health_limit)
        
        # 检查时间单位
        self.assertIn("minute", proxy_limit)
        self.assertIn("minute", health_limit)


if __name__ == "__main__":
    unittest.main()
