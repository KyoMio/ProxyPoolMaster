import unittest
from src.collectors.proxy_validator import ProxyDataValidator
from src.database.models import Proxy


class TestProxyDataValidator(unittest.TestCase):
    
    def test_validate_proxy_object_valid(self):
        """测试有效的 Proxy 对象验证"""
        proxy = Proxy(ip="192.168.1.1", port=8080, protocol="http")
        is_valid, result, error = ProxyDataValidator.validate_and_convert(proxy)
        
        self.assertTrue(is_valid)
        self.assertIsInstance(result, Proxy)
        self.assertEqual(error, "")
    
    def test_validate_dict_format_valid(self):
        """测试有效的字典格式验证"""
        data = {"ip": "192.168.1.1", "port": 8080, "protocol": "https"}
        is_valid, result, error = ProxyDataValidator.validate_and_convert(data)
        
        self.assertTrue(is_valid)
        self.assertIsInstance(result, Proxy)
        self.assertEqual(result.ip, "192.168.1.1")
        self.assertEqual(result.port, 8080)
        self.assertEqual(result.protocol, "https")
    
    def test_validate_missing_required_field(self):
        """测试缺少必填字段"""
        data = {"ip": "192.168.1.1"}  # missing port
        is_valid, result, error = ProxyDataValidator.validate_and_convert(data)
        
        self.assertFalse(is_valid)
        self.assertIsNone(result)
        self.assertIn("port", error)
    
    def test_validate_invalid_port_range(self):
        """测试端口范围无效"""
        data = {"ip": "192.168.1.1", "port": 99999}
        is_valid, result, error = ProxyDataValidator.validate_and_convert(data)
        
        self.assertFalse(is_valid)
        self.assertIn("65535", error)
    
    def test_validate_invalid_protocol(self):
        """测试无效协议"""
        data = {"ip": "192.168.1.1", "port": 8080, "protocol": "ftp"}
        is_valid, result, error = ProxyDataValidator.validate_and_convert(data)
        
        self.assertFalse(is_valid)
        self.assertIn("protocol", error.lower())
    
    def test_validate_batch(self):
        """测试批量验证"""
        data_list = [
            {"ip": "192.168.1.1", "port": 8080},
            {"ip": "192.168.1.2", "port": 8081},
            {"ip": "192.168.1.3", "port": 99999},  # invalid
        ]
        result = ProxyDataValidator.validate_batch(data_list)
        
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["valid"], 2)
        self.assertEqual(result["invalid"], 1)
        self.assertEqual(len(result["proxies"]), 2)
        self.assertEqual(len(result["errors"]), 1)
    
    def test_validate_batch_not_list(self):
        """测试批量验证传入非列表"""
        result = ProxyDataValidator.validate_batch("not a list")
        
        self.assertEqual(result["total"], 0)
        self.assertEqual(len(result["errors"]), 1)


if __name__ == "__main__":
    unittest.main()
