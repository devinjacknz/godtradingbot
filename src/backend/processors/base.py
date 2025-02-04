import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd


class BaseProcessor(ABC):
    """数据处理器基类"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.metrics = {
            "processed_count": 0,
            "error_count": 0,
            "last_process_time": None,
            "average_process_time": 0,
        }

    @abstractmethod
    def process(self, data: pd.DataFrame) -> pd.DataFrame:
        """处理数据

        Args:
            data: 输入数据

        Returns:
            pd.DataFrame: 处理后的数据
        """
        pass

    def update_metrics(self, start_time: datetime, success: bool):
        """更新处理指标"""
        process_time = (datetime.now() - start_time).total_seconds()

        self.metrics["processed_count"] += 1
        if not success:
            self.metrics["error_count"] += 1

        self.metrics["last_process_time"] = process_time
        self.metrics["average_process_time"] = (
            self.metrics["average_process_time"] * (self.metrics["processed_count"] - 1)
            + process_time
        ) / self.metrics["processed_count"]

    def get_metrics(self) -> Dict[str, Any]:
        """获取处理指标"""
        return self.metrics.copy()


class BaseFeatureComputer(ABC):
    """特征计算器基类"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.metrics = {
            "computed_count": 0,
            "error_count": 0,
            "last_compute_time": None,
            "average_compute_time": 0,
            "feature_count": 0,
        }

    @abstractmethod
    def compute(self, data: pd.DataFrame) -> Dict[str, Any]:
        """计算特征

        Args:
            data: 输入数据

        Returns:
            Dict[str, Any]: 计算的特征
        """
        pass

    def update_metrics(self, start_time: datetime, feature_count: int, success: bool):
        """更新计算指标"""
        compute_time = (datetime.now() - start_time).total_seconds()

        self.metrics["computed_count"] += 1
        if not success:
            self.metrics["error_count"] += 1

        self.metrics["last_compute_time"] = compute_time
        self.metrics["average_compute_time"] = (
            self.metrics["average_compute_time"] * (self.metrics["computed_count"] - 1)
            + compute_time
        ) / self.metrics["computed_count"]
        self.metrics["feature_count"] = feature_count

    def get_metrics(self) -> Dict[str, Any]:
        """获取计算指标"""
        return self.metrics.copy()
