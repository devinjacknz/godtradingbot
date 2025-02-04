import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional, Union

import numpy as np
import pandas as pd

from src.backend.data_infrastructure.data_processor import DataProcessor
from src.backend.data_infrastructure.feature_engineering import FeatureEngineer
from src.shared.cache.hybrid_cache import HybridCache


class DataPipeline:
    """实时数据处理流水线"""

    def __init__(self, config: Dict):
        self.config = config
        self.cache = HybridCache()

        # 初始化处理器
        self.data_processor = DataProcessor(config)
        self.feature_engineer = FeatureEngineer(config)

        # 配置参数
        self.batch_size = config.get("batch_size", 1000)
        self.max_workers = config.get("max_workers", 4)
        self.buffer_size = config.get("buffer_size", 10000)
        self.cache_ttl = config.get("cache_ttl", 3600)  # 缓存过期时间（秒）
        self.compression = config.get("compression", "gzip")  # 数据压缩方式

        # 性能优化参数
        self.use_parallel = config.get("use_parallel", True)  # 是否使用并行处理
        self.chunk_size = config.get("chunk_size", 1000)  # 数据分块大小
        self.prefetch_size = config.get("prefetch_size", 2)  # 预加载批次数

        # 初始化缓冲区
        self._init_buffers()

        # 初始化线程池
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)

        # 设置日志
        self._setup_logging()

        # 初始化性能监控
        self._init_monitoring()

    def _init_buffers(self):
        """初始化数据缓冲区"""
        self.market_buffer = []
        self.trading_buffer = []
        self.social_buffer = []

        self.processed_market_data = pd.DataFrame()
        self.processed_trading_data = pd.DataFrame()
        self.processed_social_data = pd.DataFrame()

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

    def _init_monitoring(self):
        """初始化性能监控"""
        self.processing_times = {"market": [], "trading": [], "social": []}
        self.memory_usage = []
        self.cpu_usage = []
        self.batch_sizes = []
        self.queue_sizes = []

    async def _process_in_parallel(
        self, df: pd.DataFrame, process_func: Callable, n_chunks: int = None
    ) -> pd.DataFrame:
        """并行处理数据

        Args:
            df: 输入数据框
            process_func: 处理函数
            n_chunks: 分块数量

        Returns:
            pd.DataFrame: 处理后的数据框
        """
        if not self.use_parallel or len(df) < self.chunk_size:
            return process_func(df)

        # 确定分块数量
        if n_chunks is None:
            n_chunks = min(self.max_workers, len(df) // self.chunk_size + 1)

        # 数据分块
        chunks = np.array_split(df, n_chunks)

        # 并行处理
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(self.executor, process_func, chunk) for chunk in chunks
        ]
        results = await asyncio.gather(*tasks)

        # 合并结果
        return pd.concat(results)

    def _compress_data(self, data: pd.DataFrame) -> bytes:
        """压缩数据

        Args:
            data: 输入数据框

        Returns:
            bytes: 压缩后的数据
        """
        return data.to_parquet(compression=self.compression)

    def _decompress_data(self, data: bytes) -> pd.DataFrame:
        """解压数据

        Args:
            data: 压缩的数据

        Returns:
            pd.DataFrame: 解压后的数据框
        """
        return pd.read_parquet(data)

    async def process_market_data(
        self, data: Dict, callback: Optional[Callable] = None
    ):
        """处理市场数据"""
        try:
            start_time = datetime.now()

            # 添加到缓冲区
            self.market_buffer.append(data)
            self.queue_sizes.append(len(self.market_buffer))

            # 检查是否需要处理
            if len(self.market_buffer) >= self.batch_size:
                # 创建数据框
                df = pd.DataFrame(self.market_buffer)
                self.batch_sizes.append(len(df))

                # 并行处理
                processed_df = await self._process_in_parallel(
                    df, self._process_market_batch
                )

                # 压缩数据
                compressed_data = self._compress_data(processed_df)

                # 更新处理后的数据
                self.processed_market_data = pd.concat(
                    [self.processed_market_data, processed_df]
                ).tail(self.buffer_size)

                # 缓存结果
                key = f"market_batch_{datetime.now().timestamp()}"
                self.cache.set(key, compressed_data, ttl=self.cache_ttl)

                # 清空缓冲区
                self.market_buffer = []

                # 记录处理时间
                processing_time = (datetime.now() - start_time).total_seconds()
                self.processing_times["market"].append(processing_time)

                # 记录资源使用
                self._update_resource_usage()

                # 调用回调函数
                if callback:
                    await callback(processed_df)

        except Exception as e:
            self.logger.error(f"Failed to process market data: {str(e)}")

    async def process_trading_data(
        self, data: Dict, callback: Optional[Callable] = None
    ):
        """处理交易数据

        Args:
            data: 交易数据
            callback: 处理完成后的回调函数
        """
        try:
            # 添加到缓冲区
            self.trading_buffer.append(data)

            # 检查是否需要处理
            if len(self.trading_buffer) >= self.batch_size:
                # 创建数据框
                df = pd.DataFrame(self.trading_buffer)

                # 异步处理
                loop = asyncio.get_event_loop()
                processed_df = await loop.run_in_executor(
                    self.executor, self._process_trading_batch, df
                )

                # 更新处理后的数据
                self.processed_trading_data = pd.concat(
                    [self.processed_trading_data, processed_df]
                ).tail(self.buffer_size)

                # 清空缓冲区
                self.trading_buffer = []

                # 调用回调函数
                if callback:
                    await callback(processed_df)

        except Exception as e:
            self.logger.error(f"Failed to process trading data: {str(e)}")

    async def process_social_data(
        self, data: Dict, callback: Optional[Callable] = None
    ):
        """处理社交媒体数据

        Args:
            data: 社交媒体数据
            callback: 处理完成后的回调函数
        """
        try:
            # 添加到缓冲区
            self.social_buffer.append(data)

            # 检查是否需要处理
            if len(self.social_buffer) >= self.batch_size:
                # 创建数据框
                df = pd.DataFrame(self.social_buffer)

                # 异步处理
                loop = asyncio.get_event_loop()
                processed_df = await loop.run_in_executor(
                    self.executor, self._process_social_batch, df
                )

                # 更新处理后的数据
                self.processed_social_data = pd.concat(
                    [self.processed_social_data, processed_df]
                ).tail(self.buffer_size)

                # 清空缓冲区
                self.social_buffer = []

                # 调用回调函数
                if callback:
                    await callback(processed_df)

        except Exception as e:
            self.logger.error(f"Failed to process social data: {str(e)}")

    def _process_market_batch(self, df: pd.DataFrame) -> pd.DataFrame:
        """处理一批市场数据"""
        # 数据清洗和预处理
        df = self.data_processor.process_market_data(df)

        # 特征工程
        df = self.feature_engineer.generate_market_features(df)

        # 缓存结果
        key = f"market_batch_{datetime.now().timestamp()}"
        self.cache.set(key, df.to_dict())

        return df

    def _process_trading_batch(self, df: pd.DataFrame) -> pd.DataFrame:
        """处理一批交易数据"""
        # 数据清洗和预处理
        df = self.data_processor.process_trading_data(df)

        # 特征工程
        df = self.feature_engineer.generate_trading_features(
            df, self.processed_market_data
        )

        # 缓存结果
        key = f"trading_batch_{datetime.now().timestamp()}"
        self.cache.set(key, df.to_dict())

        return df

    def _process_social_batch(self, df: pd.DataFrame) -> pd.DataFrame:
        """处理一批社交媒体数据"""
        # 数据清洗和预处理
        df = self.data_processor.process_social_data(df)

        # 特征工程
        df = self.feature_engineer.generate_social_features(
            df, self.processed_market_data
        )

        # 缓存结果
        key = f"social_batch_{datetime.now().timestamp()}"
        self.cache.set(key, df.to_dict())

        return df

    async def get_latest_data(
        self, data_type: str, n_records: int = 100
    ) -> pd.DataFrame:
        """获取最新处理后的数据

        Args:
            data_type: 数据类型 ('market', 'trading', 'social')
            n_records: 返回的记录数

        Returns:
            pd.DataFrame: 最新的数据
        """
        try:
            if data_type == "market":
                return self.processed_market_data.tail(n_records)
            elif data_type == "trading":
                return self.processed_trading_data.tail(n_records)
            elif data_type == "social":
                return self.processed_social_data.tail(n_records)
            else:
                raise ValueError(f"Invalid data type: {data_type}")

        except Exception as e:
            self.logger.error(f"Failed to get latest data: {str(e)}")
            return pd.DataFrame()

    def get_buffer_status(self) -> Dict:
        """获取缓冲区状态

        Returns:
            Dict: 缓冲区状态信息
        """
        return {
            "market_buffer_size": len(self.market_buffer),
            "trading_buffer_size": len(self.trading_buffer),
            "social_buffer_size": len(self.social_buffer),
            "processed_market_size": len(self.processed_market_data),
            "processed_trading_size": len(self.processed_trading_data),
            "processed_social_size": len(self.processed_social_data),
        }

    async def clear_buffers(self):
        """清空所有缓冲区"""
        self.market_buffer = []
        self.trading_buffer = []
        self.social_buffer = []

        self.processed_market_data = pd.DataFrame()
        self.processed_trading_data = pd.DataFrame()
        self.processed_social_data = pd.DataFrame()

        self.logger.info("All buffers cleared")

    def get_processing_stats(self) -> Dict:
        """获取处理统计信息

        Returns:
            Dict: 处理统计信息
        """
        stats = {
            "market_processing_time": [],
            "trading_processing_time": [],
            "social_processing_time": [],
        }

        # 从缓存中获取统计信息
        for key in self.cache.keys():
            if key.startswith("stats_"):
                stats.update(self.cache.get(key))

        return stats

    async def start_monitoring(self, interval: int = 60):
        """启动监控

        Args:
            interval: 监控间隔（秒）
        """
        while True:
            try:
                # 获取状态
                status = self.get_buffer_status()
                stats = self.get_processing_stats()

                # 记录状态
                self.logger.info(f"Buffer status: {status}")
                self.logger.info(f"Processing stats: {stats}")

                # 检查内存使用
                if (
                    status["processed_market_size"] > self.buffer_size
                    or status["processed_trading_size"] > self.buffer_size
                    or status["processed_social_size"] > self.buffer_size
                ):
                    self.logger.warning("Buffer size exceeded limit")

                # 等待下一次监控
                await asyncio.sleep(interval)

            except Exception as e:
                self.logger.error(f"Monitoring error: {str(e)}")
                await asyncio.sleep(interval)

    def _update_resource_usage(self):
        """更新资源使用统计"""
        import psutil

        # 记录内存使用
        process = psutil.Process()
        self.memory_usage.append(process.memory_info().rss)

        # 记录CPU使用
        self.cpu_usage.append(process.cpu_percent())

    def get_performance_metrics(self) -> Dict:
        """获取性能指标

        Returns:
            Dict: 性能指标统计
        """
        metrics = {
            "processing_times": {
                data_type: {
                    "mean": np.mean(times) if times else 0,
                    "std": np.std(times) if times else 0,
                    "min": np.min(times) if times else 0,
                    "max": np.max(times) if times else 0,
                }
                for data_type, times in self.processing_times.items()
            },
            "memory_usage": {
                "current": self.memory_usage[-1] if self.memory_usage else 0,
                "mean": np.mean(self.memory_usage) if self.memory_usage else 0,
                "max": np.max(self.memory_usage) if self.memory_usage else 0,
            },
            "cpu_usage": {
                "current": self.cpu_usage[-1] if self.cpu_usage else 0,
                "mean": np.mean(self.cpu_usage) if self.cpu_usage else 0,
                "max": np.max(self.cpu_usage) if self.cpu_usage else 0,
            },
            "batch_stats": {
                "mean_size": np.mean(self.batch_sizes) if self.batch_sizes else 0,
                "mean_queue": np.mean(self.queue_sizes) if self.queue_sizes else 0,
            },
        }

        return metrics

    async def optimize_performance(self):
        """动态优化性能参数"""
        while True:
            try:
                metrics = self.get_performance_metrics()

                # 优化批处理大小
                mean_processing_time = metrics["processing_times"]["market"]["mean"]
                if mean_processing_time > 1.0:  # 如果平均处理时间超过1秒
                    self.batch_size = max(100, self.batch_size // 2)
                elif mean_processing_time < 0.1:  # 如果平均处理时间小于0.1秒
                    self.batch_size = min(10000, self.batch_size * 2)

                # 优化工作线程数
                cpu_usage = metrics["cpu_usage"]["current"]
                if cpu_usage > 80:  # 如果CPU使用率过高
                    self.max_workers = max(2, self.max_workers - 1)
                elif cpu_usage < 50:  # 如果CPU使用率较低
                    self.max_workers = min(8, self.max_workers + 1)

                # 优化缓存策略
                memory_usage = metrics["memory_usage"]["current"]
                if memory_usage > 1e9:  # 如果内存使用超过1GB
                    self.cache_ttl = max(300, self.cache_ttl // 2)

                await asyncio.sleep(60)  # 每分钟优化一次

            except Exception as e:
                self.logger.error(f"Failed to optimize performance: {str(e)}")
                await asyncio.sleep(60)
