import time
import threading
from typing import List, Tuple, Dict, Any, Optional, Type, Union
from datetime import datetime
from src.collectors.base_collector import BaseCollector
from src.collectors.storage import store_proxy_with_cooldown_awareness
import logging


class CollectorManager:
    """
    增强的代理收集器管理器
    支持预设收集器和用户自定义收集器统一管理
    支持热重载和手动执行
    """
    
    def __init__(self, config_instance: Any, logger_instance: Any, redis_manager_instance: Any, 
                 collectors_with_intervals: Optional[Union[List[Tuple[Type[BaseCollector], int]], List[Dict]]] = None):
        """
        初始化 CollectorManager
        
        Args:
            config_instance: 配置实例
            logger_instance: 日志实例
            redis_manager_instance: Redis 管理器实例
            collectors_with_intervals: 收集器配置列表
                支持两种格式:
                1. 旧格式: [(collector_class, interval_seconds), ...]
                2. 新格式: [{"id": "...", "source": "builtin|custom", ...}, ...]
        """
        self.config = config_instance
        self.logger = logger_instance
        self.redis_manager = redis_manager_instance
        
        # 存储 (collector_id, executor/instance, interval, config, is_builtin) 的列表
        self._collectors: List[Tuple[str, Any, int, Dict, bool]] = []
        self._threads: Dict[str, threading.Thread] = {}
        self._running_flags: Dict[str, bool] = {}
        self._collector_running_flags: Dict[str, bool] = {}  # 向后兼容
        self._last_status: Dict[str, Dict] = {}
        self._running = False
        self._start_time: Optional[float] = None
        
        # 统计信息
        self._stats = {
            "total_collected": 0,
            "collection_attempts": 0,
            "successful_collections": 0,
            "last_collection_count": 0,
            "raw_count": 0,
            "stored_count": 0,
            "cooldown_blocked_count": 0,
            "queue_length": 0,
        }
        
        # 加载所有收集器
        if collectors_with_intervals:
            # 检测格式
            if collectors_with_intervals and len(collectors_with_intervals) > 0:
                first_item = collectors_with_intervals[0]
                if isinstance(first_item, dict):
                    # 新格式：配置字典列表
                    self._load_all_collectors(collectors_with_intervals)
                elif isinstance(first_item, (tuple, list)) and len(first_item) == 2:
                    # 旧格式：(class, interval) 元组列表 - 保持向后兼容
                    self._load_from_legacy_format(collectors_with_intervals)
    
    def _load_from_legacy_format(self, collectors_with_intervals: List[Tuple[Type[BaseCollector], int]]):
        """从旧格式加载收集器（向后兼容）"""
        for collector_cls, interval in collectors_with_intervals:
            self._register_collector_legacy(collector_cls, interval)
    
    def _register_collector_legacy(self, collector_cls: Type[BaseCollector], interval_seconds: int):
        """
        注册一个代理收集器及其收集间隔（向后兼容方法）
        """
        if not issubclass(collector_cls, BaseCollector) or collector_cls == BaseCollector:
            self.logger.error(f"Invalid collector class: {collector_cls}. Must be a concrete subclass of BaseCollector.")
            return
        
        collector_id = collector_cls.__name__
        # 创建收集器实例时传入 config 和 logger
        collector_instance = collector_cls(self.config, self.logger)
        
        # 添加到新格式的存储中
        config = {
            "id": collector_id,
            "name": collector_id,
            "enabled": True,
            "interval_seconds": interval_seconds,
            "source": "builtin",
            "module_path": collector_cls.__module__,
            "class_name": collector_cls.__name__,
            "env_vars": {}
        }
        
        self._collectors.append((
            collector_id,
            collector_instance,
            interval_seconds,
            config,
            True  # is_builtin
        ))
        self._collector_running_flags[collector_id] = False
        self.logger.info(
            f"Collector '{collector_id}' registered with interval {interval_seconds} seconds.",
            extra={"component": "COLLECTOR", "collector": collector_id}
        )
    
    def _load_all_collectors(self, collectors_config: List[Dict]):
        """加载所有收集器（预设 + 自定义）"""
        for col_config in collectors_config:
            if not col_config.get("enabled", True):
                self.logger.info(f"收集器 [{col_config.get('id')}] 已禁用，跳过加载")
                continue
            
            collector_id = col_config["id"]
            try:
                if col_config.get("source") == "builtin":
                    self._load_builtin_collector(col_config)
                else:
                    self._load_custom_collector(col_config)
            except Exception as e:
                self.logger.error(f"加载收集器 [{collector_id}] 失败: {e}", exc_info=True)
    
    def _load_builtin_collector(self, col_config: Dict):
        """加载预设收集器"""
        from importlib import import_module
        
        module = import_module(col_config["module_path"])
        collector_class = getattr(module, col_config["class_name"])
        
        instance = collector_class(self.config, self.logger)
        instance.set_env_vars(col_config.get("env_vars", {}))
        interval_seconds = self._resolve_runtime_interval(col_config["id"], col_config)
        
        self._collectors.append((
            col_config["id"],
            instance,
            interval_seconds,
            col_config,
            True  # is_builtin
        ))
        self._collector_running_flags[col_config["id"]] = False
        self.logger.info(
            f"预设收集器 [{col_config['id']}] 已加载",
            extra={"component": "COLLECTOR", "collector": col_config["id"]}
        )
    
    def _load_custom_collector(self, col_config: Dict):
        """加载用户自定义收集器"""
        from src.collectors.dynamic_loader import CollectorDynamicLoader
        from src.collectors.safe_executor import SafeCollectorExecutor
        
        collector_class = CollectorDynamicLoader.load_collector_class(
            col_config["filename"]
        )
        
        if not collector_class:
            raise ImportError(f"无法从文件 {col_config['filename']} 加载收集器")
        
        instance = collector_class(self.config, self.logger)
        instance.set_env_vars(col_config.get("env_vars", {}))
        
        # 包装为安全执行器
        executor = SafeCollectorExecutor(
            instance, col_config["id"],
            self.config, self.logger, self.redis_manager
        )
        interval_seconds = self._resolve_runtime_interval(col_config["id"], col_config)
        
        self._collectors.append((
            col_config["id"],
            executor,
            interval_seconds,
            col_config,
            False  # is_builtin
        ))
        self._collector_running_flags[col_config["id"]] = False
        self.logger.info(
            f"自定义收集器 [{col_config['id']}] 已加载",
            extra={"component": "COLLECTOR", "collector": col_config["id"]}
        )

    def register_collector(self, collector_cls: Type[BaseCollector], interval_seconds: int):
        """
        注册一个代理收集器及其收集间隔（向后兼容的公共方法）
        """
        self._register_collector_legacy(collector_cls, interval_seconds)
    
    def start_periodic_collection(self):
        """
        启动所有收集器的周期性采集
        保持向后兼容的接口
        """
        if self._running:
            self.logger.warning("CollectorManager is already running.")
            return
        
        if not self._collectors:
            self.logger.warning("No collectors registered. Manager will not start.")
            return
        
        self._running = True
        self._start_time = time.time()
        self.logger.info("CollectorManager starting all periodic collection threads.", extra={"component": "COLLECTOR"})
        
        for collector_id, executor, interval, config, is_builtin in self._collectors:
            if collector_id in self._threads:
                continue
            
            self._running_flags[collector_id] = True
            thread = threading.Thread(
                target=self._run_collector_loop,
                args=(collector_id, executor, interval, is_builtin),
                daemon=True,
                name=f"Collector-{collector_id}"
            )
            self._threads[collector_id] = thread
            self._collector_running_flags[collector_id] = True
            thread.start()
            self.logger.info(
                f"收集器 [{collector_id}] 线程已启动",
                extra={"component": "COLLECTOR", "collector": collector_id}
            )
        
        self.logger.info(
            f"所有 {len(self._threads)} 个收集器线程已启动",
            extra={"component": "COLLECTOR", "count": len(self._threads)}
        )
    
    def _run_collector_loop(self, collector_id: str, executor: Any, 
                           interval: int, is_builtin: bool):
        """收集器执行循环"""
        self.logger.info(
            f"收集器 [{collector_id}] 线程启动",
            extra={"component": "COLLECTOR", "collector": collector_id}
        )
        
        while self._running_flags.get(collector_id, False):
            try:
                start_time = time.time()
                self._stats["collection_attempts"] += 1
                
                if is_builtin:
                    # 预设收集器：直接执行
                    proxies = executor.fetch_proxies()
                    proxy_count = len(proxies) if proxies else 0
                    
                    self._stats["total_collected"] += proxy_count
                    self._stats["last_collection_count"] = proxy_count
                    self._stats["raw_count"] = proxy_count
                    self._stats["stored_count"] = 0
                    self._stats["cooldown_blocked_count"] = 0
                    self._stats["queue_length"] = 0
                    
                    if proxies:
                        self._stats["successful_collections"] += 1
                        self.logger.info(
                            f"收集器 [{collector_id}] 采集到 {proxy_count} 个代理",
                            extra={"component": "COLLECTOR", "collector": collector_id, "count": proxy_count}
                        )
                        stored_count = 0
                        cooldown_blocked_count = 0
                        for proxy in proxies:
                            store_result = store_proxy_with_cooldown_awareness(self.redis_manager, proxy)
                            if store_result.get("cooldown_blocked"):
                                cooldown_blocked_count += 1
                                self.logger.info(
                                    f"跳过冷却代理 {proxy.ip}:{proxy.port}",
                                    extra={
                                        "component": "COLLECTOR",
                                        "collector": collector_id,
                                        "proxy": f"{proxy.ip}:{proxy.port}",
                                        "proxy_key": store_result.get("proxy_key"),
                                    }
                                )
                                continue

                            if not store_result.get("stored", False):
                                self.logger.warning(
                                    f"添加代理 {proxy.ip}:{proxy.port} 失败",
                                    extra={"component": "COLLECTOR", "collector": collector_id, "proxy": f"{proxy.ip}:{proxy.port}"}
                                )
                            else:
                                stored_count += 1

                        self._stats["stored_count"] = stored_count
                        self._stats["cooldown_blocked_count"] = cooldown_blocked_count
                        self._stats["queue_length"] = stored_count
                    
                    self._last_status[collector_id] = {
                        "last_run": datetime.now().isoformat(),
                        "status": "success",
                        "count": proxy_count,
                        "stored": stored_count if proxies else 0,
                        "raw_count": proxy_count,
                        "stored_count": stored_count if proxies else 0,
                        "cooldown_blocked_count": cooldown_blocked_count if proxies else 0,
                        "queue_length": stored_count if proxies else 0,
                    }
                else:
                    # 自定义收集器：使用安全执行器
                    report = executor.execute()
                    self._stats["total_collected"] += report.get("raw_count", 0)
                    self._stats["last_collection_count"] = report.get("raw_count", 0)
                    self._stats["raw_count"] = report.get("raw_count", 0)
                    self._stats["stored_count"] = report.get("stored_count", 0)
                    self._stats["cooldown_blocked_count"] = report.get("cooldown_blocked_count", 0)
                    self._stats["queue_length"] = report.get("stored_count", 0)
                    
                    if report.get("success"):
                        self._stats["successful_collections"] += 1
                    
                    self._last_status[collector_id] = {
                        "last_run": datetime.now().isoformat(),
                        "status": "success" if report.get("success") else "error",
                        "report": report
                    }
                    
            except Exception as e:
                self.logger.error(
                    f"[{collector_id}] 执行失败: {e}",
                    exc_info=True,
                    extra={"component": "COLLECTOR", "collector": collector_id}
                )
                self._last_status[collector_id] = {
                    "last_run": datetime.now().isoformat(),
                    "status": "error",
                    "error": str(e)
                }
            
            # 睡眠到下次执行
            elapsed = time.time() - start_time
            sleep_time = max(1, interval - int(elapsed))
            
            for _ in range(sleep_time):
                if not self._running_flags.get(collector_id, False):
                    break
                time.sleep(1)
        
        self.logger.info(
            f"收集器 [{collector_id}] 线程停止",
            extra={"component": "COLLECTOR", "collector": collector_id}
        )
    
    def stop_periodic_collection(self):
        """
        停止所有收集器
        保持向后兼容的接口
        """
        if not self._running:
            self.logger.warning("CollectorManager is not running.")
            return
        
        self.logger.info("停止所有收集器...", extra={"component": "COLLECTOR"})
        self._running = False
        
        for collector_id in self._running_flags:
            self._running_flags[collector_id] = False
            self._collector_running_flags[collector_id] = False
        
        for collector_id, thread in self._threads.items():
            if thread.is_alive():
                thread.join(timeout=5)
            if thread.is_alive():
                self.logger.warning(
                    f"收集器 [{collector_id}] 线程未优雅退出",
                    extra={"component": "COLLECTOR", "collector": collector_id}
                )
        
        self._threads.clear()
        self.logger.info("所有收集器已停止", extra={"component": "COLLECTOR"})
    
    def reload_collector(self, collector_id: str) -> bool:
        """
        热重载指定收集器
        用于用户更新代码后动态生效
        
        Returns:
            bool: 重载是否成功
        """
        self.logger.info(f"热重载收集器 [{collector_id}]...", extra={"component": "COLLECTOR", "collector": collector_id})
        
        # 1. 找到收集器配置
        config = None
        collector_tuple = None
        for item in self._collectors:
            if item[0] == collector_id:
                config = item[3]
                collector_tuple = item
                break
        
        if not config:
            self.logger.error(f"收集器 [{collector_id}] 不存在")
            return False
        
        # 2. 停止该收集器线程
        if collector_id in self._running_flags:
            self._running_flags[collector_id] = False
        
        if collector_id in self._threads:
            self._threads[collector_id].join(timeout=5)
            del self._threads[collector_id]
        
        # 3. 从列表中移除旧实例
        self._collectors = [item for item in self._collectors if item[0] != collector_id]
        
        # 4. 重新加载
        try:
            if config.get("source") == "builtin":
                self._load_builtin_collector(config)
            else:
                self._load_custom_collector(config)
            
            # 5. 如果 manager 在运行，重新启动线程
            if self._running:
                for cid, executor, interval, cfg, is_builtin in self._collectors:
                    if cid == collector_id:
                        self._running_flags[collector_id] = True
                        self._collector_running_flags[collector_id] = True
                        thread = threading.Thread(
                            target=self._run_collector_loop,
                            args=(collector_id, executor, interval, is_builtin),
                            daemon=True,
                            name=f"Collector-{collector_id}"
                        )
                        self._threads[collector_id] = thread
                        thread.start()
                        break
            
            self.logger.info(
                f"收集器 [{collector_id}] 热重载成功",
                extra={"component": "COLLECTOR", "collector": collector_id}
            )
            return True
            
        except Exception as e:
            self.logger.error(
                f"热重载收集器 [{collector_id}] 失败: {e}",
                exc_info=True,
                extra={"component": "COLLECTOR", "collector": collector_id}
            )
            return False
    
    def run_collector_once(self, collector_id: str) -> Optional[Dict]:
        """
        手动执行一次采集（用于测试）
        
        Args:
            collector_id: 收集器ID
            
        Returns:
            执行报告字典，如果收集器不存在返回 None
        """
        for cid, executor, _, _, is_builtin in self._collectors:
            if cid == collector_id:
                try:
                    self.logger.info(
                        f"手动执行收集器 [{collector_id}]",
                        extra={"component": "COLLECTOR", "collector": collector_id}
                    )

                    if is_builtin:
                        # 预设收集器直接执行
                        proxies = executor.fetch_proxies()
                        proxy_count = len(proxies) if proxies else 0

                        # 存储到 Redis
                        stored = 0
                        if proxies:
                            for proxy in proxies:
                                store_result = store_proxy_with_cooldown_awareness(self.redis_manager, proxy)
                                if store_result.get("cooldown_blocked"):
                                    self.logger.info(
                                        f"跳过冷却代理 {proxy.ip}:{proxy.port}",
                                        extra={
                                            "component": "COLLECTOR",
                                            "collector": collector_id,
                                            "proxy": f"{proxy.ip}:{proxy.port}",
                                            "proxy_key": store_result.get("proxy_key"),
                                        }
                                    )
                                    continue

                                if store_result.get("stored", False):
                                    stored += 1
                                else:
                                    self.logger.warning(
                                        f"添加代理 {proxy.ip}:{proxy.port} 失败",
                                        extra={
                                            "component": "COLLECTOR",
                                            "collector": collector_id,
                                            "proxy": f"{proxy.ip}:{proxy.port}"
                                        }
                                    )

                        return {
                            "success": True,
                            "raw_count": proxy_count,
                            "valid_count": proxy_count,
                            "stored_count": stored,
                            "validation_errors": [],
                            "storage_errors": []
                        }

                    # 自定义收集器使用安全执行器
                    return executor.execute()
                except Exception as e:
                    self.logger.error(
                        f"手动执行收集器 [{collector_id}] 失败: {e}",
                        exc_info=True,
                        extra={"component": "COLLECTOR", "collector": collector_id}
                    )
                    return {"success": False, "exception": str(e)}
        
        self.logger.warning(f"收集器 [{collector_id}] 不存在", extra={"component": "COLLECTOR"})
        return None
    
    def get_collector_status(self, collector_id: str) -> Optional[Dict]:
        """
        获取收集器状态
        
        Args:
            collector_id: 收集器ID
            
        Returns:
            状态字典，如果不存在返回 None
        """
        return self._last_status.get(collector_id)
    
    def get_all_status(self) -> Dict[str, Any]:
        """
        获取所有收集器状态
        
        Returns:
            包含运行状态、收集器列表、统计信息的字典
        """
        now = time.time()
        uptime_seconds = now - self._start_time if self._start_time else 0
        
        collectors_status = []
        for collector_id, _, interval, config, is_builtin in self._collectors:
            is_running = self._running_flags.get(collector_id, False)
            last_status = self._last_status.get(collector_id, {})
            
            collectors_status.append({
                "id": collector_id,
                "name": config.get("name", collector_id),
                "enabled": config.get("enabled", True),
                "interval_seconds": interval,
                "source": "builtin" if is_builtin else "custom",
                "is_running": is_running,
                "last_run": last_status.get("last_run"),
                "last_status": last_status.get("status", "unknown")
            })
        
        return {
            "running": self._running,
            "uptime_seconds": uptime_seconds,
            "collectors_count": len(self._collectors),
            "collectors": collectors_status,
            "stats": self._stats
        }
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取收集器管理器状态（向后兼容的方法）
        
        Returns:
            包含运行状态、启动时间、运行时长、各收集器状态等信息
        """
        all_status = self.get_all_status()
        now = time.time()
        uptime_seconds = now - self._start_time if self._start_time else 0
        
        # 格式化运行时长
        hours, remainder = divmod(int(uptime_seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{hours}h {minutes}m {seconds}s" if hours > 0 else f"{minutes}m {seconds}s"
        
        # 转换收集器状态格式以兼容旧接口
        collectors_status = []
        for col_status in all_status.get("collectors", []):
            last_run = col_status.get("last_run")
            last_beat = datetime.fromisoformat(last_run).timestamp() if last_run else 0
            
            collectors_status.append({
                "name": col_status["name"],
                "status": "Running" if col_status["is_running"] else "Stopped",
                "interval_seconds": col_status["interval_seconds"],
                "last_heartbeat": last_run,
                "last_heartbeat_seconds_ago": int(now - last_beat) if last_beat else None
            })
        
        # 计算采集速率（个/分钟）
        collect_rate = 0
        if self._running and self._start_time:
            elapsed_minutes = uptime_seconds / 60
            if elapsed_minutes > 0:
                collect_rate = round(self._stats["total_collected"] / elapsed_minutes, 2)
        
        # 计算成功率
        success_rate = 0.0
        if self._stats["collection_attempts"] > 0:
            success_rate = round(self._stats["successful_collections"] / self._stats["collection_attempts"], 2)
        
        return {
            "running": self._running,
            "start_time": datetime.fromtimestamp(self._start_time).isoformat() if self._start_time else None,
            "uptime_seconds": uptime_seconds,
            "uptime_formatted": uptime_str,
            "collectors_count": len(self._collectors),
            "collectors": collectors_status,
            "stats": {
                "total_collected": self._stats["total_collected"],
                "collection_attempts": self._stats["collection_attempts"],
                "successful_collections": self._stats["successful_collections"],
                "last_collection_count": self._stats["last_collection_count"],
                "raw_count": self._stats["raw_count"],
                "stored_count": self._stats["stored_count"],
                "cooldown_blocked_count": self._stats["cooldown_blocked_count"],
                "queue_length": self._stats["queue_length"] or self._stats["stored_count"],
                "collect_rate_per_min": collect_rate,
                "success_rate": success_rate
            }
        }

    def _resolve_runtime_interval(self, collector_id: str, collector_config: Dict[str, Any]) -> int:
        """
        根据 collector 标识解析热更新后的目标间隔。
        """
        identifier = " ".join([
            collector_id or "",
            str(collector_config.get("id", "")),
            str(collector_config.get("class_name", "")),
            str(collector_config.get("name", "")),
        ]).lower()

        default_interval = int(collector_config.get(
            "interval_seconds",
            getattr(self.config, "COLLECT_INTERVAL_SECONDS", 300)
        ))

        if "overseas" in identifier:
            return int(getattr(
                self.config,
                "ZDAYE_OVERSEAS_COLLECT_INTERVAL",
                getattr(self.config, "COLLECT_INTERVAL_SECONDS", default_interval)
            ))

        if "zdaye" in identifier:
            return int(getattr(
                self.config,
                "ZDAYE_COLLECT_INTERVAL",
                getattr(self.config, "COLLECT_INTERVAL_SECONDS", default_interval)
            ))

        return default_interval

    def apply_runtime_config(self, updated_keys: List[str]) -> List[str]:
        """
        应用可热更新的 Collector 配置项（主要是采集间隔）。
        """
        interval_related_keys = {
            "COLLECT_INTERVAL_SECONDS",
            "ZDAYE_COLLECT_INTERVAL",
            "ZDAYE_OVERSEAS_COLLECT_INTERVAL",
        }
        if not interval_related_keys.intersection(updated_keys):
            return []

        affected_collectors: List[str] = []
        new_collectors: List[Tuple[str, Any, int, Dict, bool]] = []

        for collector_id, executor, interval, config, is_builtin in self._collectors:
            new_interval = self._resolve_runtime_interval(collector_id, config)
            updated_config = dict(config)
            updated_config["interval_seconds"] = new_interval
            new_collectors.append((collector_id, executor, new_interval, updated_config, is_builtin))

            if new_interval != interval:
                affected_collectors.append(collector_id)
                if self._running and collector_id in self._threads:
                    self.reload_collector(collector_id)

        self._collectors = new_collectors

        if affected_collectors:
            self.logger.info(
                f"Collector runtime config applied: {affected_collectors}",
                extra={"component": "COLLECTOR"}
            )
        return affected_collectors
