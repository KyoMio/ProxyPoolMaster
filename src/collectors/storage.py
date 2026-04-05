from typing import Any, Dict


def store_proxy_with_cooldown_awareness(redis_manager: Any, proxy: Any) -> Dict[str, Any]:
    """
    存储代理并保留冷却拦截的结构化结果。
    """
    store_proxy = getattr(redis_manager, "store_proxy", None)
    if callable(store_proxy):
        store_result = store_proxy(proxy)
        if isinstance(store_result, dict):
            return store_result
        return {
            "stored": bool(store_result),
            "created": bool(store_result),
            "proxy_key": None,
        }

    add_proxy = getattr(redis_manager, "add_proxy", None)
    if callable(add_proxy):
        is_new = add_proxy(proxy)
        return {
            "stored": bool(is_new),
            "created": bool(is_new),
            "proxy_key": None,
        }

    raise AttributeError("redis_manager must provide store_proxy() or add_proxy()")
