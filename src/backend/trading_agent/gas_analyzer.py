from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from src.shared.cache.hybrid_cache import HybridCache
from src.shared.models.alerts import Alert, AlertLevel


class GasAnalyzer:
    """Gas费用分析器"""

    def __init__(self, config: Dict):
        self.config = config
        self.cache = HybridCache()
        self.window_size = config.get("analysis_window", 24)  # 小时
        self.alert_thresholds = config.get(
            "alert_thresholds",
            {
                "high_fee": 100,  # Gwei
                "high_volatility": 0.5,  # 50%
                "congestion": 0.8,  # 80%
            },
        )
        self.fee_history: List[Dict] = []
        self.alerts: List[Alert] = []

    async def analyze_fees(self, new_data: Dict) -> Dict:
        """分析Gas费用

        Args:
            new_data: 新的Gas数据

        Returns:
            Dict: 分析结果
        """
        # 添加新数据
        self.fee_history.append({**new_data, "timestamp": datetime.now()})

        # 清理过期数据
        cutoff_time = datetime.now() - timedelta(hours=self.window_size)
        self.fee_history = [d for d in self.fee_history if d["timestamp"] > cutoff_time]

        if len(self.fee_history) < 2:
            return self._get_empty_analysis()

        try:
            # 转换为DataFrame
            df = pd.DataFrame(self.fee_history)

            # 计算基本统计量
            stats = {
                "current_fee": new_data["base_fee"],
                "avg_fee": df["base_fee"].mean(),
                "min_fee": df["base_fee"].min(),
                "max_fee": df["base_fee"].max(),
                "std_fee": df["base_fee"].std(),
                "volatility": self._calculate_volatility(df["base_fee"]),
                "trend": self._calculate_trend(df),
                "congestion_level": self._calculate_congestion(df),
                "timestamp": datetime.now().isoformat(),
            }

            # 检查是否需要发出告警
            await self._check_alerts(stats)

            # 添加预测
            stats.update(self._predict_trend(df))

            return stats

        except Exception as e:
            print(f"Analysis failed: {str(e)}")
            return self._get_empty_analysis()

    def _calculate_volatility(self, series: pd.Series) -> float:
        """计算波动率

        Args:
            series: 价格序列

        Returns:
            float: 波动率
        """
        returns = series.pct_change().dropna()
        return returns.std()

    def _calculate_trend(self, df: pd.DataFrame) -> str:
        """计算趋势

        Args:
            df: 数据框

        Returns:
            str: 趋势方向
        """
        # 使用简单线性回归
        x = np.arange(len(df))
        y = df["base_fee"].values
        slope = np.polyfit(x, y, 1)[0]

        if slope > 0.1:
            return "increasing"
        elif slope < -0.1:
            return "decreasing"
        else:
            return "stable"

    def _calculate_congestion(self, df: pd.DataFrame) -> float:
        """计算网络拥堵程度

        Args:
            df: 数据框

        Returns:
            float: 拥堵程度 (0-1)
        """
        if "gas_used_ratio" in df.columns:
            return df["gas_used_ratio"].mean()
        return df["base_fee"].rank(pct=True).iloc[-1]

    def _predict_trend(self, df: pd.DataFrame) -> Dict:
        """预测趋势

        Args:
            df: 数据框

        Returns:
            Dict: 预测结果
        """
        # 使用简单的移动平均预测
        ma_short = df["base_fee"].rolling(window=6).mean()
        ma_long = df["base_fee"].rolling(window=24).mean()

        last_short = ma_short.iloc[-1]
        last_long = ma_long.iloc[-1]

        if pd.isna(last_short) or pd.isna(last_long):
            return {"trend_prediction": "uncertain", "confidence": 0.0}

        # 计算趋势强度
        trend_strength = (last_short - last_long) / last_long

        if trend_strength > 0.05:
            prediction = "up"
            confidence = min(1.0, trend_strength * 10)
        elif trend_strength < -0.05:
            prediction = "down"
            confidence = min(1.0, abs(trend_strength) * 10)
        else:
            prediction = "stable"
            confidence = 1.0 - min(1.0, abs(trend_strength) * 20)

        return {"trend_prediction": prediction, "confidence": confidence}

    async def _check_alerts(self, stats: Dict):
        """检查是否需要发出告警

        Args:
            stats: 统计数据
        """
        # 检查高费用
        if stats["current_fee"] > self.alert_thresholds["high_fee"]:
            await self._create_alert(
                f"High gas fee detected: {stats['current_fee']} Gwei", AlertLevel.HIGH
            )

        # 检查高波动率
        if stats["volatility"] > self.alert_thresholds["high_volatility"]:
            await self._create_alert(
                f"High gas fee volatility: {stats['volatility']:.2%}", AlertLevel.MEDIUM
            )

        # 检查网络拥堵
        if stats["congestion_level"] > self.alert_thresholds["congestion"]:
            await self._create_alert(
                f"Network congestion detected: {stats['congestion_level']:.2%}",
                AlertLevel.MEDIUM,
            )

    async def _create_alert(self, message: str, level: AlertLevel):
        """创建告警

        Args:
            message: 告警信息
            level: 告警级别
        """
        alert = Alert(message=message, level=level, timestamp=datetime.now())
        self.alerts.append(alert)
        # TODO: 发送告警通知

    def _get_empty_analysis(self) -> Dict:
        """获取空分析结果"""
        return {
            "current_fee": 0,
            "avg_fee": 0,
            "min_fee": 0,
            "max_fee": 0,
            "std_fee": 0,
            "volatility": 0,
            "trend": "unknown",
            "congestion_level": 0,
            "trend_prediction": "uncertain",
            "confidence": 0,
            "timestamp": datetime.now().isoformat(),
        }

    def get_analysis_summary(self) -> Dict:
        """获取分析总结"""
        return {
            "window_size": self.window_size,
            "data_points": len(self.fee_history),
            "alert_thresholds": self.alert_thresholds,
            "recent_alerts": [
                {
                    "message": a.message,
                    "level": a.level.name,
                    "timestamp": a.timestamp.isoformat(),
                }
                for a in self.alerts[-5:]  # 最近5条告警
            ],
        }
