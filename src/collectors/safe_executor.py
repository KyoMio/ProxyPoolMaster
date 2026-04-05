import time
import concurrent.futures
from typing import List, Any, Dict
from datetime import datetime
from src.database.models import Proxy
from src.collectors.storage import store_proxy_with_cooldown_awareness


class SafeCollectorExecutor:
    """
    安全的收集器执行器
    隔离用户代码，提供超时、异常捕获、数据验证
    """
    
    DEFAULT_TIMEOUT = 60  # 默认超时 60 秒
    
    def __init__(self, collector_instance: Any, collector_id: str,
                 config: Any, logger: Any, redis_manager: Any):
        self.collector = collector_instance
        self.collector_id = collector_id
        self.config = config
        self.logger = logger
        self.redis_manager = redis_manager
        
        # 执行统计
        self.stats = {
            "total_runs": 0,
            "success_runs": 0,
            "failed_runs": 0,
            "total_proxies_collected": 0,
            "total_proxies_stored": 0
        }
    
    def execute(self) -> Dict[str, Any]:
        """
        执行采集并存储，返回执行报告
        """
        from .proxy_validator import ProxyDataValidator
        
        report = {
            "success": False,
            "execution_time_ms": 0,
            "raw_count": 0,
            "valid_count": 0,
            "stored_count": 0,
            "duplicate_count": 0,
            "cooldown_blocked_count": 0,
            "validation_errors": [],
            "storage_errors": [],
            "exception": None
        }
        
        start_time = time.time()
        self.stats["total_runs"] += 1
        
        try:
            self.logger.info(f"[{self.collector_id}] 开始执行采集...")
            
            # 1. 执行用户代码（带超时）
            timeout = getattr(self.config, 'COLLECTOR_EXEC_TIMEOUT', self.DEFAULT_TIMEOUT)
            raw_result = self._execute_with_timeout(timeout)
            
            # 2. 检查结果是否为列表
            if not isinstance(raw_result, (list, tuple)):
                raise ValueError(f"fetch_proxies() 必须返回列表，实际返回: {type(raw_result).__name__}")
            
            report["raw_count"] = len(raw_result)
            self.logger.info(f"[{self.collector_id}] 采集到 {report['raw_count']} 条原始数据")
            
            # 3. 数据验证
            validation_result = ProxyDataValidator.validate_batch(raw_result)
            valid_proxies = validation_result["proxies"]
            
            report["valid_count"] = validation_result["valid"]
            report["invalid"] = validation_result["invalid"]
            report["validation_errors"] = validation_result["errors"]
            
            if validation_result["invalid"] > 0:
                self.logger.warning(
                    f"[{self.collector_id}] 数据验证: "
                    f"有效 {validation_result['valid']}/{validation_result['total']}, "
                    f"无效 {validation_result['invalid']}"
                )
            
            # 4. 存储到数据库
            for proxy in valid_proxies:
                try:
                    store_result = store_proxy_with_cooldown_awareness(self.redis_manager, proxy)

                    if store_result.get("cooldown_blocked"):
                        report["cooldown_blocked_count"] += 1
                        self.logger.info(
                            f"[{self.collector_id}] 跳过冷却代理 {proxy.ip}:{proxy.port}",
                            extra={
                                "collector": self.collector_id,
                                "proxy": f"{proxy.ip}:{proxy.port}",
                                "proxy_key": store_result.get("proxy_key"),
                            }
                        )
                        continue

                    if store_result.get("stored", False):
                        report["stored_count"] += 1
                    else:
                        report["duplicate_count"] += 1
                except Exception as e:
                    error_msg = f"存储失败 {proxy.ip}:{proxy.port}: {str(e)}"
                    report["storage_errors"].append(error_msg)
                    self.logger.error(f"[{self.collector_id}] {error_msg}")
            
            # 5. 更新统计
            self.stats["success_runs"] += 1
            self.stats["total_proxies_collected"] += report["raw_count"]
            self.stats["total_proxies_stored"] += report["stored_count"]
            
            report["success"] = len(report["storage_errors"]) == 0
            
            self.logger.info(
                f"[{self.collector_id}] 执行完成: "
                f"原始={report['raw_count']}, "
                f"有效={report['valid_count']}, "
                f"存储={report['stored_count']}"
            )
            
        except TimeoutError:
            report["exception"] = f"执行超时（>{self.DEFAULT_TIMEOUT}秒）"
            self.logger.error(f"[{self.collector_id}] 执行超时")
            self.stats["failed_runs"] += 1
            
        except Exception as e:
            report["exception"] = f"执行异常: {str(e)}"
            self.logger.error(f"[{self.collector_id}] 执行异常: {str(e)}", exc_info=True)
            self.stats["failed_runs"] += 1
        
        finally:
            report["execution_time_ms"] = int((time.time() - start_time) * 1000)
        
        return report
    
    def _execute_with_timeout(self, timeout: int):
        """带超时保护的执行"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.collector.fetch_proxies)
            try:
                return future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                raise TimeoutError(f"采集执行超过 {timeout} 秒限制")
