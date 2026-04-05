from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, List, Optional
import asyncio
import os
import time
from datetime import datetime, timedelta
import redis

# 从 app_globals 导入全局的 config, logger 和 redis_manager 实例
from src.app_globals import global_config as config, global_logger as logger, global_redis_manager as redis_manager, global_collector_manager
import src.app_globals as app_globals  # 导入模块以便动态获取 global_tester_manager
from src.api.auth import verify_api_token # Assume verify_api_token is in api.auth
from src.middleware.metrics import get_metrics, get_metrics_history as get_real_metrics_history, record_metrics_snapshot
from src.collectors_v2.repository import CollectorV2Repository
from src.collectors_v2.runtime import get_collector_runtime_mode, is_collector_v2_enabled

router = APIRouter()

# 注意：指标记录任务现在在 main.py 的 lifespan 中启动
# 保留 start_metrics_recorder 函数供 main.py 调用

# 记录API服务启动时间
_api_start_time = time.time()

# 指标快照记录任务
_metrics_recorder_task = None


def _get_redis_manager():
    """动态获取最新的 RedisManager，避免导入期快照导致热更新失效。"""
    return app_globals.global_redis_manager


def _can_connect_tcp_endpoint(host: str, port: int, timeout_seconds: int = 2) -> tuple[bool, Optional[str]]:
    """执行轻量级 TCP 探测，帮助快速判断 Redis 端口是否可达。"""
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(timeout_seconds)
        result = sock.connect_ex((host, port))
        if result != 0:
            return False, f"Cannot connect to {host}:{port} (socket error {result})"
        return True, None
    finally:
        sock.close()


def merge_connection_metrics(
    api_metrics: Dict[str, Any],
    dashboard_ws_connections: int,
    log_ws_connections: int,
) -> Dict[str, Any]:
    """
    合并 HTTP 在途请求与 WS 连接数，输出统一的并发连接指标。
    """
    http_inflight = int(api_metrics.get("concurrent_connections", 0) or 0)
    websocket_total = max(0, int(dashboard_ws_connections)) + max(0, int(log_ws_connections))

    merged = dict(api_metrics)
    merged["http_inflight_requests"] = http_inflight
    merged["websocket_connections"] = websocket_total
    merged["concurrent_connections"] = http_inflight + websocket_total
    return merged


def _merge_tester_batch_metrics(stats: Dict[str, Any]) -> Dict[str, Any]:
    """补齐 tester 的批次指标，避免不同来源的 stats 结构不一致。"""
    merged = dict(stats)
    merged.setdefault("queue_backlog", 0)
    merged.setdefault("last_batch_duration_seconds", 0.0)
    merged.setdefault("batch_throughput_per_min", 0.0)
    merged.setdefault("last_batch_tested", 0)
    return merged


async def _build_proxy_pool_metrics(
    collector_stats: Dict[str, Any],
    tester_stats: Dict[str, Any],
) -> Dict[str, Any]:
    """
    统一构建代理池业务指标，确保实时卡片与历史图表使用相同口径。
    """
    collector_runtime_mode = get_collector_runtime_mode(config)
    if collector_runtime_mode == "v2":
        collect_rate_per_min = _get_v2_collect_rate_per_min()
    elif collector_runtime_mode == "legacy":
        collect_rate_per_min = collector_stats.get("collect_rate_per_min", 0)
    else:
        collect_rate_per_min = 0

    success_rate = collector_stats.get("success_rate", 0.0)
    try:
        current_redis_manager = _get_redis_manager()
        all_proxies = await asyncio.to_thread(lambda: current_redis_manager.get_all_proxies())
        total = len(all_proxies)
        available = sum(
            1
            for proxy in all_proxies
            if getattr(proxy, "grade", None) in {"S", "A", "B"}
        )
        success_rate = round(available / total, 2) if total > 0 else 0.0
    except Exception as e:
        logger.warning(f"Failed to get proxy stats: {e}")

    return {
        "collect_rate_per_min": collect_rate_per_min,
        "test_rate_per_min": tester_stats.get("test_rate_per_min", 0),
        "success_rate": success_rate,
        "cleanup_rate_per_min": tester_stats.get("cleanup_rate_per_min", 0),
        "test_queue_backlog": tester_stats.get("queue_backlog", 0),
        "last_test_batch_duration_seconds": tester_stats.get("last_batch_duration_seconds", 0.0),
        "batch_throughput_per_min": tester_stats.get("batch_throughput_per_min", 0.0),
        "last_test_batch_size": tester_stats.get("last_batch_tested", 0),
    }


def _is_tester_running_in_backend() -> bool:
    """检查 Backend 的 Tester 是否正在运行（通过 Redis）"""
    try:
        return bool(_get_redis_manager().get_redis_client().exists("tester:running"))
    except Exception:
        return False


def _get_tester_stats_from_redis() -> tuple[dict, bool]:
    """
    从 Redis 获取 Backend Tester 的统计信息
    Returns: (stats_dict, is_backend_running)
    """
    # 首先检查 Tester 是否标记为运行中（即使还没有统计数据）
    is_running = _is_tester_running_in_backend()
    
    try:
        import json
        stats_json = _get_redis_manager().get_redis_client().get("tester:stats")
        if stats_json:
            redis_stats = json.loads(stats_json)
            start_time = redis_stats.get("start_time")
            uptime_seconds = time.time() - start_time if start_time else 0
            test_rate = 0
            cleanup_rate = 0
            if uptime_seconds > 5:
                test_rate = round(redis_stats.get("total_tested", 0) / (uptime_seconds / 60), 2)
                cleanup_rate = round(redis_stats.get("total_removed", 0) / (uptime_seconds / 60), 2)
            return {
                "total_tested": redis_stats.get("total_tested", 0),
                "total_passed": redis_stats.get("total_passed", 0),
                "total_failed": redis_stats.get("total_failed", 0),
                "total_removed": redis_stats.get("total_removed", 0),
                "test_rounds": redis_stats.get("test_rounds", 0),
                "test_rate_per_min": test_rate,
                "cleanup_rate_per_min": cleanup_rate,
                "queue_backlog": redis_stats.get("queue_backlog", 0),
                "last_batch_duration_seconds": redis_stats.get("last_batch_duration_seconds", 0.0),
                "batch_throughput_per_min": redis_stats.get("batch_throughput_per_min", 0.0),
                "last_batch_tested": redis_stats.get("last_batch_tested", 0),
            }, True
    except Exception as e:
        logger.debug(f"Failed to get tester stats from Redis: {e}")
    
    # 如果有 running 标志但没有统计数据，返回空统计但标记为运行中
    if is_running:
        return {}, True
    
    return {}, False


def _get_tester_module_status(now_str: str, uptime: str) -> dict:
    """获取 Tester Manager 模块状态"""
    tm = getattr(app_globals, 'global_tester_manager', None)
    
    # 检查本地是否有运行的 TesterManager
    if tm and getattr(tm, '_running', False):
        stats = tm.get_status().get("stats", {})
        stats = _merge_tester_batch_metrics(stats)
        return {
            "moduleName": "Tester Manager",
            "status": "Running",
            "lastHeartbeat": now_str,
            "uptime": uptime,
            "performance": {
                "test_rate": stats.get("test_rate_per_min", 0),
                "cleanup_rate": stats.get("cleanup_rate_per_min", 0),
                "total_tested": stats.get("total_tested", 0),
                "total_removed": stats.get("total_removed", 0),
                "queue_backlog": stats.get("queue_backlog", 0),
                "last_batch_duration_seconds": stats.get("last_batch_duration_seconds", 0.0),
                "batch_throughput_per_min": stats.get("batch_throughput_per_min", 0.0),
                "last_batch_tested": stats.get("last_batch_tested", 0),
            }
        }
    
    # 尝试从 Redis 读取 Backend 统计
    stats, is_backend = _get_tester_stats_from_redis()
    stats = _merge_tester_batch_metrics(stats)
    return {
        "moduleName": "Tester Manager",
        "status": "Running" if is_backend else "Stopped",
        "lastHeartbeat": now_str,
        "uptime": uptime,
        "performance": {
            "test_rate": stats.get("test_rate_per_min", 0),
            "cleanup_rate": stats.get("cleanup_rate_per_min", 0),
            "total_tested": stats.get("total_tested", 0),
            "total_removed": stats.get("total_removed", 0),
            "queue_backlog": stats.get("queue_backlog", 0),
            "last_batch_duration_seconds": stats.get("last_batch_duration_seconds", 0.0),
            "batch_throughput_per_min": stats.get("batch_throughput_per_min", 0.0),
            "last_batch_tested": stats.get("last_batch_tested", 0),
        }
    }

def _get_collector_worker_heartbeat() -> Optional[Dict[str, Any]]:
    """读取 Collector Worker 心跳。"""
    worker_id = str(getattr(config, "COLLECTOR_WORKER_ID", "collector-worker-1"))
    try:
        repository = CollectorV2Repository(_get_redis_manager())
        return repository.get_worker_heartbeat(worker_id)
    except Exception as e:
        logger.debug(f"Failed to get collector worker heartbeat: {e}")
        return None


def _get_v2_collect_rate_per_min(window_minutes: int = 5, now: Optional[datetime] = None) -> float:
    """根据 V2 run 记录计算最近窗口内的真实收集速率。"""
    current = now or datetime.now()
    window = max(1, int(window_minutes))
    cutoff = current - timedelta(minutes=window)
    history_limit = max(20, int(getattr(config, "COLLECTOR_RUN_HISTORY_LIMIT", 200) or 200))

    try:
        repository = CollectorV2Repository(_get_redis_manager())
        total_stored = 0

        for definition in repository.list_definitions():
            if not isinstance(definition, dict):
                continue
            if not bool(definition.get("enabled", True)):
                continue
            if str(definition.get("lifecycle", "draft")) != "published":
                continue

            collector_id = str(definition.get("id", "")).strip()
            if not collector_id:
                continue

            for run in repository.get_runs(collector_id, limit=history_limit):
                if str(run.get("trigger", "")) != "schedule":
                    continue

                time_text = str(run.get("ended_at") or run.get("started_at") or "").strip()
                if not time_text:
                    continue

                try:
                    run_time = datetime.fromisoformat(time_text)
                except ValueError:
                    continue

                if run_time < cutoff or run_time > current:
                    continue

                metrics = run.get("metrics", {}) or {}
                total_stored += int(metrics.get("stored_count", 0) or 0)

        return round(total_stored / window, 2)
    except Exception as e:
        logger.debug(f"Failed to calculate V2 collect rate: {e}")
        return 0.0


def _to_system_module_status(raw_status: str) -> str:
    normalized = (raw_status or "").strip().lower()
    if normalized == "running":
        return "Running"
    if normalized == "degraded":
        return "Degraded"
    if normalized == "unset":
        return "Unset"
    return "Stopped"


def _get_collector_worker_module_status(now_str: str, uptime: str) -> dict:
    """构建 Collector Worker 的模块状态返回。"""
    runtime_mode = get_collector_runtime_mode(config)
    if runtime_mode != "v2":
        return {
            "moduleName": "Collector Worker",
            "status": "Unset",
            "lastHeartbeat": now_str,
            "uptime": uptime,
            "details": {
                "worker_id": str(getattr(config, "COLLECTOR_WORKER_ID", "collector-worker-1")),
                "version": "v2",
            },
            "performance": {
                "active_jobs": 0,
                "queue_backlog": 0,
            }
        }

    if not is_collector_v2_enabled(config):
        return {
            "moduleName": "Collector Worker",
            "status": "Unset",
            "lastHeartbeat": now_str,
            "uptime": uptime,
            "details": {
                "worker_id": str(getattr(config, "COLLECTOR_WORKER_ID", "collector-worker-1")),
                "version": "v2",
            },
            "performance": {
                "active_jobs": 0,
                "queue_backlog": 0,
            }
        }

    heartbeat = _get_collector_worker_heartbeat()
    if not heartbeat:
        return {
            "moduleName": "Collector Worker",
            "status": "Stopped",
            "lastHeartbeat": now_str,
            "uptime": uptime,
            "details": {
                "worker_id": str(getattr(config, "COLLECTOR_WORKER_ID", "collector-worker-1")),
                "version": "v2",
            },
            "performance": {
                "active_jobs": 0,
                "queue_backlog": 0,
            }
        }

    return {
        "moduleName": "Collector Worker",
        "status": _to_system_module_status(str(heartbeat.get("status", "stopped"))),
        "lastHeartbeat": heartbeat.get("last_heartbeat", now_str),
        "uptime": uptime,
        "details": {
            "worker_id": heartbeat.get("worker_id", str(getattr(config, "COLLECTOR_WORKER_ID", "collector-worker-1"))),
            "version": heartbeat.get("version", "v2"),
        },
        "performance": {
            "active_jobs": int(heartbeat.get("active_jobs", 0) or 0),
            "queue_backlog": int(heartbeat.get("queue_backlog", 0) or 0),
        }
    }


def _build_collector_worker_summary(module_status: Dict[str, Any]) -> Dict[str, Any]:
    """将系统模块状态压缩成前端可直接消费的 Worker 摘要。"""
    performance = module_status.get("performance", {}) or {}
    raw_status = str(module_status.get("status", "stopped")).strip().lower()
    status = raw_status if raw_status in {"running", "degraded", "stopped", "unset"} else "stopped"

    return {
        "status": status,
        "activeJobs": int(performance.get("active_jobs", 0) or 0),
        "queueBacklog": int(performance.get("queue_backlog", 0) or 0),
        "lastHeartbeat": str(module_status.get("lastHeartbeat", "")),
    }


def _build_collector_realtime_payload_sync() -> Dict[str, Any]:
    """构造 Collector 管理页实时推送载荷。"""
    now = datetime.now()
    now_str = now.isoformat()
    uptime_seconds = max(0, int(time.time() - _api_start_time))
    uptime = str(timedelta(seconds=uptime_seconds))

    collector_status = global_collector_manager.get_status()
    collector_module_status = _get_collector_module_status(now_str, uptime, collector_status)
    worker_summary = _build_collector_worker_summary(collector_module_status)
    cooldown_pool_count = 0

    try:
        current_redis_manager = _get_redis_manager()
        helper = getattr(current_redis_manager, "get_cooldown_proxy_count", None)
        if callable(helper):
            cooldown_pool_count = int(helper() or 0)
    except Exception as exc:
        logger.debug(f"Failed to load cooldown proxy count for realtime payload: {exc}")

    repository = CollectorV2Repository(_get_redis_manager())
    collectors: List[Dict[str, Any]] = []
    total = published = paused = draft = success_count = rated_count = 0
    recent_stored_count = 0

    try:
        definitions = repository.list_definitions()
    except Exception as exc:
        logger.debug(f"Failed to list collector definitions for realtime payload: {exc}")
        definitions = []

    for definition in definitions:
        if not isinstance(definition, dict):
            continue

        collector_id = str(definition.get("id", "")).strip()
        if not collector_id:
            continue

        total += 1
        lifecycle = str(definition.get("lifecycle", "draft")).strip().lower()
        if lifecycle == "published":
            published += 1
        elif lifecycle == "paused":
            paused += 1
        else:
            draft += 1

        try:
            last_run = repository.get_last_run(collector_id)
        except Exception as exc:
            logger.debug(f"Failed to load last run for collector {collector_id}: {exc}")
            last_run = None

        collector_payload = dict(definition)
        collector_payload["last_run"] = last_run
        collectors.append(collector_payload)

        if not last_run:
            continue

        rated_count += 1
        run_status = str(last_run.get("status", "")).strip().lower()
        if run_status in {"success", "partial_success"}:
            success_count += 1

        metrics = last_run.get("metrics", {}) or {}
        recent_stored_count += int(metrics.get("stored_count", 0) or 0)

    overview = {
        "total": total,
        "published": published,
        "paused": paused,
        "draft": draft,
        "recentStoredCount": recent_stored_count,
        "successRate": round(success_count / rated_count, 2) if rated_count > 0 else 0.0,
        "cooldownPoolCount": max(0, cooldown_pool_count),
    }

    return {
        "worker_summary": worker_summary,
        "overview": overview,
        "collectors": collectors,
    }


async def get_collector_realtime_payload() -> Dict[str, Any]:
    """异步获取 Collector 管理页实时推送载荷。"""
    return await asyncio.to_thread(_build_collector_realtime_payload_sync)


def _get_collector_manager_module_status(now_str: str, uptime: str, collector_status: Dict[str, Any]) -> dict:
    runtime_mode = get_collector_runtime_mode(config)
    collector_stats = collector_status.get("stats", {})

    if runtime_mode != "legacy":
        return {
            "moduleName": "Collector Manager",
            "status": "Unset",
            "lastHeartbeat": now_str,
            "uptime": uptime,
            "details": {
                "version": "legacy",
                "collectors_count": collector_status.get("collectors_count", 0),
                "collectors": collector_status.get("collectors", []),
                "stats": collector_stats,
            },
            "performance": {
                "collect_rate": 0,
                "success_rate": 0.0,
                "queue_length": 0,
                "raw_count": 0,
                "stored_count": 0,
                "cooldown_blocked_count": 0,
            }
        }

    return {
        "moduleName": "Collector Manager",
        "status": "Running" if collector_status["running"] else "Stopped",
        "lastHeartbeat": collector_status.get("collectors", [{}])[0].get("last_heartbeat", now_str) if collector_status.get("collectors") else now_str,
        "uptime": uptime,
        "details": {
            "version": "legacy",
            "collectors_count": collector_status.get("collectors_count", 0),
            "collectors": collector_status.get("collectors", []),
            "stats": collector_stats,
        },
        "performance": {
            "collect_rate": collector_stats.get("collect_rate_per_min", 0),
            "success_rate": collector_stats.get("success_rate", 0.0),
            "queue_length": collector_stats.get("queue_length", collector_stats.get("stored_count", 0)),
            "raw_count": collector_stats.get("raw_count", collector_stats.get("last_collection_count", 0)),
            "stored_count": collector_stats.get("stored_count", collector_stats.get("queue_length", 0)),
            "cooldown_blocked_count": collector_stats.get("cooldown_blocked_count", 0),
        }
    }


def _get_collector_module_status(
    now_str: str,
    uptime: str,
    collector_status: Optional[Dict[str, Any]] = None,
) -> dict:
    """统一返回当前 collector 模块状态，不再区分 manager / worker 展示。"""
    runtime_mode = get_collector_runtime_mode(config)
    current_collector_status = collector_status or global_collector_manager.get_status()

    if runtime_mode == "legacy":
        module = _get_collector_manager_module_status(now_str, uptime, current_collector_status)
    elif runtime_mode == "v2":
        module = _get_collector_worker_module_status(now_str, uptime)
    else:
        module = {
            "moduleName": "Collector",
            "status": "Unset",
            "lastHeartbeat": now_str,
            "uptime": uptime,
            "details": {
                "version": "disabled",
                "runtime_mode": "disabled",
            },
            "performance": {
                "active_jobs": 0,
                "queue_backlog": 0,
                "collect_rate": 0,
                "success_rate": 0.0,
                "queue_length": 0,
                "raw_count": 0,
                "stored_count": 0,
                "cooldown_blocked_count": 0,
            }
        }

    normalized = dict(module)
    normalized["moduleName"] = "Collector"
    details = dict(normalized.get("details", {}) or {})
    details["runtime_mode"] = runtime_mode
    normalized["details"] = details
    return normalized


async def _metrics_snapshot_worker():
    """后台任务：定期记录指标快照"""
    while True:
        try:
            await asyncio.sleep(60)  # 每分钟记录一次
            
            # 获取Collector和Tester的统计
            collector_stats = {}
            tester_stats = {}
            
            try:
                collector_status = global_collector_manager.get_status()
                collector_stats = collector_status.get("stats", {})
            except Exception as e:
                logger.debug(f"Failed to get collector stats for snapshot: {e}")
            
            try:
                # 动态获取 global_tester_manager，避免导入时的快照问题
                current_tester_manager = getattr(app_globals, 'global_tester_manager', None)
                if current_tester_manager:
                    tester_status = current_tester_manager.get_status()
                    tester_stats = tester_status.get("stats", {})
                    tester_stats = _merge_tester_batch_metrics(tester_stats)
                else:
                    # 尝试从 Redis 读取 Backend 的统计
                    import json
                    current_redis_manager = _get_redis_manager()
                    # 首先检查 Backend Tester 是否正在运行
                    backend_running = bool(current_redis_manager.get_redis_client().exists("tester:running"))
                    
                    stats_json = current_redis_manager.get_redis_client().get("tester:stats")
                    if stats_json:
                        redis_stats = json.loads(stats_json)
                        tester_stats = {
                            "total_tested": redis_stats.get("total_tested", 0),
                            "total_passed": redis_stats.get("total_passed", 0),
                            "total_failed": redis_stats.get("total_failed", 0),
                            "total_removed": redis_stats.get("total_removed", 0),
                            "test_rounds": redis_stats.get("test_rounds", 0),
                            "queue_backlog": redis_stats.get("queue_backlog", 0),
                            "last_batch_duration_seconds": redis_stats.get("last_batch_duration_seconds", 0.0),
                            "batch_throughput_per_min": redis_stats.get("batch_throughput_per_min", 0.0),
                            "last_batch_tested": redis_stats.get("last_batch_tested", 0),
                        }
                        # 计算速率
                        start_time = redis_stats.get("start_time")
                        if start_time:
                            uptime_seconds = time.time() - start_time
                            if uptime_seconds > 5:
                                tester_stats["test_rate_per_min"] = round(tester_stats["total_tested"] / (uptime_seconds / 60), 2)
                                tester_stats["cleanup_rate_per_min"] = round(tester_stats["total_removed"] / (uptime_seconds / 60), 2)
                        tester_stats = _merge_tester_batch_metrics(tester_stats)
                    elif backend_running:
                        # Backend 正在运行但还没有统计数据（刚启动）
                        tester_stats = {
                            "total_tested": 0,
                            "total_passed": 0,
                            "total_failed": 0,
                            "total_removed": 0,
                            "test_rounds": 0,
                            "test_rate_per_min": 0,
                            "cleanup_rate_per_min": 0,
                            "queue_backlog": 0,
                            "last_batch_duration_seconds": 0.0,
                            "batch_throughput_per_min": 0.0,
                            "last_batch_tested": 0,
                        }
            except Exception as e:
                logger.debug(f"Failed to get tester stats for snapshot: {e}")
            
            # 快照中的并发连接数需与实时接口一致：HTTP在途 + Dashboard WS + Log WS
            api_metrics_for_snapshot = get_metrics()
            from src.api.websocket_manager import websocket_manager
            from src.api.log_stream import log_stream_manager
            api_metrics_for_snapshot = merge_connection_metrics(
                api_metrics_for_snapshot,
                dashboard_ws_connections=websocket_manager.get_connection_count(),
                log_ws_connections=log_stream_manager.get_connection_count(),
            )

            proxy_pool_metrics = await _build_proxy_pool_metrics(collector_stats, tester_stats)
            collector_snapshot_stats = dict(collector_stats)
            collector_snapshot_stats["collect_rate_per_min"] = proxy_pool_metrics["collect_rate_per_min"]
            collector_snapshot_stats["success_rate"] = proxy_pool_metrics["success_rate"]

            record_metrics_snapshot(
                collector_snapshot_stats,
                tester_stats,
                api_metrics=api_metrics_for_snapshot,
            )
            logger.debug("Metrics snapshot recorded")
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in metrics snapshot worker: {e}")

def start_metrics_recorder():
    """启动指标记录任务"""
    global _metrics_recorder_task
    if _metrics_recorder_task is None or _metrics_recorder_task.done():
        _metrics_recorder_task = asyncio.create_task(_metrics_snapshot_worker())
        logger.info("Metrics snapshot recorder started")


async def get_system_realtime_payload() -> Dict[str, Any]:
    """
    组装系统状态 WebSocket 推送载荷。
    """
    status_data = await get_system_status()
    modules_data = await get_module_status(token="")
    metrics_data = await get_system_metrics(token="")
    return {
        "status": status_data,
        "modules": modules_data,
        "metrics": metrics_data,
        "timestamp": datetime.now().isoformat(),
    }



@router.get("/status", summary="Get overall system status (Redis, API, Services)")
async def get_system_status(
    # 直接使用 app_globals 中已初始化的全局 redis_manager
) -> Dict[str, Any]:
    """
    Retrieves the overall health status of the system and its core components.
    """
    # 获取API服务运行状态
    api_service_status = "Running"
    api_uptime = time.time() - _api_start_time
    collector_runtime_mode = get_collector_runtime_mode(config)

    # 获取CollectorManager状态
    collector_status = global_collector_manager.get_status()

    tester_service_status = _get_tester_module_status(
        datetime.now().isoformat(),
        collector_status.get("uptime_formatted", "Unknown"),
    ).get("status", "Stopped")

    collector_module_status = _get_collector_module_status(
        datetime.now().isoformat(),
        collector_status.get("uptime_formatted", "Unknown"),
        collector_status,
    )
    collector_service_status = collector_module_status.get("status", "Unset")
    collector_version = collector_module_status.get("details", {}).get("version", collector_runtime_mode or "disabled")
    collector_worker_service_status = collector_service_status

    redis_connected = False
    redis_error_msg = None
    redis_config_info = {
        "host": config.REDIS_HOST,
        "port": config.REDIS_PORT,
        "db": config.REDIS_DB
    }
    logger.info(f"Checking Redis connection to {redis_config_info}")

    try:
        is_reachable, reachability_error = _can_connect_tcp_endpoint(config.REDIS_HOST, config.REDIS_PORT)
        if not is_reachable:
            redis_error_msg = reachability_error
            logger.error(f"Socket connection failed: {redis_error_msg}")
            return {
                "redis_status": f"Disconnected ({redis_error_msg})",
                "api_service_status": api_service_status,
                "api_uptime_seconds": int(api_uptime),
                "collector_service_status": collector_service_status,
                "collector_runtime_mode": collector_runtime_mode,
                "collector_version": collector_version,
                "tester_service_status": tester_service_status,
                "collector_worker_status": collector_worker_service_status,
                "overall_status": "degraded"
            }
        else:
            logger.debug(f"Socket connection to {config.REDIS_HOST}:{config.REDIS_PORT} succeeded")
    except Exception as sock_err:
        logger.warning(f"Socket check failed (non-critical): {sock_err}")

    try:
        logger.debug("Attempting to get Redis client for status check.")
        redis_client = _get_redis_manager().get_redis_client()
        logger.debug(f"Redis client obtained: {redis_client}")

        # 尝试执行ping命令（使用较短超时）
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(redis_client.ping)
            try:
                ping_result = future.result(timeout=3)  # 3秒超时
                logger.info(f"Redis ping result: {ping_result}")
                redis_connected = bool(ping_result)
            except concurrent.futures.TimeoutError:
                redis_error_msg = "Redis ping timeout (>3s)"
                logger.error("Redis ping timeout (>3s)")
                redis_connected = False

        if redis_connected:
            # 额外尝试执行一个简单命令来确认连接真正有效
            try:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(lambda: redis_client.info("server"))
                    future.result(timeout=3)
                logger.info("Redis connection verified - INFO command succeeded")
            except Exception as info_err:
                logger.warning(f"Redis ping ok but INFO failed: {info_err}")
                # ping成功但INFO失败，仍然认为连接是成功的

    except redis.exceptions.ConnectionError as e:
        redis_error_msg = f"ConnectionError: {str(e)[:50]}"
        logger.error(f"Redis ConnectionError during status check: {e}")
        redis_connected = False
    except redis.exceptions.TimeoutError as e:
        redis_error_msg = f"TimeoutError: {str(e)[:50]}"
        logger.error(f"Redis TimeoutError during status check: {e}")
        redis_connected = False
    except redis.exceptions.RedisError as e:
        redis_error_msg = f"RedisError: {str(e)[:50]}"
        logger.error(f"Redis Error during status check: {e}")
        redis_connected = False
    except Exception as e:
        redis_error_msg = f"Error: {str(e)[:50]}"
        logger.error(f"Failed to connect to Redis for status check: {e}", exc_info=True)
        redis_connected = False

    logger.debug(f"Final redis_connected status: {redis_connected}")
    redis_status_text = "Connected" if redis_connected else f"Disconnected ({redis_error_msg or 'Unknown error'})"

    return {
        "redis_status": redis_status_text,
        "api_service_status": api_service_status,
        "api_uptime_seconds": int(api_uptime),
        "collector_service_status": collector_service_status,
        "collector_runtime_mode": collector_runtime_mode,
        "collector_version": collector_version,
        "tester_service_status": tester_service_status,
        "collector_worker_status": collector_worker_service_status,
        "overall_status": "ok" if redis_connected and api_service_status == "Running" else "degraded"
    }

@router.get("/modules", summary="Get detailed status of system modules")
async def get_module_status(
    token: str = Depends(verify_api_token)
) -> List[Dict[str, Any]]:
    """
    Retrieves detailed running status for various system modules.
    Returns real-time status from CollectorManager and other components.
    """
    now = datetime.now()
    now_str = now.isoformat()

    # 获取CollectorManager的真实状态
    collector_status = global_collector_manager.get_status()
    uptime = collector_status.get("uptime_formatted", "Unknown")

    modules = [
        {
            "moduleName": "API Service",
            "status": "Running",
            "lastHeartbeat": now_str,
            "uptime": uptime,
            "performance": {}
        },
        _get_collector_module_status(now_str, uptime, collector_status),
        _get_tester_module_status(now_str, uptime),
        {
            "moduleName": "Redis Client",
            "status": "Running",  # 如果能获取到redis_manager实例，说明已初始化
            "lastHeartbeat": now_str,
            "uptime": uptime,
            "performance": {}
        },
    ]

    return modules
@router.get("/metrics", summary="Get system performance metrics")
async def get_system_metrics(
    token: str = Depends(verify_api_token)
) -> Dict[str, Any]:
    """
    获取系统性能指标，包括API性能和代理池业务指标
    """
    try:
        # 获取API性能指标
        api_metrics = get_metrics()

        # 将 WS 连接数合并到并发连接统计，避免自动刷新改为 WS 后并发连接始终为 0
        from src.api.websocket_manager import websocket_manager
        from src.api.log_stream import log_stream_manager
        api_metrics = merge_connection_metrics(
            api_metrics,
            dashboard_ws_connections=websocket_manager.get_connection_count(),
            log_ws_connections=log_stream_manager.get_connection_count(),
        )
        
        # 获取代理池业务指标
        # 从CollectorManager获取采集统计
        collector_status = global_collector_manager.get_status()
        collector_stats = collector_status.get("stats", {})
        
        # 从TesterManager获取测试统计
        tester_stats = {}
        # 动态获取 global_tester_manager，避免导入时的快照问题
        current_tester_manager = getattr(app_globals, 'global_tester_manager', None)
        if current_tester_manager:
            try:
                tester_status = current_tester_manager.get_status()
                tester_stats = tester_status.get("stats", {})
                logger.debug(f"Tester stats from memory: {tester_stats}")
            except Exception as e:
                logger.warning(f"Failed to get tester status from memory: {e}")
        
        # 如果没有从内存获取到统计，尝试从 Redis 读取（Backend 可能在这里写入统计）
        if not tester_stats or tester_stats.get("total_tested", 0) == 0:
            try:
                import json
                current_redis_manager = _get_redis_manager()
                # 先检查 Backend Tester 是否正在运行
                tester_running = await asyncio.to_thread(
                    lambda: bool(current_redis_manager.get_redis_client().exists("tester:running"))
                )
                
                stats_json = await asyncio.to_thread(
                    lambda: current_redis_manager.get_redis_client().get("tester:stats")
                )
                if stats_json:
                    redis_stats = json.loads(stats_json)
                    # 转换为与 TesterManager.get_status() 相同的格式
                    tester_stats = {
                        "total_tested": redis_stats.get("total_tested", 0),
                        "total_passed": redis_stats.get("total_passed", 0),
                        "total_failed": redis_stats.get("total_failed", 0),
                        "total_removed": redis_stats.get("total_removed", 0),
                        "test_rounds": redis_stats.get("test_rounds", 0),
                        "start_time": redis_stats.get("start_time"),
                        "queue_backlog": redis_stats.get("queue_backlog", 0),
                        "last_batch_duration_seconds": redis_stats.get("last_batch_duration_seconds", 0.0),
                        "batch_throughput_per_min": redis_stats.get("batch_throughput_per_min", 0.0),
                        "last_batch_tested": redis_stats.get("last_batch_tested", 0),
                    }
                    # 计算速率
                    import time
                    uptime_seconds = time.time() - tester_stats["start_time"] if tester_stats["start_time"] else 0
                    if uptime_seconds > 5:
                        tester_stats["test_rate_per_min"] = round(tester_stats["total_tested"] / (uptime_seconds / 60), 2)
                        tester_stats["cleanup_rate_per_min"] = round(tester_stats["total_removed"] / (uptime_seconds / 60), 2)
                    tester_stats = _merge_tester_batch_metrics(tester_stats)
                    logger.debug(f"Tester stats from Redis: {tester_stats}")
            except Exception as e:
                logger.debug(f"Failed to get tester stats from Redis: {e}")
        
        proxy_pool_metrics = await _build_proxy_pool_metrics(collector_stats, tester_stats)
        
        return {
            "api_performance": api_metrics,
            "proxy_pool_metrics": proxy_pool_metrics,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error fetching system metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve system metrics: {e}"
        )


@router.get("/metrics/history", summary="Get historical metrics data")
async def get_metrics_history(
    metric: str,  # api_response_time, qps, collect_rate, test_rate, success_rate
    time_range: str = "1h",  # 1h, 6h, 24h
    token: str = Depends(verify_api_token)
) -> Dict[str, Any]:
    """
    获取历史指标数据，用于前端图表展示
    使用真实存储的历史数据
    """
    # 调用metrics模块获取真实历史数据
    return get_real_metrics_history(metric, time_range)
