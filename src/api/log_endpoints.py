# src/api/log_endpoints.py

import sys
import os
import glob

# 将项目根目录添加到 Python 路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import Dict, Any, List, Optional, Set
import time
import json
from datetime import datetime, timezone as dt_timezone

from src.config import Config
from src.logger import setup_logging, FIXED_LOG_FILE_NAME
from src.api.auth import verify_api_token
from src.app_globals import global_config as _config, global_logger as _logger

# 时区支持
try:
    from zoneinfo import ZoneInfo
    USE_ZONEINFO = True
except ImportError:
    try:
        from pytz import timezone as pytz_timezone
        USE_ZONEINFO = False
    except ImportError:
        ZoneInfo = None
        pytz_timezone = None
        USE_ZONEINFO = None


def get_timezone(tz_str: str):
    """获取时区对象"""
    if USE_ZONEINFO is True:
        try:
            return ZoneInfo(tz_str)
        except Exception:
            return ZoneInfo("UTC")
    elif USE_ZONEINFO is False:
        try:
            return pytz_timezone(tz_str)
        except Exception:
            return pytz_timezone("UTC")
    return None


def convert_to_timezone(dt_obj: datetime, tz_str: str = "Asia/Shanghai") -> datetime:
    """将时间转换为指定时区"""
    tz = get_timezone(tz_str)
    if tz is None:
        return dt_obj
    
    # 如果 datetime 没有时区信息，假设它是 UTC
    if dt_obj.tzinfo is None:
        dt_obj = dt_obj.replace(tzinfo=dt_timezone.utc)
    
    # 转换到目标时区
    return dt_obj.astimezone(tz)

router = APIRouter()

LOG_LEVEL_ORDER = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}


def parse_exclude_components(exclude_components: Optional[str]) -> Set[str]:
    """解析排除组件列表（逗号分隔，忽略大小写与空白）"""
    if not exclude_components:
        return set()
    return {
        item.strip().upper()
        for item in exclude_components.split(",")
        if item and item.strip()
    }


def level_meets_minimum(level: str, min_level: Optional[str]) -> bool:
    """判断日志级别是否满足最小级别要求"""
    if not min_level:
        return True
    expected = LOG_LEVEL_ORDER.get(str(min_level).upper().strip())
    if expected is None:
        return True
    current = LOG_LEVEL_ORDER.get(str(level).upper().strip(), 0)
    return current >= expected

# Construct the full path to the log file based on logger.py's logic
# 使用项目根目录作为基准
LOG_DIR = os.path.abspath(os.path.join(project_root, 'logs'))


def get_log_file_path() -> str:
    """
    获取固定日志文件路径
    """
    return os.path.join(LOG_DIR, FIXED_LOG_FILE_NAME)


# 日志文件路径将在请求时动态获取，避免模块导入时配置未加载的问题
def get_current_log_file_path() -> str:
    """获取当前日志文件路径（动态计算）"""
    return get_log_file_path()


def clear_log_files(log_file_path: str) -> Dict[str, int]:
    """清空当前日志文件并删除轮转备份文件。"""
    removed_files = 0
    log_dir = os.path.dirname(log_file_path)
    base_name = os.path.basename(log_file_path)

    os.makedirs(log_dir, exist_ok=True)

    for candidate in glob.glob(os.path.join(log_dir, f"{base_name}*")):
        if candidate.endswith(".lock"):
            continue
        if os.path.abspath(candidate) == os.path.abspath(log_file_path):
            with open(candidate, "w", encoding="utf-8"):
                pass
        else:
            os.remove(candidate)
            removed_files += 1

    if not os.path.exists(log_file_path):
        with open(log_file_path, "w", encoding="utf-8"):
            pass

    return {"removed_files": removed_files}


def parse_log_line(line: str) -> Optional[Dict[str, Any]]:
    """
    解析单行日志，支持 JSON 格式和普通文本格式
    
    JSON 格式示例:
    {"timestamp": "2026-02-20T14:30:15.123+08:00", "level": "INFO", "component": "API", "source": "ProxyPoolMaster", "message": "...", "context": {...}}
    
    旧格式示例（用于兼容）:
    2026-02-20 14:30:15,123 - ProxyPoolMaster - INFO - message
    """
    # 获取配置的时区
    tz_str = getattr(_config, 'TIMEZONE', 'Asia/Shanghai')
    
    line = line.strip()
    if not line:
        return None
    
    # 尝试解析 JSON 格式
    if line.startswith('{'):
        try:
            log_data = json.loads(line)
            
            # 转换时间戳格式
            timestamp = log_data.get("timestamp", "")
            if timestamp:
                try:
                    # ISO 格式时间戳（支持带时区的格式）
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    # 转换到配置的时区
                    dt_local = convert_to_timezone(dt, tz_str)
                    display_timestamp = dt_local.strftime('%Y-%m-%d %H:%M:%S')
                    unix_timestamp = int(dt_local.timestamp())
                except Exception as e:
                    display_timestamp = timestamp
                    unix_timestamp = int(time.time())
            else:
                display_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                unix_timestamp = int(time.time())
            
            # 构建统一的返回格式
            return {
                "timestamp": display_timestamp,
                "timestamp_unix": unix_timestamp,
                "level": log_data.get("level", "INFO"),
                "component": log_data.get("component", "APP"),
                "source": log_data.get("source", "unknown"),
                "message": log_data.get("message", ""),
                "context": log_data.get("context", {}),
                "raw": line
            }
        except json.JSONDecodeError:
            # JSON 解析失败，尝试旧格式
            pass
    
    # 尝试解析旧格式（文本格式）
    # 格式: 2026-02-20 14:30:15,123 [LEVEL] [COMPONENT] [source] message
    import re
    old_pattern = re.compile(
        r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),?(\d{3})?\s+'  # timestamp
        r'\[(\w+)\]\s+'  # level
        r'\[(\w+)\]\s+'  # component
        r'\[([^\]]+)\]\s+'  # source
        r'(.*)$'  # message
    )
    
    match = old_pattern.match(line)
    if match:
        groups = match.groups()
        timestamp_str = groups[0]
        level = groups[2] if groups[2] else "INFO"
        component = groups[3] if groups[3] else "APP"
        source = groups[4] if groups[4] else "unknown"
        message = groups[5] if groups[5] else line
        
        try:
            dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            unix_timestamp = int(dt.timestamp())
        except:
            unix_timestamp = int(time.time())
        
        return {
            "timestamp": timestamp_str,
            "timestamp_unix": unix_timestamp,
            "level": level,
            "component": component,
            "source": source,
            "message": message,
            "context": {},
            "raw": line
        }
    
    # 如果都无法解析，作为未知格式返回
    return {
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "timestamp_unix": int(time.time()),
        "level": "UNKNOWN",
        "component": "APP",
        "source": "unknown",
        "message": line,
        "context": {},
        "raw": line
    }


@router.get("", summary="Get system logs with filtering and pagination")
async def get_system_logs(
    level: Optional[str] = Query(None, description="Filter logs by level (INFO, WARNING, ERROR, DEBUG)"),
    min_level: Optional[str] = Query(None, description="Filter logs by minimum level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"),
    component: Optional[str] = Query(None, description="Filter logs by component (API, COLLECTOR, TESTER, REDIS)"),
    exclude_components: Optional[str] = Query(None, description="Exclude components, comma-separated (e.g. TESTER,REDIS)"),
    keyword: Optional[str] = Query(None, description="Filter logs by keyword in message"),
    collector_id: Optional[str] = Query(None, description="Filter logs by context.collector_id"),
    run_id: Optional[str] = Query(None, description="Filter logs by context.run_id"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Number of items per page"),
) -> Dict[str, Any]:
    """
    Retrieves system logs from the log file, supporting filtering by log level, component, keyword, and pagination.
    """
    all_logs = []
    
    log_file_path = get_current_log_file_path()
    
    if not os.path.exists(log_file_path):
        _logger.warning(f"Log file not found: {log_file_path}", extra={"component": "API"})
        return {
            "data": [],
            "total": 0,
            "page": page,
            "size": size,
        }

    try:
        # 读取日志文件
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                parsed_log = parse_log_line(line)
                if parsed_log:
                    all_logs.append(parsed_log)
        
        # 按时间戳降序排序（最新的在前）
        all_logs.sort(key=lambda x: x.get("timestamp_unix", 0), reverse=True)

        # 应用筛选
        filtered_logs = all_logs
        excluded_component_set = parse_exclude_components(exclude_components)

        if level:
            filtered_logs = [log for log in filtered_logs if log.get("level", "").upper() == level.upper()]

        if min_level:
            filtered_logs = [
                log for log in filtered_logs
                if level_meets_minimum(log.get("level", ""), min_level)
            ]
        
        if component:
            filtered_logs = [log for log in filtered_logs if log.get("component", "").upper() == component.upper()]

        if excluded_component_set:
            filtered_logs = [
                log for log in filtered_logs
                if log.get("component", "").upper() not in excluded_component_set
            ]
        
        if keyword:
            keyword_lower = keyword.lower()
            filtered_logs = [
                log for log in filtered_logs 
                if keyword_lower in log.get("message", "").lower() 
                or keyword_lower in log.get("source", "").lower()
            ]

        if collector_id:
            collector_id_text = collector_id.strip()
            filtered_logs = [
                log for log in filtered_logs
                if str((log.get("context") or {}).get("collector_id", "")).strip() == collector_id_text
            ]

        if run_id:
            run_id_text = run_id.strip()
            filtered_logs = [
                log for log in filtered_logs
                if str((log.get("context") or {}).get("run_id", "")).strip() == run_id_text
            ]

        total_items = len(filtered_logs)
        start_index = (page - 1) * size
        end_index = start_index + size
        paginated_logs = filtered_logs[start_index:end_index]

        return {
            "data": paginated_logs,
            "total": total_items,
            "page": page,
            "size": size,
        }
    except Exception as e:
        _logger.error(f"Error reading or parsing log file {log_file_path}: {e}", exc_info=True, extra={"component": "API"})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve logs: {e}"
        )


@router.get("/components", summary="Get available log components")
async def get_log_components() -> List[str]:
    """
    获取可用的日志组件列表，用于筛选
    """
    return ["API", "COLLECTOR", "TESTER", "REDIS", "APP"]


@router.get("/levels", summary="Get available log levels")
async def get_log_levels() -> List[str]:
    """
    获取可用的日志级别列表，用于筛选
    """
    return ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


@router.post("/clear", summary="Clear system logs")
async def clear_system_logs() -> Dict[str, Any]:
    """
    清空当前日志文件并删除轮转备份。
    """
    log_file_path = get_current_log_file_path()

    try:
        result = clear_log_files(log_file_path)
        return {
            "message": "Logs cleared successfully",
            "removed_files": result["removed_files"],
        }
    except Exception as e:
        _logger.error(
            f"Failed to clear logs: {e}",
            exc_info=True,
            extra={"component": "API"},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear logs: {e}"
        )
