import asyncio
import time
import zlib
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import aiohttp
import motor.motor_asyncio
import msgpack
import numpy as np
import pandas as pd
import redis
from prometheus_client import Counter, Gauge, Histogram
from pymongo import ASCENDING, DESCENDING

from src.shared.cache.hybrid_cache import HybridCache
from src.shared.utils.rate_limiter import RateLimiter


class DataPriority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DataMetrics:
    """数据指标"""

    throughput: Gauge
    latency: Histogram
    cache_hits: Counter
    cache_misses: Counter
    compression_ratio: Gauge
    storage_usage: Gauge
    query_count: Counter


class DataManager:
    """数据管理器，负责数据的收集、存储和访问"""

    def __init__(self, config: Dict):
        self.config = config
        self.cache = redis.Redis(**config.get("redis_config", {}))
        self.data_buffer = defaultdict(list)
        self.compression_stats = {}

        # 数据指标
        self.metrics = DataMetrics(
            throughput=Gauge("data_throughput", "Data throughput in bytes/sec"),
            latency=Histogram("data_latency", "Data operation latency"),
            cache_hits=Counter("data_cache_hits", "Cache hit count"),
            cache_misses=Counter("data_cache_misses", "Cache miss count"),
            compression_ratio=Gauge("data_compression_ratio", "Data compression ratio"),
            storage_usage=Gauge("data_storage_usage", "Storage usage in bytes"),
            query_count=Counter("data_query_count", "Number of queries executed"),
        )

        # 数据配置
        self.data_config = {
            "cache_ttl": config.get("cache_ttl", 3600),
            "buffer_size": config.get("buffer_size", 1000),
            "compression_threshold": config.get("compression_threshold", 1024),
            "batch_size": config.get("batch_size", 100),
            "max_workers": config.get("max_workers", 4),
        }

        # 初始化线程池
        self.executor = ThreadPoolExecutor(max_workers=self.data_config["max_workers"])

        # 初始化管理任务
        self.manager_task = None

        # 初始化数据库连接
        self._init_database()
        self._init_cache()

        # 数据收集配置
        self.collection_interval = config.get("collection_interval", 60)  # 秒
        self.retention_period = config.get("retention_period", 90)  # 天
        self.batch_size = config.get("batch_size", 1000)

        # 启动后台任务
        self._start_background_tasks()

    def _init_database(self):
        """初始化数据库连接"""
        # MongoDB连接
        mongo_client = motor.motor_asyncio.AsyncIOMotorClient(
            self.config["mongodb_uri"]
        )
        self.db = mongo_client[self.config["database_name"]]

        # 创建索引
        asyncio.create_task(self._create_indexes())

        # Redis连接
        self.redis_client = redis.Redis(
            host=self.config["redis_host"],
            port=self.config["redis_port"],
            password=self.config.get("redis_password"),
            decode_responses=True,
        )

    def _init_cache(self):
        """初始化缓存配置"""
        self.cache.configure(
            memory_size=self.config.get("memory_cache_size", 1000),
            disk_size=self.config.get("disk_cache_size", 10000),
            ttl=self.config.get("cache_ttl", 3600),
        )

    async def _create_indexes(self):
        """创建数据库索引"""
        # 市场数据索引
        await self.db.market_data.create_index(
            [("symbol", ASCENDING), ("timestamp", DESCENDING)]
        )
        await self.db.market_data.create_index(
            [("data_type", ASCENDING), ("timestamp", DESCENDING)]
        )

        # 交易数据索引
        await self.db.trades.create_index(
            [("symbol", ASCENDING), ("timestamp", DESCENDING)]
        )

        # 社交媒体数据索引
        await self.db.social_data.create_index(
            [("symbol", ASCENDING), ("platform", ASCENDING), ("timestamp", DESCENDING)]
        )

    def _start_background_tasks(self):
        """启动后台任务"""
        asyncio.create_task(self._run_data_collection())
        asyncio.create_task(self._run_data_cleanup())

    async def _run_data_collection(self):
        """运行数据收集任务"""
        while True:
            try:
                await self._collect_market_data()
                await self._collect_trading_data()
                await self._collect_social_data()
                await asyncio.sleep(self.collection_interval)
            except Exception as e:
                print(f"Data collection failed: {str(e)}")
                await asyncio.sleep(10)  # 出错后等待10秒重试

    async def _run_data_cleanup(self):
        """运行数据清理任务"""
        while True:
            try:
                await self._cleanup_old_data()
                await asyncio.sleep(86400)  # 每天运行一次
            except Exception as e:
                print(f"Data cleanup failed: {str(e)}")
                await asyncio.sleep(3600)  # 出错后等待1小时重试

    async def _collect_market_data(self):
        """收集市场数据"""
        async with aiohttp.ClientSession() as session:
            for symbol in self.config["symbols"]:
                try:
                    # 获取K线数据
                    kline_data = await self._fetch_kline_data(session, symbol)
                    if kline_data:
                        await self.db.market_data.insert_many(kline_data)

                    # 获取订单簿数据
                    orderbook_data = await self._fetch_orderbook_data(session, symbol)
                    if orderbook_data:
                        await self.db.market_data.insert_one(orderbook_data)

                    # 获取交易数据
                    trades_data = await self._fetch_trades_data(session, symbol)
                    if trades_data:
                        await self.db.market_data.insert_many(trades_data)

                except Exception as e:
                    print(f"Failed to collect market data for {symbol}: {str(e)}")

    async def _collect_trading_data(self):
        """收集交易数据"""
        for symbol in self.config["symbols"]:
            try:
                # 获取最新交易
                trades = await self._fetch_recent_trades(symbol)
                if trades:
                    await self.db.trades.insert_many(trades)

                # 获取持仓数据
                positions = await self._fetch_positions(symbol)
                if positions:
                    await self.db.positions.insert_many(positions)

            except Exception as e:
                print(f"Failed to collect trading data for {symbol}: {str(e)}")

    async def _collect_social_data(self):
        """收集社交媒体数据"""
        for symbol in self.config["symbols"]:
            try:
                # 获取社交媒体数据
                social_data = await self._fetch_social_data(symbol)
                if social_data:
                    await self.db.social_data.insert_many(social_data)

            except Exception as e:
                print(f"Failed to collect social data for {symbol}: {str(e)}")

    async def _cleanup_old_data(self):
        """清理过期数据"""
        cutoff_date = datetime.now() - timedelta(days=self.retention_period)

        # 清理市场数据
        await self.db.market_data.delete_many({"timestamp": {"$lt": cutoff_date}})

        # 清理交易数据
        await self.db.trades.delete_many({"timestamp": {"$lt": cutoff_date}})

        # 清理社交媒体数据
        await self.db.social_data.delete_many({"timestamp": {"$lt": cutoff_date}})

    async def get_market_data(
        self,
        symbol: str,
        data_type: str,
        start_time: datetime,
        end_time: datetime,
        interval: str = "1m",
    ) -> pd.DataFrame:
        """获取市场数据

        Args:
            symbol: 交易对符号
            data_type: 数据类型 (kline/orderbook/trades)
            start_time: 开始时间
            end_time: 结束时间
            interval: 时间间隔 (仅用于K线数据)

        Returns:
            pd.DataFrame: 市场数据
        """
        cache_key = (
            f"market_data:{symbol}:{data_type}:{interval}:{start_time}:{end_time}"
        )

        # 检查缓存
        if cached_data := await self.cache.get(cache_key):
            return pd.DataFrame(cached_data)

        # 从数据库查询
        query = {
            "symbol": symbol,
            "data_type": data_type,
            "timestamp": {"$gte": start_time, "$lte": end_time},
        }

        if data_type == "kline":
            query["interval"] = interval

        cursor = self.db.market_data.find(query, {"_id": 0}).sort(
            "timestamp", ASCENDING
        )

        data = await cursor.to_list(length=None)
        df = pd.DataFrame(data)

        # 更新缓存
        await self.cache.set(cache_key, data)

        return df

    async def get_trading_data(
        self, symbol: str, start_time: datetime, end_time: datetime
    ) -> pd.DataFrame:
        """获取交易数据

        Args:
            symbol: 交易对符号
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            pd.DataFrame: 交易数据
        """
        cache_key = f"trading_data:{symbol}:{start_time}:{end_time}"

        # 检查缓存
        if cached_data := await self.cache.get(cache_key):
            return pd.DataFrame(cached_data)

        # 从数据库查询
        cursor = self.db.trades.find(
            {"symbol": symbol, "timestamp": {"$gte": start_time, "$lte": end_time}},
            {"_id": 0},
        ).sort("timestamp", ASCENDING)

        data = await cursor.to_list(length=None)
        df = pd.DataFrame(data)

        # 更新缓存
        await self.cache.set(cache_key, data)

        return df

    async def get_social_data(
        self,
        symbol: str,
        platform: Optional[str] = None,
        start_time: datetime = None,
        end_time: datetime = None,
    ) -> pd.DataFrame:
        """获取社交媒体数据

        Args:
            symbol: 交易对符号
            platform: 平台名称 (可选)
            start_time: 开始时间 (可选)
            end_time: 结束时间 (可选)

        Returns:
            pd.DataFrame: 社交媒体数据
        """
        cache_key = f"social_data:{symbol}:{platform}:{start_time}:{end_time}"

        # 检查缓存
        if cached_data := await self.cache.get(cache_key):
            return pd.DataFrame(cached_data)

        # 构建查询条件
        query = {"symbol": symbol}
        if platform:
            query["platform"] = platform
        if start_time and end_time:
            query["timestamp"] = {"$gte": start_time, "$lte": end_time}

        # 从数据库查询
        cursor = self.db.social_data.find(query, {"_id": 0}).sort(
            "timestamp", ASCENDING
        )

        data = await cursor.to_list(length=None)
        df = pd.DataFrame(data)

        # 更新缓存
        await self.cache.set(cache_key, data)

        return df

    async def save_data(
        self, collection: str, data: Union[Dict, List[Dict]], upsert: bool = False
    ):
        """保存数据到数据库

        Args:
            collection: 集合名称
            data: 要保存的数据
            upsert: 是否更新插入
        """
        try:
            if isinstance(data, list):
                if upsert:
                    # 批量更新插入
                    operations = [
                        {
                            "update_one": {
                                "filter": {"_id": doc.get("_id")},
                                "update": {"$set": doc},
                                "upsert": True,
                            }
                        }
                        for doc in data
                    ]
                    await self.db[collection].bulk_write(operations)
                else:
                    # 批量插入
                    await self.db[collection].insert_many(data)
            else:
                if upsert:
                    # 单条更新插入
                    await self.db[collection].update_one(
                        {"_id": data.get("_id")}, {"$set": data}, upsert=True
                    )
                else:
                    # 单条插入
                    await self.db[collection].insert_one(data)

        except Exception as e:
            print(f"Failed to save data to {collection}: {str(e)}")
            raise

    async def delete_data(self, collection: str, query: Dict):
        """从数据库删除数据

        Args:
            collection: 集合名称
            query: 删除条件
        """
        try:
            result = await self.db[collection].delete_many(query)
            return result.deleted_count
        except Exception as e:
            print(f"Failed to delete data from {collection}: {str(e)}")
            raise

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return {
            "memory_usage": self.cache.get_memory_usage(),
            "disk_usage": self.cache.get_disk_usage(),
            "hit_rate": self.cache.get_hit_rate(),
            "miss_rate": self.cache.get_miss_rate(),
        }

    async def get_database_stats(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        stats = {}

        # 获取集合统计
        collections = ["market_data", "trades", "social_data"]
        for collection in collections:
            stats[collection] = {
                "document_count": await self.db[collection].count_documents({}),
                "size": await self.db.command("collstats", collection),
            }

        return stats

    async def start(self):
        """启动数据管理系统"""
        self.manager_task = asyncio.create_task(self._manage_data())

    async def stop(self):
        """停止数据管理系统"""
        if self.manager_task:
            self.manager_task.cancel()
            try:
                await self.manager_task
            except asyncio.CancelledError:
                pass
        self.executor.shutdown()

    async def _manage_data(self):
        """数据管理循环"""
        while True:
            try:
                # 处理数据缓冲区
                await self._process_data_buffer()

                # 更新缓存状态
                await self._update_cache_status()

                # 优化存储
                await self._optimize_storage()

                # 等待下一次处理
                await asyncio.sleep(1)

            except Exception as e:
                self.logger.error(f"Error in data management: {str(e)}")
                await asyncio.sleep(1)

    async def store_data(
        self, key: str, data: Dict, priority: DataPriority = DataPriority.MEDIUM
    ):
        """存储数据"""
        try:
            start_time = time.time()

            # 序列化数据
            serialized = msgpack.packb(data)

            # 判断是否需要压缩
            if len(serialized) > self.data_config["compression_threshold"]:
                compressed = zlib.compress(serialized)
                compression_ratio = len(compressed) / len(serialized)
                self.compression_stats[key] = compression_ratio
                self.metrics.compression_ratio.set(compression_ratio)
                data_to_store = compressed
            else:
                data_to_store = serialized

            # 根据优先级决定存储策略
            if priority == DataPriority.CRITICAL:
                # 立即存储
                await self._store_immediately(key, data_to_store)
            else:
                # 添加到缓冲区
                self.data_buffer[priority].append((key, data_to_store))

            # 更新指标
            latency = time.time() - start_time
            self.metrics.latency.observe(latency)
            self.metrics.throughput.set(len(data_to_store))

        except Exception as e:
            self.logger.error(f"Error storing data: {str(e)}")

    async def _store_immediately(self, key: str, data: bytes):
        """立即存储数据"""
        try:
            # 使用线程池执行存储操作
            await asyncio.get_event_loop().run_in_executor(
                self.executor, self.cache.set, key, data, self.data_config["cache_ttl"]
            )

        except Exception as e:
            self.logger.error(f"Error in immediate storage: {str(e)}")

    async def _process_data_buffer(self):
        """处理数据缓冲区"""
        try:
            for priority in DataPriority:
                buffer = self.data_buffer[priority]

                # 按批次处理
                while len(buffer) >= self.data_config["batch_size"]:
                    batch = buffer[: self.data_config["batch_size"]]
                    buffer = buffer[self.data_config["batch_size"] :]

                    # 批量存储
                    pipe = self.cache.pipeline()
                    for key, data in batch:
                        pipe.set(key, data, self.data_config["cache_ttl"])
                    await asyncio.get_event_loop().run_in_executor(
                        self.executor, pipe.execute
                    )

                self.data_buffer[priority] = buffer

        except Exception as e:
            self.logger.error(f"Error processing data buffer: {str(e)}")

    async def get_data(self, key: str) -> Optional[Dict]:
        """获取数据"""
        try:
            start_time = time.time()

            # 从缓存获取数据
            data = await asyncio.get_event_loop().run_in_executor(
                self.executor, self.cache.get, key
            )

            if data is None:
                self.metrics.cache_misses.inc()
                return None

            self.metrics.cache_hits.inc()

            # 判断是否需要解压
            try:
                decompressed = zlib.decompress(data)
                data = decompressed
            except:
                pass

            # 反序列化
            result = msgpack.unpackb(data)

            # 更新延迟指标
            latency = time.time() - start_time
            self.metrics.latency.observe(latency)

            return result

        except Exception as e:
            self.logger.error(f"Error getting data: {str(e)}")
            return None

    async def query_data(self, query: Dict) -> List[Dict]:
        """查询数据"""
        try:
            start_time = time.time()

            # 增加查询计数
            self.metrics.query_count.inc()

            # 获取匹配的键
            pattern = query.get("pattern", "*")
            keys = await asyncio.get_event_loop().run_in_executor(
                self.executor, self.cache.keys, pattern
            )

            # 批量获取数据
            pipe = self.cache.pipeline()
            for key in keys:
                pipe.get(key)
            values = await asyncio.get_event_loop().run_in_executor(
                self.executor, pipe.execute
            )

            # 处理结果
            results = []
            for data in values:
                if data is None:
                    continue

                # 解压缩和反序列化
                try:
                    decompressed = zlib.decompress(data)
                    data = decompressed
                except:
                    pass

                item = msgpack.unpackb(data)

                # 应用过滤条件
                if self._match_filters(item, query.get("filters", {})):
                    results.append(item)

            # 应用排序
            if "sort_by" in query:
                results.sort(
                    key=lambda x: x.get(query["sort_by"]),
                    reverse=query.get("descending", False),
                )

            # 应用分页
            offset = query.get("offset", 0)
            limit = query.get("limit", len(results))
            results = results[offset : offset + limit]

            # 更新延迟指标
            latency = time.time() - start_time
            self.metrics.latency.observe(latency)

            return results

        except Exception as e:
            self.logger.error(f"Error querying data: {str(e)}")
            return []

    def _match_filters(self, item: Dict, filters: Dict) -> bool:
        """匹配过滤条件"""
        try:
            for field, conditions in filters.items():
                value = item.get(field)

                for op, target in conditions.items():
                    if op == "eq" and value != target:
                        return False
                    elif op == "gt" and value <= target:
                        return False
                    elif op == "lt" and value >= target:
                        return False
                    elif op == "in" and value not in target:
                        return False
                    elif op == "contains" and target not in value:
                        return False

            return True

        except Exception:
            return False

    async def _update_cache_status(self):
        """更新缓存状态"""
        try:
            # 获取缓存信息
            info = await asyncio.get_event_loop().run_in_executor(
                self.executor, self.cache.info
            )

            # 更新存储使用指标
            used_memory = int(info.get("used_memory", 0))
            self.metrics.storage_usage.set(used_memory)

            # 计算平均压缩比
            if self.compression_stats:
                avg_ratio = np.mean(list(self.compression_stats.values()))
                self.metrics.compression_ratio.set(avg_ratio)

        except Exception as e:
            self.logger.error(f"Error updating cache status: {str(e)}")

    async def _optimize_storage(self):
        """优化存储"""
        try:
            # 获取所有键
            keys = await asyncio.get_event_loop().run_in_executor(
                self.executor, self.cache.keys, "*"
            )

            # 检查每个键的TTL
            pipe = self.cache.pipeline()
            for key in keys:
                pipe.ttl(key)
            ttls = await asyncio.get_event_loop().run_in_executor(
                self.executor, pipe.execute
            )

            # 对即将过期的数据进行处理
            for key, ttl in zip(keys, ttls):
                if ttl < 60:  # 小于1分钟过期
                    # 获取数据
                    data = await self.get_data(key)
                    if data:
                        # 重新设置TTL
                        await self.store_data(key, data, priority=DataPriority.LOW)

        except Exception as e:
            self.logger.error(f"Error optimizing storage: {str(e)}")

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "throughput": self.metrics.throughput._value.get(),
            "latency": self.metrics.latency.observe(),
            "cache_hits": self.metrics.cache_hits._value.get(),
            "cache_misses": self.metrics.cache_misses._value.get(),
            "compression_ratio": self.metrics.compression_ratio._value.get(),
            "storage_usage": self.metrics.storage_usage._value.get(),
            "query_count": self.metrics.query_count._value.get(),
            "buffer_size": sum(len(buffer) for buffer in self.data_buffer.values()),
        }
