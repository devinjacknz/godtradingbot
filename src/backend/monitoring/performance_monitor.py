import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import aiohttp
import aioping
import asyncpg
import psutil
from prometheus_client import Counter, Gauge, Histogram, Summary


@dataclass
class PerformanceMetrics:
    """性能指标"""

    cpu_usage: Gauge
    memory_usage: Gauge
    network_latency: Histogram
    db_query_time: Histogram
    api_response_time: Histogram
    error_count: Counter
    request_count: Counter


class PerformanceMonitor:
    """性能监控管理器"""

    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)

        # 初始化指标
        self.metrics = PerformanceMetrics(
            cpu_usage=Gauge("system_cpu_usage", "CPU usage percentage"),
            memory_usage=Gauge("system_memory_usage", "Memory usage percentage"),
            network_latency=Histogram("network_latency_seconds", "Network latency"),
            db_query_time=Histogram("db_query_time_seconds", "Database query time"),
            api_response_time=Histogram(
                "api_response_time_seconds", "API response time"
            ),
            error_count=Counter("monitor_error_total", "Total error count"),
            request_count=Counter("monitor_request_total", "Total request count"),
        )

        # 监控配置
        self.monitor_config = {
            "cpu_threshold": config.get("cpu_threshold", 80),  # CPU使用率阈值
            "memory_threshold": config.get("memory_threshold", 80),  # 内存使用率阈值
            "network_threshold": config.get("network_threshold", 0.1),  # 网络延迟阈值(秒)
            "db_query_threshold": config.get("db_query_threshold", 1.0),  # 数据库查询阈值(秒)
            "api_timeout": config.get("api_timeout", 5.0),  # API超时时间(秒)
            "monitor_interval": config.get("monitor_interval", 60),  # 监控间隔(秒)
            "alert_cooldown": config.get("alert_cooldown", 300),  # 告警冷却时间(秒)
        }

        # 监控任务
        self.monitor_task = None
        self.last_alert_time = {}

    async def start(self):
        """启动监控"""
        self.monitor_task = asyncio.create_task(self._monitor_loop())

    async def stop(self):
        """停止监控"""
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

    async def _monitor_loop(self):
        """监控循环"""
        while True:
            try:
                # 系统资源监控
                await self._monitor_system_resources()

                # 网络延迟监控
                await self._monitor_network_latency()

                # 数据库性能监控
                await self._monitor_database_performance()

                # API性能监控
                await self._monitor_api_performance()

                # 等待下一次监控
                await asyncio.sleep(self.monitor_config["monitor_interval"])

            except Exception as e:
                self.logger.error(f"Monitoring error: {str(e)}")
                self.metrics.error_count.inc()
                await asyncio.sleep(60)

    async def _monitor_system_resources(self):
        """监控系统资源"""
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            self.metrics.cpu_usage.set(cpu_percent)

            if cpu_percent > self.monitor_config["cpu_threshold"]:
                await self._create_alert("high_cpu_usage", f"CPU usage: {cpu_percent}%")

            # 内存使用率
            memory = psutil.virtual_memory()
            self.metrics.memory_usage.set(memory.percent)

            if memory.percent > self.monitor_config["memory_threshold"]:
                await self._create_alert(
                    "high_memory_usage", f"Memory usage: {memory.percent}%"
                )

        except Exception as e:
            self.logger.error(f"System resource monitoring error: {str(e)}")
            self.metrics.error_count.inc()

    async def _monitor_network_latency(self):
        """监控网络延迟"""
        try:
            # 测试关键服务延迟
            for service in self.config.get("network_services", []):
                try:
                    start_time = time.time()
                    delay = await aioping.ping(service["host"])
                    self.metrics.network_latency.observe(delay)

                    if delay > self.monitor_config["network_threshold"]:
                        await self._create_alert(
                            "high_network_latency",
                            f"High latency to {service['host']}: {delay:.3f}s",
                        )

                except Exception as e:
                    self.logger.error(
                        f"Network latency check error for {service['host']}: {str(e)}"
                    )
                    self.metrics.error_count.inc()

        except Exception as e:
            self.logger.error(f"Network monitoring error: {str(e)}")
            self.metrics.error_count.inc()

    async def _monitor_database_performance(self):
        """监控数据库性能"""
        try:
            # 连接数据库
            conn = await asyncpg.connect(self.config["database_url"])

            try:
                # 测试查询性能
                start_time = time.time()
                await conn.fetch("SELECT 1")
                query_time = time.time() - start_time

                self.metrics.db_query_time.observe(query_time)

                if query_time > self.monitor_config["db_query_threshold"]:
                    await self._create_alert(
                        "slow_database", f"Slow database response: {query_time:.3f}s"
                    )

                # 检查数据库状态
                status = await conn.fetch(
                    """
                    SELECT * FROM pg_stat_activity
                    WHERE state = 'active'
                """
                )

                # 分析长时间运行的查询
                for record in status:
                    if record["state_change"] < datetime.now() - timedelta(minutes=5):
                        await self._create_alert(
                            "long_running_query",
                            f"Long running query detected: {record['query']}",
                        )

            finally:
                await conn.close()

        except Exception as e:
            self.logger.error(f"Database monitoring error: {str(e)}")
            self.metrics.error_count.inc()

    async def _monitor_api_performance(self):
        """监控API性能"""
        try:
            async with aiohttp.ClientSession() as session:
                for endpoint in self.config.get("api_endpoints", []):
                    try:
                        start_time = time.time()
                        async with session.get(
                            endpoint["url"], timeout=self.monitor_config["api_timeout"]
                        ) as response:
                            response_time = time.time() - start_time
                            self.metrics.api_response_time.observe(response_time)

                            # 检查响应时间
                            if response_time > endpoint.get("threshold", 1.0):
                                await self._create_alert(
                                    "slow_api_response",
                                    f"Slow API response from {endpoint['url']}: {response_time:.3f}s",
                                )

                            # 检查响应状态
                            if response.status >= 400:
                                await self._create_alert(
                                    "api_error",
                                    f"API error from {endpoint['url']}: {response.status}",
                                )

                    except Exception as e:
                        self.logger.error(
                            f"API monitoring error for {endpoint['url']}: {str(e)}"
                        )
                        self.metrics.error_count.inc()

        except Exception as e:
            self.logger.error(f"API monitoring error: {str(e)}")
            self.metrics.error_count.inc()

    async def _create_alert(self, alert_type: str, message: str):
        """创建告警"""
        current_time = time.time()

        # 检查冷却时间
        if alert_type in self.last_alert_time:
            if (
                current_time - self.last_alert_time[alert_type]
                < self.monitor_config["alert_cooldown"]
            ):
                return

        self.last_alert_time[alert_type] = current_time

        # TODO: 实现告警通知
        self.logger.warning(f"Alert: {message}")

    def get_performance_metrics(self) -> Dict:
        """获取性能指标"""
        return {
            "cpu_usage": self.metrics.cpu_usage._value.get(),
            "memory_usage": self.metrics.memory_usage._value.get(),
            "network_latency": self.metrics.network_latency.observe(),
            "db_query_time": self.metrics.db_query_time.observe(),
            "api_response_time": self.metrics.api_response_time.observe(),
            "error_count": self.metrics.error_count._value.get(),
            "request_count": self.metrics.request_count._value.get(),
        }
