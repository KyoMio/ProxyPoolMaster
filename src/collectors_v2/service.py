"""collectors_v2 业务规则服务。"""

from typing import Dict, Set


_ALLOWED_TRANSITIONS: Dict[str, Dict[str, str]] = {
    "publish": {
        "draft": "published",
        "paused": "published",
    },
    "pause": {
        "published": "paused",
    },
    "resume": {
        "paused": "published",
    },
}


def apply_lifecycle_action(current: str, action: str) -> str:
    transitions = _ALLOWED_TRANSITIONS.get(action, {})
    if current not in transitions:
        raise ValueError(f"invalid lifecycle transition: {current} -> {action}")
    return transitions[current]


def editable_lifecycles() -> Set[str]:
    return {"draft", "paused"}
