"""
统一的结构化日志系统
支持 JSON 格式输出、多进程并发写入、组件级别标识、时区配置
"""

import logging
import os
import json
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Any, Dict, Optional


FIXED_LOG_FILE_NAME = "app.log"

# 时区支持
try:
    # Python 3.9+ 使用 zoneinfo
    from zoneinfo import ZoneInfo
    USE_ZONEINFO = True
except ImportError:
    try:
        # 低版本使用 pytz
        from pytz import timezone
        USE_ZONEINFO = False
    except ImportError:
        # 无时区支持
        timezone = None
        USE_ZONEINFO = None
        print("Warning: No timezone library found (zoneinfo or pytz), using UTC time")

# 尝试导入 concurrent-log-handler，如果不存在则使用标准库
try:
    from concurrent_log_handler import ConcurrentRotatingFileHandler
    USE_CONCURRENT_HANDLER = True
except ImportError:
    USE_CONCURRENT_HANDLER = False
    print("Warning: concurrent-log-handler not installed, falling back to standard handler")


class JSONFormatter(logging.Formatter):
    """
    JSON 结构化日志格式化器
    输出格式: {"timestamp": "...", "level": "...", "component": "...", "source": "...", "message": "...", "context": {...}}
    """
    
    def __init__(self, component: str = "APP", timezone_str: str = "Asia/Shanghai"):
        super().__init__()
        self.component = component
        self.timezone_str = timezone_str
        self.tz = self._get_timezone(timezone_str)
    
    def _get_timezone(self, timezone_str: str):
        """获取时区对象"""
        if USE_ZONEINFO is True:
            try:
                return ZoneInfo(timezone_str)
            except Exception:
                return ZoneInfo("UTC")
        elif USE_ZONEINFO is False:
            try:
                return timezone(timezone_str)
            except Exception:
                return timezone("UTC")
        return None
    
    def _get_now(self) -> datetime:
        """获取带时区的当前时间"""
        now = datetime.now()
        if self.tz:
            now = now.replace(tzinfo=self.tz) if now.tzinfo is None else now.astimezone(self.tz)
        return now
    
    def format(self, record: logging.LogRecord) -> str:
        now = self._get_now()
        log_data: Dict[str, Any] = {
            "timestamp": now.isoformat(),
            "level": record.levelname,
            "component": getattr(record, "component", self.component),
            "source": record.name,
            "message": record.getMessage(),
        }
        
        # 添加上下文信息（如果存在）
        context = {}
        
        # 从 extra 字段中提取上下文
        extra_fields = [
            "proxy",
            "collector",
            "tester",
            "duration_ms",
            "count",
            "grade",
            "score",
            "collector_id",
            "run_id",
            "worker_id",
            "trigger",
            "status",
            "raw_count",
            "valid_count",
            "stored_count",
            "duplicate_count",
            "error_summary",
        ]
        for field in extra_fields:
            if hasattr(record, field):
                context[field] = getattr(record, field)
        
        # 如果有异常信息，添加到上下文
        if record.exc_info:
            context["exception"] = self.formatException(record.exc_info)
        
        # 如果存在额外上下文，添加到日志
        if context:
            log_data["context"] = context
        
        return json.dumps(log_data, ensure_ascii=False, separators=(',', ':'))


class TextFormatter(logging.Formatter):
    """
    文本格式日志格式化器（用于控制台）
    格式: 2026-02-20 14:30:15 [INFO] [COMPONENT] [source] message
    """
    
    def __init__(self, component: str = "APP", timezone_str: str = "Asia/Shanghai"):
        super().__init__()
        self.component = component
        self.timezone_str = timezone_str
        self.tz = self._get_timezone(timezone_str)
    
    def _get_timezone(self, timezone_str: str):
        """获取时区对象"""
        if USE_ZONEINFO is True:
            try:
                return ZoneInfo(timezone_str)
            except Exception:
                return ZoneInfo("UTC")
        elif USE_ZONEINFO is False:
            try:
                return timezone(timezone_str)
            except Exception:
                return timezone("UTC")
        return None
    
    def _get_now(self) -> datetime:
        """获取带时区的当前时间"""
        now = datetime.now()
        if self.tz:
            now = now.replace(tzinfo=self.tz) if now.tzinfo is None else now.astimezone(self.tz)
        return now
    
    def format(self, record: logging.LogRecord) -> str:
        component = getattr(record, "component", self.component)
        timestamp = self._get_now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 构建基础日志行
        log_line = f"{timestamp} [{record.levelname}] [{component}] [{record.name}] {record.getMessage()}"
        
        # 添加额外上下文
        extras = []
        extra_fields = [
            "proxy",
            "collector",
            "duration_ms",
            "count",
            "collector_id",
            "run_id",
            "worker_id",
            "trigger",
            "status",
            "error_summary",
        ]
        for field in extra_fields:
            if hasattr(record, field):
                extras.append(f"{field}={getattr(record, field)}")
        
        if extras:
            log_line += f" ({', '.join(extras)})"
        
        # 如果有异常，添加异常信息
        if record.exc_info:
            log_line += f"\n{self.formatException(record.exc_info)}"
        
        return log_line


def _clear_and_close_handlers(logger_instance: logging.Logger):
    """清理并关闭 logger 的所有 handler"""
    for handler in list(logger_instance.handlers):
        logger_instance.removeHandler(handler)
        if isinstance(handler, logging.FileHandler):
            handler.close()


def setup_logging(cfg, logger_name: str = "ProxyPoolMaster", component: str = "APP") -> logging.Logger:
    """
    配置项目的日志系统
    
    Args:
        cfg: 配置对象
        logger_name: logger 的名称
        component: 组件标识（APP/API/COLLECTOR/TESTER）
    
    Returns:
        配置好的 logging.Logger 实例
    """
    if not hasattr(cfg, "LOG_LEVEL"):
        raise TypeError("setup_logging cfg must provide LOG_LEVEL")

    logger = logging.getLogger(logger_name)
    _clear_and_close_handlers(logger)
    logger.propagate = False

    # 设置日志级别
    log_level_str = getattr(cfg, 'LOG_LEVEL', 'INFO')
    numeric_level = getattr(logging, log_level_str.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level_str}")
    logger.setLevel(numeric_level)
    
    # 获取时区配置
    timezone_str = getattr(cfg, 'TIMEZONE', 'Asia/Shanghai')

    # 控制台处理器 - 使用文本格式（便于开发查看）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_formatter = TextFormatter(component=component, timezone_str=timezone_str)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 文件处理器 - 使用 JSON 格式（便于程序解析）
    # 使用项目根目录作为基准，确保与 log_endpoints.py 路径一致
    # 注意：logger.py 在 src/ 目录下，项目根目录是 src/ 的父目录
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_file_dir, '..'))
    log_dir = os.path.join(project_root, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # 日志文件路径固定为 logs/app.log，避免“可配置但不生效”的歧义
    log_file_path = os.path.join(log_dir, FIXED_LOG_FILE_NAME)

    # 使用并发安全的文件处理器
    if USE_CONCURRENT_HANDLER:
        file_handler = ConcurrentRotatingFileHandler(
            log_file_path,
            maxBytes=getattr(cfg, 'LOG_MAX_BYTES', 10 * 1024 * 1024),  # 默认 10MB
            backupCount=getattr(cfg, 'LOG_BACKUP_COUNT', 5),
            encoding='utf-8',
            use_gzip=True  # 压缩旧日志
        )
    else:
        # 降级方案：使用标准 RotatingFileHandler（仅适用于单进程）
        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=getattr(cfg, 'LOG_MAX_BYTES', 10 * 1024 * 1024),
            backupCount=getattr(cfg, 'LOG_BACKUP_COUNT', 5),
            encoding='utf-8',
            delay=True
        )
    
    file_handler.setLevel(numeric_level)
    file_formatter = JSONFormatter(component=component, timezone_str=timezone_str)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    return logger


def reconfigure_logger(
    cfg,
    current_logger: Optional[logging.Logger],
    component: str = "APP"
) -> logging.Logger:
    """
    运行时重建日志器配置，保留原 logger 名称。
    """
    logger_name = current_logger.name if current_logger else "ProxyPoolMaster"
    return setup_logging(cfg, logger_name=logger_name, component=component)


# 辅助函数：创建带有上下文的日志记录
def log_with_context(
    logger: logging.Logger,
    level: int,
    message: str,
    component: Optional[str] = None,
    **context
):
    """
    记录带有上下文的日志
    
    示例:
        log_with_context(logger, logging.INFO, "Proxy added", component="COLLECTOR", proxy="1.2.3.4:8080")
    """
    extra = {"component": component or "APP"}
    extra.update(context)
    logger.log(level, message, extra=extra)
