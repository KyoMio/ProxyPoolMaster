"""collectors_v2 worker 入口。"""

import asyncio

from src.collectors_v2.execution.runner import run_execution_subprocess
from src.collectors_v2.repository import CollectorV2Repository
from src.collectors_v2.scheduler import CollectorV2Scheduler
from src.config import Config
from src.database.redis_client import RedisManager
from src.logger import setup_logging


def _calc_heartbeat_ttl(tick_seconds: int) -> int:
    """确保心跳 TTL 大于上报周期，避免短抖动导致误判。"""
    return max(5, tick_seconds * 3)


async def run_worker_loop(
    config: Config,
    logger,
    repository: CollectorV2Repository,
    stop_after_ticks: int = 0,
) -> None:
    worker_id = str(getattr(config, "COLLECTOR_WORKER_ID", "collector-worker-1"))
    tick_seconds = max(1, int(getattr(config, "COLLECTOR_WORKER_TICK_SECONDS", 1)))
    heartbeat_ttl = _calc_heartbeat_ttl(tick_seconds)

    def update_heartbeat(active_jobs: int, queue_backlog: int) -> None:
        repository.upsert_worker_heartbeat(
            worker_id=worker_id,
            status="running",
            active_jobs=active_jobs,
            queue_backlog=queue_backlog,
            version="v2",
            ttl_seconds=heartbeat_ttl,
        )

    scheduler = CollectorV2Scheduler(
        repository=repository,
        run_execution=run_execution_subprocess,
        timeout_seconds=int(getattr(config, "COLLECTOR_EXEC_TIMEOUT", 60)),
        stdout_limit_kb=int(getattr(config, "COLLECTOR_EXEC_STDOUT_LIMIT_KB", 256)),
        logger=logger,
        worker_id=worker_id,
        heartbeat_update=update_heartbeat,
    )

    tick_count = 0
    while True:
        due_collectors = scheduler.list_due_collectors()
        update_heartbeat(active_jobs=0, queue_backlog=len(due_collectors))
        logger.debug(
            "collector worker heartbeat updated",
            extra={
                "component": "COLLECTOR_WORKER",
                "worker_id": worker_id,
                "active_jobs": 0,
                "queue_backlog": len(due_collectors),
            },
        )

        scheduler.tick()

        tick_count += 1
        if stop_after_ticks > 0 and tick_count >= stop_after_ticks:
            return

        await asyncio.sleep(tick_seconds)


def main() -> int:
    config = Config()
    logger = setup_logging(config, logger_name="ProxyPoolMaster", component="COLLECTOR_WORKER")

    if int(getattr(config, "COLLECTOR_V2_ENABLED", 0)) != 1:
        logger.info("Collector V2 disabled, collector worker exits.", extra={"component": "COLLECTOR_WORKER"})
        return 0

    if int(getattr(config, "COLLECTOR_WORKER_ENABLED", 1)) != 1:
        logger.info("Collector worker disabled by flag, exits.", extra={"component": "COLLECTOR_WORKER"})
        return 0

    redis_manager = RedisManager(config, logger)
    repository = CollectorV2Repository(redis_manager)

    logger.info("Collector worker started.", extra={"component": "COLLECTOR_WORKER"})
    try:
        asyncio.run(run_worker_loop(config=config, logger=logger, repository=repository))
    except KeyboardInterrupt:
        logger.info("Collector worker stopped by KeyboardInterrupt.", extra={"component": "COLLECTOR_WORKER"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
