"""子进程入口：读取 stdin payload，执行并输出 JSON 结果。"""

import json
import sys
from typing import Any, Dict

from src.collectors_v2.execution.runner import run_execution
from src.collectors_v2.execution.sandbox import apply_sandbox_limits


def _read_payload() -> Dict[str, Any]:
    raw = sys.stdin.read()
    if not raw:
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        return {}
    return data


def main() -> int:
    apply_sandbox_limits()
    try:
        payload = _read_payload()
        result = run_execution(payload)
    except Exception as exc:
        result = {
            "success": False,
            "raw_count": 0,
            "valid_count": 0,
            "stored_count": 0,
            "duplicate_count": 0,
            "cooldown_blocked_count": 0,
            "execution_time_ms": 0,
            "errors": [f"subprocess entry failed: {exc}"],
        }

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
