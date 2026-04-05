"""collectors_v2 执行入口。"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from src.collectors.proxy_validator import ProxyDataValidator
from src.collectors.storage import store_proxy_with_cooldown_awareness
from src.collectors_v2.execution.engines.code_engine import run_code_engine
from src.collectors_v2.execution.engines.simple_engine import run_simple_engine
from src.collectors_v2.execution.protocol import ExecutionInput, ExecutionResult
from src.collectors_v2.execution.sandbox import build_timeout_result, truncate_output


def _run_by_mode(collector: Dict[str, Any]) -> List[dict]:
    mode = str(collector.get("mode", "simple"))
    if mode == "simple":
        return run_simple_engine(collector.get("spec", {}))
    if mode == "code":
        return run_code_engine(collector.get("code_ref"))
    raise ValueError(f"不支持的 collector mode: {mode}")


def _get_redis_manager():
    from src import app_globals

    redis_manager = getattr(app_globals, "global_redis_manager", None)
    if redis_manager is None:
        raise ValueError("global redis manager is unavailable")
    return redis_manager


def _store_valid_proxies(valid_proxies: List[Any]) -> tuple[int, int, int, List[str]]:
    redis_manager = _get_redis_manager()
    stored_count = 0
    duplicate_count = 0
    cooldown_blocked_count = 0
    storage_errors: List[str] = []

    for proxy in valid_proxies:
        try:
            store_result = store_proxy_with_cooldown_awareness(redis_manager, proxy)
            if store_result.get("cooldown_blocked", False):
                cooldown_blocked_count += 1
                continue
            if not store_result.get("stored", False):
                storage_errors.append(f"存储失败 {proxy.ip}:{proxy.port}: store_proxy returned False")
                continue

            if store_result.get("created", False):
                stored_count += 1
            else:
                duplicate_count += 1
        except Exception as exc:
            storage_errors.append(f"存储失败 {proxy.ip}:{proxy.port}: {exc}")

    return stored_count, duplicate_count, cooldown_blocked_count, storage_errors


def run_execution(payload: ExecutionInput) -> ExecutionResult:
    started_at = time.time()
    try:
        collector = payload.get("collector")
        if not isinstance(collector, dict):
            raise ValueError("payload.collector 缺失或格式错误")

        raw_result = _run_by_mode(collector)
        if not isinstance(raw_result, (list, tuple)):
            raise ValueError("执行器返回必须是列表")

        validation_result = ProxyDataValidator.validate_batch(list(raw_result))
        valid_count = int(validation_result.get("valid", 0) or 0)
        valid_proxies = list(validation_result.get("proxies", []) or [])
        errors = list(validation_result.get("errors", []) or [])
        skip_store = os.getenv("COLLECTOR_V2_SKIP_STORE", "0") == "1"
        if skip_store:
            stored_count = valid_count
            duplicate_count = 0
            cooldown_blocked_count = 0
        else:
            stored_count, duplicate_count, cooldown_blocked_count, storage_errors = _store_valid_proxies(valid_proxies)
            errors.extend(storage_errors)

        return {
            "success": True,
            "raw_count": len(raw_result),
            "valid_count": valid_count,
            "stored_count": stored_count,
            "duplicate_count": duplicate_count,
            "cooldown_blocked_count": cooldown_blocked_count,
            "execution_time_ms": int((time.time() - started_at) * 1000),
            "errors": errors,
        }
    except Exception as exc:
        return {
            "success": False,
            "raw_count": 0,
            "valid_count": 0,
            "stored_count": 0,
            "duplicate_count": 0,
            "cooldown_blocked_count": 0,
            "execution_time_ms": int((time.time() - started_at) * 1000),
            "errors": [str(exc)],
        }


def run_execution_subprocess(
    payload: ExecutionInput,
    timeout_seconds: int = 60,
    stdout_limit_kb: int = 256,
) -> ExecutionResult:
    """
    通过子进程执行采集逻辑，避免用户逻辑阻塞 API 进程。
    """
    project_root = Path(__file__).resolve().parents[3]
    command = [sys.executable, "-m", "src.collectors_v2.execution.subprocess_entry"]
    env = os.environ.copy()
    if str(payload.get("trigger", "")).strip().lower() == "test":
        env["COLLECTOR_V2_SKIP_STORE"] = "1"

    try:
        completed = subprocess.run(
            command,
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            capture_output=True,
            cwd=str(project_root),
            env=env,
            timeout=max(1, int(timeout_seconds)),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return build_timeout_result(timeout_seconds)
    except Exception as exc:
        return {
            "success": False,
            "raw_count": 0,
            "valid_count": 0,
            "stored_count": 0,
            "duplicate_count": 0,
            "cooldown_blocked_count": 0,
            "execution_time_ms": 0,
            "errors": [f"subprocess execution failed: {exc}"],
        }

    stdout_text = truncate_output(completed.stdout or "", stdout_limit_kb)
    stderr_text = truncate_output(completed.stderr or "", stdout_limit_kb)

    if completed.returncode != 0:
        return {
            "success": False,
            "raw_count": 0,
            "valid_count": 0,
            "stored_count": 0,
            "duplicate_count": 0,
            "cooldown_blocked_count": 0,
            "execution_time_ms": 0,
            "errors": [f"subprocess exit code {completed.returncode}", stderr_text or stdout_text or "unknown error"],
        }

    candidate_json = ""
    for line in reversed((stdout_text or "").splitlines()):
        stripped = line.strip()
        if stripped:
            candidate_json = stripped
            break

    try:
        parsed = json.loads(candidate_json or "{}")
    except json.JSONDecodeError:
        return {
            "success": False,
            "raw_count": 0,
            "valid_count": 0,
            "stored_count": 0,
            "duplicate_count": 0,
            "cooldown_blocked_count": 0,
            "execution_time_ms": 0,
            "errors": [f"invalid subprocess output: {candidate_json or stdout_text or stderr_text}"],
        }

    return {
        "success": bool(parsed.get("success", False)),
        "raw_count": int(parsed.get("raw_count", 0) or 0),
        "valid_count": int(parsed.get("valid_count", 0) or 0),
        "stored_count": int(parsed.get("stored_count", 0) or 0),
        "duplicate_count": int(parsed.get("duplicate_count", 0) or 0),
        "cooldown_blocked_count": int(parsed.get("cooldown_blocked_count", 0) or 0),
        "execution_time_ms": int(parsed.get("execution_time_ms", 0) or 0),
        "errors": list(parsed.get("errors", []) or []),
    }
