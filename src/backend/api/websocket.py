import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, Optional, Set

import psutil
from fastapi import WebSocket, WebSocketDisconnect

from src.models.metrics import WebSocketMetrics
from src.utils.security import validate_ws_token

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {
            "trades": set(),
            "positions": set(),
            "metrics": set(),
        }
        self.rate_limits: Dict[str, Dict] = {}
        self.message_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self.metrics = WebSocketMetrics()
        self.reconnect_attempts: Dict[str, int] = {}

    async def connect(self, websocket: WebSocket, channel: str):
        """建立WebSocket连接"""
        # 验证WebSocket协议版本
        if not self._validate_protocol_version(websocket):
            raise Exception("Unsupported WebSocket protocol version")

        # 验证认证token
        if not await validate_ws_token(websocket):
            raise Exception("Invalid authentication token")

        # 验证频道权限
        if not self._validate_channel_permission(channel):
            raise Exception("Access to this channel is restricted")

        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = set()
        self.active_connections[channel].add(websocket)
        self.rate_limits[id(websocket)] = {
            "last_reset": time.time(),
            "message_count": 0,
            "window_size": 60.0,
            "max_requests": 100,
        }
        logger.info(f"Client connected to channel {channel}")

    def disconnect(self, websocket: WebSocket, channel: str):
        """断开WebSocket连接"""
        self.active_connections[channel].remove(websocket)
        if id(websocket) in self.rate_limits:
            del self.rate_limits[id(websocket)]
        logger.info(f"Client disconnected from channel {channel}")

    async def broadcast(self, message: dict, channel: str):
        """广播消息到指定频道"""
        # 验证消息格式
        if not self._validate_message(message):
            raise Exception("Invalid message format")

        # 检查速率限制
        if not await self._check_rate_limit(channel):
            raise Exception("Rate limit exceeded")

        # 检查队列背压
        if self.message_queue.qsize() >= self.message_queue.maxsize:
            logger.warning("Message queue full, applying backpressure")
            return

        disconnected = set()
        for connection in self.active_connections[channel]:
            try:
                await connection.send_json(message)
                self.metrics.messages_sent += 1
            except WebSocketDisconnect:
                disconnected.add(connection)
            except Exception as e:
                logger.error(f"Error broadcasting message: {str(e)}")
                disconnected.add(connection)
                self.metrics.error_count += 1

        for connection in disconnected:
            self.disconnect(connection, channel)

    def _validate_protocol_version(self, websocket: WebSocket) -> bool:
        """验证WebSocket协议版本"""
        headers = getattr(websocket, "headers", {})
        version = headers.get("Sec-WebSocket-Version")
        return version == "13"  # RFC 6455

    def _validate_channel_permission(self, channel: str) -> bool:
        """验证频道访问权限"""
        restricted_channels = {"admin", "system"}
        return channel not in restricted_channels

    def _validate_message(self, message: dict) -> bool:
        """验证消息格式和内容"""
        required_fields = {"type", "data"}
        if not all(field in message for field in required_fields):
            return False

        # 检查潜在的注入攻击
        if self._check_injection(message):
            return False

        return True

    def _check_injection(self, message: dict) -> bool:
        """检查消息中的潜在注入攻击"""
        dangerous_patterns = {
            "__proto__",
            "constructor",
            "<script>",
            "alert(",
            "'; DROP",
            "--",
        }

        message_str = json.dumps(message)
        return any(pattern in message_str for pattern in dangerous_patterns)

    async def _check_rate_limit(self, channel: str) -> bool:
        """检查频道的速率限制"""
        current_time = time.time()
        total_messages = sum(
            conn["message_count"] for conn in self.rate_limits.values()
        )

        # 重置计数器
        for conn_id, limit_info in self.rate_limits.items():
            if current_time - limit_info["last_reset"] >= limit_info["window_size"]:
                limit_info["message_count"] = 0
                limit_info["last_reset"] = current_time

        # 检查总消息数是否超过限制
        return total_messages < 1000  # 每分钟最多1000条消息


manager = ConnectionManager()


async def handle_websocket(websocket: WebSocket, channel: str):
    await manager.connect(websocket, channel)
    try:
        while True:
            try:
                data = await websocket.receive_text()
                # 处理接收到的消息
                message = json.loads(data)
                if manager._validate_message(message):
                    logger.debug(f"Received message on channel {channel}: {data}")
                else:
                    logger.warning(f"Invalid message received on channel {channel}")
            except WebSocketDisconnect:
                manager.disconnect(websocket, channel)
                break
            except json.JSONDecodeError:
                logger.error("Invalid JSON message received")
            except Exception as e:
                logger.error(f"WebSocket error: {str(e)}")
                break
    finally:
        manager.disconnect(websocket, channel)


async def broadcast_trade_update(trade_data: dict):
    """广播交易更新"""
    message = {
        "type": "trade",
        "data": trade_data,
        "timestamp": datetime.utcnow().isoformat(),
    }
    await manager.broadcast(message, "trades")


async def broadcast_position_update(position_data: dict):
    """广播仓位更新"""
    message = {
        "type": "position",
        "data": position_data,
        "timestamp": datetime.utcnow().isoformat(),
    }
    await manager.broadcast(message, "positions")


async def broadcast_metrics_update(metrics_data: dict):
    """Broadcast metrics updates to connected clients"""
    message = {
        "type": "metrics",
        "data": metrics_data,
        "timestamp": datetime.utcnow().isoformat(),
    }
    await manager.broadcast(message, "metrics")


# Example background task for periodic updates
async def periodic_metrics_update():
    """Send periodic metrics updates to connected clients"""
    while True:
        try:
            # This would typically fetch real metrics from your system
            metrics = {
                "active_strategies": 5,
                "total_positions": 10,
                "total_pnl": 15000.0,
                "win_rate": 0.65,
            }
            await broadcast_metrics_update(metrics)
        except Exception as e:
            logger.error(f"Error in periodic metrics update: {str(e)}")
        finally:
            await asyncio.sleep(5)  # Update every 5 seconds
