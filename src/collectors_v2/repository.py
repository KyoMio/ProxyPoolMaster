"""collectors_v2 持久化访问层。"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.collectors_v2.models import CollectorDefinition, CollectorRunRecord, WorkerHeartbeat
from src.database.redis_client import RedisManager


class CollectorV2Repository:
    """V2 Redis 访问入口。"""

    INDEX_KEY = "collectors:v2:index"
    DEFINITION_KEY_PREFIX = "collectors:v2:def"
    RUNS_KEY_PREFIX = "collectors:v2:runs"
    WORKER_HEARTBEAT_KEY_PREFIX = "collectors:v2:worker:heartbeat"

    def __init__(self, redis_manager: RedisManager):
        self.redis_manager = redis_manager

    def _definition_key(self, collector_id: str) -> str:
        return f"{self.DEFINITION_KEY_PREFIX}:{collector_id}"

    def _runs_key(self, collector_id: str) -> str:
        return f"{self.RUNS_KEY_PREFIX}:{collector_id}"

    def _worker_heartbeat_key(self, worker_id: str) -> str:
        return f"{self.WORKER_HEARTBEAT_KEY_PREFIX}:{worker_id}"

    def upsert_definition(self, definition: CollectorDefinition) -> CollectorDefinition:
        collector_id = str(definition.get("id", "")).strip()
        if not collector_id:
            raise ValueError("collector id is required")

        payload = dict(definition)
        redis_client = self.redis_manager.get_redis_client()
        redis_client.set(self._definition_key(collector_id), json.dumps(payload, ensure_ascii=False))
        redis_client.sadd(self.INDEX_KEY, collector_id)
        return payload

    def get_definition(self, collector_id: str) -> Optional[CollectorDefinition]:
        redis_client = self.redis_manager.get_redis_client()
        raw = redis_client.get(self._definition_key(collector_id))
        if not raw:
            return None

        try:
            parsed: CollectorDefinition = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return parsed

    def list_definitions(self) -> List[CollectorDefinition]:
        redis_client = self.redis_manager.get_redis_client()
        ids = sorted(list(redis_client.smembers(self.INDEX_KEY) or []))

        definitions: List[CollectorDefinition] = []
        for collector_id in ids:
            definition = self.get_definition(str(collector_id))
            if definition is not None:
                definitions.append(definition)
        return definitions

    def delete_definition(self, collector_id: str) -> None:
        redis_client = self.redis_manager.get_redis_client()
        redis_client.delete(self._definition_key(collector_id))
        redis_client.srem(self.INDEX_KEY, collector_id)
        redis_client.delete(self._runs_key(collector_id))

    def append_run_record(
        self,
        collector_id: str,
        run_record: CollectorRunRecord,
        history_limit: int = 200,
    ) -> CollectorRunRecord:
        redis_client = self.redis_manager.get_redis_client()
        key = self._runs_key(collector_id)
        redis_client.lpush(key, json.dumps(run_record, ensure_ascii=False))
        redis_client.ltrim(key, 0, max(0, int(history_limit) - 1))
        return run_record

    def get_runs(self, collector_id: str, limit: int = 20) -> List[CollectorRunRecord]:
        redis_client = self.redis_manager.get_redis_client()
        raw_runs = redis_client.lrange(self._runs_key(collector_id), 0, max(0, int(limit) - 1))

        runs: List[CollectorRunRecord] = []
        for raw in raw_runs:
            try:
                parsed: CollectorRunRecord = json.loads(raw)
            except json.JSONDecodeError:
                continue
            runs.append(parsed)
        return runs

    def get_last_run(self, collector_id: str) -> Optional[CollectorRunRecord]:
        runs = self.get_runs(collector_id, limit=1)
        return runs[0] if runs else None

    def upsert_worker_heartbeat(
        self,
        worker_id: str,
        status: str,
        active_jobs: int,
        queue_backlog: int,
        version: str = "v2",
        ttl_seconds: int = 30,
    ) -> WorkerHeartbeat:
        payload: WorkerHeartbeat = {
            "worker_id": worker_id,
            "status": status,
            "last_heartbeat": datetime.now().isoformat(),
            "active_jobs": max(0, int(active_jobs)),
            "queue_backlog": max(0, int(queue_backlog)),
            "version": version,
        }

        redis_client = self.redis_manager.get_redis_client()
        redis_client.setex(
            self._worker_heartbeat_key(worker_id),
            max(1, int(ttl_seconds)),
            json.dumps(payload, ensure_ascii=False),
        )
        return payload

    def get_worker_heartbeat(self, worker_id: str) -> Optional[WorkerHeartbeat]:
        redis_client = self.redis_manager.get_redis_client()
        raw = redis_client.get(self._worker_heartbeat_key(worker_id))
        if not raw:
            return None

        try:
            data: Dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            return None

        return {
            "worker_id": str(data.get("worker_id", worker_id)),
            "status": str(data.get("status", "stopped")),
            "last_heartbeat": str(data.get("last_heartbeat", "")),
            "active_jobs": int(data.get("active_jobs", 0) or 0),
            "queue_backlog": int(data.get("queue_backlog", 0) or 0),
            "version": str(data.get("version", "v2")),
        }
