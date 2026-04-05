SCRAPE_TEMPLATE = '''import requests
from bs4 import BeautifulSoup
from typing import List
from src.database.models import Proxy
from src.collectors.base_collector import BaseCollector


class {{COLLECTOR_CLASS_NAME}}(BaseCollector):
    """
    {{COLLECTOR_NAME}}
    通过网页抓取获取代理列表
    """
    
    def __init__(self, config_instance, logger_instance):
        super().__init__()
        self.config = config_instance
        self.logger = logger_instance
    
    def fetch_proxies(self) -> List[Proxy]:
        """
        从网页抓取代理列表
        
        配置项（在 Web UI 环境变量中设置）：
        - TARGET_URL: 目标网页 URL
        
        Returns:
            List[Proxy]: 代理对象列表
        """
        proxies: List[Proxy] = []
        
        # 从环境变量读取配置
        target_url = self.env.get("TARGET_URL", "https://www.example.com/free-proxy-list")
        
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            self.logger.info(f"Fetching proxies from: {target_url}")
            
            response = requests.get(
                target_url,
                headers=headers,
                timeout=self.config.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            
            # 解析 HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # TODO: 根据实际网页结构修改选择器
            # 示例：查找表格中的代理
            rows = soup.select('table.proxy-table tr')[1:]  # 跳过表头
            
            for row in rows:
                try:
                    cols = row.find_all('td')
                    if len(cols) >= 2:
                        ip = cols[0].text.strip()
                        port = int(cols[1].text.strip())
                        
                        # 可选字段
                        protocol = cols[2].text.strip().lower() if len(cols) > 2 else "http"
                        country = cols[3].text.strip() if len(cols) > 3 else "Unknown"
                        anonymity = cols[4].text.strip() if len(cols) > 4 else "Unknown"
                        
                        proxy = Proxy(
                            ip=ip,
                            port=port,
                            protocol=protocol,
                            country_code=country,
                            anonymity_level=anonymity
                        )
                        proxies.append(proxy)
                        
                except Exception as e:
                    self.logger.warning(f"解析行失败: {row}, 错误: {e}")
                    continue
            
            self.logger.info(f"成功获取 {len(proxies)} 个代理")
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"请求页面失败: {e}")
        except Exception as e:
            self.logger.error(f"意外错误: {e}")
        
        return proxies
'''
