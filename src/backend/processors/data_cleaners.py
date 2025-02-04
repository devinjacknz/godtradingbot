from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler, StandardScaler

from .base import BaseProcessor


class DataCleaningProcessor(BaseProcessor):
    """数据清洗处理器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.required_columns = config.get("required_columns", [])
        self.datetime_columns = config.get("datetime_columns", [])
        self.numeric_columns = config.get("numeric_columns", [])
        self.categorical_columns = config.get("categorical_columns", [])
        self.missing_threshold = config.get("missing_threshold", 0.5)

    def process(self, data: pd.DataFrame) -> pd.DataFrame:
        """清洗数据"""
        try:
            start_time = datetime.now()

            # 检查必需列
            if not all(col in data.columns for col in self.required_columns):
                missing_cols = set(self.required_columns) - set(data.columns)
                raise ValueError(f"Missing required columns: {missing_cols}")

            # 转换数据类型
            df = data.copy()

            # 处理时间列
            for col in self.datetime_columns:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col])

            # 处理数值列
            for col in self.numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            # 处理分类列
            for col in self.categorical_columns:
                if col in df.columns:
                    df[col] = df[col].astype("category")

            # 删除缺失值过多的列
            missing_ratio = df.isnull().sum() / len(df)
            cols_to_drop = missing_ratio[missing_ratio > self.missing_threshold].index
            df = df.drop(columns=cols_to_drop)

            # 删除重复行
            df = df.drop_duplicates()

            # 重置索引
            df = df.reset_index(drop=True)

            self.update_metrics(start_time, True)
            return df

        except Exception as e:
            self.logger.error(f"数据清洗失败: {str(e)}")
            self.update_metrics(start_time, False)
            raise


class OutlierDetectionProcessor(BaseProcessor):
    """异常值检测处理器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.numeric_columns = config.get("numeric_columns", [])
        self.n_std = config.get("n_std", 3)
        self.quantile_range = config.get("quantile_range", (0.01, 0.99))
        self.method = config.get("method", "zscore")  # zscore or iqr

    def process(self, data: pd.DataFrame) -> pd.DataFrame:
        """检测和处理异常值"""
        try:
            start_time = datetime.now()
            df = data.copy()

            for col in self.numeric_columns:
                if col not in df.columns:
                    continue

                if self.method == "zscore":
                    # Z-score方法
                    z_scores = np.abs((df[col] - df[col].mean()) / df[col].std())
                    mask = z_scores > self.n_std
                elif self.method == "iqr":
                    # IQR方法
                    Q1 = df[col].quantile(0.25)
                    Q3 = df[col].quantile(0.75)
                    IQR = Q3 - Q1
                    mask = (df[col] < (Q1 - 1.5 * IQR)) | (df[col] > (Q3 + 1.5 * IQR))
                else:
                    # 分位数方法
                    lower = df[col].quantile(self.quantile_range[0])
                    upper = df[col].quantile(self.quantile_range[1])
                    mask = (df[col] < lower) | (df[col] > upper)

                # 将异常值替换为NaN
                df.loc[mask, col] = np.nan

                # 记录异常值数量
                outlier_count = mask.sum()
                self.logger.info(f"Column {col}: {outlier_count} outliers detected")

            self.update_metrics(start_time, True)
            return df

        except Exception as e:
            self.logger.error(f"异常值检测失败: {str(e)}")
            self.update_metrics(start_time, False)
            raise


class DataNormalizationProcessor(BaseProcessor):
    """数据规范化处理器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.numeric_columns = config.get("numeric_columns", [])
        self.method = config.get("method", "standard")  # standard or minmax
        self.scalers = {}

    def process(self, data: pd.DataFrame) -> pd.DataFrame:
        """规范化数据"""
        try:
            start_time = datetime.now()
            df = data.copy()

            for col in self.numeric_columns:
                if col not in df.columns:
                    continue

                if col not in self.scalers:
                    if self.method == "standard":
                        self.scalers[col] = StandardScaler()
                    else:
                        self.scalers[col] = MinMaxScaler()

                # 重塑数据以适应scaler
                values = df[col].values.reshape(-1, 1)

                # 处理NaN值
                mask = np.isnan(values)
                if mask.any():
                    # 暂时用0填充NaN,以便进行缩放
                    values[mask] = 0

                # 转换数据
                scaled_values = self.scalers[col].fit_transform(values)

                # 将NaN值恢复
                scaled_values[mask] = np.nan

                # 更新数据框
                df[col] = scaled_values

            self.update_metrics(start_time, True)
            return df

        except Exception as e:
            self.logger.error(f"数据规范化失败: {str(e)}")
            self.update_metrics(start_time, False)
            raise

    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """使用已有的scaler转换数据"""
        try:
            df = data.copy()

            for col in self.numeric_columns:
                if col not in df.columns or col not in self.scalers:
                    continue

                values = df[col].values.reshape(-1, 1)
                mask = np.isnan(values)
                if mask.any():
                    values[mask] = 0

                scaled_values = self.scalers[col].transform(values)
                scaled_values[mask] = np.nan
                df[col] = scaled_values

            return df

        except Exception as e:
            self.logger.error(f"数据转换失败: {str(e)}")
            raise
