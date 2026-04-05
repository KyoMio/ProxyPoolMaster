"""collectors_v2 运行时辅助。"""

import asyncio
from typing import Optional

from src.collectors_v2.repository import CollectorV2Repository
from src.collectors_v2.worker_main import run_worker_loop


def get_collector_runtime_mode(config) -> str:
    mode = str(getattr(config, "COLLECTOR_RUNTIME_MODE", "") or "").strip().lower()
    if mode in {"legacy", "v2", "disabled"}:
        return mode
    if int(getattr(config, "COLLECTOR_V2_ENABLED", 0) or 0) == 1:
        return "v2"
    return "legacy"


def should_start_legacy_collector(config) -> bool:
    return get_collector_runtime_mode(config) == "legacy"


def is_collector_v2_enabled(config) -> bool:
    return (
        get_collector_runtime_mode(config) == "v2"
        and int(getattr(config, "COLLECTOR_V2_ENABLED", 0) or 0) == 1
    )


def is_collector_worker_enabled(config) -> bool:
    return is_collector_v2_enabled(config) and int(getattr(config, "COLLECTOR_WORKER_ENABLED", 1) or 0) == 1


def start_collector_worker_task(
    config,
    logger,
    redis_manager,
    create_task=asyncio.create_task,
):
    """在当前事件循环中启动 Collector Worker 心跳任务。"""
    if not is_collector_worker_enabled(config):
        return None

    repository = CollectorV2Repository(redis_manager)
    logger.info("Starting Collector Worker task...", extra={"component": "COLLECTOR_WORKER"})
    return create_task(
        run_worker_loop(
            config=config,
            logger=logger,
            repository=repository,
        )
    )


async def stop_collector_worker_task(task, logger) -> None:
    """停止 Collector Worker 心跳任务。"""
    if task is None:
        return

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    logger.info("Collector Worker task stopped.", extra={"component": "COLLECTOR_WORKER"})
