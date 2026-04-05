"""API性能指标统计中间件"""
import time
import asyncio
from collections import deque
from typing import Dict, Any, Optional
from datetime import datetime
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# 存储最近1000个请求的响应时间（用于计算平均值）
_response_times = deque(maxlen=1000)
_request_count = 0
_error_count = 0
_start_time = time.time()

# 活跃请求跟踪（用于计算并发连接数）
_active_requests = 0

# 历史数据存储（用于图表展示）
# 结构: {metric_name: [(timestamp, value), ...]}
_metrics_history = {
    "api_response_time": deque(maxlen=288),  # 保留24小时（每5分钟一个点）
    "qps": deque(maxlen=288),
    "error_rate": deque(maxlen=288),
    "concurrent_connections": deque(maxlen=288),
    "collect_rate": deque(maxlen=288),
    "test_rate": deque(maxlen=288),
    "success_rate": deque(maxlen=288),
    "cleanup_rate": deque(maxlen=288),
}
_last_snapshot_time = 0  # 上次记录快照的时间
_PERCENT_METRICS = {"error_rate", "success_rate"}

# 锁保护全局计数器，防止并发请求时的竞态条件
_metrics_lock = asyncio.Lock()


class MetricsMiddleware(BaseHTTPMiddleware):
    """统计API响应时间和请求量"""
    
    async def dispatch(self, request: Request, call_next):
        global _request_count, _error_count, _active_requests
        
        start_time = time.time()
        is_api_request = request.url.path.startswith('/api/')
        
        # 增加活跃请求计数
        if is_api_request:
            async with _metrics_lock:
                _active_requests += 1
        
        try:
            response = await call_next(request)
            
            # 只统计API请求（排除静态资源）
            if is_api_request:
                process_time = time.time() - start_time
                _response_times.append(process_time)
                
                async with _metrics_lock:
                    _request_count += 1
                    
                    # 统计错误
                    if response.status_code >= 400:
                        _error_count += 1
            
            return response
        except Exception as e:
            if is_api_request:
                async with _metrics_lock:
                    _error_count += 1
            raise
        finally:
            # 减少活跃请求计数
            if is_api_request:
                async with _metrics_lock:
                    _active_requests -= 1


def get_metrics() -> Dict[str, Any]:
    """获取当前性能指标"""
    global _request_count, _error_count, _start_time, _active_requests
    
    # 计算平均响应时间（毫秒）- deque操作是线程安全的
    avg_response_time_ms = 0
    if _response_times:
        avg_response_time_ms = round(sum(_response_times) / len(_response_times) * 1000, 2)
    
    # 复制计数器值（简单的读取在CPython中是原子的，但复制到局部变量更安全）
    total_requests = _request_count
    total_errors = _error_count
    concurrent = _active_requests
    
    # 计算QPS（近60秒）
    elapsed = time.time() - _start_time
    qps = round(total_requests / elapsed, 2) if elapsed > 0 else 0
    
    # 计算错误率
    error_rate = round(total_errors / total_requests, 4) if total_requests > 0 else 0
    
    return {
        "avg_response_time_ms": avg_response_time_ms,
        "qps": qps,
        "error_rate": error_rate,
        "concurrent_connections": concurrent,  # 当前正在处理的并发请求数
        "total_requests": total_requests,
        "total_errors": total_errors
    }


def record_metrics_snapshot(
    collector_stats: Dict = None,
    tester_stats: Dict = None,
    api_metrics: Optional[Dict[str, Any]] = None,
):
    """
    记录当前指标快照到历史数据
    应该由外部定时调用（如每分钟一次）
    """
    global _last_snapshot_time
    
    now = time.time()
    # 避免过于频繁的记录（至少间隔60秒）
    if now - _last_snapshot_time < 60:
        return
    
    _last_snapshot_time = now
    metrics = api_metrics or get_metrics()
    
    # 记录API性能指标
    _metrics_history["api_response_time"].append((now, metrics["avg_response_time_ms"]))
    _metrics_history["qps"].append((now, metrics["qps"]))
    _metrics_history["error_rate"].append((now, metrics["error_rate"]))
    _metrics_history["concurrent_connections"].append((now, metrics["concurrent_connections"]))
    
    # 记录代理池业务指标
    if collector_stats:
        _metrics_history["collect_rate"].append((now, collector_stats.get("collect_rate_per_min", 0)))
        _metrics_history["success_rate"].append((now, collector_stats.get("success_rate", 0)))
    
    if tester_stats:
        _metrics_history["test_rate"].append((now, tester_stats.get("test_rate_per_min", 0)))
        _metrics_history["cleanup_rate"].append((now, tester_stats.get("cleanup_rate_per_min", 0)))


def get_metrics_history(metric: str, time_range: str = "1h") -> Dict[str, Any]:
    """
    获取历史指标数据
    
    Args:
        metric: 指标名称
        time_range: 时间范围 (1h, 6h, 24h)
    
    Returns:
        Dict with time_labels and values
    """
    # 根据time_range确定时间窗口和采样间隔
    if time_range == "1h":
        window_seconds = 3600
        expected_points = 12
    elif time_range == "6h":
        window_seconds = 6 * 3600
        expected_points = 12
    else:  # 24h
        window_seconds = 24 * 3600
        expected_points = 12
    
    now = time.time()
    cutoff_time = now - window_seconds
    
    # 获取该指标的历史数据
    history = _metrics_history.get(metric, deque())
    
    # 过滤出时间窗口内的数据
    filtered_data = [(t, v) for t, v in history if t >= cutoff_time]
    
    # 如果没有数据，返回空数组
    if not filtered_data:
        return {
            "time_labels": [],
            "values": [],
            "metric": metric,
            "unit": _get_metric_unit(metric)
        }
    
    # 按时间排序
    filtered_data.sort(key=lambda x: x[0])
    
    # 采样到固定数量的点
    if len(filtered_data) > expected_points:
        # 均匀采样
        step = len(filtered_data) // expected_points
        sampled_data = filtered_data[::step][:expected_points]
    else:
        sampled_data = filtered_data
    
    # 格式化输出
    time_labels = [datetime.fromtimestamp(t).strftime("%H:%M") for t, v in sampled_data]
    values = [_format_history_value(metric, v) for t, v in sampled_data]
    
    return {
        "time_labels": time_labels,
        "values": values,
        "metric": metric,
        "unit": _get_metric_unit(metric)
    }


def _format_history_value(metric: str, value: Any) -> Any:
    """统一格式化历史数据，保证图表展示单位与卡片一致。"""
    if metric in _PERCENT_METRICS and isinstance(value, (int, float)):
        return round(value * 100, 2)
    return value


def _get_metric_unit(metric: str) -> str:
    """获取指标单位"""
    units = {
        "api_response_time": "ms",
        "qps": "req/s",
        "error_rate": "%",
        "concurrent_connections": "个",
        "collect_rate": "个/min",
        "test_rate": "个/min",
        "success_rate": "%",
        "cleanup_rate": "个/min"
    }
    return units.get(metric, "")


def reset_metrics():
    """重置指标（用于测试）"""
    global _request_count, _error_count, _start_time
    _response_times.clear()
    _request_count = 0
    _error_count = 0
    _start_time = time.time()
