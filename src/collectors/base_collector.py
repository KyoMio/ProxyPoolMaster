from abc import ABC, abstractmethod
from typing import List, Dict, Any
from src.database.models import Proxy


class BaseCollector(ABC):
    """
    代理收集器的抽象基类。
    所有具体的代理收集器都必须继承此类，并实现 fetch_proxies 方法。
    """
    
    def __init__(self):
        self._env_vars: Dict[str, str] = {}
        self.config = None
        self.logger = None
    
    def set_env_vars(self, env_vars: Dict[str, Any]):
        """
        设置该收集器的环境变量
        由 Manager 在初始化时调用
        
        Args:
            env_vars: 环境变量配置字典，格式为 {"VAR_NAME": {"value": "xxx", "is_secret": bool}}
        """
        self._env_vars = {
            k: v["value"] if isinstance(v, dict) else v
            for k, v in (env_vars or {}).items()
        }
    
    @property
    def env(self) -> Dict[str, str]:
        """
        访问环境变量（类似字典）
        
        Usage:
            api_key = self.env.get("API_KEY")
        """
        return self._env_vars
    
    def get_env(self, key: str, default: str = "") -> str:
        """
        获取指定环境变量
        
        Args:
            key: 环境变量名
            default: 默认值
            
        Returns:
            环境变量值或默认值
        """
        return self._env_vars.get(key, default)

    @abstractmethod
    def fetch_proxies(self) -> List[Proxy]:
        """
        抽象方法：从数据源抓取并解析代理信息。
        具体的实现需要返回一个 Proxy 对象列表。
        """
        pass
