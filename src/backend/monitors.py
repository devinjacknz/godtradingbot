import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import psutil


class BaseMonitor(ABC):
    """监控器基类"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.metrics: Dict[str, Any] = {}
        self.alerts: List[Dict[str, Any]] = []
        self.alert_thresholds = config.get("alert_thresholds", {})

    @abstractmethod
    def collect_metrics(self) -> Dict[str, Any]:
        """收集指标"""
        pass

    def check_alerts(self) -> List[Dict[str, Any]]:
        """检查告警"""
        return self.alerts

    def clear_alerts(self):
        """清除告警"""
        self.alerts = []

    def add_alert(self, alert_type: str, message: str, severity: str = "warning"):
        """添加告警"""
        self.alerts.append(
            {
                "type": alert_type,
                "message": message,
                "severity": severity,
                "timestamp": datetime.now().isoformat(),
            }
        )


class DataQualityMonitor(BaseMonitor):
    """数据质量监控器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.required_columns = config.get("required_columns", [])
        self.numeric_columns = config.get("numeric_columns", [])
        self.categorical_columns = config.get("categorical_columns", [])
        self.datetime_columns = config.get("datetime_columns", [])
        self.missing_threshold = config.get("missing_threshold", 0.1)
        self.outlier_threshold = config.get("outlier_threshold", 3)

    def collect_metrics(self, data: pd.DataFrame) -> Dict[str, Any]:
        """收集数据质量指标"""
        try:
            metrics = {}

            # 检查必需列
            missing_cols = set(self.required_columns) - set(data.columns)
            if missing_cols:
                self.add_alert(
                    "missing_columns",
                    f"Missing required columns: {missing_cols}",
                    "error",
                )

            # 计算缺失值比例
            missing_ratios = data.isnull().mean()
            metrics["missing_ratios"] = missing_ratios.to_dict()

            for col, ratio in missing_ratios.items():
                if ratio > self.missing_threshold:
                    self.add_alert(
                        "high_missing_ratio",
                        f"Column {col} has {ratio:.2%} missing values",
                        "warning",
                    )

            # 检查数值列
            for col in self.numeric_columns:
                if col not in data.columns:
                    continue

                # 检查异常值
                z_scores = np.abs((data[col] - data[col].mean()) / data[col].std())
                outlier_ratio = (z_scores > self.outlier_threshold).mean()
                metrics[f"{col}_outlier_ratio"] = outlier_ratio

                if outlier_ratio > 0.01:  # 超过1%的数据点是异常值
                    self.add_alert(
                        "high_outlier_ratio",
                        f"Column {col} has {outlier_ratio:.2%} outliers",
                        "warning",
                    )

                # 检查数值范围
                metrics[f"{col}_stats"] = {
                    "min": data[col].min(),
                    "max": data[col].max(),
                    "mean": data[col].mean(),
                    "std": data[col].std(),
                }

            # 检查分类列
            for col in self.categorical_columns:
                if col not in data.columns:
                    continue

                # 检查唯一值数量
                unique_count = data[col].nunique()
                metrics[f"{col}_unique_count"] = unique_count

                # 检查类别分布
                value_counts = data[col].value_counts(normalize=True)
                metrics[f"{col}_distribution"] = value_counts.to_dict()

                # 检查是否有新类别出现
                if "known_categories" in self.config:
                    new_categories = set(data[col].unique()) - set(
                        self.config["known_categories"]
                    )
                    if new_categories:
                        self.add_alert(
                            "new_categories",
                            f"New categories found in {col}: {new_categories}",
                            "info",
                        )

            # 检查时间列
            for col in self.datetime_columns:
                if col not in data.columns:
                    continue

                # 检查时间范围
                metrics[f"{col}_range"] = {
                    "start": data[col].min().isoformat(),
                    "end": data[col].max().isoformat(),
                }

                # 检查时间间隔
                time_diff = data[col].diff()
                metrics[f"{col}_interval"] = {
                    "mean": time_diff.mean().total_seconds(),
                    "std": time_diff.std().total_seconds(),
                }

            self.metrics = metrics
            return metrics

        except Exception as e:
            self.logger.error(f"数据质量监控失败: {str(e)}")
            raise


class PerformanceMonitor(BaseMonitor):
    """性能指标监控器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.latency_threshold = config.get("latency_threshold", 1.0)  # 秒
        self.error_rate_threshold = config.get("error_rate_threshold", 0.01)
        self.throughput_threshold = config.get("throughput_threshold", 100)  # 每秒处理数
        self.window_size = config.get("window_size", 3600)  # 1小时
        self.metrics_history: List[Dict[str, Any]] = []

    def collect_metrics(self) -> Dict[str, Any]:
        """收集性能指标"""
        try:
            current_time = datetime.now()
            metrics = {
                "timestamp": current_time.isoformat(),
                "latency": {},
                "throughput": {},
                "error_rate": {},
                "queue_size": {},
            }

            # 清理历史数据
            self.metrics_history = [
                m
                for m in self.metrics_history
                if (
                    current_time - datetime.fromisoformat(m["timestamp"])
                ).total_seconds()
                <= self.window_size
            ]

            # 计算延迟统计
            if hasattr(self, "last_process_time"):
                latency = (current_time - self.last_process_time).total_seconds()
                metrics["latency"] = {
                    "current": latency,
                    "avg": np.mean(
                        [m["latency"].get("current", 0) for m in self.metrics_history]
                    ),
                    "max": max(
                        [m["latency"].get("current", 0) for m in self.metrics_history]
                        + [latency]
                    ),
                }

                if latency > self.latency_threshold:
                    self.add_alert(
                        "high_latency",
                        f"Processing latency ({latency:.2f}s) exceeds threshold",
                        "warning",
                    )

            # 计算吞吐量
            if len(self.metrics_history) > 1:
                time_diff = (
                    current_time
                    - datetime.fromisoformat(self.metrics_history[0]["timestamp"])
                ).total_seconds()
                throughput = (
                    len(self.metrics_history) / time_diff if time_diff > 0 else 0
                )
                metrics["throughput"] = {
                    "current": throughput,
                    "avg": np.mean(
                        [
                            m["throughput"].get("current", 0)
                            for m in self.metrics_history
                        ]
                    ),
                    "max": max(
                        [
                            m["throughput"].get("current", 0)
                            for m in self.metrics_history
                        ]
                        + [throughput]
                    ),
                }

                if throughput < self.throughput_threshold:
                    self.add_alert(
                        "low_throughput",
                        f"Processing throughput ({throughput:.2f}/s) below threshold",
                        "warning",
                    )

            # 计算错误率
            if hasattr(self, "error_count") and hasattr(self, "total_count"):
                error_rate = (
                    self.error_count / self.total_count if self.total_count > 0 else 0
                )
                metrics["error_rate"] = {
                    "current": error_rate,
                    "total_errors": self.error_count,
                    "total_processed": self.total_count,
                }

                if error_rate > self.error_rate_threshold:
                    self.add_alert(
                        "high_error_rate",
                        f"Error rate ({error_rate:.2%}) exceeds threshold",
                        "error",
                    )

            self.metrics_history.append(metrics)
            self.metrics = metrics
            return metrics

        except Exception as e:
            self.logger.error(f"性能指标监控失败: {str(e)}")
            raise

    def update_counters(self, success: bool = True):
        """更新计数器"""
        if not hasattr(self, "total_count"):
            self.total_count = 0
        if not hasattr(self, "error_count"):
            self.error_count = 0

        self.total_count += 1
        if not success:
            self.error_count += 1

        self.last_process_time = datetime.now()


class ResourceMonitor(BaseMonitor):
    """资源使用监控器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.cpu_threshold = config.get("cpu_threshold", 80)  # CPU使用率阈值
        self.memory_threshold = config.get("memory_threshold", 80)  # 内存使用率阈值
        self.disk_threshold = config.get("disk_threshold", 80)  # 磁盘使用率阈值

    def collect_metrics(self) -> Dict[str, Any]:
        """收集资源使用指标"""
        try:
            metrics = {
                "timestamp": datetime.now().isoformat(),
                "cpu": {},
                "memory": {},
                "disk": {},
                "network": {},
            }

            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            metrics["cpu"] = {
                "total_percent": cpu_percent,
                "per_cpu_percent": psutil.cpu_percent(interval=1, percpu=True),
            }

            if cpu_percent > self.cpu_threshold:
                self.add_alert(
                    "high_cpu_usage",
                    f"CPU usage ({cpu_percent}%) exceeds threshold",
                    "warning",
                )

            # 内存使用
            memory = psutil.virtual_memory()
            metrics["memory"] = {
                "total": memory.total,
                "available": memory.available,
                "percent": memory.percent,
                "used": memory.used,
                "free": memory.free,
            }

            if memory.percent > self.memory_threshold:
                self.add_alert(
                    "high_memory_usage",
                    f"Memory usage ({memory.percent}%) exceeds threshold",
                    "warning",
                )

            # 磁盘使用
            disk = psutil.disk_usage("/")
            metrics["disk"] = {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": disk.percent,
            }

            if disk.percent > self.disk_threshold:
                self.add_alert(
                    "high_disk_usage",
                    f"Disk usage ({disk.percent}%) exceeds threshold",
                    "warning",
                )

            # 网络IO
            network = psutil.net_io_counters()
            metrics["network"] = {
                "bytes_sent": network.bytes_sent,
                "bytes_recv": network.bytes_recv,
                "packets_sent": network.packets_sent,
                "packets_recv": network.packets_recv,
                "errin": network.errin,
                "errout": network.errout,
                "dropin": network.dropin,
                "dropout": network.dropout,
            }

            self.metrics = metrics
            return metrics

        except Exception as e:
            self.logger.error(f"资源使用监控失败: {str(e)}")
            raise
