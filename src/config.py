# src/config.py

import logging
import os
import json
from typing import Any, Dict, List, Optional


def _int_flag(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_collector_runtime_mode(raw_value: Any) -> Optional[str]:
    if raw_value is None:
        return None

    mode = str(raw_value).strip().lower()
    aliases = {
        "legacy": "legacy",
        "v1": "legacy",
        "classic": "legacy",
        "v2": "v2",
        "new": "v2",
        "off": "disabled",
        "disabled": "disabled",
        "none": "disabled",
    }
    return aliases.get(mode)


class Config:
    """
    项目配置类，支持从环境变量、配置文件和默认值加载配置。
    配置优先级：环境变量 > 配置文件 > 默认值
    """
    
    # 配置文件路径
    CONFIG_FILE: str = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
    
    def __init__(self):
        # Config 初始化不应触发全局日志器重配置
        self._logger = logging.getLogger(__name__)
        self._config_file_path = os.getenv("CONFIG_FILE", self.CONFIG_FILE)
        
        # 先加载配置文件（如果存在）
        file_config = self._load_from_file()
        # 缓存文件配置供后续使用
        self._file_config_cache = file_config
        
        # Redis 配置
        self.REDIS_HOST: str = os.getenv("REDIS_HOST", file_config.get("REDIS_HOST", "localhost"))
        self.REDIS_PORT: int = int(os.getenv("REDIS_PORT", file_config.get("REDIS_PORT", 6379)))
        self.REDIS_DB: int = int(os.getenv("REDIS_DB", file_config.get("REDIS_DB", 0)))
        self.REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", file_config.get("REDIS_PASSWORD", ""))

        # 日志配置
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", file_config.get("LOG_LEVEL", "INFO")).upper()
        self.LOG_MAX_BYTES: int = int(os.getenv("LOG_MAX_BYTES", file_config.get("LOG_MAX_BYTES", 1024 * 1024 * 10)))  # 10MB
        self.LOG_BACKUP_COUNT: int = int(os.getenv("LOG_BACKUP_COUNT", file_config.get("LOG_BACKUP_COUNT", 5)))
        self.TIMEZONE: str = os.getenv("TIMEZONE", file_config.get("TIMEZONE", "Asia/Shanghai"))  # 默认北京时间

        # API 配置
        self.API_TOKEN: str = os.getenv("API_TOKEN", file_config.get("API_TOKEN", ""))

        # 请求配置 (用于收集器/检测器)
        self.REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", file_config.get("REQUEST_TIMEOUT", 10)))  # 请求超时时间，单位秒

        # 收集器配置 - 全局默认间隔
        self.COLLECT_INTERVAL_SECONDS: int = int(os.getenv("COLLECT_INTERVAL_SECONDS", 
                                                            file_config.get("COLLECT_INTERVAL_SECONDS", 300)))  # 代理收集周期，单位秒 (5分钟)
        
        # 各收集器独立间隔配置（优先级高于全局配置）
        # 站大爷收集器间隔（秒）
        self.ZDAYE_COLLECT_INTERVAL: int = int(os.getenv("ZDAYE_COLLECT_INTERVAL", 
                                                         file_config.get("ZDAYE_COLLECT_INTERVAL", 
                                                                         self.COLLECT_INTERVAL_SECONDS)))
        # 站大爷海外代理收集器间隔（秒）
        self.ZDAYE_OVERSEAS_COLLECT_INTERVAL: int = int(os.getenv("ZDAYE_OVERSEAS_COLLECT_INTERVAL", 
                                                                  file_config.get("ZDAYE_OVERSEAS_COLLECT_INTERVAL", 
                                                                                  self.COLLECT_INTERVAL_SECONDS)))
        
        # 收集器列表配置
        collectors_from_env = os.getenv("COLLECTORS")
        if collectors_from_env:
            try:
                self.COLLECTORS: List[Dict[str, Any]] = json.loads(collectors_from_env)
            except json.JSONDecodeError:
                self.COLLECTORS: List[Dict[str, Any]] = []
        else:
            self.COLLECTORS: List[Dict[str, Any]] = file_config.get("COLLECTORS", [])
        
        # 站大爷 API 配置
        self.ZDAYE_APP_ID: str = os.getenv("ZDAYE_APP_ID", file_config.get("ZDAYE_APP_ID", ""))
        self.ZDAYE_AKEY: str = os.getenv("ZDAYE_AKEY", file_config.get("ZDAYE_AKEY", ""))
        
        # 测试器配置
        self.TEST_INTERVAL_SECONDS: int = int(os.getenv("TEST_INTERVAL_SECONDS", 
                                                        file_config.get("TEST_INTERVAL_SECONDS", 300)))  # 代理检测周期，单位秒 (5分钟)
        self.MAX_FAIL_COUNT: int = int(os.getenv("MAX_FAIL_COUNT", 
                                                  file_config.get("MAX_FAIL_COUNT", 5)))  # 代理连续失败的最大次数，超过则删除
        self.TESTER_LOG_EACH_PROXY: bool = os.getenv(
            "TESTER_LOG_EACH_PROXY",
            str(file_config.get("TESTER_LOG_EACH_PROXY", "false"))
        ).lower() in ("1", "true", "yes", "on")
        
        # 测试器高级配置
        self.TEST_MAX_CONCURRENT: int = int(os.getenv("TEST_MAX_CONCURRENT", 
                                                       file_config.get("TEST_MAX_CONCURRENT", 100)))
        self.TEST_TARGETS: List[str] = file_config.get("TEST_TARGETS", [
            "http://www.baidu.com",
            "http://www.qq.com",
            "http://www.sina.com.cn",
            "http://www.163.com"
        ])
        self.TEST_TIMEOUT_PER_TARGET: int = int(os.getenv("TEST_TIMEOUT_PER_TARGET",
                                                           file_config.get("TEST_TIMEOUT_PER_TARGET", 5)))
        self.TEST_BATCH_SIZE: int = int(os.getenv(
            "TEST_BATCH_SIZE",
            file_config.get("TEST_BATCH_SIZE", 200),
        ))
        self.TEST_IDLE_SLEEP_SECONDS: int = int(os.getenv(
            "TEST_IDLE_SLEEP_SECONDS",
            file_config.get("TEST_IDLE_SLEEP_SECONDS", 2),
        ))
        self.TEST_SCHEDULE_ZSET_KEY: str = os.getenv(
            "TEST_SCHEDULE_ZSET_KEY",
            file_config.get("TEST_SCHEDULE_ZSET_KEY", "proxies:test_schedule"),
        )
        self.TEST_MIGRATION_BATCH_SIZE: int = int(os.getenv(
            "TEST_MIGRATION_BATCH_SIZE",
            file_config.get("TEST_MIGRATION_BATCH_SIZE", 500),
        ))
        
        # API 限流配置
        self.RATE_LIMIT_PROXY_MINUTE: str = os.getenv("RATE_LIMIT_PROXY_MINUTE", 
                                                       file_config.get("RATE_LIMIT_PROXY_MINUTE", "60/minute"))  # /random 和 /get 接口限流
        self.RATE_LIMIT_HEALTH_MINUTE: str = os.getenv("RATE_LIMIT_HEALTH_MINUTE", 
                                                        file_config.get("RATE_LIMIT_HEALTH_MINUTE", "30/minute"))  # /health 接口限流

        runtime_mode_raw = os.getenv(
            "COLLECTOR_RUNTIME_MODE",
            file_config.get("COLLECTOR_RUNTIME_MODE", "v2"),
        )
        runtime_mode = _normalize_collector_runtime_mode(runtime_mode_raw) or "v2"

        self.COLLECTOR_RUNTIME_MODE: str = runtime_mode

        # Collector V2 Feature Flags
        if self.COLLECTOR_RUNTIME_MODE == "v2":
            self.COLLECTOR_V2_ENABLED = 1
            self.COLLECTOR_V2_UI_ENABLED = 1
            self.COLLECTOR_V2_MIGRATION_AUTO = 1
        else:
            self.COLLECTOR_V2_ENABLED = 0
            self.COLLECTOR_V2_UI_ENABLED = 0
            self.COLLECTOR_V2_MIGRATION_AUTO = 0

        # Collector Worker 配置
        self.COLLECTOR_WORKER_ENABLED: int = int(os.getenv("COLLECTOR_WORKER_ENABLED",
                                                           file_config.get("COLLECTOR_WORKER_ENABLED", 1)))
        self.COLLECTOR_WORKER_ID: str = os.getenv("COLLECTOR_WORKER_ID",
                                                   file_config.get("COLLECTOR_WORKER_ID", "collector-worker-1"))
        self.COLLECTOR_WORKER_TICK_SECONDS: int = int(os.getenv("COLLECTOR_WORKER_TICK_SECONDS",
                                                                file_config.get("COLLECTOR_WORKER_TICK_SECONDS", 1)))
        self.COLLECTOR_WORKER_MAX_CONCURRENT: int = int(os.getenv("COLLECTOR_WORKER_MAX_CONCURRENT",
                                                                  file_config.get("COLLECTOR_WORKER_MAX_CONCURRENT", 4)))

        # 执行隔离配置
        self.COLLECTOR_EXEC_TIMEOUT: int = int(os.getenv("COLLECTOR_EXEC_TIMEOUT",
                                                         file_config.get("COLLECTOR_EXEC_TIMEOUT", 60)))
        self.COLLECTOR_EXEC_MAX_MEMORY_MB: int = int(os.getenv("COLLECTOR_EXEC_MAX_MEMORY_MB",
                                                               file_config.get("COLLECTOR_EXEC_MAX_MEMORY_MB", 256)))
        self.COLLECTOR_EXEC_STDOUT_LIMIT_KB: int = int(os.getenv("COLLECTOR_EXEC_STDOUT_LIMIT_KB",
                                                                 file_config.get("COLLECTOR_EXEC_STDOUT_LIMIT_KB", 256)))

        # V2 运行记录
        self.COLLECTOR_RUN_HISTORY_LIMIT: int = int(os.getenv("COLLECTOR_RUN_HISTORY_LIMIT",
                                                              file_config.get("COLLECTOR_RUN_HISTORY_LIMIT", 200)))

    def _load_from_file(self) -> Dict[str, Any]:
        """
        从配置文件加载配置
        """
        if os.path.exists(self._config_file_path):
            try:
                with open(self._config_file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Failed to load config file {self._config_file_path}: {e}")
                return {}
        return {}

    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """
        从字典更新配置项
        注意：此方法只更新内存中的配置，不会保存到文件
        """
        config_keys = set(self.to_dict().keys())
        for key, value in data.items():
            if key in config_keys and not key.startswith('_'):
                # 类型转换
                current_value = getattr(self, key)
                if isinstance(current_value, int) and isinstance(value, str):
                    try:
                        value = int(value)
                    except ValueError:
                        continue
                elif isinstance(current_value, bool) and isinstance(value, str):
                    value = value.lower() in ('true', '1', 'yes', 'on')
                setattr(self, key, value)

    def save_to_file(self, filepath: Optional[str] = None, include_secrets: bool = False) -> bool:
        """
        将当前配置保存到 JSON 文件
        
        注意：
        1. 只保存非环境变量覆盖的配置项，保留环境变量的优先级
        2. 敏感信息（API_TOKEN, REDIS_PASSWORD, ZDAYE_AKEY）默认不保存
        
        Args:
            filepath: 配置文件路径，默认使用 CONFIG_FILE
            include_secrets: 是否包含敏感信息
            
        Returns:
            bool: 保存是否成功
        """
        filepath = filepath or self._config_file_path
        
        try:
            # 读取现有配置（如果存在）
            existing = {}
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        existing = json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    self._logger.debug(f"Could not load existing config file: {e}")
                    existing = {}
            
            # 定义敏感字段
            secret_keys = {'API_TOKEN', 'REDIS_PASSWORD', 'ZDAYE_AKEY'}
            
            # 构建保存的配置（排除环境变量覆盖的项）
            save_data = {}
            for key, value in self.to_dict().items():
                # 跳过敏感信息（除非显式指定）
                if key in secret_keys and not include_secrets:
                    continue
                # 跳过内部属性
                if key.startswith('_'):
                    continue
                # 如果该值与环境变量不同，则保存到文件
                env_value = os.getenv(key)
                if env_value is None or str(value) != env_value:
                    save_data[key] = value
            
            # 合并并保存
            existing.update(save_data)
            
            # 确保目录存在
            dir_path = os.path.dirname(filepath)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
                
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)
            
            self._logger.info(f"Configuration saved to {filepath}")
            return True
        except Exception as e:
            self._logger.error(f"Failed to save config to {filepath}: {e}")
            return False

    def get_config_source(self, key: str) -> str:
        """
        获取配置项的来源
        
        Args:
            key: 配置项名称
            
        Returns:
            str: 'env' (环境变量), 'file' (配置文件), 'default' (默认值)
        """
        # 检查环境变量
        if os.getenv(key) is not None:
            return 'env'
        
        # 检查配置文件（使用缓存）
        if key in self._file_config_cache:
            return 'file'
        
        return 'default'

    def get_all_config_sources(self) -> Dict[str, str]:
        """
        获取所有配置项的来源
        
        Returns:
            Dict[str, str]: 配置项名 -> 来源
        """
        return {key: self.get_config_source(key) for key in self.to_dict().keys()}

    def add_collector_config(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        添加新的收集器配置
        
        Args:
            data: 收集器配置字典
            
        Returns:
            Dict: 添加后的收集器配置（包含分配的id）
        """
        # 分配id
        existing_ids = [c.get("id", 0) for c in self.COLLECTORS]
        new_id = max(existing_ids, default=0) + 1
        
        collector = {
            "id": new_id,
            "name": data.get("name", ""),
            "type": data.get("type", ""),
            "interval": int(data.get("interval", 300)),
            "enabled": bool(data.get("enabled", True)),
            "params": data.get("params", {})
        }
        
        self.COLLECTORS.append(collector)
        return collector

    def update_collector_config(self, collector_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        更新指定id的收集器配置
        
        Args:
            collector_id: 收集器id
            data: 更新的配置数据
            
        Returns:
            Dict: 更新后的配置，如果不存在返回None
        """
        for collector in self.COLLECTORS:
            if collector.get("id") == collector_id:
                # 不允许修改id
                data = {k: v for k, v in data.items() if k != "id"}
                collector.update(data)
                return collector
        return None

    def delete_collector_config(self, collector_id: int) -> bool:
        """
        删除指定id的收集器配置
        
        Args:
            collector_id: 收集器id
            
        Returns:
            bool: 是否删除成功
        """
        for i, collector in enumerate(self.COLLECTORS):
            if collector.get("id") == collector_id:
                self.COLLECTORS.pop(i)
                return True
        return False

    def __getattr__(self, name: str) -> Any:
        """
        动态获取配置项，不存在时抛出 AttributeError 以保持 Python 语义一致。
        """
        try:
            return self.__dict__[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def to_dict(self) -> Dict[str, Any]:
        """
        将配置对象转换为字典，方便查看和序列化
        """
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
