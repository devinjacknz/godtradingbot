import asyncio
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import aioboto3
from prometheus_client import Counter, Gauge, Histogram


@dataclass
class WebSocketMetrics:
    """WebSocket性能指标"""

    connection_count: Gauge
    message_rate: Counter
    message_latency: Histogram
    error_rate: Counter
    reconnection_count: Counter
    backpressure: Gauge
    memory_usage: Gauge


class WebSocketManager:
    """WebSocket连接管理器"""

    def __init__(self, config: Dict):
        self.config = config
        self.connections: Dict[str, List[Any]] = defaultdict(list)
        self.message_queues: Dict[str, asyncio.Queue] = {}
        self.batch_processors: Dict[str, asyncio.Task] = {}

        # 性能配置
        self.batch_size = config.get("batch_size", 100)
        self.batch_timeout = config.get("batch_timeout", 0.1)  # 100ms
        self.max_queue_size = config.get("max_queue_size", 10000)
        self.connection_pool_size = config.get("connection_pool_size", 10)

        # 速率限制
        self.rate_limits = defaultdict(
            lambda: {
                "messages_per_second": config.get("default_rate_limit", 1000),
                "burst_limit": config.get("default_burst_limit", 100),
            }
        )

        # 监控指标
        self.metrics = WebSocketMetrics(
            connection_count=Gauge(
                "ws_connection_count", "Active WebSocket connections"
            ),
            message_rate=Counter("ws_message_rate", "WebSocket messages per second"),
            message_latency=Histogram(
                "ws_message_latency", "WebSocket message latency"
            ),
            error_rate=Counter("ws_error_rate", "WebSocket errors"),
            reconnection_count=Counter(
                "ws_reconnection_count", "WebSocket reconnections"
            ),
            backpressure=Gauge("ws_backpressure", "WebSocket backpressure"),
            memory_usage=Gauge("ws_memory_usage", "WebSocket memory usage"),
        )

        # 初始化日志
        self.logger = logging.getLogger(__name__)

    async def start(self):
        """启动WebSocket管理器"""
        # 启动批处理任务
        for channel in self.connections.keys():
            if channel not in self.batch_processors:
                self.message_queues[channel] = asyncio.Queue(
                    maxsize=self.max_queue_size
                )
                self.batch_processors[channel] = asyncio.create_task(
                    self._process_message_batch(channel)
                )

    async def stop(self):
        """停止WebSocket管理器"""
        # 取消所有批处理任务
        for task in self.batch_processors.values():
            task.cancel()

        # 等待任务完成
        await asyncio.gather(*self.batch_processors.values(), return_exceptions=True)

        # 清理连接
        for connections in self.connections.values():
            for conn in connections:
                await conn.close()

    async def _process_message_batch(self, channel: str):
        """批量处理消息"""
        while True:
            try:
                batch = []
                start_time = datetime.now()

                # 收集消息批次
                while len(batch) < self.batch_size:
                    try:
                        # 如果队列为空，等待batch_timeout
                        message = await asyncio.wait_for(
                            self.message_queues[channel].get(),
                            timeout=self.batch_timeout,
                        )
                        batch.append(message)
                    except asyncio.TimeoutError:
                        break

                if not batch:
                    continue

                # 更新背压指标
                queue_size = self.message_queues[channel].qsize()
                self.metrics.backpressure.labels(channel=channel).set(
                    queue_size / self.max_queue_size
                )

                # 批量发送消息
                for conn in self.connections[channel]:
                    try:
                        await conn.send_json(
                            {
                                "type": "batch",
                                "messages": batch,
                                "timestamp": datetime.now().isoformat(),
                            }
                        )

                        # 更新性能指标
                        batch_size = len(batch)
                        self.metrics.message_rate.labels(channel=channel).inc(
                            batch_size
                        )
                        latency = (datetime.now() - start_time).total_seconds()
                        self.metrics.message_latency.labels(channel=channel).observe(
                            latency / batch_size
                        )
                    except Exception as e:
                        self.logger.error(f"Error sending batch to {channel}: {str(e)}")
                        self.metrics.error_rate.labels(channel=channel).inc()

            except Exception as e:
                self.logger.error(f"Batch processing error for {channel}: {str(e)}")
                await asyncio.sleep(1)  # 错误后等待

    async def send_message(self, channel: str, message: Dict) -> bool:
        """发送消息到指定频道"""
        try:
            # 检查速率限制
            if not self._check_rate_limit(channel):
                self.logger.warning(f"Rate limit exceeded for channel {channel}")
                return False

            # 添加消息到队列
            try:
                await self.message_queues[channel].put(message)
                return True
            except asyncio.QueueFull:
                self.logger.warning(f"Message queue full for channel {channel}")
                return False

        except Exception as e:
            self.logger.error(f"Error sending message to {channel}: {str(e)}")
            self.metrics.error_rate.labels(channel=channel).inc()
            return False

    def _check_rate_limit(self, channel: str) -> bool:
        """检查速率限制"""
        current_time = datetime.now().timestamp()
        rate_limit = self.rate_limits[channel]

        # 更新令牌桶
        if "last_update" not in rate_limit:
            rate_limit["last_update"] = current_time
            rate_limit["tokens"] = rate_limit["burst_limit"]
        else:
            time_passed = current_time - rate_limit["last_update"]
            new_tokens = time_passed * rate_limit["messages_per_second"]
            rate_limit["tokens"] = min(
                rate_limit["burst_limit"], rate_limit["tokens"] + new_tokens
            )
            rate_limit["last_update"] = current_time

        # 检查是否有足够的令牌
        if rate_limit["tokens"] >= 1:
            rate_limit["tokens"] -= 1
            return True
        return False

    async def add_connection(self, channel: str, connection: Any):
        """添加新的WebSocket连接"""
        self.connections[channel].append(connection)
        self.metrics.connection_count.labels(channel=channel).inc()

        # 确保有消息队列和处理器
        if channel not in self.message_queues:
            self.message_queues[channel] = asyncio.Queue(maxsize=self.max_queue_size)
            self.batch_processors[channel] = asyncio.create_task(
                self._process_message_batch(channel)
            )

    async def remove_connection(self, channel: str, connection: Any):
        """移除WebSocket连接"""
        if connection in self.connections[channel]:
            self.connections[channel].remove(connection)
            self.metrics.connection_count.labels(channel=channel).dec()

    async def broadcast(self, channel: str, message: Dict):
        """广播消息到频道的所有连接"""
        if not self.connections[channel]:
            return

        await self.send_message(channel, message)

    def get_connection_count(self, channel: str) -> int:
        """获取频道的连接数"""
        return len(self.connections[channel])

    def get_queue_size(self, channel: str) -> int:
        """获取频道的消息队列大小"""
        if channel in self.message_queues:
            return self.message_queues[channel].qsize()
        return 0
