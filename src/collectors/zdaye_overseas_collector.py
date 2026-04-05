# src/collectors/zdaye_overseas_collector.py

import requests
import json
import os
from typing import List, Dict
from src.database.models import Proxy
from src.collectors.zdaye_collector import ZdayeCollector


class ZdayeOverseasCollector(ZdayeCollector):
    """
    从 www.zdaye.com 网站的 API 接口收集海外免费代理。
    该收集器属于 legacy 内置收集器，需要配置 ZDAYE_APP_ID 和 ZDAYE_AKEY。
    API 文档: https://www.zdaye.com/doc/api/FreeProxy_get
    
    与 ZdayeCollector 的区别：
    - dalu 参数设为 0（海外代理）
    - 从 adr 字段提取国家/地区信息
    """
    
    def __init__(self, config_instance, logger_instance):
        super().__init__(config_instance, logger_instance)
        self.logger.info("Legacy ZdayeOverseasCollector initialized for overseas proxies.")
        # 加载国家/地区列表
        self.country_list = self._load_country_list()
        # 加载国家代码反向映射
        self._country_name_to_code_map = self._load_country_mapping()
    
    def _load_country_list(self) -> List[str]:
        """加载国家/地区名称列表"""
        try:
            data_dir = os.path.dirname(os.path.abspath(__file__))
            country_file = os.path.join(data_dir, "data", "countries_zh.json")
            with open(country_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            self.logger.warning(f"Failed to load country list: {e}. Using empty list.")
            return []

    def _load_country_mapping(self) -> Dict[str, str]:
        """加载国家代码映射并构建反向映射"""
        try:
            data_dir = os.path.dirname(os.path.abspath(__file__))
            mapping_file = os.path.join(data_dir, "data", "country_code_to_zh.json")
            with open(mapping_file, "r", encoding="utf-8") as f:
                code_to_name = json.load(f)
            # 构建反向映射：中文名 → ISO代码
            return {v: k for k, v in code_to_name.items()}
        except Exception as e:
            self.logger.warning(f"Failed to load country mapping: {e}")
            return {}

    def _country_name_to_code(self, name: str) -> str:
        """将中文国家名转换为ISO代码"""
        if not name:
            return "Unknown"
        return self._country_name_to_code_map.get(name, name)
    
    def _extract_country_from_adr(self, adr: str) -> str:
        """
        从 adr 字段提取国家/地区
        方案B：匹配国家关键词列表
        
        示例：
        - "韩国 KT电信" -> "韩国"
        - "德国" -> "德国"
        - "日本东京 Amazon数据中心" -> "日本"
        """
        if not adr:
            return ""
        
        # 优先匹配国家列表中的关键词（优先匹配较长的名称）
        sorted_countries = sorted(self.country_list, key=len, reverse=True)
        for country in sorted_countries:
            if country in adr:
                return country
        
        # 未匹配到，返回adr的第一个部分（按空格分割）
        return adr.split()[0] if " " in adr else adr

    def fetch_proxies(self) -> List[Proxy]:
        """
        通过调用 Zdaye API 接口抓取并解析海外代理信息。
        """
        proxies: List[Proxy] = []
        if not self.config.ZDAYE_APP_ID or not self.config.ZDAYE_AKEY:
            self.logger.error("Legacy ZdayeOverseasCollector is missing ZDAYE_APP_ID or ZDAYE_AKEY. Cannot fetch overseas proxies from Zdaye API.")
            return proxies

        try:
            params = {
                "count": 100,  # 每次获取代理最大数量
                "app_id": self.config.ZDAYE_APP_ID,
                "akey": self.config.ZDAYE_AKEY,
                "dalu": 0,        # 区域选择，0 -> 海外
                "return_type": 3  # 返回类型，3 -> JSON
            }

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }

            self.logger.info(f"Fetching overseas proxies from legacy Zdaye API: {self.API_URL}")
            response = requests.get(self.API_URL, params=params, headers=headers, timeout=self.config.REQUEST_TIMEOUT)
            response.raise_for_status()

            data = response.json()
            self.logger.debug(f"Zdaye API raw response: {data}")

            if data.get("code") == "10001" and data.get("data") and data["data"].get("proxy_list"):
                for item in data["data"]["proxy_list"]:
                    try:
                        ip = item.get("ip")
                        port = int(item.get("port"))
                        protocol_str = item.get("protocol")
                        anonymity_str = item.get("level")
                        
                        # 海外代理：从 adr 字段提取国家/地区
                        adr = item.get("adr", "")
                        country_name = self._extract_country_from_adr(adr)
                        # 转换为ISO代码
                        country_code = self._country_name_to_code(country_name)

                        proxy = Proxy(
                            ip=ip,
                            port=port,
                            protocol=protocol_str,
                            country_code=country_code,  # 使用ISO代码
                            anonymity_level=anonymity_str
                        )
                        proxies.append(proxy)
                    except Exception as e:
                        self.logger.warning(f"Failed to parse proxy item from Zdaye API: {item}. Error: {e}")
                        continue
                self.logger.info(f"Successfully fetched {len(proxies)} overseas proxies from Zdaye API.")
            else:
                error_msg = data.get("msg", "Unknown error")
                error_code = data.get("code", "N/A")
                self.logger.error(f"Failed to fetch overseas proxies from Zdaye API. Code: {error_code}, Message: {error_msg}")

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to fetch overseas proxies from Zdaye API: {e}")
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to decode JSON response from Zdaye API: {e}")
        except Exception as e:
            self.logger.error(f"An unexpected error occurred while collecting overseas proxies from Zdaye API: {e}")
        
        return proxies


if __name__ == "__main__":
    import logging
    import sys

    # 设置测试日志
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    test_logger = logging.getLogger("ZdayeOverseasCollector_Test")

    # 模拟 config 对象
    class MockConfig:
        ZDAYE_APP_ID = "YOUR_APP_ID"
        ZDAYE_AKEY = "YOUR_AKEY"
        REQUEST_TIMEOUT = 10
        LOG_LEVEL = "DEBUG"

    mock_config_instance = MockConfig()
    collector = ZdayeOverseasCollector(mock_config_instance, test_logger)
    
    # 测试国家提取逻辑
    test_cases = [
        "韩国 KT电信",
        "德国",
        "日本东京 Amazon数据中心",
        "新加坡",
        "美国洛杉矶",
        "英国伦敦",
        "澳大利亚悉尼",
    ]
    
    print("\n=== Country Extraction Test ===")
    for adr in test_cases:
        country = collector._extract_country_from_adr(adr)
        print(f"'{adr}' -> '{country}'")

    print("\n=== Country Name to Code Test ===")
    test_names = ["韩国", "德国", "日本", "美国", "未知国家"]
    for name in test_names:
        code = collector._country_name_to_code(name)
        print(f"'{name}' -> '{code}'")
    
    print("\n=== API Test ===")
    if mock_config_instance.ZDAYE_APP_ID == "YOUR_APP_ID":
        test_logger.warning("Please replace YOUR_APP_ID and YOUR_AKEY for actual API testing.")
    else:
        fetched_proxies = collector.fetch_proxies()
        test_logger.info(f"Test run: Fetched {len(fetched_proxies)} overseas proxies.")
        for p in fetched_proxies[:5]:
            test_logger.info(f"{p.ip}:{p.port} ({p.protocol}) - {p.country_code} - {p.anonymity_level}")
