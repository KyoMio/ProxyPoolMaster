import os
import sys
import importlib.util
import inspect
from typing import Type, Optional
from src.collectors.base_collector import BaseCollector


class CollectorDynamicLoader:
    """动态加载用户自定义收集器"""
    
    CUSTOM_COLLECTORS_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data",
        "custom_collectors",
    )
    
    @classmethod
    def ensure_directory(cls):
        """确保收集器目录存在"""
        os.makedirs(cls.CUSTOM_COLLECTORS_DIR, exist_ok=True)
        init_file = os.path.join(cls.CUSTOM_COLLECTORS_DIR, "__init__.py")
        if not os.path.exists(init_file):
            with open(init_file, "w", encoding='utf-8') as f:
                f.write("# Custom collectors package\n")
    
    @classmethod
    def load_collector_class(cls, filename: str) -> Optional[Type[BaseCollector]]:
        """从文件动态加载收集器类"""
        filepath = os.path.join(cls.CUSTOM_COLLECTORS_DIR, filename)
        
        if not os.path.exists(filepath):
            return None
        
        try:
            module_name = filename[:-3]  # 去掉 .py
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            if not spec or not spec.loader:
                return None
            
            module = importlib.util.module_from_spec(spec)
            
            # 确保目录在 sys.path 中
            if cls.CUSTOM_COLLECTORS_DIR not in sys.path:
                sys.path.insert(0, cls.CUSTOM_COLLECTORS_DIR)
            
            spec.loader.exec_module(module)
            
            # 查找继承自 BaseCollector 的类
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (issubclass(obj, BaseCollector) and 
                    obj != BaseCollector and
                    obj.__module__ == module.__name__):
                    return obj
            
            return None
            
        except Exception as e:
            print(f"Failed to load collector from {filename}: {e}")
            return None
    
    @classmethod
    def validate_code(cls, code: str) -> tuple[bool, str]:
        """验证收集器代码语法和基本结构"""
        try:
            # 语法检查
            compile(code, '<string>', 'exec')
            
            # 检查是否包含必要的基类引用
            if 'BaseCollector' not in code:
                return False, "代码必须继承 BaseCollector 基类"
            
            if 'fetch_proxies' not in code:
                return False, "代码必须实现 fetch_proxies 方法"
            
            return True, ""
            
        except SyntaxError as e:
            return False, f"语法错误: {e.msg} (第{e.lineno}行)"
        except Exception as e:
            return False, str(e)
    
    @classmethod
    def save_collector_file(cls, filename: str, code: str) -> bool:
        """保存收集器代码到文件"""
        try:
            cls.ensure_directory()
            filepath = os.path.join(cls.CUSTOM_COLLECTORS_DIR, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(code)
            return True
        except Exception as e:
            print(f"Failed to save collector file: {e}")
            return False
    
    @classmethod
    def delete_collector_file(cls, filename: str) -> bool:
        """删除收集器文件"""
        try:
            filepath = os.path.join(cls.CUSTOM_COLLECTORS_DIR, filename)
            if os.path.exists(filepath):
                os.remove(filepath)
            return True
        except Exception as e:
            print(f"Failed to delete collector file: {e}")
            return False
