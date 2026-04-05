# src/api/endpoints.py

from fastapi import APIRouter, Query, HTTPException, status, Depends, Request
from typing import Optional, List, Dict, Any
import asyncio
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import re # For log parsing

from slowapi import Limiter
from slowapi.util import get_remote_address

from src.config import Config
from src.database.redis_client import RedisManager
from src.database.models import Proxy
from src import app_globals
from src.utils.proxy_availability import is_grade_available

# 创建路由级别的速率限制器
limiter = Limiter(key_func=get_remote_address)

# For FastAPI dependencies
def get_redis_manager():
    """
    获取全局 RedisManager 实例
    使用 app_globals 中初始化的单例，避免重复创建连接池
    """
    return app_globals.global_redis_manager

# Dependency to get the Config instance
def get_config_instance():
    return app_globals.global_config

router = APIRouter()


async def _get_active_proxy_pool(redis_manager: RedisManager) -> List[Proxy]:
    helper = getattr(redis_manager, "get_all_non_cooldown_proxies", None)
    if callable(helper):
        try:
            proxies = await asyncio.to_thread(helper)
            if isinstance(proxies, list):
                return proxies
        except Exception as exc:
            app_globals.global_logger.debug(
                f"Failed to load non-cooldown proxy pool: {exc}",
                extra={"component": "API"},
            )

    proxies = await asyncio.to_thread(lambda: redis_manager.get_all_proxies())
    return proxies if isinstance(proxies, list) else []

# Pydantic Models for Configuration
class CollectorParams(BaseModel):
    """Specific parameters for a collector, e.g., API keys, URLs."""
    # This will be dynamic based on collector type, so use a flexible Dict
    # Example: {"app_id": "...", "akey": "..."} for zdaye
    pass

class CollectorConfig(BaseModel):
    """Configuration for a single collector."""
    id: Optional[int] = Field(None, description="Unique ID for the collector (assigned by system)")
    name: str = Field(..., description="Human-readable name for the collector")
    type: str = Field(..., description="Type of the collector (e.g., 'zdaye', 'free-proxy-list')")
    interval: int = Field(..., gt=0, description="Collection interval in seconds")
    enabled: bool = Field(True, description="Whether the collector is enabled")
    params: Dict[str, Any] = Field({}, description="Collector-specific parameters")

class GlobalConfig(BaseModel):
    """Model for global configuration parameters that can be updated."""
    REDIS_HOST: Optional[str] = None
    REDIS_PORT: Optional[int] = None
    REDIS_DB: Optional[int] = None
    # REDIS_PASSWORD should not be updated via API directly for security reasons
    LOG_LEVEL: Optional[str] = None
    LOG_MAX_BYTES: Optional[int] = None
    LOG_BACKUP_COUNT: Optional[int] = None
    TIMEZONE: Optional[str] = None
    # API_TOKEN should not be updated via API directly for security reasons
    REQUEST_TIMEOUT: Optional[int] = None
    COLLECT_INTERVAL_SECONDS: Optional[int] = None
    ZDAYE_COLLECT_INTERVAL: Optional[int] = None
    ZDAYE_OVERSEAS_COLLECT_INTERVAL: Optional[int] = None
    ZDAYE_APP_ID: Optional[str] = None
    ZDAYE_AKEY: Optional[str] = None
    TEST_INTERVAL_SECONDS: Optional[int] = None
    MAX_FAIL_COUNT: Optional[int] = None
    TESTER_LOG_EACH_PROXY: Optional[bool] = None
    TEST_MAX_CONCURRENT: Optional[int] = None
    TEST_TIMEOUT_PER_TARGET: Optional[int] = None
    RATE_LIMIT_PROXY_MINUTE: Optional[str] = None
    RATE_LIMIT_HEALTH_MINUTE: Optional[str] = None

class FullConfigResponse(BaseModel):
    """Full configuration response model."""
    global_config: GlobalConfig
    collectors: List[CollectorConfig]

# 注意：GET /config 和 POST /config/global 路由已移至 config_endpoints.py
# 保留以下 collector 相关路由

@router.post("/config/collector", response_model=CollectorConfig, status_code=status.HTTP_201_CREATED, summary="Add a new collector configuration")
async def add_collector(
    new_collector_data: CollectorConfig,
    config: Config = Depends(get_config_instance)
):
    """
    Adds a new collector configuration to the system.
    The 'id' field should be omitted or set to None; it will be assigned by the system.
    """
    if new_collector_data.id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Collector ID should not be provided when adding a new collector; it is assigned automatically."
        )
    
    added_collector = config.add_collector_config(new_collector_data.model_dump(exclude_unset=True))
    app_globals.global_logger.info(f"New collector added: {added_collector}")
    return CollectorConfig(**added_collector)

@router.put("/config/collector/{collector_id}", response_model=CollectorConfig, summary="Update an existing collector configuration")
async def update_collector(
    collector_id: int,
    update_data: CollectorConfig,
    config: Config = Depends(get_config_instance)
):
    """
    Updates an existing collector configuration identified by its ID.
    Only provided fields will be updated.
    """
    updated_collector = config.update_collector_config(collector_id, update_data.model_dump(exclude_unset=True))
    if not updated_collector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collector with ID {collector_id} not found."
        )
    app_globals.global_logger.info(f"Collector {collector_id} updated: {update_data.model_dump(exclude_unset=True)}")
    return CollectorConfig(**updated_collector)

@router.delete("/config/collector/{collector_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a collector configuration")
async def delete_collector(
    collector_id: int,
    config: Config = Depends(get_config_instance)
):
    """
    Deletes a collector configuration identified by its ID.
    """
    if not config.delete_collector_config(collector_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collector with ID {collector_id} not found."
        )
    app_globals.global_logger.info(f"Collector {collector_id} deleted.")
    return None # No content on successful deletion

@router.get("/random", response_model=Proxy, summary="Get a random available proxy")
@limiter.limit(app_globals.global_config.RATE_LIMIT_PROXY_MINUTE)
async def get_random_proxy(
    request: Request,
    redis_manager: RedisManager = Depends(get_redis_manager),
    config: Config = Depends(get_config_instance)
):
    """
    Retrieves a random available proxy from the pool.
    Available proxy criteria: grade in ['S', 'A', 'B'] (B级及以上).
    Rate limit: configurable via RATE_LIMIT_PROXY_MINUTE env var (default: 60/minute).
    """
    import random
    
    # 获取默认主代理池，筛选出 B级及以上代理
    all_proxies = await _get_active_proxy_pool(redis_manager)
    available_proxies = [p for p in all_proxies if is_grade_available(getattr(p, "grade", ""))]
    
    if not available_proxies:
        app_globals.global_logger.warning("No available random proxy found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No available proxies found."
        )
    
    # 从所有可用代理中完全随机选择（不按等级优先）
    proxy_obj = random.choice(available_proxies)
    app_globals.global_logger.debug(f"Selected random proxy: {proxy_obj.ip}:{proxy_obj.port} (Grade: {proxy_obj.grade})")
    return proxy_obj

@router.get("/get", summary="Get proxies with filters and pagination")
@limiter.limit(app_globals.global_config.RATE_LIMIT_PROXY_MINUTE)
async def get_proxies_with_filters(
    request: Request,
    country_code: Optional[str] = Query(None, description="Filter by ISO 3166-1 alpha-2 country code"),
    protocol: Optional[str] = Query(None, description="Filter by protocol (http, https)"),
    grade: Optional[str] = Query(None, description="Filter by proxy grade (S, A, B, C, D)"),
    anonymity_level: Optional[str] = Query(None, description="Filter by anonymity level (transparent, anonymous, elite)"),
    is_available: Optional[bool] = Query(None, description="Filter by availability (True: only available, False: only unavailable, None: all)"),
    page: int = Query(1, gt=0, description="Page number"),
    size: int = Query(10, gt=0, le=100, description="Number of items per page"),
    redis_manager: RedisManager = Depends(get_redis_manager),
    config: Config = Depends(get_config_instance)
) -> Dict[str, Any]:
    """
    Retrieves a list of proxies from the pool, optionally filtered by country code, protocol, anonymity level, and availability, with pagination.
    Rate limit: configurable via RATE_LIMIT_PROXY_MINUTE env var (default: 60/minute).
    
    Availability criteria: success_count > 0 and fail_count < MAX_FAIL_COUNT.
    
    Returns:
        dict: A dictionary containing:
            - data (List[Proxy]): List of proxies for the current page.
            - total (int): Total number of proxies matching the filters.
            - page (int): Current page number.
            - size (int): Number of items per page.
    """
    # 根据 is_available 参数决定获取哪些代理
    if is_available is True:
        # 只获取可用代理 (S/A/B 级)
        all_proxies = await _get_active_proxy_pool(redis_manager)
        all_proxies = [p for p in all_proxies if is_grade_available(getattr(p, "grade", ""))]
    elif is_available is False:
        # 只获取不可用代理（B级以下，包含 C/D/未评级）
        all_proxies = await _get_active_proxy_pool(redis_manager)
        all_proxies = [p for p in all_proxies if not is_grade_available(getattr(p, "grade", ""))]
    else:
        # 获取默认主代理池
        all_proxies = await _get_active_proxy_pool(redis_manager)
    
    # Apply filters (country_code, protocol, anonymity_level)
    filtered_proxies = []
    normalized_grade = (grade or "").strip().upper()
    for proxy in all_proxies:
        match = True
        if country_code and (not proxy.country_code or proxy.country_code.lower() != country_code.lower()):
            match = False
        if protocol and (not proxy.protocol or proxy.protocol.lower() != protocol.lower()):
            match = False
        if normalized_grade and (getattr(proxy, "grade", "") or "").upper() != normalized_grade:
            match = False
        if anonymity_level and (
            not proxy.anonymity_level
            or proxy.anonymity_level.lower() != anonymity_level.lower()
        ):
            match = False
        
        if match:
            filtered_proxies.append(proxy)
    
    total_matching_proxies = len(filtered_proxies)
    
    # Apply pagination
    skip = (page - 1) * size
    take = size
    
    paginated_proxies = filtered_proxies[skip : skip + take]
    
    # Convert Proxy objects to dicts for JSON serialization if necessary
    # FastAPI usually handles Pydantic models automatically, but if Proxy is not Pydantic
    # or has complex fields, manual conversion might be needed. Assuming it's compatible.
    
    if not paginated_proxies:
        app_globals.global_logger.warning(
            "No proxies found matching filters and pagination: "
            f"country={country_code}, protocol={protocol}, grade={grade}, "
            f"anonymity={anonymity_level}, is_available={is_available}, page={page}, size={size}"
        )
        # Instead of 404, return empty list with total count for pagination UI
        return {
            "data": [],
            "total": total_matching_proxies,
            "page": page,
            "size": size
        }
    
    return {
        "data": paginated_proxies,
        "total": total_matching_proxies,
        "page": page,
        "size": size
    }

# ===========================================
#  Dashboard 页面相关 API
# ===========================================

# ===========================================
#  Dashboard 页面相关 API
# ===========================================
# 注意：这些端点已被移至 dashboard_endpoints.py，保留此注释以避免重复实现
# - GET /api/v1/dashboard/overview -> dashboard_endpoints.get_dashboard_overview
# - GET /api/v1/dashboard/proxy_type_distribution -> (暂不提供独立端点)
# - GET /api/v1/dashboard/anonymity_distribution -> (暂不提供独立端点)
# - GET /api/v1/dashboard/country_distribution -> (暂不提供独立端点)

# ===========================================
#  System Status 页面相关 API
# ===========================================
# 注意：这些端点已被移至 system_endpoints.py，保留此注释以避免重复实现
# - GET /api/v1/system/status -> system_endpoints.get_system_status
# - GET /api/v1/system/modules -> system_endpoints.get_module_status
# - GET /api/v1/system/metrics -> system_endpoints.get_system_metrics
# - GET /api/v1/system/metrics/history -> system_endpoints.get_metrics_history
