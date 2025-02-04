import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union

import numpy as np
import pandas as pd
import psutil

from src.shared.cache.hybrid_cache import HybridCache


@dataclass
class PerformanceMetrics:
    """性能指标数据类"""

    timestamp: datetime
    data_type: str
    processing_time: float
    batch_size: int
    queue_size: int
    memory_usage: int
    cpu_usage: float
    cache_hits: int
    cache_misses: int
    error_count: int


class Monitoring:
    """监控系统，负责收集和分析性能指标"""

    def __init__(self, config: Dict):
        self.config = config
        self.cache = HybridCache()

        # 配置参数
        self.metrics_ttl = config.get("metrics_ttl", 86400)  # 指标保存时间（秒）
        self.alert_threshold = config.get("alert_threshold", 0.9)  # 告警阈值
        self.sampling_interval = config.get("sampling_interval", 60)  # 采样间隔（秒）

        # 初始化指标存储
        self._init_storage()

        # 设置日志
        self._setup_logging()

    def _init_storage(self):
        """初始化指标存储"""
        self.metrics_history = {"market": [], "trading": [], "social": []}
        self.alerts_history = []
        self.error_history = []

    def _setup_logging(self):
        """设置日志"""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def record_metrics(self, metrics: PerformanceMetrics):
        """记录性能指标

        Args:
            metrics: 性能指标数据
        """
        try:
            # 添加到历史记录
            self.metrics_history[metrics.data_type].append(metrics)

            # 清理过期数据
            self._cleanup_old_metrics()

            # 检查告警条件
            self._check_alerts(metrics)

            # 缓存指标
            key = f"metrics_{metrics.data_type}_{metrics.timestamp.timestamp()}"
            self.cache.set(key, metrics.__dict__, ttl=self.metrics_ttl)

        except Exception as e:
            self.logger.error(f"Failed to record metrics: {str(e)}")
            self.error_history.append(
                {
                    "timestamp": datetime.now(),
                    "error": str(e),
                    "component": "monitoring",
                }
            )

    def _cleanup_old_metrics(self):
        """清理过期指标"""
        cutoff_time = datetime.now() - timedelta(seconds=self.metrics_ttl)

        for data_type in self.metrics_history:
            self.metrics_history[data_type] = [
                m for m in self.metrics_history[data_type] if m.timestamp > cutoff_time
            ]

    def _check_alerts(self, metrics: PerformanceMetrics):
        """检查告警条件

        Args:
            metrics: 性能指标数据
        """
        alerts = []

        # 检查处理时间
        if metrics.processing_time > 5.0:
            alerts.append(
                {
                    "type": "processing_time",
                    "message": f"High processing time: {metrics.processing_time:.2f}s",
                }
            )

        # 检查队列大小
        if metrics.queue_size > 10000:
            alerts.append(
                {
                    "type": "queue_size",
                    "message": f"Large queue size: {metrics.queue_size}",
                }
            )

        # 检查内存使用
        memory_usage_gb = metrics.memory_usage / 1e9
        if memory_usage_gb > 2.0:
            alerts.append(
                {
                    "type": "memory_usage",
                    "message": f"High memory usage: {memory_usage_gb:.2f}GB",
                }
            )

        # 检查CPU使用
        if metrics.cpu_usage > 80:
            alerts.append(
                {
                    "type": "cpu_usage",
                    "message": f"High CPU usage: {metrics.cpu_usage}%",
                }
            )

        # 检查错误率
        error_rate = metrics.error_count / metrics.batch_size
        if error_rate > 0.01:
            alerts.append(
                {"type": "error_rate", "message": f"High error rate: {error_rate:.2%}"}
            )

        # 检查缓存命中率
        cache_total = metrics.cache_hits + metrics.cache_misses
        if cache_total > 0:
            hit_rate = metrics.cache_hits / cache_total
            if hit_rate < 0.5:
                alerts.append(
                    {
                        "type": "cache_hit_rate",
                        "message": f"Low cache hit rate: {hit_rate:.2%}",
                    }
                )

        # 记录告警
        if alerts:
            alert_record = {
                "timestamp": metrics.timestamp,
                "data_type": metrics.data_type,
                "alerts": alerts,
            }
            self.alerts_history.append(alert_record)

            # 记录日志
            for alert in alerts:
                self.logger.warning(
                    f"Alert for {metrics.data_type}: {alert['message']}"
                )

    def get_metrics_summary(self, data_type: str, time_window: int = 3600) -> Dict:
        """获取指标统计摘要

        Args:
            data_type: 数据类型
            time_window: 时间窗口（秒）

        Returns:
            Dict: 指标统计摘要
        """
        try:
            # 获取时间窗口内的指标
            cutoff_time = datetime.now() - timedelta(seconds=time_window)
            metrics_list = [
                m for m in self.metrics_history[data_type] if m.timestamp > cutoff_time
            ]

            if not metrics_list:
                return {}

            # 计算统计值
            processing_times = [m.processing_time for m in metrics_list]
            queue_sizes = [m.queue_size for m in metrics_list]
            memory_usages = [m.memory_usage for m in metrics_list]
            cpu_usages = [m.cpu_usage for m in metrics_list]
            error_counts = [m.error_count for m in metrics_list]

            # 计算缓存统计
            cache_hits = sum(m.cache_hits for m in metrics_list)
            cache_misses = sum(m.cache_misses for m in metrics_list)
            cache_total = cache_hits + cache_misses
            cache_hit_rate = cache_hits / cache_total if cache_total > 0 else 0

            return {
                "time_window": time_window,
                "sample_count": len(metrics_list),
                "processing_time": {
                    "mean": np.mean(processing_times),
                    "std": np.std(processing_times),
                    "min": np.min(processing_times),
                    "max": np.max(processing_times),
                    "p95": np.percentile(processing_times, 95),
                },
                "queue_size": {
                    "mean": np.mean(queue_sizes),
                    "max": np.max(queue_sizes),
                },
                "memory_usage": {
                    "mean": np.mean(memory_usages) / 1e9,  # 转换为GB
                    "max": np.max(memory_usages) / 1e9,
                },
                "cpu_usage": {"mean": np.mean(cpu_usages), "max": np.max(cpu_usages)},
                "error_stats": {
                    "total": sum(error_counts),
                    "rate": sum(error_counts) / sum(m.batch_size for m in metrics_list),
                },
                "cache_stats": {
                    "hits": cache_hits,
                    "misses": cache_misses,
                    "hit_rate": cache_hit_rate,
                },
            }

        except Exception as e:
            self.logger.error(f"Failed to get metrics summary: {str(e)}")
            return {}

    def get_alerts_summary(self, time_window: int = 3600) -> List[Dict]:
        """获取告警摘要

        Args:
            time_window: 时间窗口（秒）

        Returns:
            List[Dict]: 告警记录列表
        """
        try:
            cutoff_time = datetime.now() - timedelta(seconds=time_window)
            recent_alerts = [
                alert
                for alert in self.alerts_history
                if alert["timestamp"] > cutoff_time
            ]

            # 按类型统计告警
            alert_counts = {}
            for alert in recent_alerts:
                for a in alert["alerts"]:
                    alert_type = a["type"]
                    if alert_type not in alert_counts:
                        alert_counts[alert_type] = 0
                    alert_counts[alert_type] += 1

            return [
                {
                    "type": alert_type,
                    "count": count,
                    "examples": [
                        a["message"]
                        for alert in recent_alerts
                        for a in alert["alerts"]
                        if a["type"] == alert_type
                    ][
                        :3
                    ],  # 最多显示3个示例
                }
                for alert_type, count in alert_counts.items()
            ]

        except Exception as e:
            self.logger.error(f"Failed to get alerts summary: {str(e)}")
            return []

    def get_error_summary(self, time_window: int = 3600) -> List[Dict]:
        """获取错误摘要

        Args:
            time_window: 时间窗口（秒）

        Returns:
            List[Dict]: 错误记录列表
        """
        try:
            cutoff_time = datetime.now() - timedelta(seconds=time_window)
            recent_errors = [
                error
                for error in self.error_history
                if error["timestamp"] > cutoff_time
            ]

            # 按组件和错误类型统计
            error_counts = {}
            for error in recent_errors:
                key = (error["component"], error["error"])
                if key not in error_counts:
                    error_counts[key] = 0
                error_counts[key] += 1

            return [
                {
                    "component": component,
                    "error": error,
                    "count": count,
                    "last_occurrence": max(
                        error["timestamp"]
                        for error in recent_errors
                        if error["component"] == component and error["error"] == error
                    ),
                }
                for (component, error), count in error_counts.items()
            ]

        except Exception as e:
            self.logger.error(f"Failed to get error summary: {str(e)}")
            return []

    async def start_monitoring(self):
        """启动监控"""
        while True:
            try:
                # 收集系统指标
                system_metrics = self._collect_system_metrics()

                # 记录系统指标
                self.record_metrics(
                    PerformanceMetrics(
                        timestamp=datetime.now(),
                        data_type="system",
                        processing_time=0,
                        batch_size=0,
                        queue_size=0,
                        memory_usage=system_metrics["memory_usage"],
                        cpu_usage=system_metrics["cpu_usage"],
                        cache_hits=0,
                        cache_misses=0,
                        error_count=0,
                    )
                )

                # 生成监控报告
                self._generate_monitoring_report()

                # 等待下一个采样周期
                await asyncio.sleep(self.sampling_interval)

            except Exception as e:
                self.logger.error(f"Monitoring error: {str(e)}")
                await asyncio.sleep(self.sampling_interval)

    def _collect_system_metrics(self) -> Dict:
        """收集系统指标

        Returns:
            Dict: 系统指标
        """
        process = psutil.Process()

        return {
            "memory_usage": process.memory_info().rss,
            "cpu_usage": process.cpu_percent(),
            "open_files": len(process.open_files()),
            "threads": process.num_threads(),
            "connections": len(process.connections()),
        }

    def _generate_monitoring_report(self):
        """生成监控报告"""
        try:
            # 获取各类型指标摘要
            summaries = {
                data_type: self.get_metrics_summary(data_type)
                for data_type in self.metrics_history.keys()
            }

            # 获取告警摘要
            alerts = self.get_alerts_summary()

            # 获取错误摘要
            errors = self.get_error_summary()

            # 生成报告
            report = {
                "timestamp": datetime.now(),
                "metrics_summaries": summaries,
                "alerts": alerts,
                "errors": errors,
                "system_status": self._collect_system_metrics(),
            }

            # 缓存报告
            self.cache.set(
                f"monitoring_report_{datetime.now().timestamp()}",
                report,
                ttl=self.metrics_ttl,
            )

            # 记录日志
            self.logger.info("Generated monitoring report")

            # 如果有严重问题，记录警告
            if alerts or errors:
                self.logger.warning(
                    f"Found {len(alerts)} alerts and {len(errors)} errors"
                )
        except Exception as e:
            self.logger.error(f"Failed to generate monitoring report: {str(e)}")
