import logging
from typing import Dict

import psutil
from prometheus_client import CollectorRegistry, Gauge

__all__ = ["MemoryMetrics", "track_memory_usage", "track_gpu_memory"]


def track_memory_usage():
    metrics = MemoryMetrics()
    metrics.track_memory_usage()


def track_gpu_memory():
    metrics = MemoryMetrics()
    metrics.track_gpu_memory()


class MemoryMetrics:
    def __init__(self, warning_threshold=75, critical_threshold=90, registry=None):
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.registry = registry or CollectorRegistry()
        self.memory_gauge = Gauge(
            "system_memory_usage_percent",
            "System memory usage percentage",
            registry=self.registry,
        )
        self.gpu_memory_gauge = Gauge(
            "gpu_memory_usage_percent",
            "GPU memory usage percentage",
            registry=self.registry,
        )

    def get_memory_usage(self) -> float:
        try:
            return psutil.virtual_memory().percent
        except Exception as e:
            logging.error(f"Error getting memory usage: {str(e)}")
            return 0.0

    def get_memory_info(self) -> dict:
        try:
            mem = psutil.virtual_memory()
            return {
                "total": mem.total,
                "used": mem.used,
                "free": mem.available,
                "percent": mem.percent,
            }
        except Exception as e:
            logging.error(f"Error getting memory info: {str(e)}")
            return {"total": 0, "used": 0, "free": 0, "percent": 0}

    def check_memory_warning(self) -> bool:
        usage = self.get_memory_usage()
        if usage > self.warning_threshold:
            logging.warning(
                f"Memory usage {usage}% above warning threshold {self.warning_threshold}%"
            )
            return True
        return False

    def check_memory_critical(self) -> bool:
        usage = self.get_memory_usage()
        if usage > self.critical_threshold:
            logging.error(
                f"Memory usage {usage}% above critical threshold {self.critical_threshold}%"
            )
            return True
        return False

    def get_process_memory(self) -> dict:
        try:
            process = psutil.Process()
            return {"rss": process.memory_info().rss, "vms": process.memory_info().vms}
        except Exception as e:
            logging.error(f"Error getting process memory: {str(e)}")
            return {"rss": 0, "vms": 0}

    def track_memory_usage(self):
        usage = self.get_memory_usage()
        self.memory_gauge.set(usage)
        self.check_memory_warning()
        self.check_memory_critical()

    def track_gpu_memory(self):
        try:
            import nvidia_ml_py as nvml

            nvml.nvmlInit()
            handle = nvml.nvmlDeviceGetHandleByIndex(0)
            info = nvml.nvmlDeviceGetMemoryInfo(handle)
            usage = (info.used / info.total) * 100
            self.gpu_memory_gauge.set(usage)
            if usage > self.warning_threshold:
                logging.warning(
                    f"GPU memory usage {usage:.1f}% above warning threshold"
                )
        except Exception as e:
            logging.error(f"Error tracking GPU memory: {str(e)}")
            self.gpu_memory_gauge.set(0)
