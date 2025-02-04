"""Mean reversion trading strategy implementation."""

from typing import Any, Dict, List, Optional

import numpy as np

from tradingbot.models.trading import TradeStatus
from tradingbot.shared.config.tenant_config import StrategyConfig


class MeanReversionStrategy:
    """Strategy that trades based on price reversion to the mean."""

    def __init__(self, config: StrategyConfig):
        """Initialize strategy with configuration parameters."""
        params = config.parameters

        # Validate lookback period
        self.lookback_period = self._validate_positive_int(
            params.get("lookback_period", 20), "lookback_period"
        )

        # Validate standard deviation threshold
        self.std_threshold = self._validate_positive_float(
            params.get("std_threshold", 2.0), "std_threshold"
        )

        # Validate minimum volume
        self.min_volume = self._validate_positive_float(
            params.get("min_volume", 1000), "min_volume"
        )

        # Validate profit target and stop loss
        self.profit_target = self._validate_positive_float(
            params.get("profit_target", 0.02), "profit_target"
        )
        self.stop_loss = self._validate_positive_float(
            params.get("stop_loss", 0.02), "stop_loss"
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

    def _calculate_zscore(self, prices: List[float]) -> Optional[float]:
        """Calculate z-score for latest price."""
        if len(prices) < self.lookback_period:
            return None

        window = prices[-self.lookback_period :]
        mean = np.mean(window)
        std = np.std(window)

        if std == 0:
            return 0.0

        return (prices[-1] - mean) / std

    async def calculate_signals(self, market_data: List[Dict]) -> Dict[str, Any]:
        """Calculate trading signals based on mean reversion."""
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

            # Calculate z-score
            prices = [d["price"] for d in market_data]
            zscore = self._calculate_zscore(prices)

            if zscore is None:
                return {
                    "signal": "neutral",
                    "confidence": 0.0,
                    "reason": "insufficient_data",
                }

            # Generate signals based on z-score
            signal = "neutral"
            confidence = 0.5

            if zscore > self.std_threshold:
                signal = "sell"
                confidence = min(abs(zscore) / (2 * self.std_threshold), 1.0)
            elif zscore < -self.std_threshold:
                signal = "buy"
                confidence = min(abs(zscore) / (2 * self.std_threshold), 1.0)

            return {
                "signal": signal,
                "confidence": confidence,
                "zscore": zscore,
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
                "zscore": signal["zscore"],
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
            "trade_metadata": {
                "current_price": current_price,
                "profit_target": 0,
                "stop_loss": 0,
            },
        }

        return result
