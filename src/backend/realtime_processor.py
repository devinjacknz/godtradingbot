import json
import logging
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from queue import Queue
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd


@dataclass
class DataEvent:
    """数据事件基类"""

    timestamp: datetime
    symbol: str
    data: Dict[str, Any]
    event_type: str


class DataProcessor(ABC):
    """数据处理器接口"""

    @abstractmethod
    def process(self, event: DataEvent) -> Optional[Dict[str, Any]]:
        """处理数据事件"""
        pass


class FeatureComputer(ABC):
    """特征计算器接口"""

    @abstractmethod
    def compute(self, data: pd.DataFrame) -> Dict[str, Any]:
        """计算特征"""
        pass


class RealtimeProcessor:
    """实时数据处理核心类"""

    def __init__(
        self,
        symbols: List[str],
        window_size: int = 1000,
        update_interval: float = 1.0,
        feature_calculators: Optional[List[FeatureComputer]] = None,
        data_processors: Optional[List[DataProcessor]] = None,
        output_dir: str = "data/realtime",
    ):
        """
        初始化实时数据处理器

        Args:
            symbols: 交易品种列表
            window_size: 数据窗口大小
            update_interval: 更新间隔(秒)
            feature_calculators: 特征计算器列表
            data_processors: 数据处理器列表
            output_dir: 输出目录
        """
        self.symbols = symbols
        self.window_size = window_size
        self.update_interval = update_interval
        self.feature_calculators = feature_calculators or []
        self.data_processors = data_processors or []
        self.output_dir = Path(output_dir)
        self.logger = logging.getLogger(__name__)

        # 创建输出目录
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 初始化数据结构
        self._init_data_structures()

        # 初始化线程和队列
        self._init_threading()

        # 状态标志
        self.running = False

    def _init_data_structures(self):
        """初始化数据结构"""
        # 原始数据缓存
        self.raw_data = {
            symbol: deque(maxlen=self.window_size) for symbol in self.symbols
        }

        # 处理后的数据缓存
        self.processed_data = {symbol: pd.DataFrame() for symbol in self.symbols}

        # 特征数据缓存
        self.feature_data = {symbol: {} for symbol in self.symbols}

        # 统计信息
        self.stats = {
            "total_events": 0,
            "processed_events": 0,
            "error_events": 0,
            "last_update": None,
        }

    def _init_threading(self):
        """初始化线程和队列"""
        # 数据队列
        self.event_queue = Queue()

        # 处理线程
        self.processing_thread = threading.Thread(
            target=self._processing_loop, daemon=True
        )

        # 特征计算线程
        self.feature_thread = threading.Thread(target=self._feature_loop, daemon=True)

    def start(self):
        """启动处理器"""
        if self.running:
            self.logger.warning("处理器已经在运行")
            return

        self.running = True
        self.processing_thread.start()
        self.feature_thread.start()
        self.logger.info("实时数据处理器已启动")

    def stop(self):
        """停止处理器"""
        self.running = False
        self.processing_thread.join()
        self.feature_thread.join()
        self.logger.info("实时数据处理器已停止")

    def push_event(self, event: DataEvent):
        """推送数据事件"""
        try:
            self.stats["total_events"] += 1
            self.event_queue.put(event)
        except Exception as e:
            self.logger.error(f"推送事件失败: {str(e)}")
            self.stats["error_events"] += 1

    def get_latest_data(self, symbol: str, n_samples: int = 100) -> pd.DataFrame:
        """获取最新数据"""
        try:
            return self.processed_data[symbol].tail(n_samples)
        except KeyError:
            self.logger.error(f"未找到symbol: {symbol}的数据")
            return pd.DataFrame()

    def get_latest_features(self, symbol: str) -> Dict[str, Any]:
        """获取最新特征"""
        try:
            return self.feature_data[symbol]
        except KeyError:
            self.logger.error(f"未找到symbol: {symbol}的特征")
            return {}

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "queue_size": self.event_queue.qsize(),
            "memory_usage": {
                symbol: len(data) for symbol, data in self.raw_data.items()
            },
        }

    def _processing_loop(self):
        """数据处理循环"""
        while self.running:
            try:
                # 获取事件
                event = self.event_queue.get(timeout=1.0)

                # 处理事件
                processed_data = self._process_event(event)

                if processed_data:
                    # 更新原始数据
                    self.raw_data[event.symbol].append(event.data)

                    # 更新处理后的数据
                    self._update_processed_data(event.symbol, processed_data)

                    self.stats["processed_events"] += 1
                    self.stats["last_update"] = datetime.now()

            except Exception as e:
                if not isinstance(e, TimeoutError):
                    self.logger.error(f"处理事件失败: {str(e)}")
                    self.stats["error_events"] += 1

    def _feature_loop(self):
        """特征计算循环"""
        while self.running:
            try:
                # 定期计算特征
                for symbol in self.symbols:
                    if len(self.raw_data[symbol]) > 0:
                        # 转换为DataFrame
                        df = pd.DataFrame(list(self.raw_data[symbol]))

                        # 计算特征
                        features = self._compute_features(df)

                        # 更新特征数据
                        self.feature_data[symbol] = features

                # 等待下一次更新
                time.sleep(self.update_interval)

            except Exception as e:
                self.logger.error(f"计算特征失败: {str(e)}")
                time.sleep(1.0)  # 错误后等待

    def _process_event(self, event: DataEvent) -> Optional[Dict[str, Any]]:
        """处理单个事件"""
        try:
            data = event.data

            # 应用所有处理器
            for processor in self.data_processors:
                result = processor.process(event)
                if result:
                    data.update(result)

            return data

        except Exception as e:
            self.logger.error(f"处理事件失败: {str(e)}")
            return None

    def _compute_features(self, data: pd.DataFrame) -> Dict[str, Any]:
        """计算特征"""
        features = {}

        try:
            # 应用所有特征计算器
            for calculator in self.feature_calculators:
                result = calculator.compute(data)
                if result:
                    features.update(result)

            return features

        except Exception as e:
            self.logger.error(f"计算特征失败: {str(e)}")
            return features

    def _update_processed_data(self, symbol: str, data: Dict[str, Any]):
        """更新处理后的数据"""
        try:
            # 转换为DataFrame
            df = pd.DataFrame([data])

            # 更新数据
            self.processed_data[symbol] = pd.concat(
                [self.processed_data[symbol], df], ignore_index=True
            ).tail(self.window_size)

        except Exception as e:
            self.logger.error(f"更新处理后的数据失败: {str(e)}")

    def save_snapshot(self):
        """保存数据快照"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # 保存处理后的数据
            for symbol in self.symbols:
                if not self.processed_data[symbol].empty:
                    file_path = self.output_dir / f"{symbol}_data_{timestamp}.parquet"
                    self.processed_data[symbol].to_parquet(file_path)

            # 保存特征数据
            feature_path = self.output_dir / f"features_{timestamp}.json"
            with open(feature_path, "w") as f:
                json.dump(self.feature_data, f)

            # 保存统计信息
            stats_path = self.output_dir / f"stats_{timestamp}.json"
            with open(stats_path, "w") as f:
                json.dump(self.get_stats(), f)

            self.logger.info(f"数据快照已保存: {timestamp}")

        except Exception as e:
            self.logger.error(f"保存数据快照失败: {str(e)}")
