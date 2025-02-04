from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd
import talib
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import MinMaxScaler, StandardScaler

from src.shared.cache.hybrid_cache import HybridCache


class DataProcessor:
    """数据处理器，负责数据清洗、转换和分析"""

    def __init__(self, config: Dict):
        self.config = config
        self.cache = HybridCache()

        # 初始化预处理器
        self._init_preprocessors()

        # 配置参数
        self.resample_rule = config.get("resample_rule", "1min")
        self.window_size = config.get("window_size", 20)
        self.outlier_std = config.get("outlier_std", 3)

    def _init_preprocessors(self):
        """初始化预处理器"""
        self.scalers = {"standard": StandardScaler(), "minmax": MinMaxScaler()}
        self.imputer = SimpleImputer(strategy="mean")

    def process_market_data(
        self, df: pd.DataFrame, add_indicators: bool = True
    ) -> pd.DataFrame:
        """处理市场数据

        Args:
            df: 原始市场数据
            add_indicators: 是否添加技术指标

        Returns:
            pd.DataFrame: 处理后的数据
        """
        if df.empty:
            return df

        try:
            # 数据清洗
            df = self._clean_market_data(df)

            # 重采样
            df = self._resample_data(df)

            # 添加技术指标
            if add_indicators:
                df = self._add_technical_indicators(df)

            # 标准化
            df = self._normalize_market_data(df)

            return df

        except Exception as e:
            print(f"Failed to process market data: {str(e)}")
            return df

    def process_trading_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """处理交易数据

        Args:
            df: 原始交易数据

        Returns:
            pd.DataFrame: 处理后的数据
        """
        if df.empty:
            return df

        try:
            # 数据清洗
            df = self._clean_trading_data(df)

            # 计算交易统计
            df = self._calculate_trade_stats(df)

            # 添加交易特征
            df = self._add_trade_features(df)

            return df

        except Exception as e:
            print(f"Failed to process trading data: {str(e)}")
            return df

    def process_social_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """处理社交媒体数据

        Args:
            df: 原始社交媒体数据

        Returns:
            pd.DataFrame: 处理后的数据
        """
        if df.empty:
            return df

        try:
            # 数据清洗
            df = self._clean_social_data(df)

            # 聚合情绪数据
            df = self._aggregate_sentiment(df)

            # 添加社交特征
            df = self._add_social_features(df)

            return df

        except Exception as e:
            print(f"Failed to process social data: {str(e)}")
            return df

    def _clean_market_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """清洗市场数据"""
        # 删除重复数据
        df = df.drop_duplicates()

        # 处理缺失值
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        df[numeric_cols] = pd.DataFrame(
            self.imputer.fit_transform(df[numeric_cols]),
            columns=numeric_cols,
            index=df.index,
        )

        # 删除异常值
        for col in numeric_cols:
            mean = df[col].mean()
            std = df[col].std()
            df = df[
                (df[col] > mean - self.outlier_std * std)
                & (df[col] < mean + self.outlier_std * std)
            ]

        return df

    def _clean_trading_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """清洗交易数据"""
        # 删除重复交易
        df = df.drop_duplicates(subset=["trade_id"])

        # 验证交易数据
        df = df[(df["price"] > 0) & (df["amount"] > 0)]

        # 添加时间特征
        df["hour"] = df["timestamp"].dt.hour
        df["day_of_week"] = df["timestamp"].dt.dayofweek

        return df

    def _clean_social_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """清洗社交媒体数据"""
        # 删除重复内容
        df = df.drop_duplicates(subset=["text"])

        # 删除无效数据
        df = df[df["text"].notna() & (df["text"].str.len() > 0)]

        # 规范化时间戳
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        return df

    def _resample_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """重采样数据"""
        # 设置时间索引
        df = df.set_index("timestamp")

        # 按配置的规则重采样
        resampled = df.resample(self.resample_rule)

        # 使用不同的聚合方法
        agg_dict = {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }

        df = resampled.agg(agg_dict)
        return df.reset_index()

    def _add_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加技术指标"""
        # 移动平均线
        df["MA5"] = talib.MA(df["close"], timeperiod=5)
        df["MA10"] = talib.MA(df["close"], timeperiod=10)
        df["MA20"] = talib.MA(df["close"], timeperiod=20)

        # MACD
        df["MACD"], df["MACD_signal"], df["MACD_hist"] = talib.MACD(
            df["close"], fastperiod=12, slowperiod=26, signalperiod=9
        )

        # RSI
        df["RSI"] = talib.RSI(df["close"], timeperiod=14)

        # 布林带
        df["BB_upper"], df["BB_middle"], df["BB_lower"] = talib.BBANDS(
            df["close"], timeperiod=20, nbdevup=2, nbdevdn=2
        )

        return df

    def _normalize_market_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化市场数据"""
        # 选择需要标准化的列
        numeric_cols = df.select_dtypes(include=[np.number]).columns

        # 使用StandardScaler标准化
        df[numeric_cols] = self.scalers["standard"].fit_transform(df[numeric_cols])

        return df

    def _calculate_trade_stats(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算交易统计"""
        # 计算成交量统计
        df["volume_mean"] = df["amount"].rolling(self.window_size).mean()
        df["volume_std"] = df["amount"].rolling(self.window_size).std()

        # 计算价格统计
        df["price_mean"] = df["price"].rolling(self.window_size).mean()
        df["price_std"] = df["price"].rolling(self.window_size).std()

        # 计算买卖压力
        buy_volume = df[df["side"] == "buy"]["amount"].rolling(self.window_size).sum()
        sell_volume = df[df["side"] == "sell"]["amount"].rolling(self.window_size).sum()
        df["buy_sell_ratio"] = buy_volume / sell_volume

        return df

    def _add_trade_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加交易特征"""
        # 计算价格变化
        df["price_change"] = df["price"].pct_change()

        # 计算成交量变化
        df["volume_change"] = df["amount"].pct_change()

        # 添加交易间隔
        df["trade_interval"] = df["timestamp"].diff().dt.total_seconds()

        # 计算移动相关性
        df["price_volume_corr"] = (
            df["price"].rolling(self.window_size).corr(df["amount"])
        )

        return df

    def _aggregate_sentiment(self, df: pd.DataFrame) -> pd.DataFrame:
        """聚合情绪数据"""
        # 按时间窗口聚合
        df = df.set_index("timestamp")

        # 计算加权情绪得分
        df["weighted_sentiment"] = df["sentiment"] * df["influence_score"]

        # 聚合统计
        agg_dict = {
            "sentiment": ["mean", "std"],
            "weighted_sentiment": "sum",
            "influence_score": "mean",
        }

        df = df.resample(self.resample_rule).agg(agg_dict)
        return df.reset_index()

    def _add_social_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加社交特征"""
        # 计算情绪动量
        df["sentiment_momentum"] = df["sentiment_mean"].diff()

        # 计算情绪波动
        df["sentiment_volatility"] = df["sentiment_std"].rolling(self.window_size).std()

        # 计算影响力变化
        df["influence_change"] = df["influence_score"].pct_change()

        # 添加情绪趋势
        df["sentiment_trend"] = np.where(
            df["sentiment_momentum"] > 0,
            1,
            np.where(df["sentiment_momentum"] < 0, -1, 0),
        )

        return df

    def combine_data(
        self,
        market_data: pd.DataFrame,
        trading_data: pd.DataFrame,
        social_data: pd.DataFrame,
    ) -> pd.DataFrame:
        """合并不同来源的数据

        Args:
            market_data: 市场数据
            trading_data: 交易数据
            social_data: 社交媒体数据

        Returns:
            pd.DataFrame: 合并后的数据
        """
        try:
            # 确保所有数据都有时间戳索引
            dfs = [market_data, trading_data, social_data]
            for df in dfs:
                if "timestamp" not in df.columns:
                    continue
                df.set_index("timestamp", inplace=True)

            # 按时间对齐数据
            df = pd.concat(dfs, axis=1)

            # 处理重复列
            df = df.loc[:, ~df.columns.duplicated()]

            # 填充缺失值
            df = df.fillna(method="ffill").fillna(method="bfill")

            return df

        except Exception as e:
            print(f"Failed to combine data: {str(e)}")
            return pd.DataFrame()

    def get_feature_importance(
        self, df: pd.DataFrame, target_col: str
    ) -> Dict[str, float]:
        """计算特征重要性

        Args:
            df: 数据框
            target_col: 目标列名

        Returns:
            Dict[str, float]: 特征重要性得分
        """
        try:
            from sklearn.ensemble import RandomForestRegressor

            # 准备特征和目标
            features = df.drop(columns=[target_col])
            target = df[target_col]

            # 训练随机森林
            rf = RandomForestRegressor(n_estimators=100, random_state=42)
            rf.fit(features, target)

            # 计算特征重要性
            importance = dict(zip(features.columns, rf.feature_importances_))

            # 按重要性排序
            return dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))

        except Exception as e:
            print(f"Failed to calculate feature importance: {str(e)}")
            return {}
