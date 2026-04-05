# src/utils/country_mapper.py
"""
国家/地区代码与中文名称映射工具
"""

import json
import os
from typing import Dict, Optional


class CountryMapper:
    """
    国家/地区代码映射器
    支持 ISO 3166-1 alpha-2 代码到中文名称的映射
    """
    
    _instance = None
    _country_map: Dict[str, str] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_mapping()
        return cls._instance
    
    def _load_mapping(self):
        """加载国家代码映射文件"""
        try:
            # 获取项目根目录
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            mapping_file = os.path.join(base_dir, "collectors", "data", "country_code_to_zh.json")
            
            with open(mapping_file, "r", encoding="utf-8") as f:
                self._country_map = json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load country mapping file: {e}")
            self._country_map = {}
    
    def to_chinese(self, country_code: str) -> str:
        """
        将国家/地区代码转换为中文名称
        
        Args:
            country_code: ISO 3166-1 alpha-2 代码或中文名称
            
        Returns:
            中文名称，如果无法转换则返回原值
        """
        if not country_code:
            return "未知"
        
        country_code = country_code.strip().upper()
        
        # 如果已经是中文（不包含英文字母），直接返回
        if not any(c.isascii() and c.isalpha() for c in country_code):
            return country_code
        
        # 查找映射
        return self._country_map.get(country_code, country_code)
    
    def get_mapping(self) -> Dict[str, str]:
        """获取完整的映射字典"""
        return self._country_map.copy()


# 全局映射器实例
country_mapper = CountryMapper()


def to_chinese_country(country_code: str) -> str:
    """
    便捷函数：将国家/地区代码转换为中文名称
    
    Args:
        country_code: ISO 3166-1 alpha-2 代码或中文名称
        
    Returns:
        中文名称
    """
    return country_mapper.to_chinese(country_code)
