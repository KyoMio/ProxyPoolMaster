from typing import List, Dict, Any, Optional, Tuple
from src.database.models import Proxy


class ProxyDataValidator:
    """
    代理数据验证器
    确保用户代码返回的数据能正确转换为 Proxy 对象
    """
    
    REQUIRED_FIELDS = ['ip', 'port']
    ALLOWED_PROTOCOLS = ['http', 'https', 'socks4', 'socks5']
    
    @classmethod
    def validate_and_convert(cls, raw_data: Any) -> Tuple[bool, Optional[Proxy], str]:
        """验证并转换单条代理数据"""
        try:
            # 处理 Proxy 对象（已经是正确类型）
            if isinstance(raw_data, Proxy):
                return cls._validate_proxy_object(raw_data)
            
            # 处理字典格式
            if isinstance(raw_data, dict):
                return cls._validate_dict_format(raw_data)
            
            return False, None, f"不支持的数据类型: {type(raw_data).__name__}，请返回 Proxy 对象或字典"
            
        except Exception as e:
            return False, None, f"数据验证异常: {str(e)}"
    
    @classmethod
    def _validate_proxy_object(cls, proxy: Proxy) -> Tuple[bool, Optional[Proxy], str]:
        """验证 Proxy 对象"""
        if not proxy.ip or not isinstance(proxy.ip, str):
            return False, None, "IP 不能为空且必须为字符串"
        
        if not proxy.port or not isinstance(proxy.port, int):
            return False, None, "端口不能为空且必须为整数"
        
        if not (1 <= proxy.port <= 65535):
            return False, None, f"端口 {proxy.port} 超出有效范围 (1-65535)"
        
        if proxy.protocol not in cls.ALLOWED_PROTOCOLS:
            return False, None, f"协议 '{proxy.protocol}' 无效，必须是: {', '.join(cls.ALLOWED_PROTOCOLS)}"
        
        proxy.protocol = proxy.protocol.lower()
        return True, proxy, ""
    
    @classmethod
    def _validate_dict_format(cls, data: dict) -> Tuple[bool, Optional[Proxy], str]:
        """验证字典格式并转换为 Proxy"""
        for field in cls.REQUIRED_FIELDS:
            if field not in data:
                return False, None, f"缺少必填字段: '{field}'"
        
        try:
            proxy = Proxy(
                ip=str(data['ip']).strip(),
                port=int(data['port']),
                protocol=str(data.get('protocol', 'http')).lower().strip(),
                country_code=str(data.get('country_code', 'Unknown')).strip(),
                anonymity_level=str(data.get('anonymity_level', 'Unknown')).strip()
            )
            return cls._validate_proxy_object(proxy)
            
        except ValueError as e:
            return False, None, f"字段类型转换失败: {str(e)}"
        except Exception as e:
            return False, None, f"创建 Proxy 对象失败: {str(e)}"
    
    @classmethod
    def validate_batch(cls, data_list: list) -> Dict[str, Any]:
        """批量验证，返回详细报告"""
        result = {
            "total": len(data_list) if isinstance(data_list, (list, tuple)) else 0,
            "valid": 0,
            "invalid": 0,
            "proxies": [],
            "errors": []
        }
        
        if not isinstance(data_list, (list, tuple)):
            result["errors"].append(f"返回数据必须是列表，实际类型: {type(data_list).__name__}")
            return result
        
        for idx, item in enumerate(data_list):
            is_valid, proxy, error = cls.validate_and_convert(item)
            if is_valid:
                result["valid"] += 1
                result["proxies"].append(proxy)
            else:
                result["invalid"] += 1
                result["errors"].append(f"第 {idx + 1} 项: {error}")
        
        return result
