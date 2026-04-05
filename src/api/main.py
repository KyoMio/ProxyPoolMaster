# src/api/main.py

import sys
import os

if __name__ == "__main__":
    # 仅在脚本直接运行时加载 .env，避免导入阶段污染测试环境。
    from pathlib import Path

    try:
        from dotenv import load_dotenv

        env_path = Path(__file__).parent.parent.parent / '.env'
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=False)
            print(f"[INFO] Loaded environment from {env_path}")
    except ImportError:
        pass  # python-dotenv not installed

# Windows 下抑制 asyncio 连接重置错误（ConnectionResetError: [WinError 10054]）
if sys.platform == 'win32':
    import asyncio
    import warnings
    # 设置事件循环策略，抑制连接重置警告
    try:
        from asyncio import WindowsSelectorEventLoopPolicy
        asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())
    except ImportError:
        pass
    
    # 忽略特定的 socket 连接重置错误
    import socket
    original_socket_init = socket.socket.__init__
    def patched_socket_init(self, *args, **kwargs):
        original_socket_init(self, *args, **kwargs)
        # 设置 SO_LINGER 选项，优雅关闭连接
        try:
            self.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, b'\x00\x00\x00\x00')
        except:
            pass
    socket.socket.__init__ = patched_socket_init

# 将项目根目录添加到 Python 路径，确保能正确导入 src 模块
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, Request, WebSocketDisconnect
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn
import logging
import time

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import src.app_globals as app_globals
from src.app_globals import global_config as config, global_logger as logger, global_redis_manager as redis_manager, global_tester_manager
from src.api.system_endpoints import start_metrics_recorder, get_system_realtime_payload, get_collector_realtime_payload
from src.api.endpoints import router as api_router
from src.api.dashboard_endpoints import router as dashboard_router
from src.api.system_endpoints import router as system_router
from src.api.log_endpoints import router as log_router
from src.api.config_endpoints import router as config_router
from src.api.collector_v2_endpoints import router as collector_v2_router
from src.api.auth import verify_api_token
from src.api.websocket_manager import websocket_manager
from src.api.log_stream import log_stream_manager
from src.middleware.metrics import MetricsMiddleware
from src.collectors_v2.migration import auto_migrate_collectors_to_v2
from src.collectors_v2.repository import CollectorV2Repository

# 创建速率限制器
limiter = Limiter(key_func=get_remote_address)


def _get_redis_manager():
    return app_globals.global_redis_manager


def format_release_label(release_version: str, git_sha: str) -> str:
    normalized_version = (release_version or "").strip()
    normalized_sha = (git_sha or "").strip()

    if normalized_version:
        version_label = normalized_version if normalized_version.startswith("v") else f"v{normalized_version}"
        return f"{version_label} ({normalized_sha})" if normalized_sha else version_label

    return normalized_sha or "unknown"


def get_runtime_build_info() -> dict[str, str]:
    image_tag = os.getenv("APP_IMAGE_TAG", "").strip()
    release_version = os.getenv("APP_RELEASE_VERSION", "").strip()
    git_sha = os.getenv("APP_GIT_SHA", "").strip()
    label = image_tag or format_release_label(release_version, git_sha)

    return {
        "image_tag": image_tag,
        "release_version": release_version,
        "git_sha": git_sha,
        "label": label,
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理（替代已弃用的 on_event）"""
    # 启动逻辑
    import asyncio
    import os
    from src.testers.async_tester import AsyncHttpTester
    from src.testers.manager import TesterManager

    async def system_update_broadcast_loop():
        """定时广播系统状态到 WebSocket 客户端。"""
        interval_seconds = int(os.getenv("SYSTEM_WS_BROADCAST_INTERVAL_SECONDS", "10"))
        while True:
            try:
                # 无连接时跳过计算，避免无意义的 Redis/统计开销
                if websocket_manager.get_connection_count() == 0:
                    await asyncio.sleep(interval_seconds)
                    continue
                payload = await get_system_realtime_payload()
                await websocket_manager.broadcast({
                    "type": "system_update",
                    "data": payload
                })
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Failed to broadcast system update: {e}", exc_info=True)
            await asyncio.sleep(interval_seconds)

    async def dashboard_update_broadcast_loop():
        """定时广播仪表盘概览，提升 Dashboard WS 实时性。"""
        interval_seconds = int(os.getenv("DASHBOARD_WS_BROADCAST_INTERVAL_SECONDS", "10"))
        from src.api.dashboard_endpoints import get_dashboard_overview

        while True:
            try:
                if websocket_manager.get_connection_count() == 0:
                    await asyncio.sleep(interval_seconds)
                    continue
                overview = await get_dashboard_overview(_get_redis_manager())
                await websocket_manager.broadcast({
                    "type": "update",
                    "data": overview
                })
                try:
                    collector_payload = await get_collector_realtime_payload()
                    await websocket_manager.broadcast({
                        "type": "collector_update",
                        "data": collector_payload,
                    })
                except Exception as collector_error:
                    logger.error(f"Failed to broadcast collector update: {collector_error}", exc_info=True)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Failed to broadcast dashboard update: {e}", exc_info=True)
            await asyncio.sleep(interval_seconds)

    try:
        migration_report = auto_migrate_collectors_to_v2(
            config_instance=config,
            repository=CollectorV2Repository(_get_redis_manager()),
            logger_instance=logger,
        )
        if migration_report.get("executed"):
            logger.info(
                "Collector V2 auto migration executed: migrated=%s skipped=%s failed=%s",
                migration_report.get("migrated", 0),
                migration_report.get("skipped", 0),
                migration_report.get("failed", 0),
                extra={"component": "API"},
            )
    except Exception as exc:
        logger.error(
            f"Collector V2 auto migration failed: {exc}",
            extra={"component": "API"},
            exc_info=True,
        )
    
    logger.info(
        "Collector runtime is externalized; API process will not start collector tasks.",
        extra={"component": "API"},
    )
    app.state.collector_started = False
    app.state.collector_worker_task = None
    
    # 检查是否应该禁用 API 中的 Tester（避免与 Backend 重复）
    disable_tester = os.getenv("DISABLE_API_TESTER", "0") == "1"
    
    if not disable_tester:
        logger.info("Initializing TesterManager...", extra={"component": "API"})
        app.state.tester_manager = TesterManager(config, logger, _get_redis_manager(), AsyncHttpTester)
        asyncio.create_task(app.state.tester_manager.start())
        logger.info("TesterManager started.", extra={"component": "API"})
    else:
        # 当 Backend 运行Tester时，API不启动Tester，只从Redis读取统计
        logger.info("TesterManager disabled in API (using Backend Tester stats from Redis).", extra={"component": "API"})
        app.state.tester_manager = None
    
    # 启动 WebSocket Redis 监听
    logger.info("Starting WebSocket Redis listener...", extra={"component": "API"})
    await websocket_manager.start_redis_listener()

    # 启动系统状态推送任务
    logger.info("Starting system status websocket broadcaster...", extra={"component": "API"})
    app.state.system_ws_task = asyncio.create_task(system_update_broadcast_loop())

    # 启动仪表盘推送任务
    logger.info("Starting dashboard websocket broadcaster...", extra={"component": "API"})
    app.state.dashboard_ws_task = asyncio.create_task(dashboard_update_broadcast_loop())

    # 启动日志流推送
    logger.info("Starting log stream worker...", extra={"component": "API"})
    await log_stream_manager.start()
    
    # 启动指标记录任务
    logger.info("Starting metrics recorder...", extra={"component": "API"})
    start_metrics_recorder()
    
    # 同步 app.state.tester_manager 到 global_tester_manager
    if hasattr(app.state, 'tester_manager') and app.state.tester_manager:
        import src.app_globals as app_globals
        app_globals.global_tester_manager = app.state.tester_manager
        logger.info("TesterManager synchronized to global_tester_manager", extra={"component": "API"})
    
    yield  # 应用运行期间
    
    # 关闭逻辑
    logger.info("Shutting down API server...", extra={"component": "API"})
    
    # 停止 TesterManager（如果已启动）
    if hasattr(app.state, 'tester_manager') and app.state.tester_manager:
        logger.info("Stopping TesterManager...", extra={"component": "API"})
        await app.state.tester_manager.stop()

    # 停止系统状态推送任务
    if hasattr(app.state, "system_ws_task") and app.state.system_ws_task:
        logger.info("Stopping system status websocket broadcaster...", extra={"component": "API"})
        app.state.system_ws_task.cancel()
        try:
            await app.state.system_ws_task
        except asyncio.CancelledError:
            pass

    # 停止仪表盘推送任务
    if hasattr(app.state, "dashboard_ws_task") and app.state.dashboard_ws_task:
        logger.info("Stopping dashboard websocket broadcaster...", extra={"component": "API"})
        app.state.dashboard_ws_task.cancel()
        try:
            await app.state.dashboard_ws_task
        except asyncio.CancelledError:
            pass

    # 停止日志流推送
    logger.info("Stopping log stream worker...", extra={"component": "API"})
    await log_stream_manager.stop()
    
    logger.info("API server shutdown complete.", extra={"component": "API"})


app = FastAPI(
    title="ProxyPoolMaster API",
    description="RESTful API for managing and retrieving free proxies.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    redirect_slashes=False,  # 禁用斜杠重定向，避免路由匹配问题
    lifespan=lifespan  # 使用新的 lifespan API
)

# 添加速率限制器到app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 添加性能指标中间件（放在最前面以准确统计）
app.add_middleware(MetricsMiddleware)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录所有 API 请求"""
    start_time = time.time()
    
    # 记录请求开始
    client_ip = request.client.host if request.client else "unknown"
    logger.info(
        f"API Request: {request.method} {request.url.path}",
        extra={
            "component": "API",
            "client_ip": client_ip,
            "method": request.method,
            "path": request.url.path
        }
    )
    
    response = await call_next(request)
    
    # 计算处理时间
    process_time = (time.time() - start_time) * 1000
    
    # 记录请求完成
    log_level = logging.INFO if response.status_code < 400 else logging.WARNING
    logger.log(
        log_level,
        f"API Response: {request.method} {request.url.path} - {response.status_code} ({process_time:.1f}ms)",
        extra={
            "component": "API",
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(process_time, 1)
        }
    )
    
    return response


# Include API router with dependency for API key verification
app.include_router(
    api_router,
    prefix="/api/v1",
    dependencies=[Depends(verify_api_token)]
)

# Include Dashboard router
app.include_router(
    dashboard_router,
    prefix="/api/v1/dashboard",
    dependencies=[Depends(verify_api_token)]
)

# Include System router
app.include_router(
    system_router,
    prefix="/api/v1/system",
    dependencies=[Depends(verify_api_token)]
)

# Include Log router
app.include_router(
    log_router,
    prefix="/api/v1/logs",
    dependencies=[Depends(verify_api_token)]
)

# Include Config router
app.include_router(
    config_router,
    prefix="/api/v1/config",
    dependencies=[Depends(verify_api_token)]
)

def mount_collector_routers(target_app: FastAPI) -> None:
    """挂载 Collector V2 路由。"""
    target_app.include_router(
        collector_v2_router,
        prefix="/api/v1/collectors-v2",
        dependencies=[Depends(verify_api_token)]
    )


mount_collector_routers(app)


@app.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    """
    WebSocket 端点用于实时推送仪表盘数据更新
    """
    # 验证 token
    token = websocket.query_params.get("token")
    if not token or token != config.API_TOKEN:
        await websocket.close(code=4001, reason="Invalid or missing API token")
        return
    
    client_ip = websocket.client.host if websocket.client else "unknown"
    logger.info(f"WebSocket connection established from {client_ip}", extra={"component": "API", "client_ip": client_ip})
    
    await websocket_manager.connect(websocket)
    try:
        # 发送初始数据
        from src.api.dashboard_endpoints import get_dashboard_overview
        initial_data = await get_dashboard_overview(_get_redis_manager())
        await websocket.send_json({
            "type": "initial",
            "data": initial_data
        })
        collector_payload = await get_collector_realtime_payload()
        await websocket.send_json({
            "type": "collector_update",
            "data": collector_payload,
        })
        
        # 保持连接，等待客户端断开
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except Exception as e:
        logger.info(f"WebSocket connection closed: {e}", extra={"component": "API"})
    finally:
        websocket_manager.disconnect(websocket)


@app.websocket("/ws/logs")
async def logs_websocket(websocket: WebSocket):
    """
    日志流 WebSocket 端点（增量推送）。
    """
    token = websocket.query_params.get("token")
    if not token or token != config.API_TOKEN:
        await websocket.close(code=4001, reason="Invalid or missing API token")
        return

    client_ip = websocket.client.host if websocket.client else "unknown"
    logger.info(
        f"Log WebSocket connection established from {client_ip}",
        extra={"component": "API", "client_ip": client_ip},
    )

    await log_stream_manager.connect(websocket)
    try:
        # 默认先返回一份快照，前端可继续发送 subscribe 更新过滤条件
        await log_stream_manager.subscribe(
            websocket,
            filters={
                "level": "",
                "min_level": "",
                "component": "",
                "exclude_components": "",
                "keyword": "",
            },
            page_size=20,
        )
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
                continue
            await log_stream_manager.handle_message(websocket, data)
    except WebSocketDisconnect:
        logger.info("Log WebSocket disconnected", extra={"component": "API"})
    except Exception as e:
        logger.info(f"Log WebSocket connection closed: {e}", extra={"component": "API"})
    finally:
        await log_stream_manager.disconnect(websocket)


@app.get("/health", summary="Health Check")
@limiter.limit(config.RATE_LIMIT_HEALTH_MINUTE)
async def health_check(request: Request):
    """
    Checks the health of the API and its dependencies.
    """
    try:
        redis_client = _get_redis_manager().get_redis_client()
        if redis_client.ping():
            return {"status": "ok", "redis_status": "connected"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Redis not connected"
            )
    except Exception as e:
        logger.error(f"Health check failed: {e}", extra={"component": "API"})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {e}"
        )


@app.get("/api/v1/runtime-info", summary="Runtime Build Info")
async def runtime_info():
    """返回当前运行实例的构建与镜像信息。"""
    return get_runtime_build_info()


if __name__ == "__main__":
    # Check if reload mode is enabled (for development)
    reload_mode = "--reload" in sys.argv
    
    # 配置 uvicorn 使用我们的日志格式
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(asctime)s [%(levelname)s] [API] [uvicorn] %(message)s",
                "use_colors": None,
            },
            "access": {
                "()": "uvicorn.logging.AccessFormatter",
                "fmt": "%(asctime)s [%(levelname)s] [API] [uvicorn.access] %(request_line)s - %(status_code)s",
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
            "access": {
                "formatter": "access",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
            "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False},
        },
    }
    
    port = int(os.getenv("API_PORT", "8000"))
    host = os.getenv("API_HOST", "0.0.0.0")
    
    logger.info(f"Starting ProxyPoolMaster API server on {host}:{port} (reload={reload_mode})...", extra={"component": "API"})
    
    uvicorn.run(
        "src.api.main:app",  # 使用模块字符串以便 reload 正常工作
        host=host,
        port=port,
        reload=reload_mode,
        log_config=log_config,
        access_log=True,
        reload_dirs=["src"] if reload_mode else None
    )
