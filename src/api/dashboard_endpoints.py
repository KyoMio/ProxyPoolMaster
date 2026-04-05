# src/api/dashboard_endpoints.py

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, List
import asyncio
import time

from src import app_globals
from src.database.redis_client import RedisManager
from src.utils.country_mapper import to_chinese_country
from src.api.auth import verify_api_token # Assume verify_api_token is in api.auth
from src.utils.proxy_availability import is_grade_available

def get_redis_manager():
    return app_globals.global_redis_manager

router = APIRouter()


async def _get_active_proxy_pool(redis_manager: RedisManager) -> List[Any]:
    helper = getattr(redis_manager, "get_all_non_cooldown_proxies", None)
    if callable(helper):
        try:
            proxies = await asyncio.to_thread(helper)
            if isinstance(proxies, list):
                return proxies
        except Exception as exc:
            app_globals.global_logger.debug(
                f"Failed to load non-cooldown proxy pool: {exc}",
                extra={"component": "DASHBOARD"},
            )

    proxies = await asyncio.to_thread(lambda: redis_manager.get_all_proxies())
    return proxies if isinstance(proxies, list) else []


async def _get_cooldown_proxy_count(redis_manager: RedisManager, active_count: int) -> int:
    helper = getattr(redis_manager, "get_cooldown_proxy_count", None)
    if callable(helper):
        try:
            count = await asyncio.to_thread(helper)
            if isinstance(count, int):
                return max(0, count)
        except Exception as exc:
            app_globals.global_logger.debug(
                f"Failed to load cooldown proxy count: {exc}",
                extra={"component": "DASHBOARD"},
            )

    try:
        all_proxies = await asyncio.to_thread(lambda: redis_manager.get_all_proxies())
        if isinstance(all_proxies, list):
            return max(0, len(all_proxies) - active_count)
    except Exception as exc:
        app_globals.global_logger.debug(
            f"Failed to derive cooldown proxy count: {exc}",
            extra={"component": "DASHBOARD"},
        )
    return 0

@router.get("/overview", summary="Get dashboard overview statistics")
async def get_dashboard_overview(
    redis_manager: RedisManager = Depends(get_redis_manager)
) -> Dict[str, Any]:
    """
    Retrieves a summary of proxy pool statistics for the dashboard.
    Returns:
        dict: A dictionary containing:
            - total_proxies (int): Total number of proxies in the pool.
            - available_proxies (int): Number of currently available proxies.
            - avg_response_time (int): Average response time in ms for available proxies.
            - last_updated (str): Timestamp of the last update or check.
            - grade_distribution (Dict[str, int]): Distribution of all proxies by grade (S/A/B/C/D).
            - available_grade_distribution (Dict[str, int]): Distribution of available proxies by grade.
            - proxy_type_distribution (List[Dict]): Distribution of ALL proxies by protocol.
            - anonymity_distribution (List[Dict]): Distribution of ALL proxies by anonymity level.
            - country_distribution (List[Dict]): Distribution of ALL proxies by country code.
            - available_proxy_type_distribution (List[Dict]): Distribution of AVAILABLE proxies by protocol.
            - available_anonymity_distribution (List[Dict]): Distribution of AVAILABLE proxies by anonymity.
            - available_country_distribution (List[Dict]): Distribution of AVAILABLE proxies by country.
    """
    try:
        # Fetch main pool proxies to calculate statistics
        all_proxies = await _get_active_proxy_pool(redis_manager)
        cooldown_pool_count = await _get_cooldown_proxy_count(redis_manager, len(all_proxies))
        
        total_proxies = len(all_proxies)
        available_proxies = 0
        total_response_time = 0
        
        # 所有代理的分布统计
        proxy_type_counts = {}
        anonymity_counts = {}
        country_counts = {}
        grade_counts = {'S': 0, 'A': 0, 'B': 0, 'C': 0, 'D': 0, '': 0}
        
        # 可用代理的分布统计
        available_proxy_type_counts = {}
        available_anonymity_counts = {}
        available_country_counts = {}
        available_grade_counts = {'S': 0, 'A': 0, 'B': 0}

        # 默认使用当前时间；如果存在代理，则应取最新一次真实检查时间
        last_updated_timestamp = None

        if total_proxies > 0:
            for proxy in all_proxies:
                # Update last_updated based on the latest proxy check
                if hasattr(proxy, 'last_check_time') and isinstance(proxy.last_check_time, (int, float)):
                    if last_updated_timestamp is None or proxy.last_check_time > last_updated_timestamp:
                        last_updated_timestamp = proxy.last_check_time
                
                # 统计所有代理的等级分布
                proxy_grade = getattr(proxy, 'grade', '') or ''
                grade_counts[proxy_grade] = grade_counts.get(proxy_grade, 0) + 1
                
                # 统计所有代理的分布
                proxy_type_counts[proxy.protocol] = proxy_type_counts.get(proxy.protocol, 0) + 1
                anonymity_counts[proxy.anonymity_level] = anonymity_counts.get(proxy.anonymity_level, 0) + 1
                country_counts[proxy.country_code] = country_counts.get(proxy.country_code, 0) + 1
                
                # 【可用代理判断】grade in ['S', 'A', 'B']
                if is_grade_available(proxy_grade):
                    available_proxies += 1
                    
                    # 统计可用代理的等级分布
                    available_grade_counts[proxy_grade] = available_grade_counts.get(proxy_grade, 0) + 1
                    
                    # 统计可用代理的分布
                    available_proxy_type_counts[proxy.protocol] = available_proxy_type_counts.get(proxy.protocol, 0) + 1
                    available_anonymity_counts[proxy.anonymity_level] = available_anonymity_counts.get(proxy.anonymity_level, 0) + 1
                    available_country_counts[proxy.country_code] = available_country_counts.get(proxy.country_code, 0) + 1
                    
                    # 只有可用代理才计算响应时间
                    if hasattr(proxy, 'response_time') and proxy.response_time is not None and proxy.response_time > 0:
                        total_response_time += proxy.response_time
        
        # 将秒转换为毫秒（response_time 存储的是秒）
        avg_response_time = round((total_response_time / available_proxies) * 1000) if available_proxies > 0 else 0
        
        # Helper function to convert counts to list of dicts
        def counts_to_list(counts_dict: Dict[str, int], key_name: str, is_country: bool = False, keep_raw_code: bool = False) -> List[Dict[str, Any]]:
            result = []
            for name, count in counts_dict.items():
                if count > 0:
                    value = name or "unknown"
                    # 如果是国家/地区字段，可以选择保留原始代码
                    if is_country:
                        if keep_raw_code:
                            # 返回原始country_code和中文名称
                            result.append({
                                "country_code": name.upper() if name else "UNKNOWN",
                                "country_name": to_chinese_country(name),
                                "count": count
                            })
                            continue
                        else:
                            value = to_chinese_country(value)
                    result.append({key_name: value, "count": count})
            return result
        
        # 所有代理的分布
        proxy_type_distribution = counts_to_list(proxy_type_counts, "protocol")
        anonymity_distribution = counts_to_list(anonymity_counts, "level")
        country_distribution = counts_to_list(country_counts, "country_code", is_country=True)
        
        # 可用代理的分布
        available_proxy_type_distribution = counts_to_list(available_proxy_type_counts, "protocol")
        available_anonymity_distribution = counts_to_list(available_anonymity_counts, "level")
        # 对于地图使用，保留原始country_code
        available_country_distribution = counts_to_list(available_country_counts, "country_code", is_country=True, keep_raw_code=True)

        # Format last_updated timestamp
        if last_updated_timestamp is None:
            last_updated_timestamp = int(time.time())
        last_updated_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_updated_timestamp))

        return {
            "total_proxies": total_proxies,
            "available_proxies": available_proxies,
            "cooldown_pool_count": cooldown_pool_count,
            "avg_response_time": avg_response_time,
            "last_updated": last_updated_str,
            
            # 等级分布
            "grade_distribution": grade_counts,
            "available_grade_distribution": available_grade_counts,
            
            # 所有代理的分布
            "proxy_type_distribution": proxy_type_distribution,
            "anonymity_distribution": anonymity_distribution,
            "country_distribution": country_distribution,
            
            # 可用代理的分布（新增）
            "available_proxy_type_distribution": available_proxy_type_distribution,
            "available_anonymity_distribution": available_anonymity_distribution,
            "available_country_distribution": available_country_distribution,
        }
    except Exception as e:
        app_globals.global_logger.error(f"Error fetching dashboard overview: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve dashboard overview: {e}"
        )

# Add other dashboard specific endpoints here as needed (e.g., separate for distributions if needed)
# For now, get_dashboard_overview returns all distribution data directly.
