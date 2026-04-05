import unittest
import os
import tempfile
import shutil
from src.collectors.dynamic_loader import CollectorDynamicLoader
from src.collectors.base_collector import BaseCollector
from src.database.models import Proxy
from typing import List


class TestDynamicLoader(unittest.TestCase):
    
    def setUp(self):
        """设置测试环境"""
        self.test_dir = tempfile.mkdtemp()
        self.original_dir = CollectorDynamicLoader.CUSTOM_COLLECTORS_DIR
        CollectorDynamicLoader.CUSTOM_COLLECTORS_DIR = self.test_dir
        
        # 创建测试用的收集器代码
        self.test_code = '''
from src.collectors.base_collector import BaseCollector
from src.database.models import Proxy
from typing import List

class TestCollector(BaseCollector):
    def __init__(self, config, logger):
        super().__init__()
        self.config = config
        self.logger = logger
    
    def fetch_proxies(self) -> List[Proxy]:
        return [Proxy(ip="127.0.0.1", port=8080)]
'''
        self.test_filename = "test_collector.py"
        with open(os.path.join(self.test_dir, self.test_filename), 'w') as f:
            f.write(self.test_code)
    
    def tearDown(self):
        """清理测试环境"""
        shutil.rmtree(self.test_dir)
        CollectorDynamicLoader.CUSTOM_COLLECTORS_DIR = self.original_dir
    
    def test_ensure_directory(self):
        """测试确保目录存在"""
        new_dir = os.path.join(self.test_dir, "subdir")
        CollectorDynamicLoader.CUSTOM_COLLECTORS_DIR = new_dir
        CollectorDynamicLoader.ensure_directory()
        
        self.assertTrue(os.path.exists(new_dir))
        self.assertTrue(os.path.exists(os.path.join(new_dir, "__init__.py")))
    
    def test_load_collector_class(self):
        """测试加载收集器类"""
        collector_class = CollectorDynamicLoader.load_collector_class(self.test_filename)
        
        self.assertIsNotNone(collector_class)
        self.assertTrue(issubclass(collector_class, BaseCollector))
        self.assertEqual(collector_class.__name__, "TestCollector")
    
    def test_load_nonexistent_file(self):
        """测试加载不存在的文件"""
        result = CollectorDynamicLoader.load_collector_class("nonexistent.py")
        self.assertIsNone(result)
    
    def test_validate_valid_code(self):
        """测试验证有效代码"""
        valid_code = '''
from src.collectors.base_collector import BaseCollector
class MyCollector(BaseCollector):
    def fetch_proxies(self):
        return []
'''
        is_valid, error = CollectorDynamicLoader.validate_code(valid_code)
        self.assertTrue(is_valid)
        self.assertEqual(error, "")
    
    def test_validate_syntax_error(self):
        """测试验证语法错误"""
        invalid_code = "def broken("
        is_valid, error = CollectorDynamicLoader.validate_code(invalid_code)
        self.assertFalse(is_valid)
        self.assertIn("语法错误", error)
    
    def test_validate_missing_base(self):
        """测试验证缺少基类"""
        code_without_base = "class MyCollector:\n    def fetch_proxies(self): pass"
        is_valid, error = CollectorDynamicLoader.validate_code(code_without_base)
        self.assertFalse(is_valid)
        self.assertIn("BaseCollector", error)
    
    def test_validate_missing_method(self):
        """测试验证缺少方法"""
        code_without_method = '''
from src.collectors.base_collector import BaseCollector
class MyCollector(BaseCollector):
    pass
'''
        is_valid, error = CollectorDynamicLoader.validate_code(code_without_method)
        self.assertFalse(is_valid)
        self.assertIn("fetch_proxies", error)
    
    def test_save_collector_file(self):
        """测试保存收集器文件"""
        filename = "new_collector.py"
        code = "# test code"
        
        result = CollectorDynamicLoader.save_collector_file(filename, code)
        
        self.assertTrue(result)
        filepath = os.path.join(self.test_dir, filename)
        self.assertTrue(os.path.exists(filepath))
        with open(filepath, 'r') as f:
            self.assertEqual(f.read(), code)
    
    def test_delete_collector_file(self):
        """测试删除收集器文件"""
        filename = "to_delete.py"
        with open(os.path.join(self.test_dir, filename), 'w') as f:
            f.write("# test")
        
        result = CollectorDynamicLoader.delete_collector_file(filename)
        
        self.assertTrue(result)
        self.assertFalse(os.path.exists(os.path.join(self.test_dir, filename)))


if __name__ == "__main__":
    unittest.main()
