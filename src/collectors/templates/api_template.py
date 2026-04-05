API_TEMPLATE = '''import requests
import json
from typing import List
from src.database.models import Proxy
from src.collectors.base_collector import BaseCollector


class {{COLLECTOR_CLASS_NAME}}(BaseCollector):
    """
    {{COLLECTOR_NAME}}
    通过 API 接口获取代理列表
    """
    
    def __init__(self, config_instance, logger_instance):
        super().__init__()
        self.config = config_instance
        self.logger = logger_instance
    
    def fetch_proxies(self) -> List[Proxy]:
        """
        从 API 获取代理列表
        
        配置项（在 Web UI 环境变量中设置）：
        - API_KEY: API 认证密钥
        - API_ENDPOINT: API 端点地址
        
        Returns:
            List[Proxy]: 代理对象列表
        """
        proxies: List[Proxy] = []
        
        # 从环境变量读取配置
        api_key = self.env.get("API_KEY", "")
        api_endpoint = self.env.get("API_ENDPOINT", "https://api.example.com")
        
        if not api_key:
            self.logger.error("API_KEY 未配置，请在收集器设置中配置")
            return proxies
        
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            self.logger.info(f"Fetching proxies from API: {api_endpoint}")
            
            response = requests.get(
                f"{api_endpoint}/proxies",
                headers=headers,
                timeout=self.config.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            
            data = response.json()
            
            # 根据实际 API 响应格式解析数据
            if data.get("code") == 200 and data.get("data"):
                for item in data["data"]:
                    try:
                        proxy = Proxy(
                            ip=item.get("ip"),
                            port=int(item.get("port")),
                            protocol=item.get("protocol", "http").lower(),
                            country_code=item.get("country", "Unknown"),
                            anonymity_level=item.get("anonymity", "Unknown")
                        )
                        proxies.append(proxy)
                    except Exception as e:
                        self.logger.warning(f"解析代理项失败: {item}, 错误: {e}")
                        continue
                
                self.logger.info(f"成功获取 {len(proxies)} 个代理")
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"请求失败: {e}")
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON 解析失败: {e}")
        except Exception as e:
            self.logger.error(f"意外错误: {e}")
        
        return proxies
'''
