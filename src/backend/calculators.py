from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import talib

from .base import BaseFeatureComputer


class TechnicalIndicatorCalculator(BaseFeatureComputer):
    """技术指标计算器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.price_col = config.get("price_col", "close")
        self.volume_col = config.get("volume_col", "volume")
        self.high_col = config.get("high_col", "high")
        self.low_col = config.get("low_col", "low")
        self.indicators = config.get("indicators", ["MA", "RSI", "MACD", "BB"])
        self.ma_periods = config.get("ma_periods", [5, 10, 20, 60])
        self.rsi_period = config.get("rsi_period", 14)
        self.bb_period = config.get("bb_period", 20)
        self.macd_params = config.get("macd_params", (12, 26, 9))

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标"""
        try:
            start_time = datetime.now()
            df = data.copy()

            # 检查必需列
            required_cols = [self.price_col]
            if "BB" in self.indicators or "ATR" in self.indicators:
                required_cols.extend([self.high_col, self.low_col])
            if "VWAP" in self.indicators:
                required_cols.append(self.volume_col)

            if not all(col in df.columns for col in required_cols):
                missing_cols = set(required_cols) - set(df.columns)
                raise ValueError(f"Missing required columns: {missing_cols}")

            # 计算移动平均
            if "MA" in self.indicators:
                for period in self.ma_periods:
                    df[f"MA_{period}"] = talib.MA(df[self.price_col], timeperiod=period)

            # 计算RSI
            if "RSI" in self.indicators:
                df["RSI"] = talib.RSI(df[self.price_col], timeperiod=self.rsi_period)

            # 计算MACD
            if "MACD" in self.indicators:
                macd, signal, hist = talib.MACD(
                    df[self.price_col],
                    fastperiod=self.macd_params[0],
                    slowperiod=self.macd_params[1],
                    signalperiod=self.macd_params[2],
                )
                df["MACD"] = macd
                df["MACD_Signal"] = signal
                df["MACD_Hist"] = hist

            # 计算布林带
            if "BB" in self.indicators:
                upper, middle, lower = talib.BBANDS(
                    df[self.price_col], timeperiod=self.bb_period
                )
                df["BB_Upper"] = upper
                df["BB_Middle"] = middle
                df["BB_Lower"] = lower

            # 计算ATR
            if "ATR" in self.indicators:
                df["ATR"] = talib.ATR(
                    df[self.high_col],
                    df[self.low_col],
                    df[self.price_col],
                    timeperiod=14,
                )

            # 计算VWAP
            if "VWAP" in self.indicators:
                df["VWAP"] = (df[self.price_col] * df[self.volume_col]).cumsum() / df[
                    self.volume_col
                ].cumsum()

            self.update_metrics(start_time, True)
            return df

        except Exception as e:
            self.logger.error(f"技术指标计算失败: {str(e)}")
            self.update_metrics(start_time, False)
            raise


class StatisticalFeatureCalculator(BaseFeatureComputer):
    """统计特征计算器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.price_col = config.get("price_col", "close")
        self.volume_col = config.get("volume_col", "volume")
        self.window_sizes = config.get("window_sizes", [5, 10, 20])
        self.features = config.get(
            "features", ["returns", "volatility", "skew", "kurtosis"]
        )

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        """计算统计特征"""
        try:
            start_time = datetime.now()
            df = data.copy()

            # 计算收益率
            if "returns" in self.features:
                df["returns"] = df[self.price_col].pct_change()
                df["log_returns"] = np.log(df[self.price_col]).diff()

                for window in self.window_sizes:
                    # 累积收益
                    df[f"cum_returns_{window}"] = (1 + df["returns"]).rolling(
                        window
                    ).prod() - 1

            # 计算波动率
            if "volatility" in self.features:
                for window in self.window_sizes:
                    df[f"volatility_{window}"] = df["returns"].rolling(
                        window
                    ).std() * np.sqrt(252)

            # 计算偏度
            if "skew" in self.features:
                for window in self.window_sizes:
                    df[f"skew_{window}"] = df["returns"].rolling(window).skew()

            # 计算峰度
            if "kurtosis" in self.features:
                for window in self.window_sizes:
                    df[f"kurtosis_{window}"] = df["returns"].rolling(window).kurt()

            # 计算成交量特征
            if self.volume_col in df.columns:
                for window in self.window_sizes:
                    df[f"volume_ma_{window}"] = (
                        df[self.volume_col].rolling(window).mean()
                    )
                    df[f"volume_std_{window}"] = (
                        df[self.volume_col].rolling(window).std()
                    )

            self.update_metrics(start_time, True)
            return df

        except Exception as e:
            self.logger.error(f"统计特征计算失败: {str(e)}")
            self.update_metrics(start_time, False)
            raise


class MarketFeatureCalculator(BaseFeatureComputer):
    """市场特征计算器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.price_col = config.get("price_col", "close")
        self.volume_col = config.get("volume_col", "volume")
        self.bid_col = config.get("bid_col", "bid")
        self.ask_col = config.get("ask_col", "ask")
        self.window_sizes = config.get("window_sizes", [5, 10, 20])
        self.features = config.get(
            "features", ["liquidity", "momentum", "market_impact"]
        )

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        """计算市场特征"""
        try:
            start_time = datetime.now()
            df = data.copy()

            # 计算流动性指标
            if "liquidity" in self.features and all(
                col in df.columns for col in [self.bid_col, self.ask_col]
            ):
                # 买卖价差
                df["spread"] = df[self.ask_col] - df[self.bid_col]
                df["relative_spread"] = df["spread"] / df[self.price_col]

                for window in self.window_sizes:
                    # 平均价差
                    df[f"avg_spread_{window}"] = df["spread"].rolling(window).mean()
                    # 价差波动
                    df[f"spread_volatility_{window}"] = (
                        df["spread"].rolling(window).std()
                    )

            # 计算动量指标
            if "momentum" in self.features:
                for window in self.window_sizes:
                    # 价格动量
                    df[f"momentum_{window}"] = df[self.price_col].diff(window)
                    # 相对强弱
                    df[f"roc_{window}"] = df[self.price_col].pct_change(window)

            # 计算市场冲击指标
            if "market_impact" in self.features and self.volume_col in df.columns:
                # Amihud非流动性比率
                df["returns_abs"] = df["returns"].abs()
                for window in self.window_sizes:
                    df[f"illiquidity_{window}"] = (
                        (df["returns_abs"] / df[self.volume_col]).rolling(window).mean()
                    )

                # 成交量价格相关性
                for window in self.window_sizes:
                    df[f"volume_price_corr_{window}"] = (
                        df[self.price_col].rolling(window).corr(df[self.volume_col])
                    )

            self.update_metrics(start_time, True)
            return df

        except Exception as e:
            self.logger.error(f"市场特征计算失败: {str(e)}")
            self.update_metrics(start_time, False)
            raise
