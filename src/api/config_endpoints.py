import re
from typing import Dict, Any
import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src import app_globals
from src.database.redis_client import RedisManager
from src.logger import reconfigure_logger
from src.api.auth import verify_api_token

router = APIRouter()


def _get_config():
    return app_globals.global_config


def _get_logger():
    return app_globals.global_logger


def apply_runtime_config(updated_keys: list[str]) -> Dict[str, Any]:
    """
    将可热更新配置应用到运行中的组件。
    """
    key_set = set(updated_keys)
    applied_keys: set[str] = set()

    runtime_log_keys = {"LOG_LEVEL", "LOG_MAX_BYTES", "LOG_BACKUP_COUNT", "TIMEZONE"}
    runtime_redis_keys = {"REDIS_HOST", "REDIS_PORT", "REDIS_DB", "REDIS_PASSWORD"}
    runtime_tester_keys = {
        "TEST_INTERVAL_SECONDS",
        "MAX_FAIL_COUNT",
        "TEST_MAX_CONCURRENT",
        "TESTER_LOG_EACH_PROXY",
        "TEST_TIMEOUT_PER_TARGET",
        "TEST_TARGETS",
    }
    runtime_collector_keys = {
        "COLLECT_INTERVAL_SECONDS",
        "ZDAYE_COLLECT_INTERVAL",
        "ZDAYE_OVERSEAS_COLLECT_INTERVAL",
    }

    config = _get_config()

    if runtime_log_keys.intersection(key_set):
        app_globals.global_logger = reconfigure_logger(
            config,
            app_globals.global_logger,
            component="APP"
        )
        applied_keys.update(runtime_log_keys.intersection(key_set))

        if app_globals.global_redis_manager:
            app_globals.global_redis_manager.logger = app_globals.global_logger
        if app_globals.global_collector_manager:
            app_globals.global_collector_manager.logger = app_globals.global_logger
        if app_globals.global_tester_manager:
            app_globals.global_tester_manager.logger = app_globals.global_logger

    if runtime_redis_keys.intersection(key_set):
        old_redis_manager = app_globals.global_redis_manager
        if old_redis_manager:
            old_redis_manager.close_connection_pool()

        new_redis_manager = RedisManager(config, app_globals.global_logger)
        app_globals.global_redis_manager = new_redis_manager
        applied_keys.update(runtime_redis_keys.intersection(key_set))

        if app_globals.global_collector_manager:
            app_globals.global_collector_manager.redis_manager = new_redis_manager
        if app_globals.global_tester_manager:
            app_globals.global_tester_manager.redis_manager = new_redis_manager

        # WebSocket Redis 订阅器使用独立连接，需要主动触发重连到最新 Redis。
        try:
            from src.api.websocket_manager import websocket_manager

            if getattr(websocket_manager, "_redis_listener_started", False):
                loop = asyncio.get_running_loop()
                loop.create_task(websocket_manager._reconnect_loop())
        except RuntimeError:
            # 当前不在事件循环中，跳过热重连调度。
            pass
        except Exception:
            _get_logger().warning("Failed to schedule WebSocket Redis listener reconnect", exc_info=True)

    if runtime_tester_keys.intersection(key_set):
        if app_globals.global_tester_manager and hasattr(app_globals.global_tester_manager, "apply_runtime_config"):
            applied_keys.update(app_globals.global_tester_manager.apply_runtime_config(updated_keys))
        else:
            applied_keys.update(runtime_tester_keys.intersection(key_set))

    if runtime_collector_keys.intersection(key_set):
        if app_globals.global_collector_manager and hasattr(app_globals.global_collector_manager, "apply_runtime_config"):
            app_globals.global_collector_manager.apply_runtime_config(updated_keys)
        applied_keys.update(runtime_collector_keys.intersection(key_set))

    hot_keys = runtime_log_keys | runtime_redis_keys | runtime_tester_keys | runtime_collector_keys | {"API_TOKEN"}
    requires_restart = sorted([key for key in updated_keys if key not in hot_keys])

    return {
        "applied_keys": sorted(applied_keys),
        "requires_restart": requires_restart
    }


class GlobalConfigUpdate(BaseModel):
    """全局配置更新请求模型"""
    config: Dict[str, Any]
    save_to_file: bool = True
    include_secrets: bool = False


@router.get("/", summary="Get all configuration data (global and collector)")
async def get_all_config(
    token: str = Depends(verify_api_token)
) -> Dict[str, Any]:
    """
    Retrieves all global and collector-specific configuration data.
    Includes configuration source information to indicate whether each setting
    comes from environment variables, config file, or defaults.
    """
    try:
        config = _get_config()
        global_config = config.to_dict()
        
        # 敏感信息处理：
        # - API_TOKEN: 返回原始值，由前端控制显示/隐藏（环境变量配置时只读）
        # - REDIS_PASSWORD: 仍然掩码显示
        config_to_return = global_config.copy()
        if config_to_return.get('REDIS_PASSWORD'):
            config_to_return['REDIS_PASSWORD'] = '********'
        
        # 获取配置来源
        config_sources = config.get_all_config_sources()
        
        # 分类来源
        from_env = [k for k, v in config_sources.items() if v == 'env']
        from_file = [k for k, v in config_sources.items() if v == 'file']
        using_defaults = [k for k, v in config_sources.items() if v == 'default']

        # Simulate collector configurations
        # In a real application, these might be stored in a database or separate config files
        # For now, we'll return a mock structure.
        collector_configs = [
            {
                "id": "zdaye_collector",
                "name": "站大爷免费代理",
                "enabled": True,  # Assume enabled if configured
                "fetch_interval_seconds": config_to_return.get("COLLECT_INTERVAL_SECONDS"),
                "params": {
                    "app_id": config_to_return.get("ZDAYE_APP_ID"),
                    "akey": "********" if config_to_return.get("ZDAYE_AKEY") else "未设置",  # Mask AKEY
                },
                "last_run_status": "未知",  # This would need real-time monitoring
                "last_run_time": "未知"  # This would need real-time monitoring
            }
        ]

        return {
            "global_config": config_to_return,
            "collector_configs": collector_configs,
            "config_sources": {
                "from_env": from_env,
                "from_file": from_file,
                "using_defaults": using_defaults
            }
        }
    except Exception as e:
        _get_logger().error(f"Error fetching configuration: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve configuration: {e}"
        )


@router.post("/global", summary="Update global configuration data")
@router.post("/config/global", include_in_schema=False)
async def update_global_config(
    update_data: GlobalConfigUpdate,
    token: str = Depends(verify_api_token)
) -> Dict[str, Any]:
    """
    Updates the global configuration settings.
    
    Changes are applied in-memory immediately. If save_to_file is True,
    the configuration will also be persisted to the runtime config file.
    
    Note: Environment variables always take precedence over file settings.
    """
    try:
        config = _get_config()
        logger = _get_logger()
        new_config = update_data.config
        updated_keys = []
        errors = []
        
        # 验证 TIMEZONE
        if 'TIMEZONE' in new_config:
            try:
                import pytz
                pytz.timezone(new_config['TIMEZONE'])
            except ImportError:
                # pytz not installed, skip timezone validation
                pass
            except Exception:
                errors.append(f"Invalid timezone: {new_config['TIMEZONE']}")
        
        # 验证 TEST_TARGETS
        if 'TEST_TARGETS' in new_config:
            targets = new_config['TEST_TARGETS']
            if not isinstance(targets, list):
                errors.append("TEST_TARGETS must be a list")
            else:
                for url in targets:
                    if not isinstance(url, str) or not (url.startswith('http://') or url.startswith('https://')):
                        errors.append(f"Invalid test target URL: {url}")
        
        # 验证限流格式
        rate_limit_pattern = r'^(\d+)\/(minute|hour|day)$'
        for key in ['RATE_LIMIT_PROXY_MINUTE', 'RATE_LIMIT_HEALTH_MINUTE']:
            if key in new_config:
                if not re.match(rate_limit_pattern, str(new_config[key])):
                    errors.append(f"Invalid rate limit format for {key}: {new_config[key]}")
        
        if errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errors": errors}
            )
        
        editable_config_keys = set(config.to_dict().keys())

        # 更新配置
        for key, value in new_config.items():
            if key in editable_config_keys and not key.startswith('_'):
                original_value = getattr(config, key)
                converted_value = value
                
                if isinstance(original_value, bool):
                    if isinstance(value, str):
                        converted_value = value.lower() in ('1', 'true', 'yes', 'on')
                    else:
                        converted_value = bool(value)
                elif isinstance(original_value, int):
                    try:
                        converted_value = int(value)
                    except (ValueError, TypeError):
                        logger.warning(f"Failed to convert {key} to int, skipping")
                        continue
                elif isinstance(original_value, list) and isinstance(value, str):
                    converted_value = [v.strip() for v in value.split(',') if v.strip()]
                
                setattr(config, key, converted_value)
                updated_keys.append(key)
        
        # 保存到文件
        file_saved = False
        if update_data.save_to_file and updated_keys:
            file_saved = config.save_to_file(include_secrets=update_data.include_secrets)

        runtime_result = apply_runtime_config(updated_keys)
        
        return {
            "message": "Global configuration updated successfully",
            "updated_keys": updated_keys,
            "file_saved": file_saved,
            "config_sources": config.get_all_config_sources(),
            "runtime_apply": runtime_result,
            "requires_restart": runtime_result["requires_restart"]
        }
    except HTTPException:
        raise
    except Exception as e:
        _get_logger().error(f"Error updating global configuration: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update global configuration: {e}"
        )


# TODO: Implement POST /config/collector/{collectorId}, POST /config/collector, DELETE /config/collector/{collectorId}
