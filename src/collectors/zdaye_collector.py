import requests
import json
from typing import List, Optional
from src.database.models import Proxy
from src.collectors.base_collector import BaseCollector
from src.logger import setup_logging # 导入 setup_logging 模块
# from src.config import config # 不再全局导入 config
# 不再需要 hashlib 和 time 模块，因为 akey 已经加密完成，且接口文档未提及 timestamp/signature

# logger = logging.getLogger("ProxyPoolMaster") # 不再在此处获取全局 logger 实例

class ZdayeCollector(BaseCollector):
    """
    从 www.zdaye.com 网站的 API 接口收集免费代理。
    该收集器属于 legacy 内置收集器，需要配置 ZDAYE_APP_ID 和 ZDAYE_AKEY。
    API 文档: https://www.zdaye.com/doc/api/FreeProxy_get
    """
    API_URL = "http://www.zdopen.com/FreeProxy/Get/" # 更正为正确的 API 地址

    def __init__(self, config_instance, logger_instance): # 接收 config 和 logger 实例
        super().__init__()
        self.config = config_instance
        self.logger = logger_instance

        if not self.config.ZDAYE_APP_ID or not self.config.ZDAYE_AKEY:
            self.logger.error("Legacy ZdayeCollector requires ZDAYE_APP_ID and ZDAYE_AKEY. Collector will stay disabled.")
        else:
            self.logger.info("Legacy ZdayeCollector initialized with API credentials.")

    # _generate_signature 方法不再需要

    def fetch_proxies(self) -> List[Proxy]:
        """
        通过调用 Zdaye API 接口抓取并解析代理信息。
        """
        proxies: List[Proxy] = []
        if not self.config.ZDAYE_APP_ID or not self.config.ZDAYE_AKEY:
            self.logger.error("Legacy ZdayeCollector is missing ZDAYE_APP_ID or ZDAYE_AKEY. Cannot fetch proxies from Zdaye API.")
            return proxies

        try:
            params = {
                "count": 100,  # 每次获取代理最大数量
                "app_id": self.config.ZDAYE_APP_ID,
                "akey": self.config.ZDAYE_AKEY, # 直接传递已加密的 akey
                "dalu": 1,        # 区域选择，1 -> 大陆
                "return_type": 3  # 返回类型，3 -> JSON
            }

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }

            self.logger.info(f"Fetching proxies from legacy Zdaye API: {self.API_URL}")
            response = requests.get(self.API_URL, params=params, headers=headers, timeout=self.config.REQUEST_TIMEOUT)
            response.raise_for_status() # 如果请求失败，抛出 HTTPError

            data = response.json()
            self.logger.debug(f"Zdaye API raw response: {data}") # 打印完整的原始响应

            if data.get("code") == "10001" and data.get("data") and data["data"].get("proxy_list"): # 检查 code 和 proxy_list
                for item in data["data"]["proxy_list"]: # 代理列表在 proxy_list 里
                    try:
                        ip = item.get("ip")
                        port = int(item.get("port"))
                        protocol_str = item.get("protocol")
                        anonymity_str  = item.get("level")
                        # 站大爷API返回的是地理位置字符串，统一设置为CN（中国）
                        country_code = "CN"  # 统一设置为中国

                        proxy = Proxy(
                            ip=ip,
                            port=port,
                            protocol=protocol_str,
                            country_code=country_code,
                            anonymity_level=anonymity_str
                        )
                        proxies.append(proxy)
                    except Exception as e:
                        self.logger.warning(f"Failed to parse proxy item from Zdaye API: {item}. Error: {e}")
                        continue
                self.logger.info(f"Successfully fetched {len(proxies)} proxies from Zdaye API.")
            else:
                error_msg = data.get('msg', 'Unknown error')
                error_code = data.get('code', 'N/A')
                self.logger.error(f"Failed to fetch proxies from Zdaye API. Code: {error_code}, Message: {error_msg}")

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to fetch proxies from Zdaye API: {e}")
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to decode JSON response from Zdaye API: {e}. Response text: {response.text[:200] if response else 'N/A'}")
        except Exception as e:
            self.logger.error(f"An unexpected error occurred while collecting proxies from Zdaye API: {e}")
        
        return proxies

if __name__ == "__main__":
    # 模拟 config 对象
    class MockConfig:
        ZDAYE_APP_ID = "YOUR_APP_ID"  # 替换为你的 App ID
        ZDAYE_AKEY = "YOUR_AKEY"      # 替换为你的 AKey
        REQUEST_TIMEOUT = 10
        LOG_LEVEL = "DEBUG" # 测试时使用 DEBUG 级别

    # 创建临时的 config 和 logger 实例用于测试
    mock_config_instance = MockConfig()
    mock_logger_instance = logging.getLogger("ProxyPoolMaster_Test")
    mock_logger_instance.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    mock_logger_instance.addHandler(handler)

    collector = ZdayeCollector(mock_config_instance, mock_logger_instance)
    if mock_config_instance.ZDAYE_APP_ID == "YOUR_APP_ID":
        mock_logger_instance.warning("Please replace YOUR_APP_ID and YOUR_AKEY in src/config.py or environment variables for actual API testing.")
    else:
        fetched_proxies = collector.fetch_proxies()
        mock_logger_instance.info(f"Test run: Fetched {len(fetched_proxies)} proxies.")
        for p in fetched_proxies[:5]: # 打印前5个代理
            mock_logger_instance.info(p)
