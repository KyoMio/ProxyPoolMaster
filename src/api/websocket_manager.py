# src/api/websocket_manager.py
"""WebSocket 连接管理器 - 用于实时推送仪表盘数据更新"""

from typing import List
from fastapi import WebSocket
import json
import logging
import asyncio
import redis.asyncio as aioredis
import os

logger = logging.getLogger("ProxyPoolMaster")

class WebSocketManager:
    """管理 WebSocket 连接，支持广播消息给所有连接的客户端"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._redis_listener_started = False
        self._subscription_event = asyncio.Event()
        self._redis_client = None
        self._pubsub = None
        self._listen_task = None
        self._heartbeat_task = None
        self._last_message_time = 0
    
    async def start_redis_listener(self):
        """启动 Redis 订阅监听（在 FastAPI startup 事件中调用）"""
        if self._redis_listener_started and self._listen_task and not self._listen_task.done():
            logger.info("Redis listener already running")
            return
        
        try:
            await self._start_listener()
            # 启动心跳任务
            if not self._heartbeat_task or self._heartbeat_task.done():
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        except Exception as e:
            logger.error(f"Failed to start Redis listener: {e}", exc_info=True)
            self._redis_listener_started = True
            asyncio.create_task(self._reconnect_loop())
    
    async def _start_listener(self):
        """实际启动监听"""
        redis_host = os.getenv("REDIS_HOST", "redis")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        redis_db = int(os.getenv("REDIS_DB", 0))
        
        logger.info(f"Connecting to Redis at {redis_host}:{redis_port}/{redis_db}")
        
        self._redis_client = aioredis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=True,
            socket_keepalive=True,
            retry_on_timeout=True,
        )
        
        # 测试连接
        await self._redis_client.ping()
        logger.info("Redis connection successful")
        
        # 创建订阅
        self._pubsub = self._redis_client.pubsub()
        await self._pubsub.subscribe("websocket_broadcast")
        logger.info("Subscribed to websocket_broadcast channel")
        
        # 启动监听任务
        self._listen_task = asyncio.create_task(self._listen())
        self._redis_listener_started = True
        
        logger.info("Redis listener started successfully")
    
    async def _listen(self):
        """监听 Redis 消息"""
        try:
            async for message in self._pubsub.listen():
                logger.debug(f"Redis raw message: {message}")
                
                if message["type"] == "subscribe":
                    channel = message.get("channel", "unknown")
                    logger.info(f"Redis subscription confirmed: channel={channel}")
                    self._subscription_event.set()
                    
                elif message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        self._last_message_time = asyncio.get_event_loop().time()
                        logger.debug(f"Received from Redis: type={data.get('type')}")
                        await self._broadcast_internal(data)
                    except Exception as e:
                        logger.error(f"Error processing Redis message: {e}")
                        
        except asyncio.CancelledError:
            logger.info("Redis listener cancelled")
            raise
        except Exception as e:
            logger.error(f"Redis listener error: {e}", exc_info=True)
            raise
    
    async def _heartbeat_loop(self):
        """心跳检测循环，定期检查连接状态"""
        while True:
            try:
                await asyncio.sleep(10)  # 每10秒检查一次
                
                # 检查监听任务是否还在运行
                if self._listen_task and self._listen_task.done():
                    logger.warning("Redis listener task died, reconnecting...")
                    asyncio.create_task(self._reconnect_loop())
                    continue
                
                # 检查 Redis 连接
                if self._redis_client:
                    try:
                        await self._redis_client.ping()
                        logger.debug("Redis heartbeat OK")
                    except Exception as e:
                        logger.warning(f"Redis heartbeat failed: {e}, reconnecting...")
                        asyncio.create_task(self._reconnect_loop())
                        
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")
    
    async def _reconnect_loop(self):
        """自动重连循环"""
        retry_count = 0
        max_retries = 10
        
        while retry_count < max_retries:
            try:
                # 清理旧连接
                if self._pubsub:
                    try:
                        await self._pubsub.unsubscribe("websocket_broadcast")
                        await self._pubsub.close()
                    except:
                        pass
                    self._pubsub = None
                
                if self._redis_client:
                    try:
                        await self._redis_client.close()
                    except:
                        pass
                    self._redis_client = None
                
                retry_count += 1
                wait_time = min(5 * retry_count, 30)  # 递增等待时间，最大30秒
                
                logger.info(f"Redis reconnecting in {wait_time}s (attempt {retry_count}/{max_retries})...")
                await asyncio.sleep(wait_time)
                
                await self._start_listener()
                logger.info("Redis listener reconnected successfully")
                return  # 重连成功，退出循环
                
            except Exception as e:
                logger.error(f"Redis reconnect failed: {e}")
                continue
        
        logger.error(f"Redis reconnect failed after {max_retries} attempts")
    
    async def _broadcast_internal(self, message: dict):
        """内部广播方法"""
        if not self.active_connections:
            logger.debug("No active WebSocket connections to broadcast")
            return
        
        logger.debug(f"Broadcasting to {len(self.active_connections)} clients: type={message.get('type')}")
        disconnected = []
        
        for i, connection in enumerate(self.active_connections):
            try:
                await connection.send_json(message)
                logger.debug(f"Message sent to client {i+1}")
            except Exception as e:
                logger.warning(f"Failed to send to client {i+1}: {e}")
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn)
    
    async def connect(self, websocket: WebSocket):
        """接受新的 WebSocket 连接"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total: {len(self.active_connections)}")
        
        # 检查 Redis 连接，如需要则重连
        if not self._redis_client or not self._listen_task or self._listen_task.done():
            logger.info("Redis not connected, triggering reconnect on WebSocket connect")
            asyncio.create_task(self._reconnect_loop())
    
    def disconnect(self, websocket: WebSocket):
        """断开 WebSocket 连接"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Total: {len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        """广播消息给所有连接的客户端（仅本进程）"""
        if self.active_connections:
            logger.debug(f"Broadcasting to {len(self.active_connections)} clients: type={message.get('type')}")
            await self._broadcast_internal(message)
        else:
            logger.debug("No active WebSocket connections for broadcast")

    def get_connection_count(self) -> int:
        """获取当前 WebSocket 连接数。"""
        return len(self.active_connections)

# 全局 WebSocket 管理器实例
websocket_manager = WebSocketManager()
