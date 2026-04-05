import asyncio
import time
from typing import Dict, Type, Optional, List
import logging

from src.database.redis_client import RedisManager
from src.database.models import Proxy
from src.testers.async_tester import AsyncHttpTester
from src.testers.scoring import ProxyScorer
from src.config import Config


class TesterManager:
    """
    管理代理的周期性测试
    纯异步实现，支持 Semaphore 并发控制、智能分级调度
    """
    
    def __init__(
        self,
        config: Config,
        logger: logging.Logger,
        redis_manager: RedisManager,
        tester_class: Type[AsyncHttpTester] = AsyncHttpTester,
        stats_only_mode: bool = False
    ):
        self.config = config
        self.logger = logger
        self.redis_manager = redis_manager
        self.stats_only_mode = stats_only_mode  # 只统计模式：不执行实际测试，只提供统计信息
        
        # 创建测试器和评分器
        self.tester = tester_class(self.config, self.logger)
        self.scorer = ProxyScorer(self.logger)
        
        # 配置参数
        self.base_interval = config.TEST_INTERVAL_SECONDS
        self.batch_size = int(getattr(config, "TEST_BATCH_SIZE", 200))
        self.idle_sleep_seconds = int(getattr(config, "TEST_IDLE_SLEEP_SECONDS", 2))
        self.max_fail_count = config.MAX_FAIL_COUNT
        self.max_concurrent = config.TEST_MAX_CONCURRENT
        self.log_each_proxy = getattr(config, "TESTER_LOG_EACH_PROXY", False)
        
        # 并发控制
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
        
        # 运行状态
        self._running = False
        self._tester_task: Optional[asyncio.Task] = None
        
        # 统计信息
        self._stats = {
            "total_tested": 0,           # 总共测试的代理数
            "total_passed": 0,           # 通过测试的代理数
            "total_failed": 0,           # 失败的代理数
            "total_removed": 0,          # 清理的代理数（失效达到最大次数）
            "test_rounds": 0,            # 测试轮数
            "start_time": None,          # 启动时间
            "queue_backlog": 0,          # 最近一批待检代理数
            "last_batch_duration_seconds": 0.0,  # 最近一批耗时
            "batch_throughput_per_min": 0.0,     # 最近一批吞吐
            "last_batch_tested": 0,      # 最近一批实际测试数
        }
        
        mode_str = " (STATS ONLY MODE)" if stats_only_mode else ""
        self.logger.info(
            f"TesterManager initialized{mode_str}. "
            f"Max concurrent: {self.max_concurrent}, "
            f"Base interval: {self.base_interval}s, "
            f"Batch size: {self.batch_size}, "
            f"Idle sleep: {self.idle_sleep_seconds}s",
            extra={"component": "TESTER"}
        )
    
    async def _test_single_proxy(self, proxy: Proxy) -> Dict[str, object]:
        """
        测试单个代理（Semaphore 控制并发）
        返回更新后的代理对象，如果代理被删除则返回 None
        """
        async with self.semaphore:
            self.logger.debug(f"Testing proxy {proxy.ip}:{proxy.port} ({proxy.protocol})", extra={"component": "TESTER", "proxy": f"{proxy.ip}:{proxy.port}"})
            
            try:
                # 执行多目标异步测试
                test_result = await self.tester.test_proxy_async(
                    proxy.ip, proxy.port, proxy.protocol
                )
                
                # 记录详细测试结果
                success_targets = test_result.success_count
                total_targets = test_result.total_targets
                self.logger.debug(
                    f"Proxy {proxy.ip}:{proxy.port} tested - "
                    f"Success: {success_targets}/{total_targets}, "
                    f"Avg Time: {test_result.avg_response_time:.2f}s",
                    extra={"component": "TESTER", "proxy": f"{proxy.ip}:{proxy.port}", "success": success_targets, "total": total_targets}
                )
                
                # 计算评分
                total_checks = (proxy.success_count or 0) + (proxy.fail_count or 0)
                score_result = self.scorer.calculate_score(
                    test_result=test_result,
                    success_count=proxy.success_count or 0,
                    total_checks=total_checks
                )
                
                # 更新代理属性
                proxy.last_check_time = time.time()
                proxy.response_time = score_result["avg_response_time"]
                proxy.score = score_result["total_score"]
                proxy.grade = score_result["grade"]
                
                # 根据测试结果更新成功/失败计数
                if score_result["is_available"]:
                    proxy.success_count = (proxy.success_count or 0) + 1
                    proxy.fail_count = 0
                    per_proxy_log = self.logger.info if self.log_each_proxy else self.logger.debug
                    per_proxy_log(
                        f"Proxy {proxy.ip}:{proxy.port} passed. "
                        f"Grade: {proxy.grade}, Score: {proxy.score}",
                        extra={"component": "TESTER", "proxy": f"{proxy.ip}:{proxy.port}", "grade": proxy.grade, "score": proxy.score}
                    )
                else:
                    proxy.fail_count = (proxy.fail_count or 0) + 1
                    per_proxy_log = self.logger.info if self.log_each_proxy else self.logger.debug
                    per_proxy_log(
                        f"Proxy {proxy.ip}:{proxy.port} failed. "
                        f"Grade: {proxy.grade}, Fail count: {proxy.fail_count}/{self.max_fail_count}",
                        extra={"component": "TESTER", "proxy": f"{proxy.ip}:{proxy.port}", "grade": proxy.grade, "fail_count": proxy.fail_count}
                        )
                        
                remove = proxy.fail_count >= self.max_fail_count
                if remove:
                    removal_log = self.logger.info if self.log_each_proxy else self.logger.debug
                    removal_log(
                        f"Removing proxy {proxy.ip}:{proxy.port} (max fail count reached)",
                        extra={"component": "TESTER", "proxy": f"{proxy.ip}:{proxy.port}", "fail_count": proxy.fail_count}
                    )

                next_check_at = self._calculate_next_check_at(proxy)

                return {
                    "proxy": proxy,
                    "passed": bool(score_result["is_available"]),
                    "remove": remove,
                    "removed_at": time.time() if remove else None,
                    "next_check_at": next_check_at,
                }
                
            except Exception as e:
                self.logger.error(
                    f"Proxy {proxy.ip}:{proxy.port} test failed: {e}",
                    exc_info=True,
                    extra={"component": "TESTER", "proxy": f"{proxy.ip}:{proxy.port}"}
                )
                proxy.last_check_time = time.time()
                proxy.response_time = -1.0
                proxy.score = 0
                proxy.grade = "D"
                proxy.fail_count = (proxy.fail_count or 0) + 1
                remove = proxy.fail_count >= self.max_fail_count
                next_check_at = self._calculate_next_check_at(proxy)
                return {
                    "proxy": proxy,
                    "passed": False,
                    "remove": remove,
                    "removed_at": time.time() if remove else None,
                    "next_check_at": next_check_at,
                }

    def _calculate_next_check_at(self, proxy: Proxy) -> float:
        """根据代理当前状态计算下次检测时间。"""
        multiplier = self.scorer.calculate_test_interval_multiplier(
            proxy.grade or "B",
            proxy.fail_count or 0,
        )
        return time.time() + (self.base_interval * multiplier)

    def _calculate_repair_next_check_at(self, proxy: Proxy, now_ts: float) -> float:
        """为缺失调度记录的代理补算下一次检测时间。"""
        if proxy.last_check_time in (None, 0, 0.0):
            return float(now_ts)

        multiplier = self.scorer.calculate_test_interval_multiplier(
            proxy.grade or "B",
            proxy.fail_count or 0,
        )
        return float(proxy.last_check_time) + (self.base_interval * multiplier)

    def _repair_missing_schedule_entries(self, limit: Optional[int] = None, now_ts: Optional[float] = None) -> int:
        """
        补齐缺失的测试调度记录，避免历史代理长期处于未检测状态。
        """
        client = self.redis_manager.get_redis_client()
        schedule_key = getattr(self.config, "TEST_SCHEDULE_ZSET_KEY", "proxies:test_schedule")
        repair_limit = int(limit or getattr(self.config, "TEST_MIGRATION_BATCH_SIZE", self.batch_size))
        if repair_limit <= 0:
            repair_limit = 1

        current_ts = float(time.time() if now_ts is None else now_ts)
        repaired = 0

        for proxy_key in client.smembers("proxies:all"):
            if repaired >= repair_limit:
                break
            if client.zscore(schedule_key, proxy_key) is not None:
                continue

            proxy_data = client.hgetall(proxy_key)
            if not proxy_data:
                continue

            try:
                proxy = Proxy.from_dict(proxy_data)
            except Exception as exc:
                self.logger.debug(
                    f"Skip schedule repair for invalid proxy {proxy_key}: {exc}",
                    extra={"component": "TESTER", "proxy_key": proxy_key},
                )
                continue

            next_check_at = self._calculate_repair_next_check_at(proxy, current_ts)
            client.zadd(schedule_key, {proxy_key: next_check_at})
            repaired += 1

        if repaired > 0:
            self.logger.info(
                f"Repaired {repaired} missing tester schedule entries",
                extra={"component": "TESTER", "repaired": repaired},
            )

        return repaired
    
    def _calculate_proxy_priority(self, proxy: Proxy) -> float:
        """
        计算代理测试优先级（数值越小优先级越高）
        用于排序：先测新代理和可疑代理
        """
        now = time.time()
        time_since_check = now - (proxy.last_check_time or 0)
        
        # 新代理最高优先级
        if (proxy.success_count or 0) == 0 and (proxy.fail_count or 0) == 0:
            return -1000  # 确保新代理排在最前面
        
        # 计算测试间隔倍数
        multiplier = self.scorer.calculate_test_interval_multiplier(
            proxy.grade or 'B',
            proxy.fail_count or 0
        )
        
        # 理想的测试间隔
        ideal_interval = self.base_interval * multiplier
        
        # 优先级 = 理想间隔 - 实际间隔（越大越需要测试）
        priority = ideal_interval - time_since_check
        
        return -priority  # 取负值用于升序排序
    
    async def _run_test_round(self):
        """兼容旧入口，直接委托到新的到期批处理循环。"""
        return await self._drain_due_proxies()
    
    async def _save_stats_to_redis(self):
        """将统计信息保存到 Redis，供 API 进程读取"""
        try:
            import json
            stats_data = {
                "total_tested": self._stats["total_tested"],
                "total_passed": self._stats["total_passed"],
                "total_failed": self._stats["total_failed"],
                "total_removed": self._stats["total_removed"],
                "test_rounds": self._stats["test_rounds"],
                "start_time": self._stats["start_time"],
                "queue_backlog": self._stats["queue_backlog"],
                "last_batch_duration_seconds": self._stats["last_batch_duration_seconds"],
                "batch_throughput_per_min": self._stats["batch_throughput_per_min"],
                "last_batch_tested": self._stats["last_batch_tested"],
                "timestamp": time.time()
            }
            await asyncio.to_thread(
                lambda: self.redis_manager.get_redis_client().set(
                    "tester:stats", json.dumps(stats_data), ex=300  # 5分钟过期
                )
            )
            self.logger.debug(f"Tester stats saved to Redis: {stats_data}", extra={"component": "TESTER"})
        except Exception as e:
            self.logger.warning(f"Failed to save stats to Redis: {e}", extra={"component": "TESTER"})
    
    async def _broadcast_update(self):
        """广播仪表盘更新"""
        try:
            from src.api.dashboard_endpoints import get_dashboard_overview
            import redis.asyncio as aioredis
            import json
            import os
            
            data = await get_dashboard_overview(self.redis_manager)
            
            redis_client = aioredis.Redis(
                host=os.getenv("REDIS_HOST", "redis"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                db=int(os.getenv("REDIS_DB", 0)),
                decode_responses=True
            )
            
            message = {
                "type": "update",
                "data": data
            }
            
            await redis_client.publish(
                "websocket_broadcast",
                json.dumps(message, default=str)
            )
            await redis_client.close()
            
        except Exception as e:
            self.logger.error(f"Failed to broadcast update: {e}", extra={"component": "TESTER"})
    
    async def _update_running_status(self):
        """更新运行状态到 Redis，用于 API 进程检测 Tester 是否运行"""
        try:
            await asyncio.to_thread(
                lambda: self.redis_manager.get_redis_client().set(
                    "tester:running", 
                    "1", 
                    ex=60  # 60秒过期，需要定期刷新
                )
            )
            self.logger.debug("Tester running status updated in Redis", extra={"component": "TESTER"})
        except Exception as e:
            self.logger.warning(f"Failed to update running status: {e}", extra={"component": "TESTER"})
    
    async def _clear_running_status(self):
        """清除 Redis 中的运行状态"""
        try:
            await asyncio.to_thread(
                lambda: self.redis_manager.get_redis_client().delete("tester:running")
            )
            self.logger.info("Tester running status cleared from Redis", extra={"component": "TESTER"})
        except Exception as e:
            self.logger.warning(f"Failed to clear running status: {e}", extra={"component": "TESTER"})

    def _record_batch_stats(
        self,
        *,
        batch_started_at: float,
        tested: int,
        passed: int,
        failed: int,
        removed: int,
    ) -> None:
        """更新最近一批和累计统计，供批量检测与即时首检复用。"""
        batch_duration = max(0.0, time.time() - batch_started_at)
        self._stats["last_batch_duration_seconds"] = round(batch_duration, 4)
        self._stats["last_batch_tested"] = tested
        self._stats["batch_throughput_per_min"] = (
            round(tested / (batch_duration / 60), 2) if batch_duration > 0 and tested > 0 else 0.0
        )
        self._stats["total_tested"] += tested
        self._stats["total_passed"] += passed
        self._stats["total_failed"] += failed
        self._stats["total_removed"] += removed
        self._stats["test_rounds"] += 1

    async def run_tests_periodically(self):
        """持续周期性测试"""
        self.logger.info("TesterManager started", extra={"component": "TESTER"})
        self._running = True
        self._stats["start_time"] = time.time()
        
        # 立即标记为运行中
        await self._update_running_status()
        last_status_update = time.time()
        
        while self._running:
            try:
                processed = await self._drain_due_proxies()
            except Exception as e:
                self.logger.error(f"Error in test round: {e}", exc_info=True, extra={"component": "TESTER"})
                processed = 0
            
            # 每 30 秒刷新一次运行状态（防止过期）
            now = time.time()
            if now - last_status_update > 30:
                await self._update_running_status()
                last_status_update = now
            
            # 没有到期任务时短暂休眠，避免空转
            if self._running and processed == 0:
                self.logger.debug(
                    f"Sleeping for {self.idle_sleep_seconds}s",
                    extra={"component": "TESTER"},
                )
                await asyncio.sleep(self.idle_sleep_seconds)
        
        # 停止时清除状态
        await self._clear_running_status()
        self.logger.info("TesterManager stopped", extra={"component": "TESTER"})

    async def _drain_due_proxies(self) -> int:
        """拉取并处理一批到期代理。"""
        now_ts = time.time()
        schedule_key = getattr(self.config, "TEST_SCHEDULE_ZSET_KEY", "proxies:test_schedule")
        due_count = await asyncio.to_thread(
            lambda: self.redis_manager.get_redis_client().zcount(schedule_key, "-inf", now_ts)
        )
        if int(due_count or 0) < self.batch_size:
            await asyncio.to_thread(
                lambda: self._repair_missing_schedule_entries(
                    limit=max(1, self.batch_size - int(due_count or 0)),
                    now_ts=now_ts,
                )
            )
            due_count = await asyncio.to_thread(
                lambda: self.redis_manager.get_redis_client().zcount(schedule_key, "-inf", now_ts)
            )
        due_keys = await asyncio.to_thread(
            lambda: self.redis_manager.get_due_proxy_keys(limit=self.batch_size, now_ts=now_ts)
        )
        self._stats["queue_backlog"] = int(due_count or 0)

        if not due_keys:
            self.logger.debug("No due proxies to test", extra={"component": "TESTER"})
            self._stats["last_batch_duration_seconds"] = 0.0
            self._stats["batch_throughput_per_min"] = 0.0
            self._stats["last_batch_tested"] = 0
            return 0

        batch_started_at = time.time()
        try:
            proxies, missing_keys = await asyncio.to_thread(
                lambda: self.redis_manager.get_proxies_by_keys(due_keys)
            )
        except RuntimeError as e:
            self.logger.error(f"Failed to load due proxies: {e}", extra={"component": "TESTER"})
            self._stats["last_batch_duration_seconds"] = round(time.time() - batch_started_at, 4)
            self._stats["batch_throughput_per_min"] = 0.0
            self._stats["last_batch_tested"] = 0
            return 0

        for missing_key in missing_keys:
            await asyncio.to_thread(
                lambda key=missing_key: self.redis_manager.delete_proxy_by_key(key)
            )

        if not proxies:
            self.logger.debug("No valid proxies found in due batch", extra={"component": "TESTER"})
            self._stats["last_batch_duration_seconds"] = round(time.time() - batch_started_at, 4)
            self._stats["batch_throughput_per_min"] = 0.0
            self._stats["last_batch_tested"] = 0
            return 0

        tasks = [self._test_single_proxy(proxy) for proxy in proxies]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        batch_payloads = []
        tested = 0
        passed = 0
        failed = 0
        removed = 0

        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Test task failed: {result}", extra={"component": "TESTER"})
                continue

            tested += 1
            proxy = result["proxy"]
            batch_payloads.append(
                {
                    "proxy": proxy,
                    "next_check_at": result["next_check_at"],
                    "remove": result["remove"],
                    **(
                        {
                            "removed_at": result["removed_at"],
                            "last_fail_count": proxy.fail_count,
                        }
                        if result["remove"]
                        else {}
                    ),
                }
            )

            if result["remove"]:
                removed += 1
            elif result.get("passed", False):
                passed += 1
            else:
                failed += 1

        if batch_payloads:
            await asyncio.to_thread(
                lambda: self.redis_manager.batch_update_test_results(batch_payloads)
            )

        self._record_batch_stats(
            batch_started_at=batch_started_at,
            tested=tested,
            passed=passed,
            failed=failed,
            removed=removed,
        )

        self.logger.info(
            f"Batch completed: Tested={tested}, Passed={passed}, Failed={failed}, Removed={removed}",
            extra={
                "component": "TESTER",
                "tested": tested,
                "passed": passed,
                "failed": failed,
                "removed": removed,
            },
        )

        await self._save_stats_to_redis()
        await self._broadcast_update()
        return tested
    
    async def test_new_proxy(self, proxy: Proxy) -> Proxy:
        """
        测试新代理（立即测试）
        由 collector 调用
        """
        self.logger.info(f"Immediate testing new proxy: {proxy.ip}:{proxy.port}", extra={"component": "TESTER", "proxy": f"{proxy.ip}:{proxy.port}"})
        batch_started_at = time.time()
        result = await self._test_single_proxy(proxy)
        if isinstance(result, dict) and "proxy" in result:
            batch_payload = {
                "proxy": result["proxy"],
                "remove": result.get("remove", False),
            }
            if result.get("remove", False):
                batch_payload["removed_at"] = result.get("removed_at")
                batch_payload["last_fail_count"] = result["proxy"].fail_count
            if "next_check_at" in result:
                batch_payload["next_check_at"] = result["next_check_at"]
            await asyncio.to_thread(
                lambda: self.redis_manager.batch_update_test_results([batch_payload])
            )
            passed = 0 if result.get("remove", False) else int(bool(result.get("passed", False)))
            failed = 0 if result.get("remove", False) else int(not result.get("passed", False))
            removed = int(bool(result.get("remove", False)))
            self._record_batch_stats(
                batch_started_at=batch_started_at,
                tested=1,
                passed=passed,
                failed=failed,
                removed=removed,
            )
            await self._save_stats_to_redis()
            await self._broadcast_update()
            return result["proxy"]
        return result or proxy
    
    async def start(self):
        """启动 TesterManager"""
        if self._tester_task and not self._tester_task.done():
            self.logger.warning("TesterManager already running", extra={"component": "TESTER"})
            return
        
        self._tester_task = asyncio.create_task(self.run_tests_periodically())
        self.logger.info("TesterManager task created", extra={"component": "TESTER"})
    
    async def stop(self):
        """停止 TesterManager"""
        if self._running:
            self.logger.info("Stopping TesterManager", extra={"component": "TESTER"})
            self._running = False
            
            if self._tester_task:
                self._tester_task.cancel()
                try:
                    await self._tester_task
                except asyncio.CancelledError:
                    pass
            
            # 关闭测试器连接池
            await self.tester.close()
            
            self.logger.info("TesterManager stopped", extra={"component": "TESTER"})

    def apply_runtime_config(self, updated_keys: List[str]) -> List[str]:
        """
        应用可热更新的 Tester 配置项
        """
        applied_keys: List[str] = []

        if "TEST_INTERVAL_SECONDS" in updated_keys:
            self.base_interval = int(getattr(self.config, "TEST_INTERVAL_SECONDS", self.base_interval))
            applied_keys.append("TEST_INTERVAL_SECONDS")

        if "TEST_BATCH_SIZE" in updated_keys:
            self.batch_size = int(getattr(self.config, "TEST_BATCH_SIZE", self.batch_size))
            applied_keys.append("TEST_BATCH_SIZE")

        if "TEST_IDLE_SLEEP_SECONDS" in updated_keys:
            self.idle_sleep_seconds = int(getattr(self.config, "TEST_IDLE_SLEEP_SECONDS", self.idle_sleep_seconds))
            applied_keys.append("TEST_IDLE_SLEEP_SECONDS")

        if "MAX_FAIL_COUNT" in updated_keys:
            self.max_fail_count = int(getattr(self.config, "MAX_FAIL_COUNT", self.max_fail_count))
            applied_keys.append("MAX_FAIL_COUNT")

        if "TEST_MAX_CONCURRENT" in updated_keys:
            self.max_concurrent = int(getattr(self.config, "TEST_MAX_CONCURRENT", self.max_concurrent))
            # 使用新的并发值重建 semaphore
            self.semaphore = asyncio.Semaphore(max(1, self.max_concurrent))
            applied_keys.append("TEST_MAX_CONCURRENT")

        if "TESTER_LOG_EACH_PROXY" in updated_keys:
            self.log_each_proxy = bool(getattr(self.config, "TESTER_LOG_EACH_PROXY", self.log_each_proxy))
            applied_keys.append("TESTER_LOG_EACH_PROXY")

        tester_runtime_keys = {"TEST_TIMEOUT_PER_TARGET", "TEST_TARGETS"}
        if tester_runtime_keys.intersection(updated_keys):
            if hasattr(self.tester, "apply_runtime_config"):
                self.tester.apply_runtime_config(updated_keys)
            applied_keys.extend(sorted(list(tester_runtime_keys.intersection(updated_keys))))

        if applied_keys:
            self.logger.info(
                f"Tester runtime config applied: {sorted(set(applied_keys))}",
                extra={"component": "TESTER"}
            )

        return sorted(set(applied_keys))
    
    def get_status(self) -> Dict[str, any]:
        """获取TesterManager状态"""
        now = time.time()
        uptime_seconds = now - self._stats["start_time"] if self._stats["start_time"] else 0
        
        # 计算测试速率（个/分钟）
        test_rate = 0
        if uptime_seconds > 5:  # 降低阈值，更快显示速率
            test_rate = round(self._stats["total_tested"] / (uptime_seconds / 60), 2)
        
        # 计算清理速率（个/分钟）
        cleanup_rate = 0
        if uptime_seconds > 5:  # 降低阈值，更快显示速率
            cleanup_rate = round(self._stats["total_removed"] / (uptime_seconds / 60), 2)
        
        self.logger.debug(
            f"TesterManager status: tested={self._stats['total_tested']}, "
            f"removed={self._stats['total_removed']}, "
            f"test_rate={test_rate}/min, cleanup_rate={cleanup_rate}/min",
            extra={"component": "TESTER"}
        )
        
        return {
            "running": self._running,
            "uptime_seconds": uptime_seconds,
            "stats": {
                **self._stats,
                "test_rate_per_min": test_rate,
                "cleanup_rate_per_min": cleanup_rate,
            }
        }
