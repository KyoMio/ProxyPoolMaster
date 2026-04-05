import json
import time
from typing import Optional, List, Dict, Tuple
import redis
from redis import ConnectionPool, Redis as RedisClient
# from src.config import config # 不再全局导入 config
import logging # 导入 logging 模块
# from src.logger import logger # 不再全局导入 logger
from .models import Proxy
from src.utils.proxy_availability import is_grade_available

class RedisManager:
    """
    封装 Redis 数据库操作，用于存储和管理代理。
    """
    _instance: Optional[RedisClient] = None
    _pool: Optional[ConnectionPool] = None

    def __init__(self, config_instance, logger_instance): # 接收 config 和 logger 实例
        self.config = config_instance
        self.logger = logger_instance
        self._pool = None # 每个实例维护自己的连接池
        self._instance = None # 每个实例维护自己的 Redis 客户端

    def get_redis_client(self) -> RedisClient: # 改为实例方法
        """
        获取 Redis 客户端实例。采用单例模式，确保只有一个连接池。
        """
        if self._pool is None:
            self._pool = ConnectionPool(
                host=self.config.REDIS_HOST,
                port=self.config.REDIS_PORT,
                db=self.config.REDIS_DB,
                password=self.config.REDIS_PASSWORD,
                decode_responses=True # 自动解码 Redis 响应为 UTF-8 字符串
            )
            self.logger.info(f"Redis ConnectionPool created for {self.config.REDIS_HOST}:{self.config.REDIS_PORT}/{self.config.REDIS_DB}", extra={"component": "REDIS"})
        
        # Ensure _instance is valid and connected
        if self._instance is None:
            self._instance = RedisClient(connection_pool=self._pool)
            self.logger.debug("Redis client instance created from pool.", extra={"component": "REDIS"})
        
        try:
            self._instance.ping()
            self.logger.debug("Redis client ping successful.", extra={"component": "REDIS"})
        except redis.exceptions.ConnectionError as e:
            self.logger.error(f"Failed to connect to Redis: {e}", extra={"component": "REDIS"})
            # Re-create client instance if connection fails
            self._instance = RedisClient(connection_pool=self._pool)
            try:
                self._instance.ping() # Try pinging the new instance
                self.logger.debug("Redis client re-ping successful after re-creation.", extra={"component": "REDIS"})
            except redis.exceptions.ConnectionError as e_reconnect:
                self.logger.error(f"Failed to establish Redis connection: {e_reconnect}", extra={"component": "REDIS"})
                raise Exception(f"Failed to establish Redis connection: {e_reconnect}") from e_reconnect # Raise a generic Exception

        return self._instance

    def store_proxy(self, proxy: Proxy) -> Dict[str, object]:
        """
        向 Redis 中添加一个代理并返回结构化结果。
        使用 Hash 存储代理的详细信息，Set 存储所有代理的 key，Sorted Set 存储按分数排序的代理。
        如果代理已存在，保留其 score 和 grade 字段不被覆盖。
        新代理会自动加入首检调度队列。
        """
        client = self.get_redis_client()
        proxy_key = self._get_proxy_key(proxy)
        try:
            if self.is_proxy_in_cooldown(proxy_key, client=client):
                self.logger.info(
                    f"Skip proxy {proxy.ip}:{proxy.port} because it is in cooldown.",
                    extra={"component": "REDIS", "proxy": f"{proxy.ip}:{proxy.port}", "proxy_key": proxy_key},
                )
                return {
                    "stored": False,
                    "created": False,
                    "proxy_key": proxy_key,
                    "cooldown_blocked": True,
                }

            # 检查代理是否已存在
            exists = client.exists(proxy_key)
            
            if exists:
                # 代理已存在，保留原有评分字段
                existing_data = client.hgetall(proxy_key)
                existing_score = existing_data.get("score", "0")
                existing_grade = existing_data.get("grade", "")
                existing_success_count = existing_data.get("success_count", "0")
                existing_fail_count = existing_data.get("fail_count", "0")
                existing_response_time = existing_data.get("response_time", "-1")
                existing_last_check = existing_data.get("last_check_time", "0")
                
                # 使用原有值
                proxy.score = int(existing_score) if existing_score else 0
                proxy.grade = existing_grade if existing_grade else ""
                proxy.success_count = int(existing_success_count) if existing_success_count else 0
                proxy.fail_count = int(existing_fail_count) if existing_fail_count else 0
                try:
                    proxy.response_time = float(existing_response_time) if existing_response_time else -1.0
                except:
                    proxy.response_time = -1.0
                try:
                    proxy.last_check_time = float(existing_last_check) if existing_last_check else 0.0
                except:
                    proxy.last_check_time = 0.0
                
                self.logger.debug(f"Proxy {proxy.ip}:{proxy.port} already exists, preserving score/grade.", extra={"component": "REDIS", "proxy": f"{proxy.ip}:{proxy.port}"})
            
            # 使用 Hash 存储代理的详细信息 (兼容 redis-py 7.x)
            data = proxy.to_dict()
            for field, value in data.items():
                client.hset(proxy_key, field, str(value))
            
            # 将代理的 key 添加到 Set 中，方便管理所有代理
            client.sadd("proxies:all", proxy_key)
            
            # 更新分数到 sorted set
            client.zadd("proxies:score", {proxy_key: proxy.score})

            # 新代理自动进入首检调度队列，避免依赖外部调用方补调度
            if not exists:
                self.schedule_proxy_check(proxy_key, time.time())
            
            if exists:
                self.logger.debug(f"Updated existing proxy: {proxy.ip}:{proxy.port} (score={proxy.score}, grade={proxy.grade})", extra={"component": "REDIS", "proxy": f"{proxy.ip}:{proxy.port}", "score": proxy.score, "grade": proxy.grade})
            else:
                self.logger.debug(f"Added new proxy: {proxy.ip}:{proxy.port} to Redis.", extra={"component": "REDIS", "proxy": f"{proxy.ip}:{proxy.port}"})
            
            return {
                "stored": True,
                "created": not exists,
                "proxy_key": proxy_key,
            }
        except Exception as e:
            self.logger.error(f"Failed to add proxy {proxy.ip}:{proxy.port} to Redis: {e}", extra={"component": "REDIS", "proxy": f"{proxy.ip}:{proxy.port}"})
            return {
                "stored": False,
                "created": False,
                "proxy_key": proxy_key,
            }

    def calculate_proxy_cooldown_seconds(self, strike_count: int) -> int:
        """
        根据冷却命中次数计算冷却时长。
        """
        if strike_count <= 1:
            return 12 * 60 * 60
        if strike_count == 2:
            return 24 * 60 * 60
        return 72 * 60 * 60

    def record_proxy_cooldown(
        self,
        proxy: Proxy,
        removed_at: Optional[float],
        strike_count: int,
        last_fail_count: int,
        reason: str = "max_fail_count_reached",
        client: Optional[RedisClient] = None,
    ) -> Dict[str, object]:
        """
        记录代理冷却信息。
        """
        client = client or self.get_redis_client()
        proxy_key = self._get_proxy_key(proxy)
        cooldown_key = self._get_proxy_cooldown_key(proxy)
        removed_at_ts = float(removed_at if removed_at is not None else time.time())
        cooldown_seconds = self.calculate_proxy_cooldown_seconds(strike_count)
        cooldown_until = int(removed_at_ts + cooldown_seconds)
        ttl_seconds = cooldown_seconds + 60

        payload = {
            "proxy_key": proxy_key,
            "protocol": proxy.protocol,
            "ip": proxy.ip,
            "port": str(proxy.port),
            "strike_count": str(strike_count),
            "last_fail_count": str(last_fail_count),
            "last_removed_at": str(int(removed_at_ts)),
            "cooldown_until": str(cooldown_until),
            "cooldown_seconds": str(cooldown_seconds),
            "reason": reason,
        }

        for field, value in payload.items():
            client.hset(cooldown_key, field, value)

        client.zadd("proxies:cooldown", {cooldown_key: cooldown_until})
        client.expire(cooldown_key, ttl_seconds)

        self.logger.debug(
            f"Recorded cooldown for {proxy_key}: strike_count={strike_count}, cooldown_until={cooldown_until}",
            extra={
                "component": "REDIS",
                "proxy_key": proxy_key,
                "cooldown_key": cooldown_key,
                "strike_count": strike_count,
                "cooldown_until": cooldown_until,
            },
        )

        return {
            "stored": True,
            "proxy_key": proxy_key,
            "cooldown_key": cooldown_key,
            "strike_count": strike_count,
            "cooldown_seconds": cooldown_seconds,
            "cooldown_until": cooldown_until,
            "ttl_seconds": ttl_seconds,
            "reason": reason,
        }

    def get_proxy_cooldown(self, proxy_key: str, client: Optional[RedisClient] = None) -> Dict[str, str]:
        """
        获取代理冷却记录。
        """
        client = client or self.get_redis_client()
        cooldown_key = self._get_proxy_cooldown_key_from_proxy_key(proxy_key)
        data = client.hgetall(cooldown_key)
        return data or {}

    def is_proxy_in_cooldown(
        self,
        proxy_key: str,
        now_ts: Optional[float] = None,
        client: Optional[RedisClient] = None,
    ) -> bool:
        """
        判断代理是否仍在冷却期内。
        """
        client = client or self.get_redis_client()
        cooldown_key = self._get_proxy_cooldown_key_from_proxy_key(proxy_key)
        cooldown_data = self.get_proxy_cooldown(proxy_key, client=client)
        if not cooldown_data:
            client.zrem("proxies:cooldown", cooldown_key)
            return False

        now_value = float(now_ts if now_ts is not None else time.time())
        cooldown_until_raw = cooldown_data.get("cooldown_until")
        try:
            cooldown_until = float(cooldown_until_raw) if cooldown_until_raw is not None else 0.0
        except (TypeError, ValueError):
            cooldown_until = 0.0

        if cooldown_until > now_value:
            return True

        client.delete(cooldown_key)
        client.zrem("proxies:cooldown", cooldown_key)
        return False

    def add_proxy(self, proxy: Proxy) -> bool: # 改为实例方法
        """
        向 Redis 中添加一个代理。
        保留向后兼容的布尔返回值，内部复用结构化存储结果。
        """
        result = self.store_proxy(proxy)
        return bool(result.get("stored", False))

    def update_proxy(self, proxy: Proxy) -> bool: # 改为实例方法
        """
        更新 Redis 中一个代理的信息。
        """
        client = self.get_redis_client()
        proxy_key = self._get_proxy_key(proxy)
        try:
            if not client.exists(proxy_key):
                self.logger.warning(f"Attempted to update non-existent proxy: {proxy.ip}:{proxy.port}", extra={"component": "REDIS", "proxy": f"{proxy.ip}:{proxy.port}"})
                return False
            
            # 使用 Hash 存储代理的详细信息 (兼容 redis-py 7.x)
            data = proxy.to_dict()
            for field, value in data.items():
                client.hset(proxy_key, field, str(value))
            # 可以根据需要更新 sorted set 的分数
            # client.zadd("proxies:score", {proxy_key: new_score})
            self.logger.debug(f"Updated proxy: {proxy.ip}:{proxy.port} in Redis.", extra={"component": "REDIS", "proxy": f"{proxy.ip}:{proxy.port}"})
            return True
        except Exception as e:
            self.logger.error(f"Failed to update proxy {proxy.ip}:{proxy.port} in Redis: {e}", extra={"component": "REDIS", "proxy": f"{proxy.ip}:{proxy.port}"})
            return False

    def delete_proxy(self, proxy: Proxy) -> bool: # 改为实例方法
        """
        从 Redis 中删除一个代理。
        """
        proxy_key = self._get_proxy_key(proxy)
        result = self.delete_proxy_by_key(proxy_key)
        if result:
            self.logger.debug(f"Deleted proxy: {proxy.ip}:{proxy.port} from Redis.", extra={"component": "REDIS", "proxy": f"{proxy.ip}:{proxy.port}"})
        return result

    def delete_proxy_by_key(self, proxy_key: str) -> bool:
        """
        根据 Redis key 删除代理及其所有索引，适用于缺失或脏数据清理。
        """
        client = self.get_redis_client()
        schedule_key = getattr(self.config, "TEST_SCHEDULE_ZSET_KEY", "proxies:test_schedule")
        try:
            client.delete(proxy_key)
            client.srem("proxies:all", proxy_key)
            client.zrem("proxies:score", proxy_key)
            client.zrem(schedule_key, proxy_key)
            for grade in ["S", "A", "B", "C", "D"]:
                client.srem(f"proxies:grade:{grade}", proxy_key)
            client.srem("proxies:available", proxy_key)
            self.logger.debug(
                f"Deleted proxy by key: {proxy_key}",
                extra={"component": "REDIS", "proxy_key": proxy_key},
            )
            return True
        except Exception as e:
            self.logger.error(
                f"Failed to delete proxy by key {proxy_key}: {e}",
                extra={"component": "REDIS", "proxy_key": proxy_key},
            )
            return False

    def get_random_proxy(self) -> Optional[Proxy]: # 改为实例方法
        """
        从 Redis 中随机获取一个代理。
        """
        try:
            proxies = self.get_all_non_cooldown_proxies()
            if proxies:
                import random

                return random.choice(proxies)
            return None
        except Exception as e:
            self.logger.error(f"Failed to get random proxy from Redis: {e}", extra={"component": "REDIS"})
            return None

    def get_random_available_proxy(self, max_fail_count: int = 5) -> Optional[Proxy]:
        """
        从 Redis 中随机获取一个可用的代理。
        可用性条件：grade 为 B/S/A 且 fail_count < max_fail_count
        
        如果没有严格可用的代理，会降级返回未判定为失败的代理（fail_count < max_fail_count），
        以确保在测试期间也能获取代理。
        
        Args:
            max_fail_count: 最大允许的失败次数，默认为 5
        
        Returns:
            可用代理对象，如果没有可用代理则返回 None
        """
        import random
        try:
            verified_proxies: List[Proxy] = []  # 已验证可用的代理（B级及以上）
            pending_proxies: List[Proxy] = []   # 待测试/未失败的代理（尚未形成等级）

            for proxy in self.get_all_non_cooldown_proxies():
                fail_count = int(getattr(proxy, "fail_count", 0) or 0)
                grade = str(getattr(proxy, "grade", "") or "").upper()

                # 检查是否已验证可用（B级及以上）
                if is_grade_available(grade) and fail_count < max_fail_count:
                    verified_proxies.append(proxy)
                # 检查是否未判定为失败且尚未形成等级（用于降级选择）
                elif fail_count < max_fail_count and not grade:
                    pending_proxies.append(proxy)

            # 优先返回已验证可用的代理
            if verified_proxies:
                self.logger.debug(f"Selected verified proxy from {len(verified_proxies)} available", extra={"component": "REDIS", "count": len(verified_proxies)})
                return random.choice(verified_proxies)
            
            # 降级：返回未判定为失败的代理（测试期间使用）
            if pending_proxies:
                self.logger.debug(f"Selected pending proxy from {len(pending_proxies)} candidates", extra={"component": "REDIS", "count": len(pending_proxies)})
                return random.choice(pending_proxies)
            
            self.logger.warning("No available or pending proxies found", extra={"component": "REDIS"})
            return None
        except Exception as e:
            self.logger.error(f"Failed to get random available proxy from Redis: {e}", extra={"component": "REDIS"})
            return None

    def get_all_proxies(self) -> List[Proxy]: # 改为实例方法
        """
        获取 Redis 中所有存储的代理。
        """
        client = self.get_redis_client()
        proxies: List[Proxy] = []
        try:
            proxy_keys = client.smembers("proxies:all")
            for key in proxy_keys:
                proxy_data = client.hgetall(key)
                if proxy_data:
                    proxies.append(Proxy.from_dict(proxy_data))
            self.logger.debug(f"Retrieved {len(proxies)} proxies from Redis.", extra={"component": "REDIS", "count": len(proxies)})
            return proxies
        except Exception as e:
            self.logger.error(f"Failed to get all proxies from Redis: {e}", extra={"component": "REDIS"})
            return []

    def get_all_non_cooldown_proxies(self) -> List[Proxy]:
        """
        获取默认主代理池中的代理，排除仍处于冷却期的代理。
        """
        client = self.get_redis_client()
        proxies: List[Proxy] = []
        try:
            proxy_keys = client.smembers("proxies:all")
            for key in proxy_keys:
                if self.is_proxy_in_cooldown(key, client=client):
                    continue
                proxy_data = client.hgetall(key)
                if proxy_data:
                    proxies.append(Proxy.from_dict(proxy_data))
            self.logger.debug(
                f"Retrieved {len(proxies)} non-cooldown proxies from Redis.",
                extra={"component": "REDIS", "count": len(proxies)},
            )
            return proxies
        except Exception as e:
            self.logger.error(f"Failed to get non-cooldown proxies from Redis: {e}", extra={"component": "REDIS"})
            return []

    def get_cooldown_proxy_count(self) -> int:
        """
        获取当前仍处于冷却期的代理数量。
        """
        client = self.get_redis_client()
        try:
            now_value = float(time.time())
            cooldown_count = 0
            cooldown_keys = client.zrangebyscore("proxies:cooldown", f"({now_value}", "+inf")
            for cooldown_key in cooldown_keys:
                cooldown_data = client.hgetall(cooldown_key)
                if not cooldown_data:
                    client.zrem("proxies:cooldown", cooldown_key)
                    continue

                cooldown_until_raw = cooldown_data.get("cooldown_until")
                try:
                    cooldown_until = float(cooldown_until_raw) if cooldown_until_raw is not None else 0.0
                except (TypeError, ValueError):
                    cooldown_until = 0.0

                if cooldown_until > now_value:
                    cooldown_count += 1
                    continue

                client.delete(cooldown_key)
                client.zrem("proxies:cooldown", cooldown_key)
            return cooldown_count
        except Exception as e:
            self.logger.error(f"Failed to get cooldown proxy count: {e}", extra={"component": "REDIS"})
            return 0

    def schedule_proxy_check(self, proxy_key: str, next_check_at: float) -> bool:
        """
        将代理写入检测调度表。
        """
        client = self.get_redis_client()
        schedule_key = getattr(self.config, "TEST_SCHEDULE_ZSET_KEY", "proxies:test_schedule")
        try:
            client.zadd(schedule_key, {proxy_key: next_check_at})
            self.logger.debug(
                f"Scheduled proxy {proxy_key} for check at {next_check_at}",
                extra={"component": "REDIS", "proxy_key": proxy_key, "next_check_at": next_check_at},
            )
            return True
        except Exception as e:
            self.logger.error(
                f"Failed to schedule proxy {proxy_key} for check: {e}",
                extra={"component": "REDIS", "proxy": proxy_key},
            )
            return False

    def get_due_proxy_keys(self, limit: int, now_ts: float) -> List[str]:
        """
        获取到期需要检测的代理 key。
        """
        client = self.get_redis_client()
        schedule_key = getattr(self.config, "TEST_SCHEDULE_ZSET_KEY", "proxies:test_schedule")
        try:
            if limit <= 0:
                return []
            due_keys = client.zrangebyscore(
                schedule_key,
                min="-inf",
                max=now_ts,
                start=0,
                num=limit,
            )
            return list(due_keys)[:limit]
        except Exception as e:
            self.logger.error(
                f"Failed to get due proxy keys: {e}",
                extra={"component": "REDIS"},
            )
            return []

    def remove_from_test_schedule(self, proxy_key: str) -> bool:
        """
        从检测调度表移除代理。
        """
        client = self.get_redis_client()
        schedule_key = getattr(self.config, "TEST_SCHEDULE_ZSET_KEY", "proxies:test_schedule")
        try:
            client.zrem(schedule_key, proxy_key)
            return True
        except Exception as e:
            self.logger.error(
                f"Failed to remove proxy {proxy_key} from test schedule: {e}",
                extra={"component": "REDIS", "proxy": proxy_key},
            )
            return False

    def batch_update_test_results(self, test_results: List[Dict[str, object]]) -> Dict[str, int]:
        """
        批量写回代理检测结果。

        test_results 中每一项支持：
        - proxy: Proxy
        - next_check_at: float，更新场景必填
        - remove: bool，删除场景为 True
        """
        client = self.get_redis_client()
        summary = {
            "updated": 0,
            "deleted": 0,
            "scheduled": 0,
        }

        if not test_results:
            return summary

        pipeline = client.pipeline(transaction=False)
        schedule_key = getattr(self.config, "TEST_SCHEDULE_ZSET_KEY", "proxies:test_schedule")

        try:
            for item in test_results:
                if not isinstance(item, dict):
                    raise TypeError("batch_update_test_results expects dict items")

                proxy = item.get("proxy")
                if not isinstance(proxy, Proxy):
                    raise TypeError("batch_update_test_results item.proxy must be Proxy")

                proxy_key = self._get_proxy_key(proxy)
                should_remove = bool(item.get("remove", item.get("delete", False)))

                if should_remove:
                    removed_at = item.get("removed_at")
                    last_fail_count = int(item.get("last_fail_count", proxy.fail_count or 0))
                    existing_cooldown = self.get_proxy_cooldown(proxy_key, client=client)
                    existing_strike_count = 0
                    if existing_cooldown:
                        try:
                            existing_strike_count = int(existing_cooldown.get("strike_count", 0))
                        except (TypeError, ValueError):
                            existing_strike_count = 0

                    self.record_proxy_cooldown(
                        proxy=proxy,
                        removed_at=removed_at,
                        strike_count=existing_strike_count + 1,
                        last_fail_count=last_fail_count,
                        client=client,
                    )
                    self._queue_proxy_delete_to_pipeline(pipeline, proxy_key, schedule_key)
                    summary["deleted"] += 1
                    continue

                next_check_at = item.get("next_check_at")
                if next_check_at is None:
                    raise ValueError("batch_update_test_results item.next_check_at is required when remove is False")

                self._queue_proxy_update_to_pipeline(
                    pipeline,
                    proxy,
                    proxy_key,
                    float(next_check_at),
                    schedule_key,
                )
                summary["updated"] += 1
                summary["scheduled"] += 1

            pipeline.execute()
            self.logger.debug(
                f"Batch updated proxies: {summary}",
                extra={"component": "REDIS", **summary},
            )
            return summary
        except Exception as e:
            self.logger.error(
                f"Failed to batch update proxy test results: {e}",
                extra={"component": "REDIS"},
            )
            raise

    def _queue_proxy_update_to_pipeline(
        self,
        pipeline,
        proxy: Proxy,
        proxy_key: str,
        next_check_at: float,
        schedule_key: str,
    ) -> None:
        """将单个代理的检测结果写入 pipeline。"""
        data = proxy.to_dict()
        for field, value in data.items():
            pipeline.hset(proxy_key, field, str(value))

        pipeline.sadd("proxies:all", proxy_key)
        pipeline.zadd("proxies:score", {proxy_key: proxy.score})

        for grade in ["S", "A", "B", "C", "D"]:
            pipeline.srem(f"proxies:grade:{grade}", proxy_key)

        if proxy.grade:
            pipeline.sadd(f"proxies:grade:{proxy.grade}", proxy_key)

        if is_grade_available(proxy.grade):
            pipeline.sadd("proxies:available", proxy_key)
        else:
            pipeline.srem("proxies:available", proxy_key)

        pipeline.zadd(schedule_key, {proxy_key: next_check_at})

    def _queue_proxy_delete_to_pipeline(self, pipeline, proxy_key: str, schedule_key: str) -> None:
        """将单个代理的删除操作写入 pipeline。"""
        pipeline.delete(proxy_key)
        pipeline.srem("proxies:all", proxy_key)
        pipeline.zrem("proxies:score", proxy_key)
        pipeline.zrem(schedule_key, proxy_key)

        for grade in ["S", "A", "B", "C", "D"]:
            pipeline.srem(f"proxies:grade:{grade}", proxy_key)

        pipeline.srem("proxies:available", proxy_key)

    def get_proxies_by_keys(self, keys: List[str]) -> Tuple[List[Proxy], List[str]]:
        """
        按 key 批量获取代理，并返回缺失的 key。
        """
        client = self.get_redis_client()
        proxies: List[Proxy] = []
        missing_keys: List[str] = []
        try:
            if not keys:
                return proxies, missing_keys

            pipeline = client.pipeline(transaction=False)
            for key in keys:
                pipeline.hgetall(key)

            results = pipeline.execute()
            for key, proxy_data in zip(keys, results):
                if proxy_data:
                    try:
                        proxies.append(Proxy.from_dict(proxy_data))
                    except Exception as e:
                        self.logger.warning(
                            f"Proxy data is invalid for key {key}: {e}",
                            extra={"component": "REDIS", "proxy_key": key},
                        )
                        missing_keys.append(key)
                else:
                    missing_keys.append(key)
            return proxies, missing_keys
        except redis.exceptions.RedisError as e:
            self.logger.error(
                f"Failed to get proxies by keys: {e}",
                extra={"component": "REDIS"},
            )
            raise RuntimeError(f"Failed to get proxies by keys: {e}") from e
        except Exception as e:
            self.logger.error(
                f"Failed to get proxies by keys: {e}",
                extra={"component": "REDIS"},
            )
            raise

    def get_all_available_proxies(self, max_fail_count: int = 5) -> List[Proxy]:
        """
        获取 Redis 中所有可用的代理。
        可用性条件：success_count > 0 且 fail_count < max_fail_count
        
        Args:
            max_fail_count: 最大允许的失败次数，默认为 5
        
        Returns:
            可用代理列表
        """
        available_proxies: List[Proxy] = []
        try:
            for proxy in self.get_all_non_cooldown_proxies():
                fail_count = int(getattr(proxy, "fail_count", 0) or 0)
                grade = str(getattr(proxy, "grade", "") or "").upper()

                # 检查可用性条件（B级及以上）
                if is_grade_available(grade) and fail_count < max_fail_count:
                    available_proxies.append(proxy)
            
            self.logger.debug(f"Retrieved {len(available_proxies)} available proxies from Redis.", extra={"component": "REDIS", "count": len(available_proxies)})
            return available_proxies
        except Exception as e:
            self.logger.error(f"Failed to get all available proxies from Redis: {e}", extra={"component": "REDIS"})
            return []

    @staticmethod
    def _get_proxy_key(proxy: Proxy) -> str:
        """
        根据代理信息生成唯一的 Redis key。
        """
        return f"proxy:{proxy.protocol}:{proxy.ip}:{proxy.port}"

    @staticmethod
    def _get_proxy_cooldown_key(proxy: Proxy) -> str:
        """
        根据代理信息生成冷却记录 key。
        """
        return f"proxy:cooldown:{proxy.protocol}:{proxy.ip}:{proxy.port}"

    @staticmethod
    def _get_proxy_cooldown_key_from_proxy_key(proxy_key: str) -> str:
        """
        根据代理 key 生成冷却记录 key。
        """
        parts = proxy_key.split(":")
        if len(parts) >= 4 and parts[0] == "proxy":
            return f"proxy:cooldown:{parts[1]}:{parts[2]}:{parts[3]}"
        return f"proxy:cooldown:{proxy_key}"

    def close_connection_pool(self): # 改为实例方法
        """关闭 Redis 连接池"""
        if self._pool:
            self._pool.disconnect()
            self._pool = None
            self._instance = None
            self.logger.info("Redis ConnectionPool closed.", extra={"component": "REDIS"})

    def rebuild_connection_pool(self):
        """
        重建 Redis 连接池（配置热更新后调用）
        """
        self.close_connection_pool()
        self.logger.info("Redis ConnectionPool rebuild requested.", extra={"component": "REDIS"})
        return self.get_redis_client()

    def get_proxies_by_grade(self, grade: str) -> List[Proxy]:
        """
        获取指定等级的所有代理
        """
        client = self.get_redis_client()
        proxies = []
        try:
            proxy_keys = client.smembers(f"proxies:grade:{grade}")
            for key in proxy_keys:
                proxy_data = client.hgetall(key)
                if proxy_data:
                    proxies.append(Proxy.from_dict(proxy_data))
            return proxies
        except Exception as e:
            self.logger.error(f"Failed to get proxies by grade {grade}: {e}", extra={"component": "REDIS", "grade": grade})
            return []

    def get_available_proxy_count(self) -> int:
        """
        获取可用代理数量（B级及以上）
        """
        client = self.get_redis_client()
        try:
            return client.scard("proxies:available")
        except Exception as e:
            self.logger.error(f"Failed to get available proxy count: {e}", extra={"component": "REDIS"})
            return 0

    def get_grade_statistics(self) -> Dict[str, int]:
        """
        获取各等级代理数量统计
        """
        client = self.get_redis_client()
        stats = {}
        try:
            for grade in ['S', 'A', 'B', 'C', 'D']:
                count = client.scard(f"proxies:grade:{grade}")
                stats[grade] = count
            stats['available'] = client.scard("proxies:available")
            stats['total'] = client.scard("proxies:all")
            return stats
        except Exception as e:
            self.logger.error(f"Failed to get grade statistics: {e}", extra={"component": "REDIS"})
            return {}
