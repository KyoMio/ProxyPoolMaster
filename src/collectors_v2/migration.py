"""collectors_v2 迁移逻辑。"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Optional

from src.collectors_v2.repository import CollectorV2Repository


def _normalize_collector_id(collector: Dict[str, Any], index: int) -> str:
    raw_id = str(collector.get("id", "")).strip()
    if raw_id:
        return raw_id

    raw_name = str(collector.get("name", "")).strip().lower()
    normalized = re.sub(r"[^a-z0-9_\-\s]", "", raw_name)
    normalized = re.sub(r"[\s\-]+", "_", normalized).strip("_")
    if normalized:
        return normalized
    return f"collector_{index + 1}"


def _to_bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _to_positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed <= 0:
        return default
    return parsed


def _normalize_mode(collector: Dict[str, Any]) -> str:
    collector_type = str(collector.get("type", "")).strip().lower()
    source = str(collector.get("source", "")).strip().lower()

    if collector_type == "code":
        return "code"
    if source in {"code", "custom"}:
        return "code"
    if collector.get("module_path") or collector.get("class_name"):
        return "code"
    return "simple"


def _normalize_source(collector: Dict[str, Any]) -> str:
    source = str(collector.get("source", "")).strip().lower()
    if source in {"api", "scrape"}:
        return source

    collector_type = str(collector.get("type", "")).strip().lower()
    if collector_type in {"scrape", "crawler", "html"}:
        return "scrape"
    return "api"


def _build_spec(collector: Dict[str, Any]) -> Dict[str, Any]:
    spec = collector.get("spec")
    if isinstance(spec, dict):
        return dict(spec)

    params = collector.get("params")
    if isinstance(params, dict):
        return dict(params)
    return {}


def _build_code_ref(collector: Dict[str, Any], mode: str) -> Optional[Dict[str, Any]]:
    if mode != "code":
        return None

    code_ref = collector.get("code_ref")
    if isinstance(code_ref, dict) and code_ref:
        return dict(code_ref)

    built: Dict[str, Any] = {}
    module_path = str(collector.get("module_path", "")).strip()
    class_name = str(collector.get("class_name", "")).strip()
    filename = str(collector.get("filename", "")).strip()
    if module_path:
        built["module_path"] = module_path
    if class_name:
        built["class_name"] = class_name
    if filename:
        built["filename"] = filename

    return built or None


def _build_definition(collector: Dict[str, Any], index: int, default_interval: int) -> Dict[str, Any]:
    collector_id = _normalize_collector_id(collector, index)
    name = str(collector.get("name", collector_id)).strip() or collector_id
    mode = _normalize_mode(collector)
    enabled = _to_bool(collector.get("enabled", True), default=True)
    now = datetime.now().isoformat()

    env_vars = collector.get("env_vars")
    if not isinstance(env_vars, dict):
        env_vars = {}

    interval_seconds = _to_positive_int(
        collector.get("interval_seconds", collector.get("interval")),
        default=default_interval,
    )

    return {
        "id": collector_id,
        "name": name,
        "mode": mode,
        "source": _normalize_source(collector),
        "enabled": enabled,
        "lifecycle": "published" if enabled else "paused",
        "interval_seconds": interval_seconds,
        "spec": _build_spec(collector),
        "code_ref": _build_code_ref(collector, mode),
        "env_vars": dict(env_vars),
        "meta": {
            "version": 1,
            "created_at": now,
            "updated_at": now,
            "migrated_from": "config.COLLECTORS",
        },
    }


def _resolve_dependencies(
    config_instance: Optional[Any],
    repository: Optional[CollectorV2Repository],
    logger_instance: Optional[Any],
) -> tuple[Any, CollectorV2Repository, Any]:
    if config_instance is not None and repository is not None and logger_instance is not None:
        return config_instance, repository, logger_instance

    from src import app_globals

    resolved_config = config_instance or app_globals.global_config
    resolved_repo = repository or CollectorV2Repository(app_globals.global_redis_manager)
    resolved_logger = logger_instance or app_globals.global_logger
    return resolved_config, resolved_repo, resolved_logger


def migrate_collectors_to_v2(
    config_instance: Optional[Any] = None,
    repository: Optional[CollectorV2Repository] = None,
    logger_instance: Optional[Any] = None,
    force_update: bool = False,
) -> Dict[str, Any]:
    """将 legacy `config.COLLECTORS` 迁移为 V2 定义。"""
    config_instance, repository, logger_instance = _resolve_dependencies(
        config_instance=config_instance,
        repository=repository,
        logger_instance=logger_instance,
    )

    collectors = getattr(config_instance, "COLLECTORS", []) or []
    default_interval = _to_positive_int(
        getattr(config_instance, "COLLECT_INTERVAL_SECONDS", 300),
        default=300,
    )

    summary: Dict[str, Any] = {
        "total": len(collectors),
        "migrated": 0,
        "skipped": 0,
        "failed": 0,
        "errors": [],
    }

    for index, raw in enumerate(collectors):
        if not isinstance(raw, dict):
            summary["failed"] += 1
            summary["errors"].append(f"index={index} collector is not a dict")
            continue

        try:
            definition = _build_definition(raw, index=index, default_interval=default_interval)
            existing = repository.get_definition(definition["id"])
            if existing and not force_update:
                summary["skipped"] += 1
                continue

            repository.upsert_definition(definition)
            summary["migrated"] += 1
        except Exception as exc:  # pragma: no cover - 防御性保护
            summary["failed"] += 1
            summary["errors"].append(f"id={raw.get('id', index)} {exc}")

    logger_instance.info(
        "collector v2 migration finished: total=%s migrated=%s skipped=%s failed=%s",
        summary["total"],
        summary["migrated"],
        summary["skipped"],
        summary["failed"],
    )
    return summary


def auto_migrate_collectors_to_v2(
    config_instance: Optional[Any] = None,
    repository: Optional[CollectorV2Repository] = None,
    logger_instance: Optional[Any] = None,
) -> Dict[str, Any]:
    """根据 feature flag 自动执行迁移。"""
    config_instance, repository, logger_instance = _resolve_dependencies(
        config_instance=config_instance,
        repository=repository,
        logger_instance=logger_instance,
    )
    v2_enabled = _to_bool(getattr(config_instance, "COLLECTOR_V2_ENABLED", 0), default=False)
    migration_auto = _to_bool(getattr(config_instance, "COLLECTOR_V2_MIGRATION_AUTO", 0), default=False)

    if not (v2_enabled and migration_auto):
        return {
            "executed": False,
            "total": 0,
            "migrated": 0,
            "skipped": 0,
            "failed": 0,
            "errors": [],
        }

    report = migrate_collectors_to_v2(
        config_instance=config_instance,
        repository=repository,
        logger_instance=logger_instance,
    )
    report["executed"] = True
    return report
