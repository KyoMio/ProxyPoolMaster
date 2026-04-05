import os
import sys
import time
import asyncio # 用于运行异步任务

# 将项目根目录添加到 Python 路径中，确保能正确导入 src 模块
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, project_root)

if __name__ == "__main__":
    try:
        from dotenv import load_dotenv  # 导入 load_dotenv

        load_dotenv(os.path.join(project_root, '.env'))
    except ImportError:
        pass

# 确保在环境变量加载后，再导入并初始化 config 和 logger
# 这样它们才能正确读取到 .env 中的值
from src.config import Config # Import Config class
from src.logger import setup_logging # Import setup_logging function
from src.database.redis_client import RedisManager # 导入 RedisManager

# 初始化 config 对象，确保它读取到 .env 中的环境变量
config = Config()
# 初始化 logger，确保它使用最新的 config
app_logger = setup_logging(config, component="APP")

# 初始化 RedisManager 实例
redis_manager = RedisManager(config, app_logger)


# 导入依赖于 config、logger 和 redis_manager 的模块
# 注意：这些模块的导入必须在 config、logger 和 redis_manager 初始化之后
from src.collectors.manager import CollectorManager
from src.testers.async_tester import AsyncHttpTester # 导入 AsyncHttpTester
from src.testers.manager import TesterManager # 导入 TesterManager
from src.collectors_v2.runtime import (
    should_start_legacy_collector,
    start_collector_worker_task,
    stop_collector_worker_task,
)
from src import app_globals  # 导入 app_globals 以设置 global_tester_manager

# 该脚本用于“独立后端调度模式”（collector/tester 独立进程）。
# 容器默认入口改为 API 进程托管调度，不再由 entrypoint.sh 直接后台拉起本脚本。


async def main(): # main 函数改为异步
    app_logger.info("ProxyPoolMaster application starting...")
    collector_manager = None

    if should_start_legacy_collector(config):
        # 初始化 CollectorManager - 使用新的配置格式
        collectors_config = getattr(config, 'COLLECTORS', [])

        # 创建 CollectorManager
        collector_manager = CollectorManager(
            config, app_logger, redis_manager,
            collectors_with_intervals=collectors_config
        )

        # 设置全局引用以便 API 使用
        app_globals.global_collector_manager = collector_manager
        app_logger.info(f"CollectorManager 已初始化，加载了 {len(collectors_config)} 个收集器")
    else:
        app_globals.global_collector_manager = None
        app_logger.info(
            "Legacy CollectorManager skipped by runtime mode.",
            extra={"component": "APP", "collector_runtime_mode": getattr(config, "COLLECTOR_RUNTIME_MODE", "legacy")},
        )
    
    app_logger.info("Initializing TesterManager...")
    # 初始化 TesterManager
    # BaiduTester 的检测频率从 config.CHECK_INTERVAL_SECONDS 获取（默认为 60 秒）
    tester_manager = TesterManager(config, app_logger, redis_manager, AsyncHttpTester) # 传入 AsyncHttpTester 类
    app_globals.global_tester_manager = tester_manager  # 设置全局引用
    app_logger.info("TesterManager initialized and set to app_globals.")

    # 启动收集任务
    if collector_manager is not None:
        collector_manager.start_periodic_collection()
    
    app_logger.info("Starting TesterManager task...")
    # 启动检测任务
    # 使用 asyncio.create_task 运行异步任务，避免阻塞主线程
    tester_task = asyncio.create_task(tester_manager.start())
    app_logger.info("TesterManager task created and scheduled.")
    collector_worker_task = start_collector_worker_task(
        config=config,
        logger=app_logger,
        redis_manager=redis_manager,
    )

    try:
        # 保持主线程（或事件循环）运行
        while True:
            await asyncio.sleep(1) # 异步等待，不阻塞
    except KeyboardInterrupt:
        app_logger.info("Received KeyboardInterrupt, stopping application.")
    finally:
        if collector_manager is not None:
            collector_manager.stop_periodic_collection()
        await stop_collector_worker_task(collector_worker_task, logger=app_logger)
        await tester_manager.stop() # 停止异步检测任务
        # 关闭 Redis 连接池
        redis_manager.close_connection_pool()
        app_logger.info("ProxyPoolMaster application stopped.")

if __name__ == "__main__":
    asyncio.run(main()) # 运行异步 main 函数
