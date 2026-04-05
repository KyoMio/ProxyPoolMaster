#!/usr/bin/env python3
"""初始化或补齐代理检测调度索引。"""

from __future__ import annotations

import argparse
import os
import sys
import time
from itertools import islice
from typing import Any, Dict, Iterable, List, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.config import Config
from src.database.models import Proxy
from src.database.redis_client import RedisManager
from src.testers.scoring import ProxyScorer


def chunked(items: Iterable[str], size: int) -> Iterable[List[str]]:
    """按固定大小分块，避免一次性处理过多代理 key。"""
    iterator = iter(items)
    while True:
        batch = list(islice(iterator, size))
        if not batch:
            break
        yield batch


def calculate_next_check_at(
    proxy: Proxy,
    scorer: ProxyScorer,
    base_interval: int,
    now_ts: float,
) -> float:
    """
    根据代理当前状态计算下一次调度时间。

    规则与 tester 的间隔倍数保持一致；
    如果代理从未被检测过，则优先给一个立即可消费的时间。
    """
    if proxy.last_check_time in (None, 0, 0.0):
        return now_ts

    multiplier = scorer.calculate_test_interval_multiplier(
        proxy.grade or "B",
        proxy.fail_count or 0,
    )
    return float(proxy.last_check_time) + (base_interval * multiplier)


def migrate_test_schedule(
    redis_manager: RedisManager,
    config: Config,
    *,
    dry_run: bool = False,
    force: bool = False,
    batch_size: Optional[int] = None,
    now_ts: Optional[float] = None,
) -> Dict[str, int]:
    """
    初始化或补齐 `proxies:test_schedule`。

    返回统计摘要，方便测试和 CLI 输出。
    """
    client = redis_manager.get_redis_client()
    schedule_key = getattr(config, "TEST_SCHEDULE_ZSET_KEY", "proxies:test_schedule")
    effective_batch_size = int(batch_size or getattr(config, "TEST_MIGRATION_BATCH_SIZE", 500))
    if effective_batch_size <= 0:
        effective_batch_size = 1

    current_ts = time.time() if now_ts is None else float(now_ts)
    scorer = ProxyScorer(getattr(redis_manager, "logger", None))

    proxy_keys = sorted(client.smembers("proxies:all"))
    summary = {
        "total": len(proxy_keys),
        "existing": 0,
        "added": 0,
        "rebuilt": 0,
        "dirty": 0,
    }

    for batch_keys in chunked(proxy_keys, effective_batch_size):
        read_pipeline = client.pipeline(transaction=False)
        for proxy_key in batch_keys:
            read_pipeline.hgetall(proxy_key)
            read_pipeline.zscore(schedule_key, proxy_key)

        batch_results = read_pipeline.execute()
        write_ops = []
        batch_interval = int(getattr(config, "TEST_INTERVAL_SECONDS", 300))

        for index, proxy_key in enumerate(batch_keys):
            raw_proxy_data = batch_results[index * 2]
            existing_schedule = batch_results[index * 2 + 1]

            if not raw_proxy_data:
                summary["dirty"] += 1
                if not dry_run:
                    redis_manager.delete_proxy_by_key(proxy_key)
                continue

            try:
                proxy = Proxy.from_dict(raw_proxy_data)
            except Exception:
                summary["dirty"] += 1
                if not dry_run:
                    redis_manager.delete_proxy_by_key(proxy_key)
                continue

            if existing_schedule is not None and not force:
                summary["existing"] += 1
                continue

            next_check_at = calculate_next_check_at(
                proxy,
                scorer,
                batch_interval,
                current_ts,
            )

            if existing_schedule is None:
                summary["added"] += 1
            else:
                summary["rebuilt"] += 1

            if not dry_run:
                write_ops.append(("zadd", proxy_key, next_check_at))

        if write_ops and not dry_run:
            write_pipeline = client.pipeline(transaction=False)
            for op, proxy_key, value in write_ops:
                if op == "zrem":
                    write_pipeline.zrem(schedule_key, proxy_key)
                else:
                    write_pipeline.zadd(schedule_key, {proxy_key: value})
            write_pipeline.execute()

    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="初始化或补齐代理检测调度索引")
    parser.add_argument("--dry-run", action="store_true", help="只统计不写入 Redis")
    parser.add_argument("--force", action="store_true", help="重建已有调度时间")
    parser.add_argument("--batch-size", type=int, default=None, help="批处理大小")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    config = Config()
    from src.logger import setup_logging

    logger = setup_logging(config, component="MIGRATION")
    redis_manager = RedisManager(config, logger)

    summary = migrate_test_schedule(
        redis_manager,
        config,
        dry_run=args.dry_run,
        force=args.force,
        batch_size=args.batch_size,
    )

    print(f"总代理数: {summary['total']}")
    print(f"已存在数量: {summary['existing']}")
    print(f"新增数量: {summary['added']}")
    print(f"重建数量: {summary['rebuilt']}")
    print(f"脏数据数量: {summary['dirty']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
