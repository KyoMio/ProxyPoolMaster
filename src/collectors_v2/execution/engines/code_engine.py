"""code 模式执行引擎。"""


from typing import Any, Dict, List, Optional


def run_code_engine(code_ref: Optional[Dict[str, Any]]) -> List[dict]:
    """
    阶段 2 最小实现：
    - 支持 code_ref.mock_proxies 作为测试数据输入
    - 后续将替换为动态模块加载 + 子进程调用
    """
    if code_ref is None:
        return []
    if not isinstance(code_ref, dict):
        raise ValueError("code_ref 必须是 dict")

    mock_proxies = code_ref.get("mock_proxies", [])
    if mock_proxies is None:
        return []
    if not isinstance(mock_proxies, list):
        raise ValueError("code_ref.mock_proxies 必须是列表")
    return list(mock_proxies)
