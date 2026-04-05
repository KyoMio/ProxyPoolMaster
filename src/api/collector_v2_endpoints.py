"""Collector V2 API endpoints。"""

import re
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src import app_globals
from src.api.auth import verify_api_token
from src.collectors_v2.execution.runner import run_execution_subprocess
from src.collectors_v2.repository import CollectorV2Repository
from src.collectors_v2.run_status import (
    resolve_error_summary as _resolve_error_summary,
    resolve_run_status as _resolve_run_status,
)
from src.collectors_v2.service import apply_lifecycle_action, editable_lifecycles

router = APIRouter()


class CollectorV2Create(BaseModel):
    id: Optional[str] = Field(default=None)
    name: str = Field(..., min_length=1)
    mode: Literal["simple", "code"] = "simple"
    source: Literal["api", "scrape"] = "api"
    enabled: bool = True
    interval_seconds: int = Field(default=300, ge=1)
    spec: Dict[str, Any] = Field(default_factory=dict)
    code_ref: Optional[Dict[str, Any]] = None
    env_vars: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class CollectorV2Update(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    interval_seconds: Optional[int] = Field(default=None, ge=1)
    spec: Optional[Dict[str, Any]] = None
    code_ref: Optional[Dict[str, Any]] = None
    env_vars: Optional[Dict[str, Dict[str, Any]]] = None


class PublishRequest(BaseModel):
    skip_test_validation: bool = False


class TestRunRequest(BaseModel):
    trigger: Literal["test", "manual"] = "test"


def _get_v2_repository() -> CollectorV2Repository:
    return CollectorV2Repository(app_globals.global_redis_manager)


def _now_iso() -> str:
    return datetime.now().isoformat()


def _generate_collector_id(name: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_\-\s]", "", name.strip().lower())
    normalized = re.sub(r"[\s\-]+", "_", normalized)
    normalized = normalized.strip("_") or "collector_v2"
    return normalized


def _require_definition(repo: CollectorV2Repository, collector_id: str) -> Dict[str, Any]:
    definition = repo.get_definition(collector_id)
    if not definition:
        raise HTTPException(status_code=404, detail="collector not found")
    return dict(definition)


def _touch_meta(definition: Dict[str, Any], created: bool = False) -> Dict[str, Any]:
    meta = dict(definition.get("meta") or {})
    now = _now_iso()
    if created and not meta.get("created_at"):
        meta["created_at"] = now
    meta["updated_at"] = now
    if not meta.get("version"):
        meta["version"] = 1
    definition["meta"] = meta
    return definition


def _log_collector_run_event(level: str, message: str, *, collector_id: str, run_id: str, trigger: str, **kwargs: Any) -> None:
    logger = app_globals.global_logger
    error_summary = str(kwargs.get("error_summary") or "").strip()
    if error_summary:
        message = f"{message}: {error_summary}"
    log_extra = {
        "component": "COLLECTOR_WORKER",
        "collector_id": collector_id,
        "run_id": run_id,
        "trigger": trigger,
    }
    log_extra.update(kwargs)
    getattr(logger, level)(message, extra=log_extra)


@router.get("", summary="V2: 获取收集器列表")
async def list_collectors_v2(
    token: str = Depends(verify_api_token),
) -> Dict[str, Any]:
    repo = _get_v2_repository()
    collectors = repo.list_definitions()
    return {"collectors": collectors}


@router.post("", summary="V2: 创建收集器")
async def create_collector_v2(
    data: CollectorV2Create,
    token: str = Depends(verify_api_token),
) -> Dict[str, Any]:
    repo = _get_v2_repository()

    collector_id = (data.id or _generate_collector_id(data.name)).strip()
    if repo.get_definition(collector_id):
        raise HTTPException(status_code=409, detail="collector id already exists")

    definition: Dict[str, Any] = {
        "id": collector_id,
        "name": data.name,
        "mode": data.mode,
        "source": data.source,
        "enabled": data.enabled,
        "lifecycle": "draft",
        "interval_seconds": data.interval_seconds,
        "spec": data.spec,
        "code_ref": data.code_ref,
        "env_vars": data.env_vars,
    }
    definition = _touch_meta(definition, created=True)
    repo.upsert_definition(definition)
    return definition


@router.get("/{collector_id}", summary="V2: 获取收集器详情")
async def get_collector_v2(
    collector_id: str,
    token: str = Depends(verify_api_token),
) -> Dict[str, Any]:
    repo = _get_v2_repository()
    return _require_definition(repo, collector_id)


@router.put("/{collector_id}", summary="V2: 更新收集器")
async def update_collector_v2(
    collector_id: str,
    data: CollectorV2Update,
    token: str = Depends(verify_api_token),
) -> Dict[str, Any]:
    repo = _get_v2_repository()
    definition = _require_definition(repo, collector_id)

    lifecycle = definition.get("lifecycle", "draft")
    if lifecycle not in editable_lifecycles():
        if any([
            data.interval_seconds is not None,
            data.spec is not None,
            data.code_ref is not None,
            data.env_vars is not None,
        ]):
            raise HTTPException(status_code=400, detail="published collector only supports basic updates")

    if data.name is not None:
        definition["name"] = data.name
    if data.enabled is not None:
        definition["enabled"] = data.enabled
    if data.interval_seconds is not None:
        definition["interval_seconds"] = data.interval_seconds
    if data.spec is not None:
        definition["spec"] = data.spec
    if data.code_ref is not None:
        definition["code_ref"] = data.code_ref
    if data.env_vars is not None:
        definition["env_vars"] = data.env_vars

    definition = _touch_meta(definition)
    repo.upsert_definition(definition)
    return definition


@router.post("/{collector_id}/test-run", summary="V2: 测试运行")
async def test_run_collector_v2(
    collector_id: str,
    data: TestRunRequest = TestRunRequest(),
    token: str = Depends(verify_api_token),
) -> Dict[str, Any]:
    repo = _get_v2_repository()
    definition = _require_definition(repo, collector_id)

    run_id = str(uuid4())
    started_at = _now_iso()
    timeout_seconds = int(getattr(app_globals.global_config, "COLLECTOR_EXEC_TIMEOUT", 60))
    stdout_limit_kb = int(getattr(app_globals.global_config, "COLLECTOR_EXEC_STDOUT_LIMIT_KB", 256))
    _log_collector_run_event(
        "info",
        "collector test-run started",
        collector_id=collector_id,
        run_id=run_id,
        trigger=data.trigger,
    )
    exec_result = run_execution_subprocess(
        {
            "run_id": run_id,
            "collector": definition,
            "trigger": data.trigger,
        },
        timeout_seconds=timeout_seconds,
        stdout_limit_kb=stdout_limit_kb,
    )
    ended_at = _now_iso()

    errors = list(exec_result.get("errors", []) or [])
    status = _resolve_run_status(exec_result, errors)
    error_summary = _resolve_error_summary(exec_result, errors, status)
    run_record: Dict[str, Any] = {
        "run_id": run_id,
        "collector_id": collector_id,
        "trigger": data.trigger,
        "status": status,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_ms": int(exec_result.get("execution_time_ms", 0) or 0),
        "metrics": {
            "raw_count": int(exec_result.get("raw_count", 0) or 0),
            "valid_count": int(exec_result.get("valid_count", 0) or 0),
            "stored_count": int(exec_result.get("stored_count", 0) or 0),
            "duplicate_count": int(exec_result.get("duplicate_count", 0) or 0),
            "cooldown_blocked_count": int(exec_result.get("cooldown_blocked_count", 0) or 0),
        },
        "error_summary": error_summary,
        "error_details": errors,
    }
    repo.append_run_record(collector_id, run_record)
    log_level = "error" if status in {"failed", "timeout"} else "info"
    _log_collector_run_event(
        log_level,
        "collector test-run finished",
        collector_id=collector_id,
        run_id=run_id,
        trigger=data.trigger,
        status=status,
        duration_ms=run_record["duration_ms"],
        raw_count=run_record["metrics"]["raw_count"],
        valid_count=run_record["metrics"]["valid_count"],
        stored_count=run_record["metrics"]["stored_count"],
        duplicate_count=run_record["metrics"]["duplicate_count"],
        cooldown_blocked_count=run_record["metrics"]["cooldown_blocked_count"],
        error_summary=run_record["error_summary"],
    )
    return run_record


@router.post("/{collector_id}/publish", summary="V2: 发布收集器")
async def publish_collector_v2(
    collector_id: str,
    data: PublishRequest,
    token: str = Depends(verify_api_token),
) -> Dict[str, Any]:
    repo = _get_v2_repository()
    definition = _require_definition(repo, collector_id)

    if not data.skip_test_validation:
        last_run = repo.get_last_run(collector_id)
        if not last_run or last_run.get("status") not in {"success", "partial_success"}:
            raise HTTPException(status_code=400, detail="publish requires a successful test-run")

    try:
        definition["lifecycle"] = apply_lifecycle_action(definition.get("lifecycle", "draft"), "publish")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    definition = _touch_meta(definition)
    repo.upsert_definition(definition)
    return definition


@router.post("/{collector_id}/pause", summary="V2: 暂停收集器")
async def pause_collector_v2(
    collector_id: str,
    token: str = Depends(verify_api_token),
) -> Dict[str, Any]:
    repo = _get_v2_repository()
    definition = _require_definition(repo, collector_id)

    try:
        definition["lifecycle"] = apply_lifecycle_action(definition.get("lifecycle", "draft"), "pause")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    definition = _touch_meta(definition)
    repo.upsert_definition(definition)
    return definition


@router.post("/{collector_id}/resume", summary="V2: 恢复收集器")
async def resume_collector_v2(
    collector_id: str,
    token: str = Depends(verify_api_token),
) -> Dict[str, Any]:
    repo = _get_v2_repository()
    definition = _require_definition(repo, collector_id)

    try:
        definition["lifecycle"] = apply_lifecycle_action(definition.get("lifecycle", "draft"), "resume")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    definition = _touch_meta(definition)
    repo.upsert_definition(definition)
    return definition


@router.get("/{collector_id}/runs", summary="V2: 运行记录")
async def get_collector_runs_v2(
    collector_id: str,
    limit: int = 20,
    token: str = Depends(verify_api_token),
) -> Dict[str, Any]:
    repo = _get_v2_repository()
    _require_definition(repo, collector_id)
    return {"runs": repo.get_runs(collector_id, limit=max(1, min(limit, 200)))}


@router.delete("/{collector_id}", summary="V2: 删除收集器")
async def delete_collector_v2(
    collector_id: str,
    token: str = Depends(verify_api_token),
) -> Dict[str, Any]:
    repo = _get_v2_repository()
    definition = _require_definition(repo, collector_id)

    lifecycle = definition.get("lifecycle", "draft")
    if lifecycle not in editable_lifecycles():
        raise HTTPException(status_code=400, detail="published collector must be paused before delete")

    repo.delete_definition(collector_id)
    return {"collector_id": collector_id, "deleted": True}
