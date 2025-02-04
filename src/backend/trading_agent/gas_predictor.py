from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler

from src.shared.cache.hybrid_cache import HybridCache


class GasPredictor:
    """Gas费用预测器"""

    def __init__(self, config: Dict):
        self.config = config
        self.cache = HybridCache()
        self.model = GradientBoostingRegressor(
            n_estimators=100, learning_rate=0.1, max_depth=3
        )
        self.scaler = StandardScaler()
        self.feature_columns = [
            "hour",
            "day_of_week",
            "gas_used_ratio",
            "prev_base_fee",
            "prev_priority_fee",
        ]
        self.is_trained = False
        self.last_training_time = None
        self.training_history: List[Dict] = []

    def prepare_features(self, data: List[Dict]) -> pd.DataFrame:
        """准备特征数据

        Args:
            data: 原始数据列表

        Returns:
            pd.DataFrame: 处理后的特征数据
        """
        df = pd.DataFrame(data)

        # 添加时间特征
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["hour"] = df["timestamp"].dt.hour
        df["day_of_week"] = df["timestamp"].dt.dayofweek

        # 添加滞后特征
        df["prev_base_fee"] = df["base_fee"].shift(1)
        df["prev_priority_fee"] = df["priority_fee"].shift(1)

        # 填充缺失值
        df = df.fillna(method="ffill")

        return df[self.feature_columns]

    async def train(self, historical_data: List[Dict]):
        """训练模型

        Args:
            historical_data: 历史Gas数据
        """
        if len(historical_data) < 100:
            return

        try:
            # 准备训练数据
            df = self.prepare_features(historical_data)
            X = df[self.feature_columns].values
            y = np.array([d["base_fee"] for d in historical_data])

            # 标准化特征
            X_scaled = self.scaler.fit_transform(X)

            # 训练模型
            self.model.fit(X_scaled, y)

            # 记录训练信息
            self.is_trained = True
            self.last_training_time = datetime.now()

            training_metrics = {
                "timestamp": self.last_training_time,
                "data_points": len(historical_data),
                "feature_importance": dict(
                    zip(self.feature_columns, self.model.feature_importances_)
                ),
            }
            self.training_history.append(training_metrics)

        except Exception as e:
            print(f"Training failed: {str(e)}")

    async def predict(self, current_state: Dict) -> Dict[str, float]:
        """预测Gas费用

        Args:
            current_state: 当前状态信息

        Returns:
            Dict: 预测结果
        """
        if not self.is_trained:
            return {
                "base_fee": current_state.get("base_fee", 30),
                "confidence": 0.0,
                "source": "fallback",
            }

        try:
            # 准备特征
            features = pd.DataFrame(
                [
                    {
                        "hour": datetime.now().hour,
                        "day_of_week": datetime.now().weekday(),
                        "gas_used_ratio": current_state.get("gas_used_ratio", 0.5),
                        "prev_base_fee": current_state.get("base_fee", 30),
                        "prev_priority_fee": current_state.get("priority_fee", 1.0),
                    }
                ]
            )

            # 标准化特征
            X = self.scaler.transform(features[self.feature_columns].values)

            # 预测
            prediction = self.model.predict(X)[0]

            # 计算置信度
            confidence = self._calculate_confidence(prediction, current_state)

            return {"base_fee": prediction, "confidence": confidence, "source": "model"}

        except Exception as e:
            print(f"Prediction failed: {str(e)}")
            return {
                "base_fee": current_state.get("base_fee", 30),
                "confidence": 0.0,
                "source": "fallback",
            }

    def _calculate_confidence(self, prediction: float, current_state: Dict) -> float:
        """计算预测置信度

        Args:
            prediction: 预测值
            current_state: 当前状态

        Returns:
            float: 置信度 (0-1)
        """
        # 基于多个因素计算置信度
        confidence = 1.0

        # 1. 训练数据时效性
        if self.last_training_time:
            hours_since_training = (
                datetime.now() - self.last_training_time
            ).total_seconds() / 3600
            confidence *= max(0.5, min(1.0, 24 / hours_since_training))

        # 2. 预测值与当前值的偏差
        current_fee = current_state.get("base_fee", 30)
        if current_fee > 0:
            deviation = abs(prediction - current_fee) / current_fee
            confidence *= max(0.5, min(1.0, 1 - deviation))

        # 3. 网络拥堵程度
        gas_used_ratio = current_state.get("gas_used_ratio", 0.5)
        if gas_used_ratio > 0.8:
            confidence *= 0.8  # 高拥堵时降低置信度

        return confidence

    def get_model_info(self) -> Dict:
        """获取模型信息"""
        return {
            "is_trained": self.is_trained,
            "last_training_time": self.last_training_time,
            "feature_columns": self.feature_columns,
            "training_history": self.training_history[-5:],  # 最近5次训练记录
            "model_params": {
                "n_estimators": self.model.n_estimators,
                "learning_rate": self.model.learning_rate,
                "max_depth": self.model.max_depth,
            },
        }
