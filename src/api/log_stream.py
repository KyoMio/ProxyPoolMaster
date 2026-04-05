"""日志 WebSocket 增量推送管理器。"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Optional

from fastapi import WebSocket

from src.api.log_endpoints import (
    get_system_logs,
    get_current_log_file_path,
    parse_log_line,
    parse_exclude_components,
    level_meets_minimum,
)

logger = logging.getLogger("ProxyPoolMaster")


def normalize_filters(filters: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """规范化前端订阅过滤条件。"""
    if not isinstance(filters, dict):
        return {
            "level": "",
            "min_level": "",
            "component": "",
            "exclude_components": "",
            "keyword": "",
            "collector_id": "",
            "run_id": "",
        }

    return {
        "level": str(filters.get("level", "") or "").strip(),
        "min_level": str(filters.get("min_level", "") or "").strip(),
        "component": str(filters.get("component", "") or "").strip(),
        "exclude_components": str(filters.get("exclude_components", "") or "").strip(),
        "keyword": str(filters.get("keyword", "") or "").strip(),
        "collector_id": str(filters.get("collector_id", "") or "").strip(),
        "run_id": str(filters.get("run_id", "") or "").strip(),
    }


def matches_filters(log_entry: Dict[str, Any], filters: Optional[Dict[str, Any]]) -> bool:
    """判断单条日志是否命中过滤条件。"""
    normalized = normalize_filters(filters)
    level = normalized["level"]
    min_level = normalized["min_level"]
    component = normalized["component"]
    excluded_component_set = parse_exclude_components(normalized["exclude_components"])
    keyword = normalized["keyword"].lower()
    collector_id = normalized["collector_id"]
    run_id = normalized["run_id"]

    if level and str(log_entry.get("level", "")).upper() != level.upper():
        return False

    if min_level and not level_meets_minimum(str(log_entry.get("level", "")), min_level):
        return False

    if component and str(log_entry.get("component", "")).upper() != component.upper():
        return False

    if excluded_component_set and str(log_entry.get("component", "")).upper() in excluded_component_set:
        return False

    if keyword:
        message = str(log_entry.get("message", "")).lower()
        source = str(log_entry.get("source", "")).lower()
        if keyword not in message and keyword not in source:
            return False

    context = log_entry.get("context", {}) or {}
    if collector_id and str(context.get("collector_id", "")).strip() != collector_id:
        return False

    if run_id and str(context.get("run_id", "")).strip() != run_id:
        return False

    return True


@dataclass
class LogClientState:
    """单个 WebSocket 客户端状态。"""

    websocket: Optional[WebSocket] = None
    filters: Dict[str, str] = field(
        default_factory=lambda: {
            "level": "",
            "min_level": "",
            "component": "",
            "exclude_components": "",
            "keyword": "",
            "collector_id": "",
            "run_id": "",
        }
    )
    page_size: int = 20
    max_queue_size: int = 1000
    dropped_count: int = 0
    queue: Deque[Dict[str, Any]] = field(init=False)

    def __post_init__(self):
        self.queue = deque(maxlen=self.max_queue_size)

    def enqueue(self, item: Dict[str, Any]):
        if len(self.queue) >= self.max_queue_size:
            self.dropped_count += 1
        self.queue.append(item)

    def pop_batch(self, max_batch: int) -> list[Dict[str, Any]]:
        items: list[Dict[str, Any]] = []
        while self.queue and len(items) < max_batch:
            items.append(self.queue.popleft())
        return items


class LogStreamManager:
    """日志增量推送管理器。"""

    def __init__(
        self,
        poll_interval_seconds: float = 0.5,
        max_batch_size: int = 100,
        max_queue_size: int = 1000,
    ):
        self._poll_interval_seconds = poll_interval_seconds
        self._max_batch_size = max_batch_size
        self._max_queue_size = max_queue_size

        self._clients: Dict[int, LogClientState] = {}
        self._lock = asyncio.Lock()
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False

        self._log_offset = 0
        self._log_inode: Optional[tuple[int, int]] = None

    async def start(self):
        if self._worker_task and not self._worker_task.done():
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Log stream worker started")

    async def stop(self):
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
        logger.info("Log stream worker stopped")

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        client_id = id(websocket)
        async with self._lock:
            self._clients[client_id] = LogClientState(
                websocket=websocket,
                max_queue_size=self._max_queue_size,
            )
        logger.info("Log WS client connected, total=%s", len(self._clients))

    async def disconnect(self, websocket: WebSocket):
        client_id = id(websocket)
        async with self._lock:
            self._clients.pop(client_id, None)
        logger.info("Log WS client disconnected, total=%s", len(self._clients))

    def get_connection_count(self) -> int:
        """获取当前日志 WS 连接数。"""
        return len(self._clients)

    async def handle_message(self, websocket: WebSocket, raw_message: str):
        try:
            payload = json.loads(raw_message)
        except json.JSONDecodeError:
            await websocket.send_json({"type": "error", "message": "Invalid JSON payload"})
            return

        msg_type = str(payload.get("type", "")).strip().lower()
        if msg_type == "subscribe":
            filters = normalize_filters(payload.get("filters"))
            page_size = int(payload.get("pageSize", 20) or 20)
            await self.subscribe(websocket, filters, page_size)
            return
        if msg_type == "unsubscribe":
            await self.unsubscribe(websocket)
            return

        await websocket.send_json({"type": "error", "message": "Unsupported message type"})

    async def subscribe(self, websocket: WebSocket, filters: Dict[str, str], page_size: int):
        client_id = id(websocket)
        safe_page_size = max(1, min(page_size, 100))
        async with self._lock:
            state = self._clients.get(client_id)
            if not state:
                return
            state.filters = filters
            state.page_size = safe_page_size
            state.queue.clear()
            state.dropped_count = 0

        snapshot = await get_system_logs(
            level=filters["level"] or None,
            min_level=filters["min_level"] or None,
            component=filters["component"] or None,
            exclude_components=filters["exclude_components"] or None,
            keyword=filters["keyword"] or None,
            collector_id=filters["collector_id"] or None,
            run_id=filters["run_id"] or None,
            page=1,
            size=safe_page_size,
        )
        await websocket.send_json(
            {
                "type": "log_snapshot",
                "data": {
                    "logs": snapshot.get("data", []),
                    "total": snapshot.get("total", 0),
                },
            }
        )

    async def unsubscribe(self, websocket: WebSocket):
        client_id = id(websocket)
        async with self._lock:
            state = self._clients.get(client_id)
            if not state:
                return
            state.filters = {
                "level": "",
                "min_level": "",
                "component": "",
                "exclude_components": "",
                "keyword": "",
                "collector_id": "",
                "run_id": "",
            }
            state.queue.clear()
            state.dropped_count = 0

    def _read_new_logs(self) -> list[Dict[str, Any]]:
        log_file_path = get_current_log_file_path()
        if not os.path.exists(log_file_path):
            self._log_offset = 0
            self._log_inode = None
            return []

        stat_info = os.stat(log_file_path)
        inode = (stat_info.st_dev, stat_info.st_ino)
        if self._log_inode != inode or stat_info.st_size < self._log_offset:
            self._log_offset = 0
        self._log_inode = inode

        with open(log_file_path, "r", encoding="utf-8", errors="ignore") as file_handle:
            file_handle.seek(self._log_offset)
            lines = file_handle.readlines()
            self._log_offset = file_handle.tell()

        parsed_entries: list[Dict[str, Any]] = []
        for line in lines:
            parsed = parse_log_line(line)
            if parsed:
                parsed_entries.append(parsed)
        return parsed_entries

    async def _worker_loop(self):
        while self._running:
            try:
                new_logs = await asyncio.to_thread(self._read_new_logs)
                if new_logs:
                    await self._distribute_logs(new_logs)
                    await self._flush_queues()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("Log stream worker error: %s", exc, exc_info=True)
            await asyncio.sleep(self._poll_interval_seconds)

    async def _distribute_logs(self, logs: list[Dict[str, Any]]):
        async with self._lock:
            for log_entry in logs:
                for state in self._clients.values():
                    if matches_filters(log_entry, state.filters):
                        state.enqueue(log_entry)

    async def _flush_queues(self):
        disconnected_ids: list[int] = []
        async with self._lock:
            client_items = list(self._clients.items())

        for client_id, state in client_items:
            ws = state.websocket
            if ws is None:
                disconnected_ids.append(client_id)
                continue

            try:
                if state.dropped_count > 0:
                    await ws.send_json(
                        {
                            "type": "log_overflow",
                            "data": {"dropped": state.dropped_count},
                        }
                    )
                    state.dropped_count = 0

                batch = state.pop_batch(self._max_batch_size)
                if batch:
                    await ws.send_json(
                        {
                            "type": "log_append",
                            "data": {"logs": batch},
                        }
                    )
            except Exception:
                disconnected_ids.append(client_id)

        if disconnected_ids:
            async with self._lock:
                for client_id in disconnected_ids:
                    self._clients.pop(client_id, None)


log_stream_manager = LogStreamManager()
