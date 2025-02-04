import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union

import numpy as np
import pandas as pd
import ta
import talib
from sklearn.decomposition import PCA
from sklearn.feature_selection import SelectKBest, mutual_info_regression
from sklearn.preprocessing import MinMaxScaler, StandardScaler


def show_deprecation_warning():
    warnings.warn(
        "This Python implementation is deprecated and will be replaced by Go version. "
        "Please refer to the Go implementation in go_executor for new development.",
        DeprecationWarning,
        stacklevel=2,
    )


class FeatureEngineer:
    """特征工程器，负责生成高级特征

    Note: 此实现已废弃，将被Go版本替代。请参考go_executor中的新实现。
    """

    def __init__(self, config: Dict):
        show_deprecation_warning()
        self.config = config
        self.window_sizes = config.get("window_sizes", [5, 10, 20, 30, 60])
        self.volatility_windows = config.get("volatility_windows", [5, 10, 20])
        self.correlation_threshold = config.get("correlation_threshold", 0.8)

        # 初始化预处理器
        self._init_preprocessors()

    def _init_preprocessors(self):
        """初始化预处理器"""
        self.scalers = {"standard": StandardScaler(), "minmax": MinMaxScaler()}
        self.pca = PCA(n_components=0.95)  # 保留95%的方差

    def generate_market_features(
        self,
        df: pd.DataFrame,
        add_ta_features: bool = True,
        add_custom_features: bool = True,
    ) -> pd.DataFrame:
        """生成市场特征

        Args:
            df: 市场数据
            add_ta_features: 是否添加技术分析特征
            add_custom_features: 是否添加自定义特征

        Returns:
            pd.DataFrame: 包含新特征的数据框
        """
        if df.empty:
            return df

        try:
            # 添加技术分析特征
            if add_ta_features:
                df = self._add_ta_features(df)

            # 添加自定义特征
            if add_custom_features:
                df = self._add_custom_market_features(df)

            # 删除高度相关的特征
            df = self._remove_highly_correlated(df)

            return df

        except Exception as e:
            print(f"Failed to generate market features: {str(e)}")
            return df

    def generate_trading_features(
        self, df: pd.DataFrame, market_data: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """生成交易特征

        Args:
            df: 交易数据
            market_data: 市场数据（可选）

        Returns:
            pd.DataFrame: 包含新特征的数据框
        """
        if df.empty:
            return df

        try:
            # 添加基本交易特征
            df = self._add_basic_trade_features(df)

            # 添加市场相关特征
            if market_data is not None:
                df = self._add_market_related_features(df, market_data)

            # 添加订单流特征
            df = self._add_order_flow_features(df)

            return df

        except Exception as e:
            print(f"Failed to generate trading features: {str(e)}")
            return df

    def generate_social_features(
        self, df: pd.DataFrame, market_data: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """生成社交媒体特征

        Args:
            df: 社交媒体数据
            market_data: 市场数据（可选）

        Returns:
            pd.DataFrame: 包含新特征的数据框
        """
        if df.empty:
            return df

        try:
            # 添加情绪特征
            df = self._add_sentiment_features(df)

            # 添加市场相关特征
            if market_data is not None:
                df = self._add_sentiment_market_features(df, market_data)

            # 添加社交网络特征
            df = self._add_social_network_features(df)

            return df

        except Exception as e:
            print(f"Failed to generate social features: {str(e)}")
            return df

    def _add_ta_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加技术分析特征"""
        # 趋势指标
        df["ADX"] = ta.trend.adx(df["high"], df["low"], df["close"])
        df["CCI"] = ta.trend.cci(df["high"], df["low"], df["close"])
        df["DPO"] = ta.trend.dpo(df["close"])

        # 动量指标
        df["RSI"] = ta.momentum.rsi(df["close"])
        df["STOCH"] = ta.momentum.stoch(df["high"], df["low"], df["close"])
        df["STOCH_SIGNAL"] = ta.momentum.stoch_signal(
            df["high"], df["low"], df["close"]
        )

        # 波动性指标
        df["ATR"] = ta.volatility.average_true_range(df["high"], df["low"], df["close"])
        df["BBH"] = ta.volatility.bollinger_hband(df["close"])
        df["BBL"] = ta.volatility.bollinger_lband(df["close"])

        # 成交量指标
        df["ADI"] = ta.volume.acc_dist_index(
            df["high"], df["low"], df["close"], df["volume"]
        )
        df["CMF"] = ta.volume.chaikin_money_flow(
            df["high"], df["low"], df["close"], df["volume"]
        )
        df["FI"] = ta.volume.force_index(df["close"], df["volume"])

        # 新增趋势指标
        df["TRIX"] = ta.trend.trix(df["close"])  # Triple EMA
        df["MASS"] = ta.trend.mass_index(df["high"], df["low"])  # 质量指标
        df["VORTEX_POS"] = ta.trend.vortex_indicator_pos(
            df["high"], df["low"], df["close"]
        )
        df["VORTEX_NEG"] = ta.trend.vortex_indicator_neg(
            df["high"], df["low"], df["close"]
        )

        # 新增动量指标
        df["TSI"] = ta.momentum.tsi(df["close"])  # True Strength Index
        df["UO"] = ta.momentum.ultimate_oscillator(
            df["high"], df["low"], df["close"]
        )  # Ultimate Oscillator
        df["STOCH_RSI"] = ta.momentum.stochrsi(df["close"])  # Stochastic RSI

        # 新增波动性指标
        df["UI"] = ta.volatility.ulcer_index(df["close"])  # Ulcer Index
        df["BBWIDTH"] = (df["BBH"] - df["BBL"]) / df["BB_middle"]  # 布林带宽度

        # 新增成交量指标
        df["EMV"] = ta.volume.ease_of_movement(
            df["high"], df["low"], df["volume"]
        )  # Ease of Movement
        df["VPT"] = ta.volume.volume_price_trend(
            df["close"], df["volume"]
        )  # Volume-Price Trend
        df["NVI"] = ta.volume.negative_volume_index(
            df["close"], df["volume"]
        )  # Negative Volume Index

        return df

    def _add_custom_market_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加自定义市场特征"""
        # 价格动态特征
        for window in self.window_sizes:
            # 价格变化率
            df[f"return_{window}"] = df["close"].pct_change(window)

            # 对数收益率
            df[f"log_return_{window}"] = np.log(df["close"] / df["close"].shift(window))

            # 价格动量
            df[f"momentum_{window}"] = df["close"] - df["close"].shift(window)

            # 移动平均线
            df[f"ma_{window}"] = df["close"].rolling(window).mean()

            # 移动平均线交叉
            df[f"ma_cross_{window}"] = np.where(df["close"] > df[f"ma_{window}"], 1, -1)

        # 波动性特征
        for window in self.volatility_windows:
            # 实现波动率
            df[f"realized_vol_{window}"] = (
                (df["log_return_1"] * np.sqrt(252)).rolling(window).std()
            )

            # 帕金森波动率
            df[f"parkinson_vol_{window}"] = (
                (
                    np.sqrt(1 / (4 * window * np.log(2)))
                    * np.sqrt(np.log(df["high"] / df["low"]) ** 2)
                )
                .rolling(window)
                .mean()
            )

            # 振幅
            df[f"amplitude_{window}"] = (
                ((df["high"] - df["low"]) / df["close"]).rolling(window).mean()
            )

        # 新增价格动态特征
        for window in self.window_sizes:
            # 价格加速度
            df[f"price_acceleration_{window}"] = df[f"momentum_{window}"].diff()

            # 对数收益率的波动率
            df[f"log_return_vol_{window}"] = (
                df[f"log_return_{window}"].rolling(window).std()
            )

            # Z-score
            df[f"price_zscore_{window}"] = (
                df["close"] - df["close"].rolling(window).mean()
            ) / df["close"].rolling(window).std()

            # 相对强度
            df[f"relative_strength_{window}"] = (
                df["close"] / df["close"].rolling(window).mean()
            )

        # 新增价格形态特征
        df["price_range"] = (df["high"] - df["low"]) / df["close"]
        df["price_range_ma"] = df["price_range"].rolling(20).mean()
        df["gap_up"] = (df["low"] > df["high"].shift(1)).astype(int)
        df["gap_down"] = (df["high"] < df["low"].shift(1)).astype(int)

        # 新增日内特征
        df["intraday_return"] = (df["close"] - df["open"]) / df["open"]
        df["intraday_range"] = (df["high"] - df["low"]) / df["open"]
        df["morning_return"] = (df["close"] - df["open"]) / df["open"]  # 可根据实际时间调整
        df["afternoon_return"] = (df["close"] - df["open"]) / df["open"]  # 可根据实际时间调整

        # 新增成交量特征
        df["volume_price_corr"] = df["close"].rolling(20).corr(df["volume"])
        df["volume_surprise"] = (df["volume"] - df["volume"].rolling(20).mean()) / df[
            "volume"
        ].rolling(20).std()

        return df

    def _add_basic_trade_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加基本交易特征"""
        # 交易规模特征
        for window in self.window_sizes:
            # 成交量变化
            df[f"volume_change_{window}"] = df["amount"].pct_change(window)

            # 成交量趋势
            df[f"volume_ma_{window}"] = df["amount"].rolling(window).mean()

            # 成交量波动
            df[f"volume_std_{window}"] = df["amount"].rolling(window).std()

            # 大单指标
            mean_amount = df["amount"].mean()
            df[f"large_order_{window}"] = (
                (df["amount"] > mean_amount * 2).rolling(window).sum()
            )

        # 交易频率特征
        df["trade_interval"] = df["timestamp"].diff().dt.total_seconds()
        df["trade_freq"] = 1 / df["trade_interval"]

        # 买卖压力特征
        df["buy_ratio"] = np.where(df["side"] == "buy", 1, 0)
        df["sell_ratio"] = np.where(df["side"] == "sell", 1, 0)

        for window in self.window_sizes:
            df[f"buy_pressure_{window}"] = df["buy_ratio"].rolling(window).mean()
            df[f"sell_pressure_{window}"] = df["sell_ratio"].rolling(window).mean()

        return df

    def _add_market_related_features(
        self, df: pd.DataFrame, market_data: pd.DataFrame
    ) -> pd.DataFrame:
        """添加市场相关特征"""
        # 确保时间戳对齐
        df = df.set_index("timestamp")
        market_data = market_data.set_index("timestamp")

        # 计算每笔交易相对于市场价格的偏差
        df["price_deviation"] = (df["price"] - market_data["close"]) / market_data[
            "close"
        ]

        # 计算交易价格的有效价差
        df["effective_spread"] = abs(df["price"] - market_data["close"])

        # 计算交易成本
        df["transaction_cost"] = df["effective_spread"] * df["amount"]

        return df.reset_index()

    def _add_order_flow_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加订单流特征"""
        # 订单流不平衡
        for window in self.window_sizes:
            buy_volume = df[df["side"] == "buy"]["amount"].rolling(window).sum()
            sell_volume = df[df["side"] == "sell"]["amount"].rolling(window).sum()

            df[f"order_imbalance_{window}"] = (buy_volume - sell_volume) / (
                buy_volume + sell_volume
            )

            # 订单流毒性
            df[f"toxicity_{window}"] = (
                (df["price"].diff(window) * df[f"order_imbalance_{window}"])
                .rolling(window)
                .mean()
            )

        # 订单链接特征
        df["next_trade_same_side"] = df["side"].shift(-1) == df["side"]
        df["prev_trade_same_side"] = df["side"].shift(1) == df["side"]

        # 新增订单流特征
        for window in self.window_sizes:
            # 订单流动量
            df[f"order_flow_momentum_{window}"] = df[f"order_imbalance_{window}"].diff()

            # 订单流加速度
            df[f"order_flow_acceleration_{window}"] = df[
                f"order_flow_momentum_{window}"
            ].diff()

            # 订单流波动率
            df[f"order_flow_volatility_{window}"] = (
                df[f"order_imbalance_{window}"].rolling(window).std()
            )

            # 大单比例变化
            df[f"large_order_change_{window}"] = df[f"large_order_{window}"].diff()

        # 新增交易行为特征
        df["trade_size_variance"] = df["amount"].rolling(20).var()
        df["trade_intensity"] = df["amount"] * df["trade_freq"]
        df["trade_size_skew"] = df["amount"].rolling(20).skew()
        df["trade_size_kurt"] = df["amount"].rolling(20).kurt()

        # 新增价格冲击特征
        df["price_impact"] = df["price_change"].abs() / df["amount"]
        df["price_reversal"] = -df["price_change"].shift(-1) / df["price_change"]

        return df

    def _add_sentiment_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加情绪特征"""
        # 情绪动态特征
        for window in self.window_sizes:
            # 情绪趋势
            df[f"sentiment_ma_{window}"] = df["sentiment"].rolling(window).mean()

            # 情绪波动
            df[f"sentiment_std_{window}"] = df["sentiment"].rolling(window).std()

            # 情绪动量
            df[f"sentiment_momentum_{window}"] = df["sentiment"] - df[
                "sentiment"
            ].shift(window)

            # 极端情绪
            sentiment_mean = df["sentiment"].mean()
            sentiment_std = df["sentiment"].std()
            df[f"extreme_sentiment_{window}"] = (
                (
                    (df["sentiment"] > sentiment_mean + 2 * sentiment_std)
                    | (df["sentiment"] < sentiment_mean - 2 * sentiment_std)
                )
                .rolling(window)
                .sum()
            )

        # 情绪分布特征
        df["sentiment_skew"] = df["sentiment"].rolling(20).skew()
        df["sentiment_kurt"] = df["sentiment"].rolling(20).kurt()

        # 新增情绪动态特征
        for window in self.window_sizes:
            # 情绪加速度
            df[f"sentiment_acceleration_{window}"] = df[
                f"sentiment_momentum_{window}"
            ].diff()

            # 情绪波动率变化
            df[f"sentiment_vol_change_{window}"] = df[f"sentiment_std_{window}"].diff()

            # 极端情绪比例变化
            df[f"extreme_sentiment_change_{window}"] = df[
                f"extreme_sentiment_{window}"
            ].diff()

            # 情绪反转
            df[f"sentiment_reversal_{window}"] = -df["sentiment"].diff(window) / df[
                "sentiment"
            ].shift(window)

        # 新增情绪分布特征
        df["sentiment_range"] = (
            df["sentiment"].rolling(20).max() - df["sentiment"].rolling(20).min()
        )
        df["sentiment_entropy"] = (
            -df["sentiment"]
            .rolling(20)
            .apply(lambda x: np.sum(x * np.log(np.abs(x) + 1e-10)))
        )

        # 新增情绪极化特征
        sentiment_mean = df["sentiment"].mean()
        sentiment_std = df["sentiment"].std()
        df["sentiment_polarization"] = (
            (df["sentiment"] > sentiment_mean + 2 * sentiment_std)
            | (df["sentiment"] < sentiment_mean - 2 * sentiment_std)
        ).astype(int)

        return df

    def _add_sentiment_market_features(
        self, df: pd.DataFrame, market_data: pd.DataFrame
    ) -> pd.DataFrame:
        """添加情绪市场特征"""
        # 确保时间戳对齐
        df = df.set_index("timestamp")
        market_data = market_data.set_index("timestamp")

        # 计算情绪与价格变化的相关性
        for window in self.window_sizes:
            df[f"sentiment_price_corr_{window}"] = (
                df["sentiment"].rolling(window).corr(market_data["close"])
            )

            # 情绪领先指标
            df[f"sentiment_lead_{window}"] = (
                df["sentiment"].shift(window) * market_data["close"].pct_change()
            )

            # 情绪与波动性的关系
            df[f"sentiment_vol_impact_{window}"] = (
                (df["sentiment"].abs() * market_data["close"].pct_change().abs())
                .rolling(window)
                .mean()
            )

        return df.reset_index()

    def _add_social_network_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加社交网络特征"""
        # 平台活跃度
        platform_counts = df["platform"].value_counts()
        total_posts = len(df)

        for platform in platform_counts.index:
            df[f"{platform}_ratio"] = (
                np.where(df["platform"] == platform, 1, 0).rolling(20).mean()
            )

        # 影响力分布
        df["high_influence"] = df["influence_score"] > df["influence_score"].quantile(
            0.8
        )

        for window in self.window_sizes:
            # 高影响力占比
            df[f"high_influence_ratio_{window}"] = (
                (df["high_influence"]).rolling(window).mean()
            )

            # 影响力集中度
            df[f"influence_concentration_{window}"] = (
                df["influence_score"].rolling(window).std()
                / df["influence_score"].rolling(window).mean()
            )

        # 新增平台交互特征
        platform_pairs = [
            ("twitter", "reddit"),
            ("twitter", "discord"),
            ("twitter", "telegram"),
            ("reddit", "discord"),
            ("reddit", "telegram"),
            ("discord", "telegram"),
        ]

        for p1, p2 in platform_pairs:
            # 平台情绪相关性
            df[f"{p1}_{p2}_corr"] = (
                df[f"{p1}_ratio"].rolling(20).corr(df[f"{p2}_ratio"])
            )

            # 平台活跃度差异
            df[f"{p1}_{p2}_diff"] = df[f"{p1}_ratio"] - df[f"{p2}_ratio"]

        # 新增影响力网络特征
        df["influence_entropy"] = (
            -df["influence_score"]
            .rolling(20)
            .apply(lambda x: np.sum(x * np.log(x + 1e-10)))
        )
        df["influence_gini"] = (
            df["influence_score"]
            .rolling(20)
            .apply(lambda x: np.abs(np.subtract.outer(x, x)).mean() / (2 * x.mean()))
        )

        # 新增时间特征
        df["hour"] = pd.to_datetime(df["timestamp"]).dt.hour
        df["day_of_week"] = pd.to_datetime(df["timestamp"]).dt.dayofweek

        # 计算每个时间段的活跃度
        for hour in range(24):
            df[f"hour_{hour}_activity"] = (df["hour"] == hour).astype(int)

        for day in range(7):
            df[f"day_{day}_activity"] = (df["day_of_week"] == day).astype(int)

        return df

    def _remove_highly_correlated(self, df: pd.DataFrame) -> pd.DataFrame:
        """删除高度相关的特征"""
        # 计算相关性矩阵
        corr_matrix = df.corr().abs()

        # 获取上三角矩阵
        upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))

        # 找出高度相关的特征
        to_drop = [
            column
            for column in upper.columns
            if any(upper[column] > self.correlation_threshold)
        ]

        # 删除这些特征
        df = df.drop(columns=to_drop)

        return df

    def reduce_dimensions(
        self, df: pd.DataFrame, n_components: Optional[int] = None
    ) -> pd.DataFrame:
        """降维

        Args:
            df: 数据框
            n_components: 目标维度

        Returns:
            pd.DataFrame: 降维后的数据框
        """
        try:
            # 准备数据
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            X = df[numeric_cols]

            # 标准化
            X_scaled = self.scalers["standard"].fit_transform(X)

            # 设置PCA组件数
            if n_components:
                self.pca.n_components = n_components

            # 执行PCA
            X_pca = self.pca.fit_transform(X_scaled)

            # 创建新的数据框
            pca_cols = [f"PC{i+1}" for i in range(X_pca.shape[1])]
            df_pca = pd.DataFrame(X_pca, columns=pca_cols, index=df.index)

            # 添加非数值列
            for col in df.columns:
                if col not in numeric_cols:
                    df_pca[col] = df[col]

            return df_pca

        except Exception as e:
            print(f"Failed to reduce dimensions: {str(e)}")
            return df

    def select_features(
        self, df: pd.DataFrame, target_col: str, n_features: int = 10
    ) -> List[str]:
        """特征选择

        Args:
            df: 数据框
            target_col: 目标列名
            n_features: 选择的特征数量

        Returns:
            List[str]: 选中的特征列表
        """
        try:
            # 准备数据
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            feature_cols = [col for col in numeric_cols if col != target_col]

            X = df[feature_cols]
            y = df[target_col]

            # 使用互信息进行特征选择
            selector = SelectKBest(score_func=mutual_info_regression, k=n_features)
            selector.fit(X, y)

            # 获取选中的特征
            selected_features = [
                feature_cols[i] for i in selector.get_support(indices=True)
            ]

            return selected_features

        except Exception as e:
            print(f"Failed to select features: {str(e)}")
            return []
