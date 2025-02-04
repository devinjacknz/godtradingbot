"""Momentum trading strategy implementation."""

from typing import Any, Dict, List, Optional

import numpy as np

from tradingbot.models.trading import TradeStatus
from tradingbot.shared.config.tenant_config import StrategyConfig


class MomentumStrategy:
    """Strategy that trades based on price momentum and trend strength."""

    def __init__(self, config: StrategyConfig):
        """Initialize strategy with configuration parameters."""
        params = config.parameters

        # Validate momentum parameters
        self.momentum_window = self._validate_positive_int(
            params.get("momentum_window", 20), "momentum_window"
        )
        self.momentum_threshold = self._validate_positive_float(
            params.get("momentum_threshold", 0.02),  # 2% minimum momentum
            "momentum_threshold",
        )

        # Validate trend parameters
        self.trend_window = self._validate_positive_int(
            params.get("trend_window", 50), "trend_window"
        )
        self.trend_strength = self._validate_positive_float(
            params.get("trend_strength", 0.6),  # 60% directional strength
            "trend_strength",
        )

        # Validate volume and volatility
        self.min_volume = self._validate_positive_float(
            params.get("min_volume", 1000), "min_volume"
        )
        self.max_volatility = self._validate_positive_float(
            params.get("max_volatility", 0.03),  # 3% maximum volatility
            "max_volatility",
        )

        # Validate profit target and stop loss
        self.profit_target = self._validate_positive_float(
            params.get("profit_target", 0.05), "profit_target"  # 5% profit target
        )
        self.stop_loss = self._validate_positive_float(
            params.get("stop_loss", 0.03), "stop_loss"  # 3% stop loss
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

    def _calculate_momentum(self, prices: List[float]) -> Optional[float]:
        """Calculate price momentum."""
        if len(prices) < self.momentum_window:
            return None

        returns = np.diff(np.log(prices[-self.momentum_window :]))
        return np.mean(returns)

    def _calculate_trend_strength(self, prices: List[float]) -> Optional[float]:
        """Calculate trend directional strength."""
        if len(prices) < self.trend_window:
            return None

        returns = np.diff(np.log(prices[-self.trend_window :]))
        positive_days = sum(1 for r in returns if r > 0)
        return positive_days / len(returns)

    def _calculate_volatility(self, prices: List[float]) -> Optional[float]:
        """Calculate price volatility."""
        if len(prices) < 2:
            return None

        returns = np.diff(np.log(prices))
        return np.std(returns)

    async def calculate_signals(self, market_data: List[Dict]) -> Dict[str, Any]:
        """Calculate trading signals based on momentum and trend."""
        if not market_data:
            return {"signal": "neutral", "confidence": 0.0, "reason": "no_data"}

        try:
            # Check volume
            if market_data[-1]["volume"] < self.min_volume:
                return {
                    "signal": "neutral",
                    "confidence": 0.0,
                    "reason": "insufficient_volume",
                }

            # Calculate indicators
            prices = [d["price"] for d in market_data]
            momentum = self._calculate_momentum(prices)
            trend_strength = self._calculate_trend_strength(prices)
            volatility = self._calculate_volatility(prices)

            if None in (momentum, trend_strength, volatility):
                return {
                    "signal": "neutral",
                    "confidence": 0.0,
                    "reason": "insufficient_data",
                }

            # Check volatility
            if volatility > self.max_volatility:
                return {
                    "signal": "neutral",
                    "confidence": 0.0,
                    "reason": "high_volatility",
                }

            # Generate signals
            signal = "neutral"
            confidence = 0.5

            if abs(momentum) > self.momentum_threshold:
                if momentum > 0 and trend_strength > self.trend_strength:
                    signal = "buy"
                    confidence = min(momentum / self.momentum_threshold, 1.0)
                elif momentum < 0 and trend_strength < (1 - self.trend_strength):
                    signal = "sell"
                    confidence = min(abs(momentum) / self.momentum_threshold, 1.0)

            return {
                "signal": signal,
                "confidence": confidence,
                "momentum": momentum,
                "trend_strength": trend_strength,
                "volatility": volatility,
                "price": market_data[-1]["price"],
                "volume": market_data[-1]["volume"],
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
        """Execute trade based on signal."""
        if signal["signal"] == "neutral":
            return None

        trade = {
            "tenant_id": tenant_id,
            "wallet_address": wallet["address"],
            "pair": market_data["pair"],
            "side": signal["signal"],
            "amount": market_data["amount"] * signal["confidence"],
            "price": market_data["price"],
            "status": TradeStatus.PENDING,
            "trade_metadata": {
                "momentum": signal["momentum"],
                "trend_strength": signal["trend_strength"],
                "confidence": signal["confidence"],
                "entry_price": market_data["price"],
                "profit_target": market_data["price"]
                * (
                    1 + self.profit_target
                    if signal["signal"] == "buy"
                    else 1 - self.profit_target
                ),
                "stop_loss": market_data["price"]
                * (
                    1 - self.stop_loss
                    if signal["signal"] == "buy"
                    else 1 + self.stop_loss
                ),
            },
        }

        return trade

    async def update_positions(
        self, tenant_id: str, market_data: Optional[Dict]
    ) -> Optional[Dict]:
        """Update existing positions based on new market data."""
        if market_data is None:
            raise ValueError("Market data cannot be None")

        current_price = market_data["price"]
        result = {
            "status": TradeStatus.OPEN,
            "trade_metadata": {"current_price": current_price},
        }

        # Check profit target and stop loss
        entry_price = result["trade_metadata"].get("entry_price", current_price)
        profit_target = result["trade_metadata"].get("profit_target")
        stop_loss = result["trade_metadata"].get("stop_loss")

        if profit_target and current_price >= profit_target:
            result["status"] = TradeStatus.CLOSED
            result["trade_metadata"]["exit_reason"] = "profit_target"
        elif stop_loss and current_price <= stop_loss:
            result["status"] = TradeStatus.CLOSED
            result["trade_metadata"]["exit_reason"] = "stop_loss"

        return result
