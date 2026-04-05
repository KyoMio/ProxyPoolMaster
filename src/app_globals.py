# src/app_globals.py
# This module defines global instances to avoid circular imports.

from src.config import Config
from src.logger import setup_logging
from src.database.redis_client import RedisManager
from src.collectors.manager import CollectorManager
from src.collectors.zdaye_collector import ZdayeCollector
from src.collectors.zdaye_overseas_collector import ZdayeOverseasCollector

# Initialize global instances once
global_config = Config()
global_logger = setup_logging(global_config, logger_name="ProxyPoolMaster", component="APP")
global_redis_manager = RedisManager(global_config, global_logger)

# Initialize CollectorManager with all collectors
# 站大爷大陆/海外收集器间隔均从配置读取
zdaye_interval = int(getattr(global_config, "ZDAYE_COLLECT_INTERVAL", global_config.COLLECT_INTERVAL_SECONDS))
zdaye_overseas_interval = int(getattr(global_config, "ZDAYE_OVERSEAS_COLLECT_INTERVAL", global_config.COLLECT_INTERVAL_SECONDS))
global_logger.info(f"ZdayeCollector interval set to {zdaye_interval} seconds (from config)")
global_logger.info(f"ZdayeOverseasCollector interval set to {zdaye_overseas_interval} seconds (from config)")

global_collector_manager = CollectorManager(
    config_instance=global_config,
    logger_instance=global_logger,
    redis_manager_instance=global_redis_manager
)
global_collector_manager.register_collector(ZdayeCollector, zdaye_interval)
global_collector_manager.register_collector(ZdayeOverseasCollector, zdaye_overseas_interval)

# TesterManager will be set by main.py when it's initialized
# This avoids circular imports while allowing global access
global_tester_manager = None
