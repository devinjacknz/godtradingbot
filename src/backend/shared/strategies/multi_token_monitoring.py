"""Multi-token monitoring strategy implementation."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np

from src.backend.shared.strategies.base_strategy import BaseStrategy
from src.backend.shared.strategies.mean_reversion import MeanReversionStrategy
from src.backend.shared.strategies.momentum import MomentumStrategy
from src.backend.shared.strategies.social_sentiment import SocialSentimentStrategy
from src.backend.shared.strategies.technical_analysis import TechnicalAnalysisStrategy
from src.shared.config.tenant_config import TenantConfig
from src.shared.models.trading import Position, Signal, Trade
from tradingbot.models.trading import TradeStatus
from tradingbot.shared.config.tenant_config import StrategyConfig


class MultiTokenMonitoringStrategy:
    """Strategy that monitors multiple tokens for trading opportunities."""

    def __init__(self, config: StrategyConfig):
        """Initialize strategy with configuration parameters."""
        params = config.parameters

        # Validate monitoring parameters
        self.max_tokens = self._validate_positive_int(
            params.get("max_tokens", 10), "max_tokens"
        )
        self.update_interval = self._validate_positive_int(
            params.get("update_interval", 300), "update_interval"  # 5 minutes
        )

        # Validate volume and volatility thresholds
        self.min_volume = self._validate_positive_float(
            params.get("min_volume", 1000), "min_volume"
        )
        self.max_volatility = self._validate_positive_float(
            params.get("max_volatility", 0.05),  # 5% maximum volatility
            "max_volatility",
        )

        # Validate correlation parameters
        self.correlation_window = self._validate_positive_int(
            params.get("correlation_window", 100), "correlation_window"
        )
        self.correlation_threshold = self._validate_positive_float(
            params.get("correlation_threshold", 0.7),  # 70% correlation
            "correlation_threshold",
        )

        # Validate risk parameters
        self.max_exposure = self._validate_positive_float(
            params.get("max_exposure", 0.2), "max_exposure"  # 20% max exposure
        )
        self.risk_per_trade = self._validate_positive_float(
            params.get("risk_per_trade", 0.01), "risk_per_trade"  # 1% risk per trade
        )

    def _validate_positive_int(self, value: int, param_name: str) -> int:
        """Validate that a parameter is a positive integer."""
        try:
            value = int(value)
            if value <= 0:
                raise ValueError
            return value
        except (ValueError, TypeError):
            raise ValueError(f"{param_name} must be a positive integer")

    def _validate_positive_float(self, value: float, param_name: str) -> float:
        """Validate that a parameter is a positive float."""
        try:
            value = float(value)
            if value <= 0:
                raise ValueError
            return value
        except (ValueError, TypeError):
            raise ValueError(f"{param_name} must be a positive number")

    def _calculate_volatility(self, prices: List[float]) -> Optional[float]:
        """Calculate price volatility."""
        if len(prices) < 2:
            return None

        returns = np.diff(np.log(prices))
        return np.std(returns)

    def _calculate_correlation(
        self, prices1: List[float], prices2: List[float]
    ) -> Optional[float]:
        """Calculate price correlation between two assets."""
        if len(prices1) != len(prices2) or len(prices1) < self.correlation_window:
            return None

        returns1 = np.diff(np.log(prices1[-self.correlation_window :]))
        returns2 = np.diff(np.log(prices2[-self.correlation_window :]))

        return np.corrcoef(returns1, returns2)[0, 1]

    def _calculate_portfolio_risk(self, positions: List[Dict]) -> float:
        """Calculate total portfolio risk."""
        total_risk = 0
        for position in positions:
            risk = position.get("amount", 0) * position.get("price", 0)
            total_risk += risk
        return total_risk

    async def calculate_signals(self, market_data: List[Dict]) -> Dict[str, Any]:
        """Calculate trading signals for multiple tokens."""
        if not market_data:
            return {"signal": "neutral", "confidence": 0.0, "reason": "no_data"}

        try:
            # Group data by token
            token_data = {}
            for data in market_data:
                pair = data["pair"]
                if pair not in token_data:
                    token_data[pair] = []
                token_data[pair].append(data)

            # Analyze each token
            token_signals = []
            for pair, data in token_data.items():
                # Check volume
                if data[-1]["volume"] < self.min_volume:
                    continue

                # Calculate volatility
                prices = [d["price"] for d in data]
                volatility = self._calculate_volatility(prices)

                if volatility is None or volatility > self.max_volatility:
                    continue

                # Calculate correlations with other tokens
                correlations = []
                for other_pair, other_data in token_data.items():
                    if other_pair != pair:
                        other_prices = [d["price"] for d in other_data]
                        correlation = self._calculate_correlation(prices, other_prices)
                        if correlation is not None:
                            correlations.append(correlation)

                # Generate token signal
                avg_correlation = np.mean(correlations) if correlations else 0
                signal = {
                    "pair": pair,
                    "price": data[-1]["price"],
                    "volume": data[-1]["volume"],
                    "volatility": volatility,
                    "correlation": avg_correlation,
                }
                token_signals.append(signal)

            if not token_signals:
                return {
                    "signal": "neutral",
                    "confidence": 0.0,
                    "reason": "no_valid_tokens",
                }

            # Sort by volatility/correlation ratio
            token_signals.sort(
                key=lambda x: x["volatility"] / (x["correlation"] + 0.1), reverse=True
            )

            return {
                "signal": "monitor",
                "confidence": 1.0,
                "tokens": token_signals[: self.max_tokens],
                "next_update": (
                    datetime.utcnow() + timedelta(seconds=self.update_interval)
                ).isoformat(),
            }

        except Exception as e:
            return {
                "signal": "neutral",
                "confidence": 0.0,
                "reason": f"error: {str(e)}",
            }

    async def execute_trade(
        self, tenant_id: str, wallet: Dict, market_data: Dict, signal: Dict
    ) -> Optional[Dict]:
        """Execute trades for monitored tokens."""
        if signal["signal"] != "monitor":
            return None

        # Calculate position sizes based on risk
        total_portfolio = float(wallet.get("balance", 0))
        max_risk = total_portfolio * self.max_exposure
        risk_per_token = max_risk / len(signal["tokens"])

        trades = []
        for token in signal["tokens"]:
            position_size = risk_per_token / token["price"]
            trade = {
                "tenant_id": tenant_id,
                "wallet_address": wallet["address"],
                "pair": token["pair"],
                "side": "buy",  # Initial position
                "amount": position_size,
                "price": token["price"],
                "status": TradeStatus.PENDING,
                "trade_metadata": {
                    "volatility": token["volatility"],
                    "correlation": token["correlation"],
                    "risk_amount": risk_per_token,
                    "next_update": signal["next_update"],
                },
            }
            trades.append(trade)

        return {
            "tenant_id": tenant_id,
            "wallet_address": wallet["address"],
            "trades": trades,
            "trade_metadata": {
                "total_risk": max_risk,
                "risk_per_trade": risk_per_token,
                "next_update": signal["next_update"],
            },
        }

    async def update_positions(
        self, tenant_id: str, market_data: Optional[Dict]
    ) -> Optional[Dict]:
        """Update existing positions based on new market data."""
        if market_data is None:
            raise ValueError("Market data cannot be None")

        current_time = datetime.utcnow()

        result = {
            "status": TradeStatus.OPEN,
            "trade_metadata": {"current_time": current_time.isoformat()},
        }

        # Check if update is needed
        next_update = datetime.fromisoformat(
            result["trade_metadata"].get("next_update", "")
        )
        if current_time >= next_update:
            result["status"] = TradeStatus.CLOSED
            result["trade_metadata"]["exit_reason"] = "rebalance"

        return result


class MultiStrategyManager:
    """多策略管理器"""

    def __init__(self, config: Dict):
        self.strategies: Dict[str, BaseStrategy] = {}
        self.weights: Dict[str, float] = {}
        self.performance_history: Dict[str, List[float]] = {}
        self.config = config
        self.tenant_config = TenantConfig()

        # 初始化策略
        self._initialize_strategies()

    def _initialize_strategies(self):
        """初始化策略组合"""
        # 动量策略
        self.strategies["momentum"] = MomentumStrategy(
            lookback_period=self.config.get("momentum_lookback", 14),
            threshold=self.config.get("momentum_threshold", 0.02),
        )

        # 均值回归策略
        self.strategies["mean_reversion"] = MeanReversionStrategy(
            window_size=self.config.get("mr_window", 20),
            std_dev=self.config.get("mr_std_dev", 2.0),
        )

        # 技术分析策略
        self.strategies["technical"] = TechnicalAnalysisStrategy(
            indicators=self.config.get("technical_indicators", ["RSI", "MACD", "BB"])
        )

        # 社交情绪策略
        self.strategies["sentiment"] = SocialSentimentStrategy(
            sources=self.config.get("sentiment_sources", ["twitter", "reddit"])
        )

        # 初始化权重
        total_weight = len(self.strategies)
        self.weights = {name: 1.0 / total_weight for name in self.strategies}

    async def update_weights(self, performance_metrics: Dict[str, float]):
        """更新策略权重

        Args:
            performance_metrics: 各策略的性能指标
        """
        # 更新性能历史
        for strategy_name, metric in performance_metrics.items():
            if strategy_name not in self.performance_history:
                self.performance_history[strategy_name] = []
            self.performance_history[strategy_name].append(metric)

        # 计算新权重
        total_performance = sum(performance_metrics.values())
        if total_performance > 0:
            self.weights = {
                name: perf / total_performance
                for name, perf in performance_metrics.items()
            }

        # 应用最小权重限制
        min_weight = self.config.get("min_strategy_weight", 0.1)
        for name in self.weights:
            if self.weights[name] < min_weight:
                self.weights[name] = min_weight

        # 重新归一化
        total_weight = sum(self.weights.values())
        self.weights = {
            name: weight / total_weight for name, weight in self.weights.items()
        }

    async def generate_signals(self, market_data: Dict) -> List[Signal]:
        """生成交易信号

        Args:
            market_data: 市场数据

        Returns:
            List[Signal]: 合成的交易信号
        """
        all_signals = []

        # 收集各策略的信号
        for name, strategy in self.strategies.items():
            signals = await strategy.generate_signals(market_data)
            for signal in signals:
                signal.confidence *= self.weights[name]  # 应用权重
                all_signals.append(signal)

        # 按交易对合并信号
        merged_signals = {}
        for signal in all_signals:
            if signal.symbol not in merged_signals:
                merged_signals[signal.symbol] = signal
            else:
                # 合并同一交易对的信号
                existing = merged_signals[signal.symbol]
                existing.confidence = (
                    existing.confidence + signal.confidence
                ) / 2  # 平均置信度
                existing.indicators.update(signal.indicators)

        return list(merged_signals.values())

    async def validate_signals(self, signals: List[Signal]) -> List[Signal]:
        """验证交易信号

        Args:
            signals: 原始信号列表

        Returns:
            List[Signal]: 验证后的信号
        """
        validated_signals = []

        for signal in signals:
            # 检查信号强度
            if signal.confidence < self.config.get("min_confidence", 0.5):
                continue

            # 检查交易限制
            if not self._check_trading_limits(signal.symbol):
                continue

            # 检查风险限制
            if not self._check_risk_limits(signal):
                continue

            validated_signals.append(signal)

        return validated_signals

    def _check_trading_limits(self, symbol: str) -> bool:
        """检查交易限制"""
        # 获取当前时间
        current_time = datetime.now()

        # 检查交易时间
        trading_hours = self.tenant_config.get_trading_hours(symbol)
        if trading_hours and not trading_hours.is_trading_time(current_time):
            return False

        # 检查交易频率
        if not self.tenant_config.check_trading_frequency(symbol):
            return False

        return True

    def _check_risk_limits(self, signal: Signal) -> bool:
        """检查风险限制"""
        # 获取风险限制
        risk_limits = self.tenant_config.get_risk_limits()

        # 检查波动率限制
        if signal.volatility > risk_limits.get("max_volatility", float("inf")):
            return False

        # 检查流动性限制
        if signal.liquidity < risk_limits.get("min_liquidity", 0):
            return False

        # 检查价格偏差限制
        if abs(signal.price_change) > risk_limits.get(
            "max_price_deviation", float("inf")
        ):
            return False

        return True

    def get_strategy_metrics(self) -> Dict:
        """获取策略指标"""
        metrics = {}

        for name, strategy in self.strategies.items():
            metrics[name] = {
                "weight": self.weights[name],
                "performance": np.mean(self.performance_history.get(name, [0])),
                "signal_count": strategy.signal_count,
                "success_rate": strategy.success_rate,
            }

        return metrics

    async def optimize_parameters(self, market_data: Dict):
        """优化策略参数"""
        for strategy in self.strategies.values():
            await strategy.optimize_parameters(market_data)

        # 更新配置
        self.config.update(
            {
                "momentum_lookback": self.strategies["momentum"].lookback_period,
                "momentum_threshold": self.strategies["momentum"].threshold,
                "mr_window": self.strategies["mean_reversion"].window_size,
                "mr_std_dev": self.strategies["mean_reversion"].std_dev,
            }
        )
